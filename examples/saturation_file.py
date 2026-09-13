import numpy as np

import dspplay as dp

drive = dp.slider("Drive", 1.0, 0.1, 20.0, scale="log", decimals=2)
output = dp.slider("Output", 0.5, 0.0, 1.0, decimals=2)


def process(block, fs):
    return output.value * np.tanh(drive.value * block)


dp.play_file(
    "../audio/example_stereo.wav",
    process,
    controls=[drive, output],
    title="Saturation",
)
