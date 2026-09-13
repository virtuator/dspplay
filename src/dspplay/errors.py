"""Exceptions used for expected, course-facing playback rejections."""


class SignalSafetyError(ValueError):
    """Raised when audio is deliberately rejected before playback."""
