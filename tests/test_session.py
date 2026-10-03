from threading import Event

import pytest

from dspplay import Playback, _session, slider
from dspplay.errors import SignalSafetyError
from dspplay.playback import _run_stream


class FakeStream:
    def __init__(self):
        self.active = False
        self.stopped = Event()
        self.failure = None
        self.stop_count = 0

    def start(self):
        self.active = True

    def check(self):
        if self.failure is not None:
            raise self.failure

    def stop(self):
        self.active = False
        self.stop_count += 1
        self.stopped.set()


class FakeWindow:
    def __init__(self, parameters, title):
        self.parameters = parameters
        self.open = True
        self.failure = None
        self.closed = False

    def poll(self):
        if self.failure:
            raise self.failure
        self.parameters[0].value = 0.75
        return self.open

    def close(self):
        self.closed = True


def test_nonblocking_playback_returns_running_handle_and_stop_is_idempotent():
    stream = FakeStream()
    playback = _run_stream(stream, (), "Test", False)
    assert isinstance(playback, Playback)
    assert playback.active
    playback.stop()
    playback.stop()
    assert not playback.active
    assert stream.stop_count == 1


def test_window_close_stops_audio_and_preserves_parameter(monkeypatch):
    monkeypatch.setattr(_session, "ControlWindow", FakeWindow)
    stream = FakeStream()
    gain = slider("Gain", 0.5, 0, 1)
    playback = Playback(stream, [gain])
    playback._window.open = False
    assert stream.stopped.wait(2)
    playback.wait()
    assert gain.value == 0.75
    assert playback._window.closed


def test_window_failure_stops_audio_and_is_reported(monkeypatch):
    monkeypatch.setattr(_session, "ControlWindow", FakeWindow)
    stream = FakeStream()
    playback = Playback(stream, [slider("Gain", 0.5, 0, 1)])
    playback._window.failure = RuntimeError("window crashed")
    assert stream.stopped.wait(2)
    with pytest.raises(RuntimeError, match="window crashed"):
        playback.wait()
    assert playback._window.closed


def test_callback_failure_is_saved_until_checked():
    stream = FakeStream()
    playback = Playback(stream)
    original = ValueError("processor failed")
    error = RuntimeError("audio callback failed")
    error.__cause__ = original
    stream.failure = error
    assert stream.stopped.wait(2)
    with pytest.raises(RuntimeError) as caught:
        playback.wait()
    assert caught.value.__cause__ is original
    with pytest.raises(RuntimeError):
        playback.check()


def test_gui_start_failure_does_not_start_audio(monkeypatch):
    stream = FakeStream()

    def fail(*args):
        raise RuntimeError("Tk unavailable")

    monkeypatch.setattr(_session, "ControlWindow", fail)
    with pytest.raises(RuntimeError, match="Tk unavailable"):
        Playback(stream, [slider("Gain", 0.5, 0, 1)])
    assert not stream.active
    assert stream.stopped.is_set()


def test_context_exit_closes_playback_even_when_user_code_fails():
    stream = FakeStream()
    with pytest.raises(ValueError, match="user code"), Playback(stream):
        raise ValueError("user code")
    assert stream.stopped.is_set()


def test_audio_start_failure_closes_window(monkeypatch):
    windows = []

    def create(*args):
        window = FakeWindow(*args)
        windows.append(window)
        return window

    class FailedStream(FakeStream):
        def start(self):
            raise RuntimeError("device unavailable")

    monkeypatch.setattr(_session, "ControlWindow", create)
    with pytest.raises(RuntimeError, match="device unavailable"):
        Playback(FailedStream(), [slider("Gain", 0.5, 0, 1)])
    assert windows[0].closed


def test_blocking_safety_failure_keeps_concise_message(monkeypatch, capsys):
    class UnsafeStream(FakeStream):
        def check(self):
            raise RuntimeError("callback") from SignalSafetyError("Peak too high")

    stream = UnsafeStream()
    assert _run_stream(stream, (), "Test", True, finite=True) is False
    assert capsys.readouterr().out == "Playback stopped: Peak too high\n"
    assert stream.stopped.is_set()
