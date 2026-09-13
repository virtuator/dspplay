from dspplay import play_input, slider

gain = slider("Gain", 0.25, 0.0, 1.0, decimals=2)


def process(block, fs):
    return gain.value * block


# Use headphones and begin with a low output level to avoid feedback.
play_input(
    process,
    controls=[gain],
    channels=1,
    title="Live gain",
)
