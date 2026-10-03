import numpy as np
import pytest

from dspplay import play


class FakeDevice:
    class CallbackStop(Exception):
        pass

    def __init__(self):
        self.streams = []

    def OutputStream(self, **kwargs):
        owner = self

        class Stream:
            active = False
            closed = False

            def start(self):
                self.active = True

            def stop(self):
                self.active = False

            def close(self):
                self.closed = True

            def render(self, frames):
                out = np.empty((frames, kwargs["channels"]), np.float32)
                try:
                    kwargs["callback"](out, frames, None, None)
                except owner.CallbackStop:
                    self.active = False
                return out

        stream = Stream()
        self.streams.append(stream)
        return stream


def test_two_one_shot_playbacks_do_not_stop_each_other(monkeypatch):
    device = FakeDevice()
    monkeypatch.setattr("dspplay.streams._sounddevice", lambda: device)
    first = play(np.array([0.1, 0.2, 0.3]), 48_000, blocking=False)
    second = play(np.array([0.4, 0.5]), 48_000, blocking=False)
    try:
        np.testing.assert_allclose(device.streams[0].render(2)[:, 0], [0.1, 0.2])
        np.testing.assert_allclose(device.streams[1].render(4)[:, 0], [0.4, 0.5, 0, 0])
        second.wait()
        assert first.active
        np.testing.assert_allclose(device.streams[0].render(3)[:, 0], [0.3, 0, 0])
        first.wait()
        assert all(stream.closed for stream in device.streams)
    finally:
        first.stop()
        second.stop()


def test_stereo_shape_preserved_in_one_shot_output(monkeypatch):
    device = FakeDevice()
    monkeypatch.setattr("dspplay.streams._sounddevice", lambda: device)
    x = np.array([[0.1, -0.1], [0.2, -0.2]])
    playback = play(x, 44_100, blocking=False)
    try:
        np.testing.assert_allclose(device.streams[0].render(2), x)
        playback.wait()
        assert not playback.active
    finally:
        playback.stop()


@pytest.mark.parametrize("name", ["play_loop", "play_file", "play_input"])
def test_all_realtime_entry_points_support_background_handles(monkeypatch, name):
    from test_session import FakeStream

    from dspplay import Playback
    from dspplay import playback as api

    stream = FakeStream()
    monkeypatch.setattr(api, "ArrayLoop", lambda *args, **kwargs: stream)
    monkeypatch.setattr(api, "FileLoop", lambda *args, **kwargs: stream)
    monkeypatch.setattr(api, "LiveInput", lambda *args, **kwargs: stream)
    process = lambda block, fs: block
    args = {
        "play_loop": (np.zeros(8), 48_000, process),
        "play_file": ("unused.wav", process),
        "play_input": (process,),
    }
    result = getattr(api, name)(*args[name], blocking=False)
    try:
        assert isinstance(result, Playback)
        assert result.active
    finally:
        result.stop()
