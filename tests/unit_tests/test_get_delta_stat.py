"""Test get_delta_stat function."""

import re
import zoneinfo

import numpy as np
import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import get_delta_stat


def test_get_delta_stat_valid_positive_delta() -> None:
    """Test get_delta_stat with valid positive delta."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00", "delta": "10.5"})
    result = get_delta_stat(row, tz)

    assert result != {}
    assert result["delta"] == 10.5
    assert result["start"].year == 2022
    assert result["start"].month == 1
    assert result["start"].day == 1
    assert result["start"].hour == 0
    assert result["start"].minute == 0


def test_get_delta_stat_valid_negative_delta() -> None:
    """Test get_delta_stat with valid negative delta."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00", "delta": "-5.2"})
    result = get_delta_stat(row, tz)

    assert result != {}
    assert result["delta"] == -5.2


def test_get_delta_stat_valid_zero_delta() -> None:
    """Test get_delta_stat with zero delta."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00", "delta": "0"})
    result = get_delta_stat(row, tz)

    assert result != {}
    assert result["delta"] == 0.0


def test_get_delta_stat_invalid_timestamp_not_full_hour() -> None:
    """Test get_delta_stat with invalid timestamp (not full hour)."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:30", "delta": "10.5"})

    with pytest.raises(HomeAssistantError, match=re.escape("Invalid timestamp: 01.01.2022 00:30. The timestamp must be a full hour.")):
        get_delta_stat(row, tz)


def test_get_delta_stat_invalid_timestamp_with_seconds() -> None:
    """Test get_delta_stat with invalid timestamp (has seconds)."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00:30", "delta": "10.5"})

    with pytest.raises(HomeAssistantError, match=re.escape("Invalid timestamp: 01.01.2022 00:00:30. The timestamp must be in the format '%d.%m.%Y %H:%M'.")):
        get_delta_stat(row, tz)


def test_get_delta_stat_invalid_delta_non_numeric() -> None:
    """Test get_delta_stat with non-numeric delta."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00", "delta": "abc"})

    with pytest.raises(HomeAssistantError, match=re.escape("Invalid float value: abc. Check the decimal separator.")):
        get_delta_stat(row, tz)


def test_get_delta_stat_invalid_delta_comma_separator() -> None:
    """Test get_delta_stat with comma as decimal separator (invalid)."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00", "delta": "10,5"})

    with pytest.raises(HomeAssistantError, match=re.escape("Invalid float value: 10,5. Check the decimal separator.")):
        get_delta_stat(row, tz)


def test_get_delta_stat_valid_delta_dot_separator() -> None:
    """Test get_delta_stat with dot as decimal separator (valid)."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00", "delta": "10.5"})
    result = get_delta_stat(row, tz)

    assert result != {}
    assert result["delta"] == 10.5


def test_get_delta_stat_missing_delta_column() -> None:
    """Test get_delta_stat with missing delta column."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00"})

    with pytest.raises(KeyError):
        get_delta_stat(row, tz)


def test_get_delta_stat_large_delta_value() -> None:
    """Test get_delta_stat with large delta value."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00", "delta": "999999.99"})
    result = get_delta_stat(row, tz)

    assert result != {}
    assert result["delta"] == 999999.99


def test_get_delta_stat_timezone_applied() -> None:
    """Test that get_delta_stat applies timezone correctly."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00", "delta": "10.5"})
    result = get_delta_stat(row, tz)

    assert result["start"].tzinfo == tz


def test_get_delta_stat_nan_delta() -> None:
    """Test get_delta_stat with NaN delta value (should raise error)."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00", "delta": np.nan})

    with pytest.raises(HomeAssistantError, match=re.escape("(NaN/empty value not allowed)")):
        get_delta_stat(row, tz)


def test_get_delta_stat_empty_string_delta() -> None:
    """Test get_delta_stat with empty string delta (should raise error)."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:00", "delta": ""})

    with pytest.raises(HomeAssistantError, match=re.escape("Invalid float value:")):
        get_delta_stat(row, tz)


def test_get_delta_stat_different_timezone() -> None:
    """Test get_delta_stat with different timezone."""
    tz = zoneinfo.ZoneInfo("UTC")
    row = pd.Series({"start": "01.01.2022 00:00", "delta": "10.5"})
    result = get_delta_stat(row, tz)

    assert result["start"].tzinfo == tz
