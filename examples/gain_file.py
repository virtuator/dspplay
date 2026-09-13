from dspplay import FileLoop, Parameter, show_controls

gain = Parameter("Gain", 0.5, 0.0, 2.0, decimals=2)


def process(block):
    return gain.value * block


with FileLoop("audio/drums.wav", process) as player:
    show_controls(gain, title="Gain", check=player.check)
