import numpy as np
import pytest

from dspplay import play, play_loop
from dspplay.playback import _validated_signal


def test_signal_validation_accepts_public_shapes():
    mono, mono_fs = _validated_signal(np.zeros(8), 48_000, 1.0)
    stereo, stereo_fs = _validated_signal(np.zeros((8, 2)), 44_100, 1.0)

    assert mono.shape == (8,)
    assert stereo.shape == (8, 2)
    assert mono_fs == 48_000
    assert stereo_fs == 44_100


@pytest.mark.parametrize(
    ("audio", "message"),
    [
        (np.zeros((2, 2, 2)), "shape"),
        (np.array([]), "empty"),
        (np.array([np.nan]), "NaN"),
        (np.array([1.01]), "allowed maximum"),
    ],
)
def test_signal_validation_rejects_unsafe_audio(audio, message):
    with pytest.raises(ValueError, match=message):
        _validated_signal(audio, 48_000, 1.0)


def test_play_owns_and_closes_its_output_stream(monkeypatch):
    calls = []

    class FakeSoundDevice:
        class CallbackStop(Exception):
            pass

        def OutputStream(self, **kwargs):
            calls.append(kwargs)

            class Stream:
                active = False

                def start(self):
                    output = np.empty((5, 1), np.float32)
                    with pytest.raises(FakeSoundDevice.CallbackStop):
                        kwargs["callback"](output, 5, None, None)
                    calls.append(output)

                def stop(self):
                    calls.append("stop")

                def close(self):
                    calls.append("close")

            return Stream()

    fake_sounddevice = FakeSoundDevice()
    monkeypatch.setattr("dspplay.streams._sounddevice", lambda: fake_sounddevice)

    signal = np.array([0.0, 0.5, -0.5])
    played = play(signal, 48_000, device="output")

    assert played is True
    assert calls[0]["samplerate"] == 48_000
    assert calls[0]["device"] == "output"
    np.testing.assert_array_equal(calls[1][:, 0], [0, 0.5, -0.5, 0, 0])
    assert calls[2:] == ["stop", "close"]


def test_nonblocking_invalid_signal_raises_before_starting():
    with pytest.raises(ValueError, match="allowed maximum"):
        play(np.array([1.1]), 48_000, blocking=False)


def test_play_reports_rejection_without_traceback(capsys):
    played = play(np.array([1.1]), 48_000)

    assert played is False
    assert capsys.readouterr().out == (
        "Playback stopped: Peak 1.100 exceeds the allowed maximum of 1.000. "
        "Reduce the level explicitly before playback.\n"
    )


def test_play_loop_reports_invalid_source_without_traceback(capsys):
    played = play_loop(np.array([np.nan]), 48_000, lambda block, fs: block)

    assert played is False
    assert capsys.readouterr().out == (
        "Playback stopped: Signal contains NaN or infinite values.\n"
    )
