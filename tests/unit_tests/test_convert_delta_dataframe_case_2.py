"""Tests for convert_delta_dataframe_with_references with Case 2 support."""

import datetime as dt

import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import UnitFrom
from custom_components.import_statistics.prepare_data import convert_delta_dataframe_with_references


def test_convert_delta_dataframe_case_1_older_reference() -> None:
    """Test that Case 1 is used when reference is before import data."""
    # Reference at 09:00 (before import data starting at 10:00)
    ref_start = dt.datetime(2025, 1, 1, 9, 0, tzinfo=dt.UTC)

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.test", "sensor.test"],
            "start": ["01.01.2025 10:00", "01.01.2025 11:00"],
            "delta": [10.0, 20.0],
            "unit": ["kWh", "kWh"],
        }
    )

    references = {
        "sensor.test": {
            "start": ref_start,
            "sum": 100.0,
            "state": 100.0,
        }
    }

    result = convert_delta_dataframe_with_references(df, references, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE)

    assert "sensor.test" in result
    metadata, stats = result["sensor.test"]
    assert metadata["source"] == "recorder"
    assert len(stats) == 2
    # Case 1: accumulate forward
    assert stats[0]["sum"] == 110.0  # 100 + 10
    assert stats[1]["sum"] == 130.0  # 100 + 10 + 20


def test_convert_delta_dataframe_case_2_younger_reference() -> None:
    """Test that Case 2 is used when reference is after import data."""
    # Reference at 13:00 (after import data ending at 11:00)
    ref_start = dt.datetime(2025, 1, 1, 13, 0, tzinfo=dt.UTC)

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.test", "sensor.test"],
            "start": ["01.01.2025 10:00", "01.01.2025 11:00"],
            "delta": [10.0, 20.0],
            "unit": ["kWh", "kWh"],
        }
    )

    references = {
        "sensor.test": {
            "start": ref_start,
            "sum": 130.0,
            "state": 130.0,
        }
    }

    result = convert_delta_dataframe_with_references(df, references, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE)

    assert "sensor.test" in result
    metadata, stats = result["sensor.test"]
    assert metadata["source"] == "recorder"
    assert len(stats) == 2
    # Case 2: subtract backward from younger reference
    # Reference is 130, last delta is 20: 130 - 20 = 110
    # Second calculation: 110 - 10 = 100
    # Reverse to ascending: [100, 110]
    assert stats[0]["sum"] == 100.0
    assert stats[1]["sum"] == 110.0


def test_convert_delta_dataframe_case_2_disabled() -> None:
    """Test that Case 2 raises error when disabled."""
    ref_start = dt.datetime(2025, 1, 1, 13, 0, tzinfo=dt.UTC)

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.test"],
            "start": ["01.01.2025 10:00"],
            "delta": [10.0],
            "unit": ["kWh"],
        }
    )

    references = {
        "sensor.test": {
            "start": ref_start,
            "sum": 110.0,
            "state": 110.0,
        }
    }

    with pytest.raises(HomeAssistantError):
        convert_delta_dataframe_with_references(df, references, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE, case_2_conversion_enabled=False)


def test_convert_delta_dataframe_invalid_reference_timestamp() -> None:
    """Test that error is raised for invalid reference timestamp."""
    # Reference at 10:30 (between import data timestamps)
    ref_start = dt.datetime(2025, 1, 1, 10, 30, tzinfo=dt.UTC)

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.test"],
            "start": ["01.01.2025 10:00"],
            "delta": [10.0],
            "unit": ["kWh"],
        }
    )

    references = {
        "sensor.test": {
            "start": ref_start,
            "sum": 100.0,
            "state": 100.0,
        }
    }

    with pytest.raises(HomeAssistantError):
        convert_delta_dataframe_with_references(df, references, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE)


def test_convert_delta_dataframe_multiple_statistics_mixed_cases() -> None:
    """Test mixed Case 1 and Case 2 references for different statistics."""
    ref_start_1 = dt.datetime(2025, 1, 1, 9, 0, tzinfo=dt.UTC)  # Before
    ref_start_2 = dt.datetime(2025, 1, 1, 13, 0, tzinfo=dt.UTC)  # After

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.test1", "sensor.test1", "sensor.test2", "sensor.test2"],
            "start": ["01.01.2025 10:00", "01.01.2025 11:00", "01.01.2025 10:00", "01.01.2025 11:00"],
            "delta": [10.0, 20.0, 10.0, 20.0],
            "unit": ["kWh", "kWh", "kWh", "kWh"],
        }
    )

    references = {
        "sensor.test1": {
            "start": ref_start_1,
            "sum": 100.0,
            "state": 100.0,
        },
        "sensor.test2": {
            "start": ref_start_2,
            "sum": 130.0,
            "state": 130.0,
        },
    }

    result = convert_delta_dataframe_with_references(df, references, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE)

    assert len(result) == 2

    # Test Case 1 (sensor.test1)
    _metadata1, stats1 = result["sensor.test1"]
    assert stats1[0]["sum"] == 110.0
    assert stats1[1]["sum"] == 130.0

    # Test Case 2 (sensor.test2)
    _metadata2, stats2 = result["sensor.test2"]
    assert stats2[0]["sum"] == 100.0
    assert stats2[1]["sum"] == 110.0
