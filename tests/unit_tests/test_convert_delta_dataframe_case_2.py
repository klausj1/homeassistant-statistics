"""Tests for handle_dataframe_delta with OLDER and NEWER reference support."""

import datetime as dt

import pandas as pd

from custom_components.import_statistics.helpers import DeltaReferenceType, UnitFrom
from custom_components.import_statistics.import_service_delta_helper import handle_dataframe_delta


def test_convert_delta_dataframe_case_1_older_reference() -> None:
    """Test that OLDER_REFERENCE is used when reference is before import data."""
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
            "reference": {
                "start": ref_start,
                "sum": 100.0,
                "state": 100.0,
            },
            "ref_type": DeltaReferenceType.OLDER_REFERENCE,
        }
    }

    result = handle_dataframe_delta(df, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE, references)

    assert "sensor.test" in result
    metadata, stats = result["sensor.test"]
    assert metadata["source"] == "recorder"
    assert len(stats) == 2
    # OLDER_REFERENCE: accumulate forward
    assert stats[0]["sum"] == 110.0  # 100 + 10
    assert stats[1]["sum"] == 130.0  # 100 + 10 + 20


def test_convert_delta_dataframe_case_2_newer_reference() -> None:
    """Test that NEWER_REFERENCE is used when reference is after import data."""
    # Reference at 11:00 (at newest import data time)
    ref_start = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.UTC)

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
            "reference": {
                "start": ref_start,
                "sum": 130.0,
                "state": 130.0,
            },
            "ref_type": DeltaReferenceType.NEWER_REFERENCE,
        }
    }

    result = handle_dataframe_delta(df, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE, references)

    assert "sensor.test" in result
    metadata, stats = result["sensor.test"]
    assert metadata["source"] == "recorder"
    assert len(stats) == 3  # Now includes connection record
    # NEWER_REFERENCE: subtract backward from newer reference
    # Reference is 130, last delta is 20: 130 - 20 = 110
    # Second calculation: 110 - 10 = 100
    # Reverse to ascending: [100, 110, 130 (connection record)]
    assert stats[0]["sum"] == 100.0
    assert stats[1]["sum"] == 110.0
    assert stats[2]["sum"] == 130.0  # Connection record at reference time


def test_convert_delta_dataframe_multiple_statistics_mixed_cases() -> None:
    """Test mixed OLDER_REFERENCE and NEWER_REFERENCE for different statistics."""
    ref_start_1 = dt.datetime(2025, 1, 1, 9, 0, tzinfo=dt.UTC)  # Before
    ref_start_2 = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.UTC)  # At newest import time

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
            "reference": {
                "start": ref_start_1,
                "sum": 100.0,
                "state": 100.0,
            },
            "ref_type": DeltaReferenceType.OLDER_REFERENCE,
        },
        "sensor.test2": {
            "reference": {
                "start": ref_start_2,
                "sum": 130.0,
                "state": 130.0,
            },
            "ref_type": DeltaReferenceType.NEWER_REFERENCE,
        },
    }

    result = handle_dataframe_delta(df, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE, references)

    assert len(result) == 2

    # Test OLDER_REFERENCE (sensor.test1)
    _metadata1, stats1 = result["sensor.test1"]
    assert len(stats1) == 2
    assert stats1[0]["sum"] == 110.0
    assert stats1[1]["sum"] == 130.0

    # Test NEWER_REFERENCE (sensor.test2) - now includes connection record
    _metadata2, stats2 = result["sensor.test2"]
    assert len(stats2) == 3  # Now includes connection record
    assert stats2[0]["sum"] == 100.0
    assert stats2[1]["sum"] == 110.0
    assert stats2[2]["sum"] == 130.0  # Connection record
