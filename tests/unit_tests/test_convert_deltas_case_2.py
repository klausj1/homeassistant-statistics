"""Tests for convert_deltas_case_2 function."""

import datetime as dt

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.import_service_delta_helper import convert_deltas_case_2


def test_convert_deltas_case_2_basic() -> None:
    """Test Case 2 conversion with basic delta rows."""
    # Reference is 100, and we have three deltas: 10, 20, 30 (from oldest to youngest)
    # Working backward from 100:
    # - Row 1 (oldest): 100 - 30 = 70 (subtract the last delta first)
    # - Row 2 (middle): 100 - 30 - 20 = 50
    # - Row 3 (youngest): 100 - 30 - 20 - 10 = 40 (but we subtract in reverse)

    tz = dt.UTC
    delta_rows = [
        {"start": dt.datetime(2025, 1, 1, 10, 0, tzinfo=tz), "delta": 10.0},
        {"start": dt.datetime(2025, 1, 1, 11, 0, tzinfo=tz), "delta": 20.0},
        {"start": dt.datetime(2025, 1, 1, 12, 0, tzinfo=tz), "delta": 30.0},
    ]

    result = convert_deltas_case_2(delta_rows, 100.0, 100.0)

    # With Case 2, we work backward from 100:
    # After processing row 3 (delta=30): 100 - 30 = 70
    # After processing row 2 (delta=20): 70 - 20 = 50
    # After processing row 1 (delta=10): 50 - 10 = 40
    # Then reverse to ascending order
    assert len(result) == 3
    assert result[0]["sum"] == 40.0
    assert result[1]["sum"] == 50.0
    assert result[2]["sum"] == 70.0
    assert result[0]["state"] == 40.0
    assert result[1]["state"] == 50.0
    assert result[2]["state"] == 70.0


def test_convert_deltas_case_2_single_row() -> None:
    """Test Case 2 conversion with single delta row."""
    tz = dt.UTC
    delta_rows = [
        {"start": dt.datetime(2025, 1, 1, 10, 0, tzinfo=tz), "delta": 25.0},
    ]

    result = convert_deltas_case_2(delta_rows, 100.0, 100.0)

    assert len(result) == 1
    assert result[0]["sum"] == 75.0
    assert result[0]["state"] == 75.0


def test_convert_deltas_case_2_empty_rows() -> None:
    """Test Case 2 conversion with no delta rows."""
    result = convert_deltas_case_2([], 100.0, 100.0)

    assert result == []


def test_convert_deltas_case_2_negative_deltas() -> None:
    """Test Case 2 conversion with negative delta values."""
    tz = dt.UTC
    delta_rows = [
        {"start": dt.datetime(2025, 1, 1, 10, 0, tzinfo=tz), "delta": -5.0},
        {"start": dt.datetime(2025, 1, 1, 11, 0, tzinfo=tz), "delta": 10.0},
    ]

    result = convert_deltas_case_2(delta_rows, 100.0, 100.0)

    # Working backward from 100:
    # After row 2 (delta=10): 100 - 10 = 90
    # After row 1 (delta=-5): 90 - (-5) = 95
    # Reverse to ascending: [95, 90]
    assert len(result) == 2
    assert result[0]["sum"] == 95.0
    assert result[1]["sum"] == 90.0


def test_convert_deltas_case_2_unsorted_rows() -> None:
    """Test that Case 2 raises error for unsorted rows."""
    tz = dt.UTC
    delta_rows = [
        {"start": dt.datetime(2025, 1, 1, 11, 0, tzinfo=tz), "delta": 20.0},  # Second
        {"start": dt.datetime(2025, 1, 1, 10, 0, tzinfo=tz), "delta": 10.0},  # First
    ]

    with pytest.raises(HomeAssistantError):
        convert_deltas_case_2(delta_rows, 100.0, 100.0)


def test_convert_deltas_case_2_preserves_timestamps() -> None:
    """Test that Case 2 preserves original timestamps in correct order."""
    tz = dt.UTC
    time1 = dt.datetime(2025, 1, 1, 10, 0, tzinfo=tz)
    time2 = dt.datetime(2025, 1, 1, 11, 0, tzinfo=tz)
    time3 = dt.datetime(2025, 1, 1, 12, 0, tzinfo=tz)

    delta_rows = [
        {"start": time1, "delta": 10.0},
        {"start": time2, "delta": 20.0},
        {"start": time3, "delta": 30.0},
    ]

    result = convert_deltas_case_2(delta_rows, 100.0, 100.0)

    assert result[0]["start"] == time1
    assert result[1]["start"] == time2
    assert result[2]["start"] == time3


def test_convert_deltas_case_2_float_precision() -> None:
    """Test Case 2 with floating point values."""
    tz = dt.UTC
    delta_rows = [
        {"start": dt.datetime(2025, 1, 1, 10, 0, tzinfo=tz), "delta": 10.5},
        {"start": dt.datetime(2025, 1, 1, 11, 0, tzinfo=tz), "delta": 20.25},
    ]

    result = convert_deltas_case_2(delta_rows, 100.123, 100.123)

    assert len(result) == 2
    # Working backward: 100.123 - 20.25 = 79.873, then 79.873 - 10.5 = 69.373
    assert abs(result[0]["sum"] - 69.373) < 0.001
    assert abs(result[1]["sum"] - 79.873) < 0.001
