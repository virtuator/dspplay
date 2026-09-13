"""Small, dependency-free controls for course examples."""

from __future__ import annotations

import math
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
    """Create a course-friendly slider parameter.

    The lower-case factory keeps the beginner-facing API function-oriented.
    ``Parameter`` remains available for advanced use and backwards compatibility.
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
    title: str = "dspplay",
    check: Callable[[], None] | None = None,
) -> None:
    """Show sliders and block until the window is closed.

    Tkinter is part of the standard Python installation on most course
    machines, so the control window adds no Python package dependency.
    """

    if not parameters:
        raise ValueError("show_controls() needs at least one Parameter")

    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError as error:
        raise RuntimeError(
            "Tkinter is not available in this Python installation."
        ) from error

    root = tk.Tk()
    root.title(title)
    root.resizable(True, False)
    root.columnconfigure(0, weight=1)
    pending_error: list[Exception] = []

    slider_steps = 1_000

    for row, parameter in enumerate(parameters):
        frame = ttk.Frame(root, padding=(12, 8))
        frame.grid(row=row, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        label = ttk.Label(frame, text=parameter.name)
        label.grid(row=0, column=0, sticky="w")

        value_label = ttk.Label(frame, width=14, anchor="e")
        value_label.grid(row=0, column=1, sticky="e")

        def update(raw_value: str, p: Parameter = parameter, v=value_label) -> None:
            p.value = p._from_normalized(float(raw_value) / slider_steps)
            v.configure(text=p._formatted())

        slider = ttk.Scale(
            frame,
            from_=0,
            to=slider_steps,
            command=update,
        )
        slider.set(parameter._to_normalized() * slider_steps)
        slider.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        value_label.configure(text=parameter._formatted())

    if check is not None:

        def poll() -> None:
            try:
                check()
            except Exception as error:  # noqa: BLE001 - surface the audio error
                pending_error.append(error)
                root.destroy()
                return
            root.after(50, poll)

        root.after(50, poll)

    root.mainloop()
    if pending_error:
        raise pending_error[0]
