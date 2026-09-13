import numpy as np
import pytest

from dspplay.streams import _copy_processed, _LoopReader


def test_loop_reader_wraps_without_a_gap():
    audio = np.array([[1.0], [2.0], [3.0]], dtype=np.float32)
    block = np.empty((5, 1), dtype=np.float32)

    _LoopReader(audio).fill(block)

    np.testing.assert_array_equal(block[:, 0], [1.0, 2.0, 3.0, 1.0, 2.0])


def test_processed_block_is_copied_to_output():
    block = np.ones((4, 2), dtype=np.float32)
    output = np.empty_like(block)

    _copy_processed(lambda x: 0.25 * x, block, output)

    np.testing.assert_array_equal(output, 0.25 * block)


def test_wrong_output_shape_is_explained():
    block = np.ones((4, 2), dtype=np.float32)
    output = np.empty_like(block)

    with pytest.raises(ValueError, match="expected .*frames, channels"):
        _copy_processed(lambda x: x[:, 0], block, output)
