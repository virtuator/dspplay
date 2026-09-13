"""Realtime streams that call a user-supplied ``process(block)`` function."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

AudioBlock = NDArray[np.float32]
Processor = Callable[[AudioBlock], AudioBlock]


def _sounddevice():
    try:
        import sounddevice as sd
    except ImportError as error:
        raise RuntimeError(
            "Realtime audio needs sounddevice. Install the project with `uv sync`."
        ) from error
    return sd


def list_devices() -> None:
    """Print the audio devices known to PortAudio."""

    print(_sounddevice().query_devices())


def _copy_processed(process: Processor, block: AudioBlock, outdata: AudioBlock) -> None:
    result = np.asarray(process(block))
    if result.shape != outdata.shape:
        raise ValueError(
            "process(block) returned shape "
            f"{result.shape}; expected {outdata.shape} (frames, channels)"
        )
    outdata[:] = result


class _LoopReader:
    def __init__(self, audio: AudioBlock) -> None:
        if audio.ndim != 2 or audio.shape[0] == 0:
            raise ValueError(
                "audio must have shape (frames, channels) and not be empty"
            )
        self.audio = audio
        self.position = 0

    def fill(self, block: AudioBlock) -> None:
        written = 0
        while written < len(block):
            available = len(self.audio) - self.position
            count = min(len(block) - written, available)
            block[written : written + count] = self.audio[
                self.position : self.position + count
            ]
            written += count
            self.position = (self.position + count) % len(self.audio)


class _RealtimeStream:
    def __init__(self, process: Processor) -> None:
        if not callable(process):
            raise TypeError("process must be callable")
        self.process = process
        self._stream: Any | None = None
        self._error: BaseException | None = None
        self.last_status = ""

    @property
    def active(self) -> bool:
        return bool(self._stream is not None and self._stream.active)

    @property
    def cpu_load(self) -> float:
        if self._stream is None:
            return 0.0
        return float(self._stream.cpu_load)

    def start(self):
        if self._stream is None:
            self._stream = self._create_stream()
        self._error = None
        self._stream.start()
        return self

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self.check()

    def check(self) -> None:
        """Raise an exception that occurred in the audio callback, if any."""

        if self._error is not None:
            error = self._error
            self._error = None
            raise RuntimeError("process(block) failed in the audio callback") from error

    def _remember_status(self, status: Any) -> None:
        if status:
            self.last_status = str(status)

    def _abort(self, outdata: AudioBlock, error: BaseException) -> None:
        outdata.fill(0)
        self._error = error
        raise _sounddevice().CallbackAbort

    def _create_stream(self):
        raise NotImplementedError

    def __enter__(self):
        return self.start()

    def __exit__(self, exception_type, exception, traceback) -> None:
        self.stop()


class FileLoop(_RealtimeStream):
    """Play a sound file in a loop and process each block before playback."""

    def __init__(
        self,
        path: str | Path,
        process: Processor,
        *,
        blocksize: int = 256,
        device: int | str | None = None,
        latency: float | str | None = "low",
    ) -> None:
        super().__init__(process)
        try:
            import soundfile as sf
        except ImportError as error:
            raise RuntimeError(
                "File playback needs soundfile. Install the project with `uv sync`."
            ) from error

        audio, samplerate = sf.read(path, dtype="float32", always_2d=True)
        self.samplerate = float(samplerate)
        self.channels = int(audio.shape[1])
        self.blocksize = int(blocksize)
        self.device = device
        self.latency = latency
        self._reader = _LoopReader(audio)
        self._input_block = np.empty(
            (max(1, self.blocksize), self.channels), np.float32
        )

    def _create_stream(self):
        sd = _sounddevice()

        def callback(outdata, frames, time, status) -> None:
            del time
            self._remember_status(status)
            if self._input_block.shape[0] != frames:
                self._input_block = np.empty((frames, self.channels), np.float32)
            self._reader.fill(self._input_block)
            try:
                _copy_processed(self.process, self._input_block, outdata)
            except Exception as error:  # noqa: BLE001 - audio must fail silent
                self._abort(outdata, error)

        return sd.OutputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            channels=self.channels,
            dtype="float32",
            device=self.device,
            latency=self.latency,
            callback=callback,
        )


class LiveInput(_RealtimeStream):
    """Process audio from an input device and send it to an output device."""

    def __init__(
        self,
        process: Processor,
        *,
        samplerate: float = 48_000,
        blocksize: int = 256,
        channels: int = 1,
        device: int | str | tuple[int | str | None, int | str | None] | None = None,
        latency: float | str | tuple[float | str, float | str] | None = "low",
    ) -> None:
        super().__init__(process)
        self.samplerate = float(samplerate)
        self.blocksize = int(blocksize)
        self.channels = int(channels)
        self.device = device
        self.latency = latency

    def _create_stream(self):
        sd = _sounddevice()

        def callback(indata, outdata, frames, time, status) -> None:
            del frames, time
            self._remember_status(status)
            try:
                _copy_processed(self.process, indata, outdata)
            except Exception as error:  # noqa: BLE001 - audio must fail silent
                self._abort(outdata, error)

        return sd.Stream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            channels=self.channels,
            dtype="float32",
            device=self.device,
            latency=self.latency,
            callback=callback,
        )
