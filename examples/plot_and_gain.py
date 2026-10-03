"""Run in PyCharm: plot and controls have independent lifetimes.

Requires Matplotlib in the environment: uv add matplotlib
"""

import matplotlib.pyplot as plt
import numpy as np

import dspplay as dp

fs = 48_000
t = np.arange(fs) / fs
x = 0.1 * np.sin(2 * np.pi * 220 * t)
gain = dp.slider("Gain", 0.5, 0, 1)


def process(block, fs):
    return gain.value * block


playback = dp.play_loop(x, fs, process, controls=[gain], title="Gain", blocking=False)
try:
    plt.plot(t[:500], x[:500])
    plt.xlabel("Time [s]")
    plt.ylabel("Amplitude")
    plt.show()
    # Closing the plot does not stop audio. Wait for the control window to close.
    playback.wait()
finally:
    playback.stop()
