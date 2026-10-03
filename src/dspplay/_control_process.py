"""Parent-side transport for the isolated control window (never imports Tk)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from .controls import Parameter


class ControlWindow:
    def __init__(self, parameters, title: str, *, timeout: float = 10.0):
        self.parameters: tuple[Parameter, ...] = tuple(parameters)
        self._events = Queue()
        self._closed = False
        self._normal_close = False
        self._stderr = ""
        self._last_values = [p.value for p in self.parameters]
        env = os.environ.copy()
        package_root = str(Path(__file__).resolve().parent.parent)
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, (package_root, env.get("PYTHONPATH")))
        )
        self._process = subprocess.Popen(
            [sys.executable, "-u", "-m", "dspplay._control_window"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
        )
        self._readers = [
            Thread(target=self._read_events, daemon=True),
            Thread(target=self._read_stderr, daemon=True),
        ]
        for reader in self._readers:
            reader.start()
        try:
            self._send(
                {
                    "title": title,
                    "parameters": [
                        {
                            "name": p.name,
                            "value": p.value,
                            "minimum": p.minimum,
                            "maximum": p.maximum,
                            "scale": p.scale,
                            "unit": p.unit,
                            "decimals": p.decimals,
                        }
                        for p in self.parameters
                    ],
                }
            )
            # Audio is started only after Tk has successfully created the window.
            event = self._events.get(timeout=timeout)
            if event["event"] != "ready":
                raise RuntimeError(
                    event.get("message", "Control window failed to start.")
                )
        except Empty as error:
            self.close()
            raise RuntimeError(
                "Timed out starting the DspPlay control window."
            ) from error
        except BaseException:
            self.close()
            raise

    def _send(self, message):
        self._process.stdin.write(json.dumps(message, allow_nan=False) + "\n")
        self._process.stdin.flush()

    def _read_events(self):
        try:
            for line in self._process.stdout:
                self._events.put(json.loads(line))
        except (ValueError, OSError) as error:
            self._events.put({"event": "error", "message": str(error)})
        finally:
            self._events.put({"event": "eof"})

    def _read_stderr(self):
        for line in self._process.stderr:
            self._stderr = (self._stderr + line)[-4000:]

    def poll(self) -> bool:
        """Apply GUI changes locally; called outside the audio callback."""
        if self._normal_close or self._closed:
            return False
        while True:
            try:
                event = self._events.get_nowait()
            except Empty:
                break
            kind = event["event"]
            if kind == "value":
                index = event["index"]
                self.parameters[index].value = event["value"]
                self._last_values[index] = self.parameters[index].value
            elif kind == "closed":
                self._normal_close = True
                return False
            elif kind in {"error", "eof"}:
                message = event.get("message", "Control window exited unexpectedly.")
                raise RuntimeError(f"{message} {self._stderr}".strip())

        # Programmatic changes to gain.value are reflected in the window too.
        values = [p.value for p in self.parameters]
        if values != self._last_values:
            try:
                self._send({"values": values})
            except (BrokenPipeError, OSError) as error:
                raise RuntimeError("Control window connection was lost.") from error
            self._last_values = values
        return True

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._process.stdin.close()  # EOF also closes the GUI after parent exit.
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        except (BrokenPipeError, OSError):
            self._process.kill()
            self._process.wait()
        finally:
            for reader in self._readers:
                reader.join(timeout=1)
            self._process.stdout.close()
            self._process.stderr.close()
