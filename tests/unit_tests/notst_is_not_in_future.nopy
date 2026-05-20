"""Unit tests for is_not_in_future function."""

import datetime as dt
import zoneinfo

import pytest
from freezegun import freeze_time
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import is_not_in_future


@freeze_time("2024-03-17 14:30:00", tz_offset=0)
def test_is_not_in_future_valid_old_timestamp() -> None:
    """Test is_not_in_future with a timestamp that is old enough (2 hours ago)."""
    # Current time: 14:30 UTC
    # Cutoff: 14:30 - 65min = 13:25 -> truncated to 13:00
    # Timestamp 2 hours ago (12:00) should be valid
    timestamp = dt.datetime(2024, 3, 17, 12, 0, 0, tzinfo=dt.UTC)
    result = is_not_in_future(timestamp)
    assert result is True


@freeze_time("2024-03-17 14:30:00", tz_offset=0)
def test_is_not_in_future_valid_exactly_at_cutoff() -> None:
    """Test is_not_in_future with a timestamp exactly at the cutoff."""
    # Current time: 14:30
    # Cutoff: 14:30 - 65min = 13:25 -> truncated to 13:00
    # Timestamp at 13:00 should be valid (exactly at cutoff)
    timestamp = dt.datetime(2024, 3, 17, 13, 0, 0, tzinfo=dt.UTC)
    result = is_not_in_future(timestamp)
    assert result is True


@freeze_time("2024-03-17 14:30:00", tz_offset=0)
def test_is_not_in_future_invalid_too_recent() -> None:
    """Test is_not_in_future with a timestamp that is too recent."""
    # Current time: 14:30
    # Cutoff: 14:30 - 65min = 13:25 -> truncated to 13:00
    # Timestamp at 14:00 should be invalid (too recent)
    timestamp = dt.datetime(2024, 3, 17, 14, 0, 0, tzinfo=dt.UTC)

    with pytest.raises(
        HomeAssistantError,
        match=r"Timestamp .* is too recent\. The newest allowed timestamp is",
    ):
        is_not_in_future(timestamp)


@freeze_time("2024-03-17 15:00:00", tz_offset=0)
def test_is_not_in_future_cutoff_calculation() -> None:
    """Test that cutoff is calculated correctly: current - 65 min, truncated to full hour."""
    # Current time: 15:00
    # Cutoff: 15:00 - 65min = 13:55 -> truncated to 13:00

    # 13:00 is valid (at cutoff)
    timestamp_valid = dt.datetime(2024, 3, 17, 13, 0, 0, tzinfo=dt.UTC)
    assert is_not_in_future(timestamp_valid) is True

    # 14:00 is invalid (too recent)
    timestamp_invalid = dt.datetime(2024, 3, 17, 14, 0, 0, tzinfo=dt.UTC)
    with pytest.raises(HomeAssistantError):
        is_not_in_future(timestamp_invalid)


@freeze_time("2024-03-17 14:30:00", tz_offset=0)
def test_is_not_in_future_different_timezone() -> None:
    """Test is_not_in_future with a timestamp in a different timezone."""
    # Current time: 14:30 UTC
    # Cutoff: 14:30 - 65min = 13:25 -> truncated to 13:00 UTC

    # Timestamp in Europe/Berlin (UTC+1 in March after DST switch)
    # 14:00 Berlin = 13:00 UTC, which should be valid (exactly at cutoff)
    berlin_tz = zoneinfo.ZoneInfo("Europe/Berlin")
    timestamp = dt.datetime(2024, 3, 17, 14, 0, 0, tzinfo=berlin_tz)
    result = is_not_in_future(timestamp)
    assert result is True


@freeze_time("2024-03-17 14:06:00", tz_offset=0)
def test_is_not_in_future_edge_case_minute_6() -> None:
    """Test edge case where current time is at minute 6 (65 min before gives previous hour +1 min)."""
    # Current time: 14:06
    # Cutoff: 14:06 - 65min = 13:01 -> truncated to 13:00

    # 13:00 should be valid (at cutoff)
    timestamp = dt.datetime(2024, 3, 17, 13, 0, 0, tzinfo=dt.UTC)
    result = is_not_in_future(timestamp)
    assert result is True


@freeze_time("2024-03-17 14:04:00", tz_offset=0)
def test_is_not_in_future_edge_case_minute_4() -> None:
    """Test edge case where current time is at minute 4 (65 min before crosses hour boundary)."""
    # Current time: 14:04
    # Cutoff: 14:04 - 65min = 12:59 -> truncated to 12:00

    # 12:00 should be valid (at cutoff)
    timestamp_valid = dt.datetime(2024, 3, 17, 12, 0, 0, tzinfo=dt.UTC)
    assert is_not_in_future(timestamp_valid) is True

    # 13:00 should be invalid (too recent)
    timestamp_invalid = dt.datetime(2024, 3, 17, 13, 0, 0, tzinfo=dt.UTC)
    with pytest.raises(HomeAssistantError):
        is_not_in_future(timestamp_invalid)


@freeze_time("2024-03-17 14:05:00", tz_offset=0)
def test_is_not_in_future_edge_case_minute_5() -> None:
    """Test edge case where current time is at minute 5 (65 min before = exactly previous hour)."""
    # Current time: 14:05
    # Cutoff: 14:05 - 65min = 13:00 -> truncated to 13:00 (no change)

    # 13:00 should be valid (exactly at cutoff)
    timestamp_valid = dt.datetime(2024, 3, 17, 13, 0, 0, tzinfo=dt.UTC)
    assert is_not_in_future(timestamp_valid) is True

    # 14:00 should be invalid (too recent)
    timestamp_invalid = dt.datetime(2024, 3, 17, 14, 0, 0, tzinfo=dt.UTC)
    with pytest.raises(HomeAssistantError):
        is_not_in_future(timestamp_invalid)


@freeze_time("2024-03-17 14:30:00", tz_offset=0)
def test_is_not_in_future_future_timestamp() -> None:
    """Test is_not_in_future with a timestamp in the actual future."""
    # Timestamp in the future (tomorrow) should definitely be invalid
    timestamp = dt.datetime(2024, 3, 18, 14, 0, 0, tzinfo=dt.UTC)

    with pytest.raises(
        HomeAssistantError,
        match=r"Timestamp .* is too recent\. The newest allowed timestamp is",
    ):
        is_not_in_future(timestamp)
