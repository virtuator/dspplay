# dspplay

`dspplay` is a small real-time audio wrapper for NumPy-based DSP experiments.
It provides audio devices, block processing, file looping, guarded playback,
and a minimal control window while keeping the signal-processing code visible.

The library is conventionally imported as `dp`:

```python
import dspplay as dp
```

Write a regular processing function:

```python
def process(block, fs):
    return 0.5 * block
```

## Install from GitHub

Add the latest version from GitHub to an existing `uv` project:

```bash
uv add git+https://github.com/virtuator/dspplay.git
```

Then import the library in Python:

```python
import dspplay as dp
```

## Development

To work on `dspplay` itself, clone the repository and create its development
environment:

```bash
git clone https://github.com/virtuator/dspplay.git
cd dspplay
uv sync
```

To use that local checkout from another `uv` project while developing, add it
as an editable dependency:

```bash
uv add --editable ../dspplay
```

## Play a signal safely

Use `play_signal(...)` to play a computed signal:

```python
import dspplay as dp

y = 0.5 * x

dp.play_signal(y, fs)
```

The function waits until playback has ended. Before playback, it checks:

- mono shape `(N,)` or multichannel shape `(N, C)`
- a non-empty array
- real numeric values
- no `NaN` or infinite values
- a positive sample rate
- a peak within the allowed range

Unsafe signals are not silently normalized or clipped. Playback is refused with
a concise message and no traceback:

```text
Playback stopped: Peak 1.100 exceeds the allowed maximum of 1.000. Reduce the level explicitly before playback.
```

`play_signal(...)` returns `False` when playback is refused and `True` after
successful playback. The return value can usually be ignored. Unexpected
programming and audio-device errors remain regular Python exceptions with a
traceback.

## Process a file in real time

This example loops `audio/example_stereo.wav`. Moving the control affects the
next audio block:

```python
import dspplay as dp


gain = dp.slider(
    "Gain",
    value=0.5,
    minimum=0.0,
    maximum=1.0,
)


def process(block, fs):
    return gain.value * block


dp.play_file(
    "audio/example_stereo.wav",
    process,
    controls=[gain],
    title="Gain",
)
```

The higher-level `FileLoop` and `LiveInput` classes remain available when more
control is needed, but `play_file(...)` and `play_input(...)` are the intended
convenience API.

## Data model

The public interface follows the same convention as SoundFile:

```text
Mono:         (frames,)
Multichannel: (frames, channels)
```

A stereo block with 256 frames therefore has
`block.shape == (256, 2)`. A mono block of the same length has
`block.shape == (256,)`.

Sounddevice uses a two-dimensional representation for mono internally.
`dspplay` converts at the boundary before calling `process(...)`; the function
must return an array with the same public shape.

Real-time data uses `float32`. The usual sample range is from `-1.0` to `+1.0`.

## Sample rate

`process(...)` always receives the sample rate `fs` with its block:

```python
def process(block, fs):
    return block
```

For `play_file(...)`, `fs` comes from the audio file. For `play_input(...)`, it
is chosen when the stream starts. This allows filter coefficients, delay times,
and LFOs to be computed without a hard-coded sample rate.

## Multiple and logarithmic controls

For frequencies, a logarithmic slider scale is usually appropriate:

```python
import dspplay as dp

cutoff = dp.slider(
    "Cutoff",
    value=1_000,
    minimum=20,
    maximum=20_000,
    scale="log",
    unit="Hz",
    decimals=0,
)
```

Pass multiple controls as a list:

```python
dp.play_file(
    "audio/example_stereo.wav",
    process,
    controls=[cutoff, resonance],
    title="Lowpass",
)
```

`slider(...)` automatically constrains its value to `minimum` through
`maximum`. Parameter changes are deliberately not smoothed; smoothing belongs
to the DSP algorithm when it is needed.

## Live input

The same `process(...)` function can process a microphone, guitar, or audio
interface input:

```python
import dspplay as dp


gain = dp.slider("Gain", 0.25, 0.0, 1.0)


def process(block, fs):
    return gain.value * block


dp.play_input(
    process,
    controls=[gain],
    samplerate=48_000,
    channels=1,
    title="Live gain",
)
```

Use headphones and begin with a low output level. A microphone and speakers can
immediately create acoustic feedback.

## State across blocks

During playback, `dspplay` calls the same processor for consecutive blocks.
Filter, delay, or LFO state created outside `process(...)` therefore remains
available between calls. `dspplay` does not reset it at block boundaries.

The following rules apply:

- Blocks are processed in order.
- The processor is not replaced during playback.
- Each call to `play_file(...)` or `play_input(...)` creates a new audio
  stream.
- State belongs to the processor; `dspplay` does not modify it.

## Select audio devices

List available devices with:

```python
import dspplay as dp

dp.list_devices()
```

Then pass a device name or number:

```python
dp.play_file(
    "audio/example_stereo.wav",
    process,
    device="MacBook Pro Speakers",
)
```

For distinct input and output devices:

```python
dp.play_input(process, device=(2, 5))
```

## Block size and latency

The default `blocksize` is 256. At 48 kHz, one block corresponds to

$$
\frac{256}{48\,000} \approx 5.3\,\text{ms}.
$$

This is only one part of total input/output latency; audio drivers and hardware
buffers add more latency.

If you hear dropouts or clicks, first choose a larger block size:

```python
dp.play_input(process, blocksize=512)
```

If needed, request a more robust device latency:

```python
dp.play_input(process, blocksize=512, latency="high")
```

## Rules for `process(...)`

The function runs in the audio thread and must finish before the next block.

- Do not open, read, or write files.
- Do not call `print()` for every audio block.
- Do not open windows or plots from inside `process(...)`.
- Avoid long Python loops; prefer NumPy operations.
- Preserve filter, delay, and other state between blocks.
- Always return an array with the same shape as the input block.

An error in `process(...)` stops the stream. Non-finite values, a wrong array
shape, and a peak above `max_peak` are also reported to the main program.

## Offline and real time

A stateless function can be applied unchanged to a complete signal or to
consecutive blocks:

```python
import soundfile as sf
import dspplay as dp


def process(block, fs):
    return 0.5 * block


x, fs = sf.read("audio/example_stereo.wav")
y = process(x, fs)

dp.play_signal(y, fs)
dp.play_file("audio/example_stereo.wav", process)
```

For stateful algorithms, define when state is initialized or reset. The same
question applies to blockwise offline processing.

## Pedalboard integration

Pedalboard can be used inside `process(...)`. Take care with array axes:
`dspplay` uses `(frames, channels)` for multichannel audio, while Pedalboard
usually uses `(channels, frames)`.

Conceptually:

```python
def process(block, fs):
    plugin_input = block.T
    plugin_output = plugin(plugin_input, fs, reset=False)
    return plugin_output.T
```

`reset=False` preserves plugin state across consecutive blocks. Mono requires
an additional shape conversion in a future adapter.

## Included examples

- `examples/signal_playback.py`: safe playback of a generated sine signal
- `examples/gain_file.py`: gain on a file loop
- `examples/saturation_file.py`: two controls and logarithmic scaling
- `examples/gain_live.py`: live input to output

Run an example from the project directory:

```bash
uv run python examples/gain_file.py
```

## Deliberately not included yet

This version does not include automatic parameter smoothing, bypass, level
metering, recording, or a safe adapter for arbitrary Pedalboard plugins. A
freely distributable shared audio example is also not included.

## Technical foundations

- [sounddevice: Streams using NumPy Arrays](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html)
- [SoundFile documentation](https://python-soundfile.readthedocs.io/en/latest/)
- [Pedalboard API](https://spotify.github.io/pedalboard/reference/pedalboard.html)
