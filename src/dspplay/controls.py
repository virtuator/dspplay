"""Small, dependency-free controls for real-time examples."""

from __future__ import annotations

import math
import time
from collections.abc import Callable


class Parameter:
    """A scalar parameter that may be changed while audio is running.

    Reading and replacing one Python float is intentionally kept lock-free so
    that the audio callback never waits for the user-interface thread.
    """

    def __init__(
        self,
        name: str,
        value: float,
        minimum: float,
        maximum: float,
        *,
        scale: str = "linear",
        unit: str = "",
        decimals: int = 2,
    ) -> None:
        if maximum <= minimum:
            raise ValueError("maximum must be greater than minimum")
        if scale not in {"linear", "log"}:
            raise ValueError("scale must be 'linear' or 'log'")
        if scale == "log" and minimum <= 0:
            raise ValueError("a logarithmic parameter needs minimum > 0")

        self.name = name
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.scale = scale
        self.unit = unit
        self.decimals = decimals
        self._value = self._clamp(value)

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, new_value: float) -> None:
        self._value = self._clamp(new_value)

    def _clamp(self, value: float) -> float:
        return min(self.maximum, max(self.minimum, float(value)))

    def _from_normalized(self, position: float) -> float:
        position = min(1.0, max(0.0, position))
        if self.scale == "log":
            low = math.log(self.minimum)
            high = math.log(self.maximum)
            return math.exp(low + position * (high - low))
        return self.minimum + position * (self.maximum - self.minimum)

    def _to_normalized(self) -> float:
        if self.scale == "log":
            low = math.log(self.minimum)
            high = math.log(self.maximum)
            return (math.log(self.value) - low) / (high - low)
        return (self.value - self.minimum) / (self.maximum - self.minimum)

    def _formatted(self) -> str:
        suffix = f" {self.unit}" if self.unit else ""
        return f"{self.value:.{self.decimals}f}{suffix}"


def slider(
    name: str,
    value: float,
    minimum: float,
    maximum: float,
    *,
    scale: str = "linear",
    unit: str = "",
    decimals: int = 2,
) -> Parameter:
    """Create a convenient slider parameter.

    The lower-case factory keeps the convenience API function-oriented.
    ``Parameter`` remains available for direct use and backwards compatibility.
    """

    return Parameter(
        name,
        value,
        minimum,
        maximum,
        scale=scale,
        unit=unit,
        decimals=decimals,
    )


def show_controls(
    *parameters: Parameter,
    title: str = "DspPlay",
    check: Callable[[], None] | None = None,
) -> None:
    """Show sliders in a separate process and wait until the window closes."""

    if not parameters:
        raise ValueError("show_controls() needs at least one Parameter")

    from ._control_process import ControlWindow

    window = ControlWindow(parameters, title)
    try:
        while window.poll():
            if check is not None:
                check()
            time.sleep(0.02)
    finally:
        window.close()
