"""Realtime streams that call a user-supplied ``process(block)`` function."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

AudioBlock = NDArray[np.float32]
Processor = Callable[[AudioBlock, float], AudioBlock]


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


def _course_block(block: AudioBlock) -> AudioBlock:
    """Expose mono as 1-D while keeping multichannel audio sample-first."""

    if block.shape[1] == 1:
        return block[:, 0]
    return block


def _copy_processed(
    process: Processor,
    block: AudioBlock,
    outdata: AudioBlock,
    samplerate: float,
    *,
    max_peak: float = 1.0,
) -> None:
    course_block = _course_block(block)
    result = np.asarray(process(course_block, samplerate))
    if result.shape != course_block.shape:
        raise ValueError(
            "process(block) returned shape "
            f"{result.shape}; expected {course_block.shape}"
        )
    if not np.issubdtype(result.dtype, np.number) or np.iscomplexobj(result):
        raise TypeError("process(block, fs) must return real numeric audio data")
    if not np.all(np.isfinite(result)):
        raise ValueError("process(block, fs) returned NaN or infinite values")

    peak = float(np.max(np.abs(result), initial=0.0))
    if peak > max_peak:
        raise ValueError(
            f"process(block, fs) returned peak {peak:.3f}; "
            f"the allowed maximum is {max_peak:.3f}"
        )

    if outdata.shape[1] == 1:
        outdata[:, 0] = result
    else:
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
    def __init__(self, process: Processor, max_peak: float) -> None:
        if not callable(process):
            raise TypeError("process must be callable")
        if not np.isfinite(max_peak) or max_peak <= 0:
            raise ValueError("max_peak must be a positive finite number")
        self.process = process
        self.max_peak = float(max_peak)
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
        max_peak: float = 1.0,
    ) -> None:
        super().__init__(process, max_peak)
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
                _copy_processed(
                    self.process,
                    self._input_block,
                    outdata,
                    self.samplerate,
                    max_peak=self.max_peak,
                )
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
        max_peak: float = 1.0,
    ) -> None:
        super().__init__(process, max_peak)
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
                _copy_processed(
                    self.process,
                    indata,
                    outdata,
                    self.samplerate,
                    max_peak=self.max_peak,
                )
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
