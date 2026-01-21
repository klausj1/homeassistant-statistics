"""Test handle_dataframe_delta function."""

import datetime as dt
import re
import zoneinfo

import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import DeltaReferenceType, UnitFrom
from custom_components.import_statistics.import_service_delta_helper import handle_dataframe_delta


def test_convert_delta_dataframe_with_references_single_statistic() -> None:
    """Test handle_dataframe_delta with single statistic."""
    tz_id = "Europe/Vienna"
    tz = zoneinfo.ZoneInfo(tz_id)
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.temperature", "sensor.temperature"],
            "start": ["01.01.2022 00:00", "01.01.2022 01:00"],
            "delta": ["10.5", "5.2"],
            "unit": ["°C", "°C"],
        }
    )

    references = {
        "sensor.temperature": {
            "reference": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 100.0, "state": 100.0},
            "ref_type": DeltaReferenceType.OLDER_REFERENCE,
        }
    }

    result = handle_dataframe_delta(df, tz_id, datetime_format, UnitFrom.TABLE, references)

    assert len(result) == 1
    assert "sensor.temperature" in result
    metadata, stats = result["sensor.temperature"]
    assert metadata["has_sum"] is True
    assert metadata["mean_type"].value == 0  # NONE
    assert len(stats) == 2
    assert stats[0]["sum"] == 110.5
    assert stats[1]["sum"] == 115.7


def test_convert_delta_dataframe_with_references_multiple_statistics() -> None:
    """Test handle_dataframe_delta with multiple statistics."""
    tz_id = "Europe/Vienna"
    tz = zoneinfo.ZoneInfo(tz_id)
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.energy", "sensor.energy", "sensor.gas", "sensor.gas"],
            "start": ["01.01.2022 00:00", "01.01.2022 01:00", "01.01.2022 00:00", "01.01.2022 01:00"],
            "delta": [10.5, 5.2, 1.5, 2.1],
            "unit": ["kWh", "kWh", "m³", "m³"],
        }
    )

    references = {
        "sensor.energy": {
            "reference": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 100.0, "state": 100.0},
            "ref_type": DeltaReferenceType.OLDER_REFERENCE,
        },
        "sensor.gas": {
            "reference": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 50.0, "state": 50.0},
            "ref_type": DeltaReferenceType.OLDER_REFERENCE,
        },
    }

    result = handle_dataframe_delta(df, tz_id, datetime_format, UnitFrom.TABLE, references)

    assert len(result) == 2
    assert "sensor.energy" in result
    assert "sensor.gas" in result

    # Check energy
    _energy_meta, energy_stats = result["sensor.energy"]
    assert len(energy_stats) == 2
    assert energy_stats[0]["sum"] == 110.5

    # Check gas
    _gas_meta, gas_stats = result["sensor.gas"]
    assert len(gas_stats) == 2
    assert gas_stats[0]["sum"] == 51.5


def test_convert_delta_dataframe_with_references_missing_reference() -> None:
    """Test handle_dataframe_delta raises error for missing reference."""
    tz_id = "Europe/Vienna"
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.temperature"],
            "start": ["01.01.2022 00:00"],
            "delta": [10.5],
            "unit": ["°C"],
        }
    )

    references = {"sensor.temperature": None}

    with pytest.raises(HomeAssistantError, match="Failed to find database reference"):
        handle_dataframe_delta(df, tz_id, datetime_format, UnitFrom.TABLE, references)


def test_convert_delta_dataframe_with_references_unit_from_entity() -> None:
    """Test handle_dataframe_delta with unit_from_entity."""
    tz_id = "Europe/Vienna"
    tz = zoneinfo.ZoneInfo(tz_id)
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.temperature"],
            "start": ["01.01.2022 00:00"],
            "delta": [10.5],
        }
    )

    references = {
        "sensor.temperature": {
            "reference": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 100.0, "state": 100.0},
            "ref_type": DeltaReferenceType.OLDER_REFERENCE,
        }
    }

    result = handle_dataframe_delta(df, tz_id, datetime_format, UnitFrom.ENTITY, references)

    assert len(result) == 1
    metadata, _stats = result["sensor.temperature"]
    assert metadata["unit_of_measurement"] == ""  # Empty for unit_from_entity


def test_convert_delta_dataframe_with_references_external_statistics() -> None:
    """Test handle_dataframe_delta with external (colon-format) statistic."""
    tz_id = "Europe/Vienna"
    tz = zoneinfo.ZoneInfo(tz_id)
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["custom:energy", "custom:energy"],
            "start": ["01.01.2022 00:00", "01.01.2022 01:00"],
            "delta": ["10.5", "5.2"],
            "unit": ["kWh", "kWh"],
        }
    )

    references = {
        "custom:energy": {
            "reference": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 100.0, "state": 100.0},
            "ref_type": DeltaReferenceType.OLDER_REFERENCE,
        }
    }

    result = handle_dataframe_delta(df, tz_id, datetime_format, UnitFrom.TABLE, references)

    assert len(result) == 1
    metadata, _stats = result["custom:energy"]
    assert metadata["source"] == "custom"
    assert metadata["has_sum"] is True


def test_convert_delta_dataframe_with_references_invalid_rows_throws_error() -> None:
    """Test handle_dataframe_delta throws an error for invalid rows."""
    tz_id = "Europe/Vienna"
    tz = zoneinfo.ZoneInfo(tz_id)
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.temperature", "sensor.temperature"],
            "start": ["01.01.2022 00:30", "01.01.2022 01:00"],  # First row has invalid timestamp (not full hour)
            "delta": [10.5, 5.2],
            "unit": ["°C", "°C"],
        }
    )

    references = {
        "sensor.temperature": {
            "reference": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 100.0, "state": 100.0},
            "ref_type": DeltaReferenceType.OLDER_REFERENCE,
        }
    }

    with pytest.raises(HomeAssistantError, match=re.escape("Invalid timestamp: 01.01.2022 00:30. The timestamp must be a full hour.")):
        handle_dataframe_delta(df, tz_id, datetime_format, UnitFrom.TABLE, references)
