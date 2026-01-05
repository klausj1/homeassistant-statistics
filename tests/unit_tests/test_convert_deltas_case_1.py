"""Test convert_deltas_with_older_reference function."""

import datetime as dt
import zoneinfo

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.import_service_delta_helper import convert_deltas_with_older_reference


def test_convert_deltas_case_1_single_delta() -> None:
    """Test convert_deltas_case_1 with single delta row."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    delta_rows = [
        {
            "start": dt.datetime(2022, 1, 1, 0, 0, tzinfo=tz),
            "delta": 10.5,
        }
    ]

    result = convert_deltas_with_older_reference(delta_rows, sum_oldest=100.0, state_oldest=100.0)

    assert len(result) == 1
    assert result[0]["start"] == dt.datetime(2022, 1, 1, 0, 0, tzinfo=tz)
    assert result[0]["sum"] == 110.5
    assert result[0]["state"] == 110.5


def test_convert_deltas_case_1_multiple_deltas() -> None:
    """Test convert_deltas_case_1 with multiple delta rows."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    delta_rows = [
        {"start": dt.datetime(2022, 1, 1, 0, 0, tzinfo=tz), "delta": 10.5},
        {"start": dt.datetime(2022, 1, 1, 1, 0, tzinfo=tz), "delta": 5.2},
        {"start": dt.datetime(2022, 1, 1, 2, 0, tzinfo=tz), "delta": 3.1},
    ]

    result = convert_deltas_with_older_reference(delta_rows, sum_oldest=100.0, state_oldest=100.0)

    assert len(result) == 3
    assert result[0]["sum"] == 110.5
    assert result[0]["state"] == 110.5
    assert result[1]["sum"] == 115.7
    assert result[1]["state"] == 115.7
    assert result[2]["sum"] == 118.8
    assert result[2]["state"] == 118.8


def test_convert_deltas_case_1_negative_deltas() -> None:
    """Test convert_deltas_case_1 with negative deltas."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    delta_rows = [
        {"start": dt.datetime(2022, 1, 1, 0, 0, tzinfo=tz), "delta": -10.5},
        {"start": dt.datetime(2022, 1, 1, 1, 0, tzinfo=tz), "delta": -5.2},
    ]

    result = convert_deltas_with_older_reference(delta_rows, sum_oldest=100.0, state_oldest=100.0)

    assert len(result) == 2
    assert result[0]["sum"] == 89.5
    assert result[0]["state"] == 89.5
    assert result[1]["sum"] == 84.3
    assert result[1]["state"] == 84.3


def test_convert_deltas_case_1_zero_delta() -> None:
    """Test convert_deltas_case_1 with zero delta."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    delta_rows = [
        {"start": dt.datetime(2022, 1, 1, 0, 0, tzinfo=tz), "delta": 0.0},
    ]

    result = convert_deltas_with_older_reference(delta_rows, sum_oldest=100.0, state_oldest=100.0)

    assert len(result) == 1
    assert result[0]["sum"] == 100.0
    assert result[0]["state"] == 100.0


def test_convert_deltas_case_1_mixed_deltas() -> None:
    """Test convert_deltas_case_1 with mixed positive and negative deltas."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    delta_rows = [
        {"start": dt.datetime(2022, 1, 1, 0, 0, tzinfo=tz), "delta": 10.0},
        {"start": dt.datetime(2022, 1, 1, 1, 0, tzinfo=tz), "delta": -5.0},
        {"start": dt.datetime(2022, 1, 1, 2, 0, tzinfo=tz), "delta": 3.0},
    ]

    result = convert_deltas_with_older_reference(delta_rows, sum_oldest=100.0, state_oldest=100.0)

    assert len(result) == 3
    assert result[0]["sum"] == 110.0
    assert result[1]["sum"] == 105.0
    assert result[2]["sum"] == 108.0


def test_convert_deltas_case_1_large_values() -> None:
    """Test convert_deltas_case_1 with large delta values."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    delta_rows = [
        {"start": dt.datetime(2022, 1, 1, 0, 0, tzinfo=tz), "delta": 999999.99},
    ]

    result = convert_deltas_with_older_reference(delta_rows, sum_oldest=1000000.0, state_oldest=1000000.0)

    assert len(result) == 1
    assert result[0]["sum"] == 1999999.99
    assert result[0]["state"] == 1999999.99


def test_convert_deltas_case_1_unsorted_rows_raises_error() -> None:
    """Test convert_deltas_case_1 raises error for unsorted rows."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    delta_rows = [
        {"start": dt.datetime(2022, 1, 1, 2, 0, tzinfo=tz), "delta": 3.1},
        {"start": dt.datetime(2022, 1, 1, 0, 0, tzinfo=tz), "delta": 10.5},
        {"start": dt.datetime(2022, 1, 1, 1, 0, tzinfo=tz), "delta": 5.2},
    ]

    with pytest.raises(HomeAssistantError, match="Delta rows must be sorted"):
        convert_deltas_with_older_reference(delta_rows, sum_oldest=100.0, state_oldest=100.0)


def test_convert_deltas_case_1_empty_rows() -> None:
    """Test convert_deltas_case_1 with empty rows."""
    result = convert_deltas_with_older_reference([], sum_oldest=100.0, state_oldest=100.0)

    assert result == []


def test_convert_deltas_case_1_preserves_order() -> None:
    """Test convert_deltas_case_1 preserves chronological order."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    delta_rows = [
        {"start": dt.datetime(2022, 1, 1, 0, 0, tzinfo=tz), "delta": 1.0},
        {"start": dt.datetime(2022, 1, 1, 1, 0, tzinfo=tz), "delta": 2.0},
        {"start": dt.datetime(2022, 1, 1, 2, 0, tzinfo=tz), "delta": 3.0},
    ]

    result = convert_deltas_with_older_reference(delta_rows, sum_oldest=0.0, state_oldest=0.0)

    assert result[0]["start"] < result[1]["start"] < result[2]["start"]
    assert result[0]["start"] == dt.datetime(2022, 1, 1, 0, 0, tzinfo=tz)
    assert result[1]["start"] == dt.datetime(2022, 1, 1, 1, 0, tzinfo=tz)
    assert result[2]["start"] == dt.datetime(2022, 1, 1, 2, 0, tzinfo=tz)
