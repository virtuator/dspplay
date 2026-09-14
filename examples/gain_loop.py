import numpy as np

import dspplay as dp

fs = 48_000
duration = 1.0
t = np.arange(int(duration * fs)) / fs
x = 0.2 * np.sin(2 * np.pi * 220 * t)

gain = dp.slider("Gain", value=0.5, minimum=0.0, maximum=1.0)


def process(block, fs):
    return gain.value * block


dp.play_loop(x, fs, process, controls=[gain], title="Gain")
