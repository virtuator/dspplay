import numpy as np

from dspplay import FileLoop, Parameter, show_controls

drive = Parameter("Drive", 1.0, 0.1, 20.0, scale="log", decimals=2)
output = Parameter("Output", 0.5, 0.0, 1.0, decimals=2)


def process(block):
    return output.value * np.tanh(drive.value * block)


with FileLoop("audio/drums.wav", process) as player:
    show_controls(drive, output, title="Saturation", check=player.check)
