import pytest

from dspplay import Parameter, slider


def test_parameter_clamps_values():
    gain = Parameter("Gain", 0.5, 0.0, 1.0)

    gain.value = 2.0
    assert gain.value == 1.0

    gain.value = -1.0
    assert gain.value == 0.0


def test_log_parameter_round_trip():
    cutoff = Parameter("Cutoff", 1_000, 20, 20_000, scale="log")

    position = cutoff._to_normalized()
    assert cutoff._from_normalized(position) == pytest.approx(1_000)


def test_log_parameter_rejects_zero_minimum():
    with pytest.raises(ValueError):
        Parameter("Cutoff", 1_000, 0, 20_000, scale="log")


def test_slider_creates_parameter():
    gain = slider("Gain", 0.5, 0.0, 1.0)

    assert isinstance(gain, Parameter)
    assert gain.value == 0.5
