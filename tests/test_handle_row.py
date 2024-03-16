"""Unit tests for functions _is_full_hour, _get_mean_stat and _get_sum_stat."""

from homeassistant.exceptions import HomeAssistantError
from custom_components.import_statistics import _is_full_hour
from custom_components.import_statistics import _is_valid_float
from custom_components.import_statistics import _min_max_mean_are_valid

def test_is_full_hour_valid():
    """
    Test the _is_full_hour function with a valid full hour timestamp.
    """
    timestamp_str = "01.01.2022 12:00:00"

    result = _is_full_hour(timestamp_str)
    assert result is True


def test_is_full_hour_invalid_minute():
    """
    Test the _is_full_hour function with an invalid timestamp due to non-zero minute.
    """
    timestamp_str = "01.01.2022 12:30:00"

    try:
        _is_full_hour(timestamp_str)
        assert False, "Expected an exception to be raised for invalid timestamp"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid timestamp: {timestamp_str}. The timestamp must be a full hour."

def test_is_full_hour_invalid_second():
    """
    Test the _is_full_hour function with an invalid timestamp due to non-zero second.
    """
    timestamp_str = "01.01.2022 12:00:30"

    try:
        _is_full_hour(timestamp_str)
        assert False, "Expected an exception to be raised for invalid timestamp"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid timestamp: {timestamp_str}. The timestamp must be a full hour."

def test_is_full_hour_no_second():
    """
    Test the _is_full_hour function with a valid timestamp due to missing second.
    """
    timestamp_str = "01.01.2022 12:00"

    result = _is_full_hour(timestamp_str)
    assert result is True

def test_is_full_hour_no_minute():
    """
    Test the _is_full_hour function with an invalid timestamp due to non-zero minute.
    """
    timestamp_str = "01.01.2022 12"

    try:
        _is_full_hour(timestamp_str)
        assert False, "Expected an exception to be raised for invalid timestamp"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '%d.%m.%Y %H:%M' or '%d.%m.%Y %H:%M:%S'."

def test_is_full_hour_invalid_minute_second():
    """
    Test the _is_full_hour function with an invalid timestamp due to non-zero second.
    """
    timestamp_str = "01.01.2022 12:01:30"

    try:
        _is_full_hour(timestamp_str)
        assert False, "Expected an exception to be raised for invalid timestamp"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid timestamp: {timestamp_str}. The timestamp must be a full hour."

def test_min_max_mean_are_valid_valid_values():
    """
    Test the _min_max_mean_are_valid function with valid values.
    """
    min_value = 0.0
    max_value = 10.0
    mean_value = 5.0

    assert _min_max_mean_are_valid(min_value, max_value, mean_value)

def test_min_max_mean_are_valid_invalid_values():
    """
    Test the _min_max_mean_are_valid function with invalid values.
    """
    min_value = 10.0
    max_value = 0.0
    mean_value = 5.0

    try:
        _min_max_mean_are_valid(min_value, max_value, mean_value)
        assert False, "Expected an exception to be raised for invalid values"
    except HomeAssistantError as e:
        assert str(e) == "Invalid values: min: 10.0, max: 0.0, mean: 5.0, mean must be between min and max."

def test_min_max_mean_are_valid_equal_values():
    """
    Test the _min_max_mean_are_valid function with equal min, max, and mean values.
    """
    min_value = 5.0
    max_value = 5.0
    mean_value = 5.0

    assert _min_max_mean_are_valid(min_value, max_value, mean_value)

def test_min_max_mean_are_valid_mean_outside_range():
    """
    Test the _min_max_mean_are_valid function with mean value outside the range of min and max.
    """
    min_value = 0.0
    max_value = 10.0
    mean_value = 15.0

    try:
        _min_max_mean_are_valid(min_value, max_value, mean_value)
        assert False, "Expected an exception to be raised for invalid values"
    except HomeAssistantError as e:
        assert str(e) == "Invalid values: min: 0.0, max: 10.0, mean: 15.0, mean must be between min and max."

def test_is_valid_float_valid():
    """
    Test the _is_valid_float function with a valid float value.
    """
    value = "3.14"
    assert _is_valid_float(value)

def test_is_valid_float_invalid():
    """
    Test the _is_valid_float function with an invalid float value.
    """
    value = "abc"
    assert not _is_valid_float(value)

def test_is_valid_float_empty():
    """
    Test the _is_valid_float function with an empty value.
    """
    value = ""
    assert not _is_valid_float(value)
