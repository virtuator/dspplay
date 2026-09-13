import dspplay as dp

gain = dp.slider("Gain", 0.5, 0.0, 1.0, decimals=2)


def process(block, fs):
    return gain.value * block


dp.play_file(
    "../audio/example_stereo.wav",
    process,
    controls=[gain],
    title="Gain",
)
