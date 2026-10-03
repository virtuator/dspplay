"""Playback lifetime management, independent of the caller's GUI event loop."""

from __future__ import annotations

import atexit
from threading import Event, Lock, Thread

from ._control_process import ControlWindow

_sessions: set[Playback] = set()
_sessions_lock = Lock()


class Playback:
    """An already-running playback returned by ``blocking=False``.

    ``stop()``, ``wait()`` and ``check()`` surface background errors. The
    context manager stops playback when its block ends, not when a plot closes.
    """

    def __init__(self, stream, controls=(), title="DspPlay"):
        self._stream = stream
        self._window = None
        self._stop_requested = Event()
        self._done = Event()
        self._error: BaseException | None = None
        self._thread = Thread(
            target=self._monitor, name="DspPlay playback", daemon=True
        )
        try:
            if controls:
                self._window = ControlWindow(controls, title)
            stream.start()
            with _sessions_lock:
                _sessions.add(self)
            self._thread.start()
        except BaseException:
            try:
                stream.stop()
            finally:
                if self._window is not None:
                    self._window.close()
                with _sessions_lock:
                    _sessions.discard(self)
            raise

    @property
    def active(self) -> bool:
        """Whether the audio stream is still running."""
        return not self._done.is_set() and self._stream.active

    def _monitor(self):
        try:
            while not self._stop_requested.is_set():
                self._stream.check()
                if not self._stream.active:
                    break
                if self._window is not None and not self._window.poll():
                    break
                self._stop_requested.wait(0.02)
        except BaseException as error:  # noqa: BLE001 - preserve background failures
            self._error = error
        finally:
            try:
                self._stream.stop()
            except BaseException as error:  # noqa: BLE001 - finish GUI cleanup too
                if self._error is None:
                    self._error = error
            finally:
                try:
                    if self._window is not None:
                        self._window.close()
                except BaseException as error:  # noqa: BLE001 - always signal completion
                    if self._error is None:
                        self._error = error
                finally:
                    with _sessions_lock:
                        _sessions.discard(self)
                    self._done.set()

    def check(self) -> None:
        """Raise a saved audio or control-window error, if any."""
        if self._error is not None:
            raise self._error

    def wait(self) -> None:
        """Wait for completion; this does not service other GUI event loops."""
        try:
            self._done.wait()
        except KeyboardInterrupt:
            self.stop()
            raise
        self.check()

    def stop(self) -> None:
        """Stop audio and close its controls; safe to call more than once."""
        self._stop_requested.set()
        self._thread.join()
        self.check()

    def __enter__(self):
        self.check()
        return self

    def __exit__(self, exception_type, exception, traceback):
        try:
            self.stop()
        except BaseException:
            if exception is None:
                raise


def _shutdown():
    with _sessions_lock:
        sessions = tuple(_sessions)
    for session in sessions:
        try:
            session.stop()
        except BaseException:  # noqa: BLE001, S110 - best effort during interpreter exit
            pass


atexit.register(_shutdown)
