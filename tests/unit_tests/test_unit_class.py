"""Unit tests to verify unit_class field in metadata."""

from zoneinfo import ZoneInfo

import pandas as pd
from homeassistant.components.recorder.models import StatisticMeanType

from custom_components.import_statistics.const import DATETIME_DEFAULT_FORMAT
from custom_components.import_statistics.import_service_helper import handle_dataframe_no_delta


def test_unit_class_present_in_metadata_mean() -> None:
    """
    Test that unit_class field is present and set to None in metadata for mean statistics.

    This test verifies that the metadata dictionary includes the unit_class field
    and that it is set to None when creating statistics from data with mean values.
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

    # Call the function without unit_class (default None)
    stats = handle_dataframe_no_delta(my_df)

    # Get the metadata for the statistic
    metadata = stats["stat1.temp"][0]

    # Verify unit_class is present
    assert "unit_class" in metadata, "unit_class field is missing from metadata"

    # Verify unit_class is None
    assert metadata["unit_class"] is None, f"unit_class should be None, got {metadata['unit_class']}"

    # Verify other expected fields are present
    assert metadata["mean_type"] == StatisticMeanType.ARITHMETIC
    assert metadata["has_sum"] is False
    assert metadata["statistic_id"] == "stat1.temp"
    assert metadata["source"] == "recorder"
    assert metadata["unit_of_measurement"] == "°C"
    assert metadata["name"] is None


def test_unit_class_present_in_metadata_sum() -> None:
    """
    Test that unit_class field is present and set to None in metadata for sum statistics.

    This test verifies that the metadata dictionary includes the unit_class field
    and that it is set to None when creating statistics from data with sum values.
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

    # Call the function without unit_class (default None)
    stats = handle_dataframe_no_delta(my_df)

    # Get the metadata for the statistic
    metadata = stats["stat2.energy"][0]

    # Verify unit_class is present
    assert "unit_class" in metadata, "unit_class field is missing from metadata"

    # Verify unit_class is None
    assert metadata["unit_class"] is None, f"unit_class should be None, got {metadata['unit_class']}"

    # Verify other expected fields are present
    assert metadata["mean_type"] == StatisticMeanType.NONE
    assert metadata["has_sum"] is True
    assert metadata["statistic_id"] == "stat2.energy"
    assert metadata["source"] == "recorder"
    assert metadata["unit_of_measurement"] == "kWh"
    assert metadata["name"] is None


def test_unit_class_multiple_statistics() -> None:
    """
    Test that unit_class field is set to None for multiple statistics.

    This test verifies that the unit_class field is properly set to None
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

    # Call the function without unit_class (default None)
    stats = handle_dataframe_no_delta(my_df)

    # Verify all statistics have unit_class set to None
    for stat_id in ["sensor.temperature", "sensor.humidity", "sensor.pressure"]:
        assert stat_id in stats, f"Statistic {stat_id} not found in results"
        metadata = stats[stat_id][0]
        assert "unit_class" in metadata, f"unit_class field is missing for {stat_id}"
        assert metadata["unit_class"] is None, f"unit_class should be None for {stat_id}, got {metadata['unit_class']}"


def test_unit_class_set_to_energy() -> None:
    """
    Test that unit_class field is set to "energy" when provided.

    This test verifies that the unit_class field is properly set to "energy"
    when the unit_class parameter is provided, which is needed for energy dashboard support.
    """
    # Create a sample dataframe with 'sum' (energy data)
    my_df = pd.DataFrame(
        [
            ["sensor:external_energy", "01.01.2022 00:00", "kWh", 100],
        ],
        columns=["statistic_id", "start", "unit", "sum"],
    )

    # Parse timestamps (simulating what prepare_data_to_import does)
    my_df["start"] = pd.to_datetime(my_df["start"], format=DATETIME_DEFAULT_FORMAT).dt.tz_localize(ZoneInfo("UTC"))

    # Call the function with unit_class set to "energy"
    stats = handle_dataframe_no_delta(my_df, unit_class="energy")

    # Get the metadata for the statistic
    metadata = stats["sensor:external_energy"][0]

    # Verify unit_class is present and set to "energy"
    assert "unit_class" in metadata, "unit_class field is missing from metadata"
    assert metadata["unit_class"] == "energy", f"unit_class should be 'energy', got {metadata['unit_class']}"

    # Verify other expected fields are present
    assert metadata["mean_type"] == StatisticMeanType.NONE
    assert metadata["has_sum"] is True
    assert metadata["statistic_id"] == "sensor:external_energy"
    assert metadata["source"] == "sensor"  # External statistics use domain as source
    assert metadata["unit_of_measurement"] == "kWh"
    assert metadata["name"] is None


def test_unit_class_set_to_power() -> None:
    """
    Test that unit_class field is set to "power" when provided.

    This test verifies that the unit_class field is properly set to "power"
    when the unit_class parameter is provided.
    """
    # Create a sample dataframe with 'mean' (power data)
    my_df = pd.DataFrame(
        [
            ["sensor:external_power", "01.01.2022 00:00", "W", 10, 500, 250],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean"],
    )

    # Parse timestamps (simulating what prepare_data_to_import does)
    my_df["start"] = pd.to_datetime(my_df["start"], format=DATETIME_DEFAULT_FORMAT).dt.tz_localize(ZoneInfo("UTC"))

    # Call the function with unit_class set to "power"
    stats = handle_dataframe_no_delta(my_df, unit_class="power")

    # Get the metadata for the statistic
    metadata = stats["sensor:external_power"][0]

    # Verify unit_class is present and set to "power"
    assert "unit_class" in metadata, "unit_class field is missing from metadata"
    assert metadata["unit_class"] == "power", f"unit_class should be 'power', got {metadata['unit_class']}"

    # Verify other expected fields are present
    assert metadata["mean_type"] == StatisticMeanType.ARITHMETIC
    assert metadata["has_sum"] is False
    assert metadata["statistic_id"] == "sensor:external_power"
    assert metadata["source"] == "sensor"
    assert metadata["unit_of_measurement"] == "W"
    assert metadata["name"] is None
