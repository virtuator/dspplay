"""Exceptions used for expected playback rejections."""


class SignalSafetyError(ValueError):
    """Raised when audio is deliberately rejected before playback."""
