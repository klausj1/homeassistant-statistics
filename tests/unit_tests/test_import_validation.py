"""Unit tests for import timestamp and dataframe validation."""

import datetime as dt

import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import AggregatedValidationError
from custom_components.import_statistics.import_service import (
    PreparedImportData,
    _validate_local_import_data,
    _validation_errors_from_exception,
)
from custom_components.import_statistics.import_service_helper import (
    CounterDataType,
    ImportDataClassification,
    ImportDataType,
    _collect_validation_errors,
    _parse_import_timestamps,
    _validate_dataframe_for_import,
    collect_dataframe_validation_errors,
)


def test_parse_import_timestamps_preserves_valid_rows_and_reports_invalid_values() -> None:
    """Keep good timestamps while returning errors for malformed and nonexistent values."""
    df = pd.DataFrame(
        {
            "start": ["29.03.2026 01:00", "not a timestamp", "29.03.2026 02:00", "29.03.2026 03:00"],
        }
    )

    errors = _parse_import_timestamps(df, "%d.%m.%Y %H:%M", "Europe/Berlin")

    assert len(errors) == 2
    assert "Invalid timestamp format at row 3" in errors[0]
    assert "Timestamp does not exist due to daylight saving time transition at row 4" in errors[1]
    assert pd.isna(df.loc[1, "start"])
    assert pd.isna(df.loc[2, "start"])
    assert df.loc[0, "start"] == pd.Timestamp("2026-03-29 01:00", tz="Europe/Berlin")
    assert df.loc[3, "start"] == pd.Timestamp("2026-03-29 03:00", tz="Europe/Berlin")


def test_parse_import_timestamps_reports_an_invalid_format_as_homeassistant_error() -> None:
    """Reject malformed format directives using the integration's validation error type."""
    with pytest.raises(HomeAssistantError, match="Invalid datetime format"):
        _parse_import_timestamps(pd.DataFrame({"start": ["01.01.2020 00:00"]}), "%d.%m.%Y %H:%xxxMsss", "UTC")


def test_collect_dataframe_validation_errors_returns_all_independent_errors() -> None:
    """Collect timestamp, numeric, min/max/mean, and unit errors in one pass."""
    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.energy", "sensor.energy"],
            "unit": ["kWh", "Wh"],
            "start": [
                pd.Timestamp("2020-01-01 00:30", tz="UTC"),
                pd.Timestamp("2020-01-01 01:00", tz="UTC"),
            ],
            "min": [4, "not numeric"],
            "max": [2, 3],
            "mean": [3, 2],
        }
    )

    errors = collect_dataframe_validation_errors(df, ["min", "max", "mean"])

    assert any("Invalid timestamp at row 2" in error for error in errors)
    assert any("Invalid float value in column 'min' at row 3" in error for error in errors)
    assert any("Invalid values at row 2" in error for error in errors)
    assert any("Inconsistent units for 'sensor.energy'" in error for error in errors)


def test_collect_dataframe_validation_errors_handles_empty_and_all_invalid_timestamps() -> None:
    """Return no errors for an empty frame and a clear error when no timestamp is usable."""
    assert collect_dataframe_validation_errors(pd.DataFrame(), ["sum"]) == []

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.energy"],
            "unit": ["kWh"],
            "start": pd.to_datetime([None], utc=True),
            "sum": [1],
        }
    )
    errors = collect_dataframe_validation_errors(df, ["sum"])

    assert "No valid timestamps found in import data" in errors


def test_collect_validation_errors_returns_aggregated_and_single_errors() -> None:
    """Normalize Home Assistant validation exceptions to lists without swallowing other errors."""
    assert _collect_validation_errors(lambda: None) == []

    def raise_aggregated() -> None:
        raise AggregatedValidationError(["first", "second"])

    def raise_single() -> None:
        message = "single"
        raise HomeAssistantError(message)

    assert _collect_validation_errors(raise_aggregated) == ["first", "second"]
    assert _collect_validation_errors(raise_single) == ["single"]

    def raise_unexpected() -> None:
        message = "unexpected"
        raise RuntimeError(message)

    with pytest.raises(RuntimeError, match="unexpected"):
        _collect_validation_errors(raise_unexpected)


def test_validate_dataframe_for_import_raises_collected_value_and_unit_errors() -> None:
    """Raise all frame validation errors rather than stopping at the first one."""
    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.energy", "sensor.energy"],
            "unit": ["kWh", "Wh"],
            "start": [pd.Timestamp("2020-01-01 00:00", tz="UTC")] * 2,
            "min": ["invalid", 1],
            "max": [3, 3],
            "mean": [2, 2],
        }
    )

    with pytest.raises(AggregatedValidationError) as exc_info:
        _validate_dataframe_for_import(df)

    assert any("Invalid float value in column 'min'" in error for error in exc_info.value.errors)
    assert any("Inconsistent units for 'sensor.energy'" in error for error in exc_info.value.errors)


def test_validate_dataframe_for_import_accepts_valid_sum_and_state_values() -> None:
    """Validate counter sum/state columns without producing errors for valid data."""
    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.energy"],
            "unit": ["kWh"],
            "start": [pd.Timestamp("2020-01-01 00:00", tz="UTC")],
            "sum": [10],
            "state": [2],
        }
    )

    assert _validate_dataframe_for_import(df) is None


def test_validate_dataframe_for_import_reports_missing_supported_value_columns() -> None:
    """Treat unsupported dataframe shapes as an explicit import validation error."""
    with pytest.raises(HomeAssistantError, match="neither mean nor sum columns found"):
        _validate_dataframe_for_import(pd.DataFrame({"start": []}))


def test_validation_errors_from_exception_preserves_aggregated_errors() -> None:
    """Return every aggregated message or the single ordinary exception message."""
    assert _validation_errors_from_exception(AggregatedValidationError(["first", "second"])) == ["first", "second"]
    assert _validation_errors_from_exception(HomeAssistantError("single")) == ["single"]


def test_validate_local_import_data_collects_saved_and_sensor_errors() -> None:
    """Combine preparation errors with row-level sensor, numeric, and unit errors."""
    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.energy", "sensor.energy"],
            "unit": ["kWh", "Wh"],
            "start": [pd.Timestamp("2020-01-01 00:00", tz="UTC")] * 2,
            "min": [1, "invalid"],
            "max": [3, 3],
            "mean": [2, 2],
        }
    )
    df.attrs["validation_errors"] = ["invalid source timestamp"]
    data = PreparedImportData(
        df=df,
        timezone_id="UTC",
        datetime_format="%d.%m.%Y %H:%M",
        classification=ImportDataClassification(ImportDataType.SENSOR, None),
    )

    errors = _validate_local_import_data(data)

    assert "invalid source timestamp" in errors
    assert any("Invalid float value in column 'min'" in error for error in errors)
    assert any("Inconsistent units for 'sensor.energy'" in error for error in errors)


def test_validate_local_import_data_keeps_counter_mode_and_value_errors() -> None:
    """Report conflicting counter representations without losing invalid value errors."""
    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.energy"],
            "unit": ["kWh"],
            "start": [dt.datetime(2020, 1, 1, tzinfo=dt.UTC)],
            "sum": [1],
            "delta": ["invalid"],
        }
    )
    data = PreparedImportData(
        df=df,
        timezone_id="UTC",
        datetime_format="%d.%m.%Y %H:%M",
        classification=ImportDataClassification(ImportDataType.COUNTER, CounterDataType.BOTH),
    )

    errors = _validate_local_import_data(data)

    assert any("Counter data is conflicting" in error for error in errors)
    assert any("Invalid float value in column 'delta'" in error for error in errors)


def test_validate_local_import_data_validates_mixed_sensor_and_sum_data() -> None:
    """Validate each statistic through its sensor or counter partition."""
    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.temperature", "sensor.energy"],
            "unit": ["°C", "kWh"],
            "start": [pd.Timestamp("2020-01-01 00:00", tz="UTC")] * 2,
            "min": [1, None],
            "max": [3, None],
            "mean": [2, None],
            "sum": [None, 10],
        }
    )
    data = PreparedImportData(
        df=df,
        timezone_id="UTC",
        datetime_format="%d.%m.%Y %H:%M",
        classification=ImportDataClassification(ImportDataType.MIXED, CounterDataType.SUM_STATE),
    )

    assert _validate_local_import_data(data) == []


def test_validate_local_import_data_validates_sum_state_counters() -> None:
    """Run the selected sum/state validation branch for counter imports."""
    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.energy"],
            "unit": ["kWh"],
            "start": [pd.Timestamp("2020-01-01 00:00", tz="UTC")],
            "sum": [10],
            "state": [2],
        }
    )
    data = PreparedImportData(
        df=df,
        timezone_id="UTC",
        datetime_format="%d.%m.%Y %H:%M",
        classification=ImportDataClassification(ImportDataType.COUNTER, CounterDataType.SUM_STATE),
    )

    assert _validate_local_import_data(data) == []


def test_validate_local_import_data_validates_delta_counter_values() -> None:
    """Run delta-mode validation and retain invalid values as row-specific errors."""
    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.energy", "sensor.energy"],
            "unit": ["kWh", "kWh"],
            "start": [
                pd.Timestamp("2020-01-01 00:00", tz="UTC"),
                pd.Timestamp("2020-01-01 01:00", tz="UTC"),
            ],
            "delta": [1.5, "invalid"],
        }
    )
    data = PreparedImportData(
        df=df,
        timezone_id="UTC",
        datetime_format="%d.%m.%Y %H:%M",
        classification=ImportDataClassification(ImportDataType.COUNTER, CounterDataType.DELTA),
        counter_mode="delta",
    )

    errors = _validate_local_import_data(data)

    assert len(errors) == 1
    assert "Invalid float value in column 'delta' at row 3" in errors[0]
