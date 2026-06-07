"""Unit tests for mixed import functionality (sensor + counter in one file)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import are_columns_valid
from custom_components.import_statistics.import_service_helper import (
    ImportDataType,
    _validate_and_detect_delta,
    handle_dataframe_mixed,
    split_dataframe_by_type,
)


def test_are_columns_valid_mixed_accepted() -> None:
    """Verify a DataFrame with both sensor and counter columns passes are_columns_valid()."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "min", "max", "mean", "sum", "state"])
    assert are_columns_valid(my_df)


def test_validate_and_detect_delta_returns_mixed() -> None:
    """Verify _validate_and_detect_delta() returns ImportDataType.MIXED when both sensor and counter columns are present."""
    my_df = pd.DataFrame(
        [
            ["sensor.temp", "01.01.2022 00:00", "°C", 1.0, 10.0, 5.0, np.nan, np.nan],
            ["counter.energy", "01.01.2022 00:00", "kWh", np.nan, np.nan, np.nan, 100.0, 50.0],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean", "sum", "state"],
    )
    result = _validate_and_detect_delta(my_df)
    assert result == ImportDataType.MIXED


def test_validate_and_detect_delta_returns_sensor() -> None:
    """Verify _validate_and_detect_delta() returns ImportDataType.SENSOR for sensor-only columns."""
    my_df = pd.DataFrame(
        [
            ["sensor.temp", "01.01.2022 00:00", "°C", 1.0, 10.0, 5.0],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean"],
    )
    result = _validate_and_detect_delta(my_df)
    assert result == ImportDataType.SENSOR


def test_validate_and_detect_delta_returns_counter() -> None:
    """Verify _validate_and_detect_delta() returns ImportDataType.COUNTER for counter-only columns."""
    my_df = pd.DataFrame(
        [
            ["counter.energy", "01.01.2022 00:00", "kWh", 100.0, 50.0],
        ],
        columns=["statistic_id", "start", "unit", "sum", "state"],
    )
    result = _validate_and_detect_delta(my_df)
    assert result == ImportDataType.COUNTER


def test_validate_and_detect_delta_returns_delta() -> None:
    """Verify _validate_and_detect_delta() returns ImportDataType.DELTA for delta columns."""
    my_df = pd.DataFrame(
        [
            ["counter.energy", "01.01.2022 00:00", "kWh", 5.0],
        ],
        columns=["statistic_id", "start", "unit", "delta"],
    )
    result = _validate_and_detect_delta(my_df)
    assert result == ImportDataType.DELTA


def test_split_dataframe_by_type_basic() -> None:
    """Create a DataFrame with 2 sensor and 2 counter entities, verify correct split."""
    my_df = pd.DataFrame(
        [
            ["sensor.temp", "°C", pd.Timestamp("2022-01-01 00:00", tz="UTC"), 1.0, 10.0, 5.0, np.nan, np.nan],
            ["sensor.temp", "°C", pd.Timestamp("2022-01-01 01:00", tz="UTC"), 2.0, 20.0, 15.0, np.nan, np.nan],
            ["sensor.humidity", "%", pd.Timestamp("2022-01-01 00:00", tz="UTC"), 30.0, 80.0, 55.0, np.nan, np.nan],
            ["sensor.humidity", "%", pd.Timestamp("2022-01-01 01:00", tz="UTC"), 35.0, 85.0, 60.0, np.nan, np.nan],
            ["counter.energy", "kWh", pd.Timestamp("2022-01-01 00:00", tz="UTC"), np.nan, np.nan, np.nan, 100.0, 50.0],
            ["counter.energy", "kWh", pd.Timestamp("2022-01-01 01:00", tz="UTC"), np.nan, np.nan, np.nan, 110.0, 55.0],
            ["counter.gas", "m³", pd.Timestamp("2022-01-01 00:00", tz="UTC"), np.nan, np.nan, np.nan, 200.0, 100.0],
            ["counter.gas", "m³", pd.Timestamp("2022-01-01 01:00", tz="UTC"), np.nan, np.nan, np.nan, 220.0, 110.0],
        ],
        columns=["statistic_id", "unit", "start", "min", "max", "mean", "sum", "state"],
    )

    sensor_df, counter_df = split_dataframe_by_type(my_df)

    # Verify sensor_df
    assert len(sensor_df) == 4
    assert set(sensor_df["statistic_id"].unique()) == {"sensor.temp", "sensor.humidity"}
    assert list(sensor_df.columns) == ["statistic_id", "unit", "start", "min", "max", "mean"]

    # Verify counter_df
    assert len(counter_df) == 4
    assert set(counter_df["statistic_id"].unique()) == {"counter.energy", "counter.gas"}
    assert list(counter_df.columns) == ["statistic_id", "unit", "start", "sum", "state"]


def test_split_dataframe_by_type_sensor_only() -> None:
    """All entities are sensors → counter_df is empty."""
    my_df = pd.DataFrame(
        [
            ["sensor.temp", "°C", pd.Timestamp("2022-01-01 00:00", tz="UTC"), 1.0, 10.0, 5.0, np.nan, np.nan],
            ["sensor.humidity", "%", pd.Timestamp("2022-01-01 00:00", tz="UTC"), 30.0, 80.0, 55.0, np.nan, np.nan],
        ],
        columns=["statistic_id", "unit", "start", "min", "max", "mean", "sum", "state"],
    )

    sensor_df, counter_df = split_dataframe_by_type(my_df)

    assert len(sensor_df) == 2
    assert set(sensor_df["statistic_id"].unique()) == {"sensor.temp", "sensor.humidity"}
    assert counter_df.empty


def test_split_dataframe_by_type_counter_only() -> None:
    """All entities are counters → sensor_df is empty."""
    my_df = pd.DataFrame(
        [
            ["counter.energy", "kWh", pd.Timestamp("2022-01-01 00:00", tz="UTC"), np.nan, np.nan, np.nan, 100.0, 50.0],
            ["counter.gas", "m³", pd.Timestamp("2022-01-01 00:00", tz="UTC"), np.nan, np.nan, np.nan, 200.0, 100.0],
        ],
        columns=["statistic_id", "unit", "start", "min", "max", "mean", "sum", "state"],
    )

    sensor_df, counter_df = split_dataframe_by_type(my_df)

    assert sensor_df.empty
    assert len(counter_df) == 2
    assert set(counter_df["statistic_id"].unique()) == {"counter.energy", "counter.gas"}


def test_split_dataframe_by_type_single_entity_both_types_error() -> None:
    """A single statistic_id has rows with mean AND rows with sum → should raise HomeAssistantError."""
    my_df = pd.DataFrame(
        [
            ["sensor.mixed", "unit", pd.Timestamp("2022-01-01 00:00", tz="UTC"), 1.0, 10.0, 5.0, 100.0, np.nan],
        ],
        columns=["statistic_id", "unit", "start", "min", "max", "mean", "sum", "state"],
    )

    with pytest.raises(
        HomeAssistantError,
        match=r"has both sensor.*and counter.*data",
    ):
        split_dataframe_by_type(my_df)


def test_handle_dataframe_mixed_end_to_end() -> None:
    """Create a mixed DataFrame with localized timestamps, call handle_dataframe_mixed(), verify results."""
    tz = ZoneInfo("Europe/Berlin")
    my_df = pd.DataFrame(
        [
            ["sensor.temp", "°C", pd.Timestamp(datetime(2022, 1, 1, 0, 0, tzinfo=tz)), 1.0, 10.0, 5.0, np.nan, np.nan],
            ["sensor.temp", "°C", pd.Timestamp(datetime(2022, 1, 1, 1, 0, tzinfo=tz)), 2.0, 20.0, 15.0, np.nan, np.nan],
            ["counter.energy", "kWh", pd.Timestamp(datetime(2022, 1, 1, 0, 0, tzinfo=tz)), np.nan, np.nan, np.nan, 100.0, 50.0],
            ["counter.energy", "kWh", pd.Timestamp(datetime(2022, 1, 1, 1, 0, tzinfo=tz)), np.nan, np.nan, np.nan, 110.0, 55.0],
        ],
        columns=["statistic_id", "unit", "start", "min", "max", "mean", "sum", "state"],
    )

    stats = handle_dataframe_mixed(my_df)

    # Verify both entities are present
    assert "sensor.temp" in stats
    assert "counter.energy" in stats

    # Verify sensor metadata
    sensor_meta, sensor_stats = stats["sensor.temp"]
    assert sensor_meta["mean_type"] == StatisticMeanType.ARITHMETIC
    assert sensor_meta["has_sum"] is False
    assert sensor_meta["statistic_id"] == "sensor.temp"
    assert sensor_meta["source"] == "recorder"
    assert sensor_meta["unit_of_measurement"] == "°C"

    # Verify sensor statistics list
    assert len(sensor_stats) == 2
    assert sensor_stats[0]["min"] == 1.0
    assert sensor_stats[0]["max"] == 10.0
    assert sensor_stats[0]["mean"] == 5.0
    assert sensor_stats[1]["min"] == 2.0
    assert sensor_stats[1]["max"] == 20.0
    assert sensor_stats[1]["mean"] == 15.0

    # Verify counter metadata
    counter_meta, counter_stats = stats["counter.energy"]
    assert counter_meta["mean_type"] == StatisticMeanType.NONE
    assert counter_meta["has_sum"] is True
    assert counter_meta["statistic_id"] == "counter.energy"
    assert counter_meta["source"] == "recorder"
    assert counter_meta["unit_of_measurement"] == "kWh"

    # Verify counter statistics list
    assert len(counter_stats) == 2
    assert counter_stats[0]["sum"] == 100.0
    assert counter_stats[0]["state"] == 50.0
    assert counter_stats[1]["sum"] == 110.0
    assert counter_stats[1]["state"] == 55.0
