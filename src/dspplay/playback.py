"""Convenience functions for safe audio playback and real-time processing."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike

from .controls import Parameter, show_controls
from .errors import SignalSafetyError
from .streams import FileLoop, LiveInput, Processor, _RealtimeStream, _sounddevice


def _validated_signal(
    signal: ArrayLike,
    samplerate: float,
    max_peak: float,
) -> tuple[np.ndarray, float]:
    data = np.asarray(signal)

    if data.ndim not in {1, 2}:
        raise SignalSafetyError("Signal must have shape (N,) or (N, channels).")
    if data.shape[0] == 0 or (data.ndim == 2 and data.shape[1] == 0):
        raise SignalSafetyError("Signal is empty.")
    if not np.issubdtype(data.dtype, np.number) or np.iscomplexobj(data):
        raise SignalSafetyError("Signal must contain real numeric values.")
    if not np.all(np.isfinite(data)):
        raise SignalSafetyError("Signal contains NaN or infinite values.")
    if not np.isfinite(samplerate) or samplerate <= 0:
        raise SignalSafetyError("fs must be a positive finite sample rate.")
    if not np.isfinite(max_peak) or max_peak <= 0:
        raise ValueError("max_peak must be a positive finite number")

    peak = float(np.max(np.abs(data), initial=0.0))
    if peak > max_peak:
        raise SignalSafetyError(
            f"Peak {peak:.3f} exceeds the allowed maximum of {max_peak:.3f}. "
            "Reduce the level explicitly before playback."
        )

    return data, float(samplerate)


def play_signal(
    signal: ArrayLike,
    fs: float,
    *,
    device: int | str | None = None,
    max_peak: float = 1.0,
) -> bool:
    """Validate and play a complete mono or multichannel signal safely."""

    try:
        data, samplerate = _validated_signal(signal, fs, max_peak)
    except SignalSafetyError as error:
        print(f"Playback stopped: {error}")
        return False

    sd = _sounddevice()
    sd.play(data, samplerate, device=device)
    sd.wait()
    return True


def _run_stream(
    stream: _RealtimeStream,
    controls: Sequence[Parameter] | None,
    title: str,
) -> bool:
    parameters = tuple(controls or ())

    try:
        with stream:
            if parameters:
                show_controls(*parameters, title=title, check=stream.check)
            else:
                try:
                    input("Audio is running. Press Enter to stop ... ")
                except KeyboardInterrupt:
                    pass
    except RuntimeError as error:
        if isinstance(error.__cause__, SignalSafetyError):
            print(f"Playback stopped: {error.__cause__}")
            return False
        raise

    return True


def play_file(
    path: str | Path,
    process: Processor,
    *,
    controls: Sequence[Parameter] | None = None,
    title: str = "DspPlay",
    blocksize: int = 256,
    device: int | str | None = None,
    latency: float | str | None = "low",
    max_peak: float = 1.0,
) -> bool:
    """Process a sound file block by block and play it repeatedly."""

    stream = FileLoop(
        path,
        process,
        blocksize=blocksize,
        device=device,
        latency=latency,
        max_peak=max_peak,
    )
    return _run_stream(stream, controls, title)


def play_input(
    process: Processor,
    *,
    controls: Sequence[Parameter] | None = None,
    title: str = "DspPlay",
    samplerate: float = 48_000,
    blocksize: int = 256,
    channels: int = 1,
    device: int | str | tuple[int | str | None, int | str | None] | None = None,
    latency: float | str | tuple[float | str, float | str] | None = "low",
    max_peak: float = 1.0,
) -> bool:
    """Process an audio input block by block and play the result."""

    stream = LiveInput(
        process,
        samplerate=samplerate,
        blocksize=blocksize,
        channels=channels,
        device=device,
        latency=latency,
        max_peak=max_peak,
    )
    return _run_stream(stream, controls, title)
