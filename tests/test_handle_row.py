"""Unit tests for functions is_full_hour, get_mean_stat and get_sum_stat."""

from homeassistant.exceptions import HomeAssistantError
from custom_components.import_statistics.helpers import is_full_hour
from custom_components.import_statistics.helpers import is_valid_float
from custom_components.import_statistics.helpers import min_max_mean_are_valid

def test_seconds_not_allowed():
    """Test the is_full_hour function with seconds, what is not allowed."""
    timestamp_str = "01.01.2022 12:00:00"

    try:
        is_full_hour(timestamp_str)
        assert False, "Expected an exception to be raised for invalid timestamp"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '%d.%m.%Y %H:%M'."

    timestamp_str = "01.01.2022 12:00:05"

    try:
        is_full_hour(timestamp_str)
        assert False, "Expected an exception to be raised for invalid timestamp"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '%d.%m.%Y %H:%M'."


def test_is_full_hour_invalid_minute():
    """Test the is_full_hour function with an invalid timestamp due to non-zero minute."""
    timestamp_str = "01.01.2022 12:30"

    try:
        is_full_hour(timestamp_str)
        assert False, "Expected an exception to be raised for invalid timestamp"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid timestamp: {timestamp_str}. The timestamp must be a full hour."

def test_is_full_hour_no_second():
    """Test the is_full_hour function with a valid timestamp due to missing second."""
    timestamp_str = "01.01.2022 12:00"

    result = is_full_hour(timestamp_str)
    assert result is True

def test_is_full_hour_no_minute():
    """Test the is_full_hour function with an invalid timestamp due to non-zero minute."""
    timestamp_str = "01.01.2022 12"

    try:
        is_full_hour(timestamp_str)
        assert False, "Expected an exception to be raised for invalid timestamp"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '%d.%m.%Y %H:%M'."

def test_is_full_hour_other_datetime_format():
    """Test the is_full_hour function with an invalid timestamp due to non-zero minute."""
    timestamp_str = "2022-12-27 12:00"
    datetime_format = "%Y-%m-%d %H:%M"

    result = is_full_hour(timestamp_str, datetime_format)
    assert result is True

def test_is_full_hour_timestampstr_and_datetime_format_do_not_match():
    """Test the is_full_hour function with an invalid timestamp due to non-zero minute."""
    timestamp_str = "01.01.2022 12:00"
    datetime_format = "%Y/%m.%d %H:%M"

    try:
        is_full_hour(timestamp_str, datetime_format)
        assert False, "Expected an exception to be raised for invalid timestamp"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '{datetime_format}'."

def test_is_full_hour_invalid_datetime_format():
    """Test the is_full_hour function with an invalid timestamp due to non-zero minute."""
    timestamp_str = "01.01.2022 12:00"
    datetime_format = "invalid format"

    try:
        is_full_hour(timestamp_str, datetime_format)
        assert False, "Expected an exception to be raised for invalid timestamp"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '{datetime_format}'."

def test_min_max_mean_are_valid_valid_values():
    """Test the min_max_mean_are_valid function with valid values."""
    min_value = 0.0
    max_value = 10.0
    mean_value = 5.0

    assert min_max_mean_are_valid(min_value, max_value, mean_value)

def test_min_max_mean_are_valid_invalid_values():
    """Test the min_max_mean_are_valid function with invalid values."""
    min_value = 10.0
    max_value = 0.0
    mean_value = 5.0

    try:
        min_max_mean_are_valid(min_value, max_value, mean_value)
        assert False, "Expected an exception to be raised for invalid values"
    except HomeAssistantError as e:
        assert str(e) == "Invalid values: min: 10.0, max: 0.0, mean: 5.0, mean must be between min and max."

def test_min_max_mean_are_valid_equal_values():
    """Test the min_max_mean_are_valid function with equal min, max, and mean values."""
    min_value = 5.0
    max_value = 5.0
    mean_value = 5.0

    assert min_max_mean_are_valid(min_value, max_value, mean_value)

def test_min_max_mean_are_valid_mean_outside_range():
    """Test the min_max_mean_are_valid function with mean value outside the range of min and max."""
    min_value = 0.0
    max_value = 10.0
    mean_value = 15.0

    try:
        min_max_mean_are_valid(min_value, max_value, mean_value)
        assert False, "Expected an exception to be raised for invalid values"
    except HomeAssistantError as e:
        assert str(e) == "Invalid values: min: 0.0, max: 10.0, mean: 15.0, mean must be between min and max."

def test_is_valid_float_valid():
    """Test the is_valid_float function with a valid float value."""
    value = "3.14"
    assert is_valid_float(value)

def test_is_valid_float_invalid():
    """Test the is_valid_float function with an invalid float value."""
    value = "abc"

    try:
        _ = is_valid_float(value)
    except HomeAssistantError as e:
        assert str(e) == f"Invalid float value: {value}. Check the decimal separator."
    else:
        # If no exception is raised, fail the test
        assert False, "Expected HomeAssistantError to be raised"

def test_is_valid_float_empty():
    """Test the is_valid_float function with an empty value."""
    value = ""

    try:
        _ = is_valid_float(value)
    except HomeAssistantError as e:
        assert str(e) == f"Invalid float value: {value}. Check the decimal separator."
    else:
        # If no exception is raised, fail the test
        assert False, "Expected HomeAssistantError to be raised"
