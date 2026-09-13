import numpy as np
import pytest

from dspplay import play_signal
from dspplay.playback import _validated_signal


def test_signal_validation_accepts_course_shapes():
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


def test_play_signal_uses_sounddevice_and_waits(monkeypatch):
    calls = []

    class FakeSoundDevice:
        def play(self, signal, samplerate, device=None):
            calls.append(("play", signal.copy(), samplerate, device))

        def wait(self):
            calls.append(("wait",))

    fake_sounddevice = FakeSoundDevice()
    monkeypatch.setattr("dspplay.playback._sounddevice", lambda: fake_sounddevice)

    signal = np.array([0.0, 0.5, -0.5])
    play_signal(signal, 48_000, device="output")

    assert calls[0][0] == "play"
    np.testing.assert_array_equal(calls[0][1], signal)
    assert calls[0][2:] == (48_000, "output")
    assert calls[1] == ("wait",)
