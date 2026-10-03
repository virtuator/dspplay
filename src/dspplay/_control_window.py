"""Tk GUI entry point, run only in a fresh interpreter via subprocess."""

import json
import sys
from queue import Empty, Queue
from threading import Thread

from .controls import Parameter


def _emit(event):
    print(json.dumps(event, allow_nan=False), flush=True)


def main():
    config = json.loads(sys.stdin.readline())
    import tkinter as tk
    from tkinter import ttk

    parameters = [Parameter(**p) for p in config["parameters"]]
    root = tk.Tk()
    root.title(config["title"])
    root.resizable(True, False)
    root.columnconfigure(0, weight=1)
    messages = Queue()
    widgets = []
    syncing = False

    for index, parameter in enumerate(parameters):
        frame = ttk.Frame(root, padding=(12, 8))
        frame.grid(row=index, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text=parameter.name).grid(row=0, column=0, sticky="w")
        label = ttk.Label(frame, width=14, anchor="e")
        label.grid(row=0, column=1, sticky="e")

        def update(raw, p=parameter, i=index, value_label=label):
            p.value = p._from_normalized(float(raw) / 1000)
            value_label.configure(text=p._formatted())
            if not syncing:
                _emit({"event": "value", "index": i, "value": p.value})

        widget = ttk.Scale(frame, from_=0, to=1000)
        widget.set(parameter._to_normalized() * 1000)
        widget.configure(command=update)
        widget.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        label.configure(text=parameter._formatted())
        widgets.append((widget, label))

    def receive():
        try:
            for line in sys.stdin:
                messages.put(json.loads(line))
        finally:
            messages.put(None)

    def poll():
        nonlocal syncing
        try:
            while True:
                message = messages.get_nowait()
                if message is None:
                    root.destroy()
                    return
                syncing = True
                try:
                    for p, (widget, label), value in zip(
                        parameters, widgets, message["values"], strict=True
                    ):
                        p.value = value
                        widget.set(p._to_normalized() * 1000)
                        label.configure(text=p._formatted())
                finally:
                    syncing = False
        except Empty:
            pass
        root.after(20, poll)

    def ready():
        _emit({"event": "ready"})
        poll()

    Thread(target=receive, daemon=True).start()
    root.after_idle(ready)
    root.mainloop()
    _emit({"event": "closed"})


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - report startup failures over IPC
        _emit({"event": "error", "message": f"Control window failed: {error}"})
        sys.exit(1)
