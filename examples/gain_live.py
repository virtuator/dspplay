from dspplay import LiveInput, Parameter, show_controls

gain = Parameter("Gain", 0.25, 0.0, 1.0, decimals=2)


def process(block):
    return gain.value * block


# Use headphones and begin with a low output level to avoid feedback.
with LiveInput(process, channels=1) as player:
    show_controls(gain, title="Live gain", check=player.check)
