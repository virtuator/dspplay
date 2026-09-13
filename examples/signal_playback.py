import numpy as np

import dspplay as dp

fs = 48_000
duration = 1.0
f = 440
amplitude = 0.1

t = np.arange(int(duration * fs)) / fs
x = amplitude * np.sin(2 * np.pi * f * t)

dp.play_signal(x, fs)
