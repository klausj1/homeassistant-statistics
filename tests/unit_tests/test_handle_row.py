"""Unit tests for functions is_full_hour, get_mean_stat and get_sum_stat."""

import re

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import (
    is_full_hour,
    is_valid_float,
    min_max_mean_are_valid,
)


def test_seconds_not_allowed() -> None:
    """Test the is_full_hour function with seconds, what is not allowed."""
    timestamp_str = "01.01.2022 12:00:00"

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '%d.%m.%Y %H:%M'."),
    ):
        is_full_hour(timestamp_str)

    timestamp_str = "01.01.2022 12:00:05"

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '%d.%m.%Y %H:%M'."),
    ):
        is_full_hour(timestamp_str)


def test_is_full_hour_invalid_minute() -> None:
    """Test the is_full_hour function with an invalid timestamp due to non-zero minute."""
    timestamp_str = "01.01.2022 12:30"

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Invalid timestamp: {timestamp_str}. The timestamp must be a full hour."),
    ):
        is_full_hour(timestamp_str)


def test_is_full_hour_no_second() -> None:
    """Test the is_full_hour function with a valid timestamp due to missing second."""
    timestamp_str = "01.01.2022 12:00"

    result = is_full_hour(timestamp_str)
    assert result is True


def test_is_full_hour_no_minute() -> None:
    """Test the is_full_hour function with an invalid timestamp due to non-zero minute."""
    timestamp_str = "01.01.2022 12"

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '%d.%m.%Y %H:%M'."),
    ):
        is_full_hour(timestamp_str)


def test_is_full_hour_other_datetime_format() -> None:
    """Test the is_full_hour function with an invalid timestamp due to non-zero minute."""
    timestamp_str = "2022-12-27 12:00"
    datetime_format = "%Y-%m-%d %H:%M"

    result = is_full_hour(timestamp_str, datetime_format)
    assert result is True


def test_is_full_hour_timestampstr_and_datetime_format_do_not_match() -> None:
    """Test the is_full_hour function with an invalid timestamp due to non-zero minute."""
    timestamp_str = "01.01.2022 12:00"
    datetime_format = "%Y/%m.%d %H:%M"

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '{datetime_format}'."),
    ):
        is_full_hour(timestamp_str, datetime_format)


def test_is_full_hour_invalid_datetime_format() -> None:
    """Test the is_full_hour function with an invalid timestamp due to non-zero minute."""
    timestamp_str = "01.01.2022 12:00"
    datetime_format = "invalid format"

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '{datetime_format}'."),
    ):
        is_full_hour(timestamp_str, datetime_format)


def test_min_max_mean_are_valid_valid_values() -> None:
    """Test the min_max_mean_are_valid function with valid values."""
    min_value = 0.0
    max_value = 10.0
    mean_value = 5.0

    assert min_max_mean_are_valid(min_value, max_value, mean_value)


def test_min_max_mean_are_valid_invalid_values() -> None:
    """Test the min_max_mean_are_valid function with invalid values."""
    min_value = 10.0
    max_value = 0.0
    mean_value = 5.0

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Invalid values: min: 10.0, max: 0.0, mean: 5.0, mean must be between min and max."),
    ):
        min_max_mean_are_valid(min_value, max_value, mean_value)


def test_min_max_mean_are_valid_equal_values() -> None:
    """Test the min_max_mean_are_valid function with equal min, max, and mean values."""
    min_value = 5.0
    max_value = 5.0
    mean_value = 5.0

    assert min_max_mean_are_valid(min_value, max_value, mean_value)


def test_min_max_mean_are_valid_mean_outside_range() -> None:
    """Test the min_max_mean_are_valid function with mean value outside the range of min and max."""
    min_value = 0.0
    max_value = 10.0
    mean_value = 15.0

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Invalid values: min: 0.0, max: 10.0, mean: 15.0, mean must be between min and max."),
    ):
        min_max_mean_are_valid(min_value, max_value, mean_value)


def test_is_valid_float_valid() -> None:
    """Test the is_valid_float function with a valid float value."""
    value = "3.14"
    assert is_valid_float(value)


def test_is_valid_float_invalid() -> None:
    """Test the is_valid_float function with an invalid float value."""
    value = "abc"

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Invalid float value: {value}. Check the decimal separator."),
    ):
        is_valid_float(value)


def test_is_valid_float_empty() -> None:
    """Test the is_valid_float function with an empty value."""
    value = ""

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Invalid float value: {value}. Check the decimal separator."),
    ):
        is_valid_float(value)
