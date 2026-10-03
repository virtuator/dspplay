"""Exercise real subprocess pipes without requiring a desktop or audio device."""

import subprocess
import sys
import time

import pytest

from dspplay import _control_process, slider
from dspplay._control_process import ControlWindow


def child(monkeypatch, script):
    popen = subprocess.Popen
    processes = []

    def launch(command, **kwargs):
        process = popen([sys.executable, "-u", "-c", script], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(_control_process.subprocess, "Popen", launch)
    return processes


def test_pipe_transfers_values_and_closes_on_eof(monkeypatch):
    script = """
import json, sys
config = json.loads(sys.stdin.readline())
print(json.dumps({"event": "ready"}), flush=True)
print(json.dumps({"event": "value", "index": 0, "value": 0.75}), flush=True)
for line in sys.stdin:
    values = json.loads(line)["values"]
    print(json.dumps({"event": "value", "index": 0, "value": values[0]}), flush=True)
print(json.dumps({"event": "closed"}), flush=True)
"""
    processes = child(monkeypatch, script)
    gain = slider("Gain", 0.5, 0, 1)
    window = ControlWindow([gain], "Gain")
    try:
        deadline = time.monotonic() + 2
        while gain.value != 0.75 and time.monotonic() < deadline:
            window.poll()
            time.sleep(0.01)
        assert gain.value == 0.75
        gain.value = 0.25
        assert window.poll()
        assert window._last_values == [0.25]
    finally:
        window.close()
    assert processes[0].returncode == 0


def test_startup_error_is_reported_and_child_reaped(monkeypatch):
    script = """
import json, sys
sys.stdin.readline()
print(json.dumps({"event": "error", "message": "Tk unavailable"}), flush=True)
sys.exit(1)
"""
    processes = child(monkeypatch, script)
    with pytest.raises(RuntimeError, match="Tk unavailable"):
        ControlWindow([slider("Gain", 0.5, 0, 1)], "Gain")
    assert processes[0].returncode == 1


def test_native_crash_is_detected_and_does_not_kill_parent(monkeypatch):
    script = """
import json, sys, time, os
sys.stdin.readline()
print(json.dumps({"event": "ready"}), flush=True)
time.sleep(0.05)
os._exit(7)
"""
    processes = child(monkeypatch, script)
    window = ControlWindow([slider("Gain", 0.5, 0, 1)], "Gain")
    try:
        deadline = time.monotonic() + 2
        with pytest.raises(RuntimeError, match="unexpectedly"):
            while time.monotonic() < deadline:
                window.poll()
                time.sleep(0.01)
    finally:
        window.close()
    assert processes[0].returncode == 7


def test_startup_timeout_closes_child(monkeypatch):
    processes = child(monkeypatch, "import sys; sys.stdin.read()")
    with pytest.raises(RuntimeError, match="Timed out"):
        ControlWindow([slider("Gain", 0.5, 0, 1)], "Gain", timeout=0.05)
    assert processes[0].returncode is not None
