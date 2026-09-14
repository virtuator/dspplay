import numpy as np
import pytest

from dspplay.streams import ArrayLoop, _copy_processed, _LoopReader


def test_loop_reader_wraps_without_a_gap():
    audio = np.array([[1.0], [2.0], [3.0]], dtype=np.float32)
    block = np.empty((5, 1), dtype=np.float32)

    _LoopReader(audio).fill(block)

    np.testing.assert_array_equal(block[:, 0], [1.0, 2.0, 3.0, 1.0, 2.0])


def test_array_loop_accepts_public_mono_shape():
    stream = ArrayLoop(np.zeros(8), 48_000, lambda block, fs: block)

    assert stream.samplerate == 48_000
    assert stream.channels == 1
    assert stream._reader.audio.shape == (8, 1)


def test_processed_block_is_copied_to_output():
    block = np.ones((4, 2), dtype=np.float32)
    output = np.empty_like(block)

    _copy_processed(lambda x, fs: 0.25 * x, block, output, 48_000)

    np.testing.assert_array_equal(output, 0.25 * block)


def test_mono_is_exposed_as_one_dimensional():
    block = np.ones((4, 1), dtype=np.float32)
    output = np.empty_like(block)
    seen = {}

    def process(x, fs):
        seen["shape"] = x.shape
        seen["fs"] = fs
        return 0.5 * x

    _copy_processed(process, block, output, 44_100)

    assert seen == {"shape": (4,), "fs": 44_100}
    np.testing.assert_array_equal(output[:, 0], np.full(4, 0.5))


def test_processor_state_is_preserved_across_blocks():
    block = np.zeros((3, 1), dtype=np.float32)
    output = np.empty_like(block)
    state = {"value": 0.0}

    def process(x, fs):
        state["value"] += 0.25
        return x + state["value"]

    _copy_processed(process, block, output, 48_000)
    np.testing.assert_array_equal(output[:, 0], np.full(3, 0.25))

    _copy_processed(process, block, output, 48_000)
    np.testing.assert_array_equal(output[:, 0], np.full(3, 0.5))


def test_wrong_output_shape_is_explained():
    block = np.ones((4, 2), dtype=np.float32)
    output = np.empty_like(block)

    with pytest.raises(ValueError, match="expected"):
        _copy_processed(lambda x, fs: x[:, 0], block, output, 48_000)


def test_non_finite_output_is_rejected():
    block = np.ones((4, 1), dtype=np.float32)
    output = np.empty_like(block)

    with pytest.raises(ValueError, match="NaN or infinite"):
        _copy_processed(lambda x, fs: x * np.nan, block, output, 48_000)


def test_unsafe_peak_is_rejected():
    block = np.ones((4, 1), dtype=np.float32)
    output = np.empty_like(block)

    with pytest.raises(ValueError, match="allowed maximum"):
        _copy_processed(lambda x, fs: 1.1 * x, block, output, 48_000)
