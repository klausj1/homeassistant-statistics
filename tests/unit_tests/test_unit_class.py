"""Unit tests to verify unit_class field in metadata."""

from zoneinfo import ZoneInfo

import pandas as pd
from homeassistant.components.recorder.models import StatisticMeanType

from custom_components.import_statistics.const import DATETIME_DEFAULT_FORMAT
from custom_components.import_statistics.helpers import get_unit_class
from custom_components.import_statistics.import_service_helper import handle_dataframe_no_delta


def test_unit_class_present_in_metadata_mean() -> None:
    """
    Test that unit_class field is present and correctly resolved for mean statistics.

    Verifies that the metadata dictionary includes the unit_class field
    and that it is resolved from the unit of measurement (°C -> temperature).
    """
    # Create a sample dataframe with 'mean'
    my_df = pd.DataFrame(
        [
            ["stat1.temp", "01.01.2022 00:00", "°C", 10, 20, 15],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean"],
    )

    # Parse timestamps (simulating what prepare_data_to_import does)
    my_df["start"] = pd.to_datetime(my_df["start"], format=DATETIME_DEFAULT_FORMAT).dt.tz_localize(ZoneInfo("UTC"))

    # Call the function
    stats = handle_dataframe_no_delta(my_df)

    # Get the metadata for the statistic
    metadata = stats["stat1.temp"][0]

    # Verify unit_class is present and correctly resolved
    assert "unit_class" in metadata, "unit_class field is missing from metadata"
    assert metadata["unit_class"] == "temperature", f"unit_class should be 'temperature', got {metadata['unit_class']}"

    # Verify other expected fields are present
    assert metadata["mean_type"] == StatisticMeanType.ARITHMETIC
    assert metadata["has_sum"] is False
    assert metadata["statistic_id"] == "stat1.temp"
    assert metadata["source"] == "recorder"
    assert metadata["unit_of_measurement"] == "°C"
    assert metadata["name"] is None


def test_unit_class_present_in_metadata_sum() -> None:
    """
    Test that unit_class field is present and correctly resolved for sum statistics.

    Verifies that the metadata dictionary includes the unit_class field
    and that it is resolved from the unit of measurement (kWh -> energy).
    """
    # Create a sample dataframe with 'sum'
    my_df = pd.DataFrame(
        [
            ["stat2.energy", "01.01.2022 00:00", "kWh", 100],
        ],
        columns=["statistic_id", "start", "unit", "sum"],
    )

    # Parse timestamps (simulating what prepare_data_to_import does)
    my_df["start"] = pd.to_datetime(my_df["start"], format=DATETIME_DEFAULT_FORMAT).dt.tz_localize(ZoneInfo("UTC"))

    # Call the function
    stats = handle_dataframe_no_delta(my_df)

    # Get the metadata for the statistic
    metadata = stats["stat2.energy"][0]

    # Verify unit_class is present and correctly resolved
    assert "unit_class" in metadata, "unit_class field is missing from metadata"
    assert metadata["unit_class"] == "energy", f"unit_class should be 'energy', got {metadata['unit_class']}"

    # Verify other expected fields are present
    assert metadata["mean_type"] == StatisticMeanType.NONE
    assert metadata["has_sum"] is True
    assert metadata["statistic_id"] == "stat2.energy"
    assert metadata["source"] == "recorder"
    assert metadata["unit_of_measurement"] == "kWh"
    assert metadata["name"] is None


def test_unit_class_multiple_statistics() -> None:
    """
    Test that unit_class field is correctly resolved for multiple statistics.

    Verifies that the unit_class field is properly resolved from the unit
    for each statistic when processing multiple different statistics.
    """
    # Create a sample dataframe with multiple statistics with mean values
    my_df = pd.DataFrame(
        [
            ["sensor.temperature", "01.01.2022 00:00", "°C", 10, 30, 20],
            ["sensor.humidity", "01.01.2022 00:00", "%", 20, 80, 50],
            ["sensor.pressure", "01.01.2022 00:00", "hPa", 990, 1020, 1000],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean"],
    )

    # Parse timestamps (simulating what prepare_data_to_import does)
    my_df["start"] = pd.to_datetime(my_df["start"], format=DATETIME_DEFAULT_FORMAT).dt.tz_localize(ZoneInfo("UTC"))

    # Call the function
    stats = handle_dataframe_no_delta(my_df)

    # Verify all statistics have correct unit_class
    expected_unit_classes = {
        "sensor.temperature": "temperature",
        "sensor.humidity": "unitless",
        "sensor.pressure": "pressure",
    }
    for stat_id, expected_class in expected_unit_classes.items():
        assert stat_id in stats, f"Statistic {stat_id} not found in results"
        metadata = stats[stat_id][0]
        assert "unit_class" in metadata, f"unit_class field is missing for {stat_id}"
        assert metadata["unit_class"] == expected_class, f"unit_class should be '{expected_class}' for {stat_id}, got {metadata['unit_class']}"


def test_unit_class_none_for_unknown_unit() -> None:
    """
    Test that unit_class is None for units not in HA's converter registry.

    Units like custom strings that don't map to any HA unit converter
    should result in unit_class=None.
    """
    my_df = pd.DataFrame(
        [
            ["sensor.custom", "01.01.2022 00:00", "bananas", 1, 5, 3],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean"],
    )

    my_df["start"] = pd.to_datetime(my_df["start"], format=DATETIME_DEFAULT_FORMAT).dt.tz_localize(ZoneInfo("UTC"))

    stats = handle_dataframe_no_delta(my_df)
    metadata = stats["sensor.custom"][0]

    assert "unit_class" in metadata, "unit_class field is missing from metadata"
    assert metadata["unit_class"] is None, f"unit_class should be None for unknown unit, got {metadata['unit_class']}"


def test_unit_class_none_for_empty_unit() -> None:
    """
    Test that unit_class is None when unit is empty/None.

    Statistics with no unit should have unit_class=None.
    """
    my_df = pd.DataFrame(
        [
            ["sensor.unitless", "01.01.2022 00:00", "", 1, 5, 3],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean"],
    )

    my_df["start"] = pd.to_datetime(my_df["start"], format=DATETIME_DEFAULT_FORMAT).dt.tz_localize(ZoneInfo("UTC"))

    stats = handle_dataframe_no_delta(my_df)
    metadata = stats["sensor.unitless"][0]

    assert "unit_class" in metadata, "unit_class field is missing from metadata"
    assert metadata["unit_class"] is None, f"unit_class should be None for empty unit, got {metadata['unit_class']}"


def test_get_unit_class_direct() -> None:
    """Test get_unit_class helper function directly with various units."""
    # Known HA units
    assert get_unit_class("°C") == "temperature"
    assert get_unit_class("°F") == "temperature"
    assert get_unit_class("K") == "temperature"
    assert get_unit_class("kWh") == "energy"
    assert get_unit_class("Wh") == "energy"
    assert get_unit_class("W") == "power"
    assert get_unit_class("kW") == "power"
    assert get_unit_class("hPa") == "pressure"
    assert get_unit_class("bar") == "pressure"
    assert get_unit_class("m") == "distance"
    assert get_unit_class("km") == "distance"
    assert get_unit_class("L") == "volume"
    assert get_unit_class("m³") == "volume"
    assert get_unit_class("A") == "electric_current"
    assert get_unit_class("V") == "voltage"
    assert get_unit_class("kg") == "mass"
    assert get_unit_class("%") == "unitless"
    assert get_unit_class("s") == "duration"
    assert get_unit_class("min") == "duration"

    # Unknown units -> None
    assert get_unit_class("bananas") is None
    assert get_unit_class("custom_unit") is None
    assert get_unit_class("") is None

    # None -> None
    assert get_unit_class(None) is None
