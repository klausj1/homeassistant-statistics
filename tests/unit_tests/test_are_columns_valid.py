"""Test component setup."""

import re

import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import are_columns_valid


def test_are_columns_valid_valid_columns() -> None:
    """Test the are_columns_valid function with valid columns."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "mean", "min", "max"])
    assert are_columns_valid(my_df)


def test_are_columns_valid_missing_required_columns() -> None:
    """Test the are_columns_valid function with missing required columns."""
    my_df = pd.DataFrame(columns=["statistic_id", "start"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("The file must contain the columns 'statistic_id', 'start' and 'unit' (check delimiter)"),
    ):
        are_columns_valid(my_df)


def test_are_columns_valid_missing_optional_columns() -> None:
    """Test the are_columns_valid function with missing optional columns."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "sum"])
    assert are_columns_valid(my_df)


@pytest.mark.parametrize(
    "sensor_columns",
    [
        ["mean"],
        ["min"],
        ["max"],
        ["mean", "min"],
        ["mean", "max"],
        ["min", "max"],
    ],
)
def test_are_columns_valid_partial_sensor_columns(sensor_columns: list[str]) -> None:
    """Test that sensor imports require all mean, min, and max columns."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", *sensor_columns])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Columns 'mean', 'min', and 'max' must either all be present or all be absent"),
    ):
        are_columns_valid(my_df)


def test_are_columns_valid_invalid_columns_combination() -> None:
    """Test the are_columns_valid function with mixed sensor and counter columns (now accepted)."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "mean", "min", "max", "sum"])
    assert are_columns_valid(my_df)


def test_are_columns_valid_unknown_columns_rejected() -> None:
    """
    Test the are_columns_valid function with unknown column headers.

    This test verifies that unknown columns are rejected and an error is raised.
    Only the allowed columns are permitted in the input file.
    """
    # Valid columns with an additional unknown column
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "mean", "min", "max", "unknown_column"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unknown columns in file: unknown_column."),
    ):
        are_columns_valid(my_df)


def test_are_columns_valid_multiple_unknown_columns_rejected() -> None:
    """
    Test the are_columns_valid function with multiple unknown column headers.

    This test verifies that multiple unknown columns are rejected with an error message
    listing all the unknown columns.
    """
    # Valid columns with multiple additional unknown columns
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "mean", "min", "max", "extra_field_1", "extra_field_2", "notes"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unknown columns in file: extra_field_1, extra_field_2, notes."),
    ):
        are_columns_valid(my_df)


def test_are_columns_valid_delta_with_unit() -> None:
    """Test the are_columns_valid function with valid delta-only CSV (with unit column)."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "delta"])
    assert are_columns_valid(my_df)


def test_are_columns_valid_delta_plus_sum_allowed() -> None:
    """Sparse export files may include both delta and sum columns before row-level validation."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "delta", "sum"])
    assert are_columns_valid(my_df)


def test_are_columns_valid_delta_plus_state_allowed() -> None:
    """Sparse export files may include both delta and state columns before row-level validation."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "delta", "state"])
    assert are_columns_valid(my_df)


def test_are_columns_valid_delta_plus_sensor_columns_allowed() -> None:
    """Sparse export files may include both delta and complete measurement columns before row-level validation."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "delta", "mean", "min", "max"])
    assert are_columns_valid(my_df)


def test_are_columns_valid_delta_plus_sensor_columns_allowed_2() -> None:
    """The same rule applies when the sensor side is represented in a different column order."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "min", "max", "mean", "delta"])
    assert are_columns_valid(my_df)


def test_are_columns_valid_delta_plus_sensor_columns_allowed_3() -> None:
    """Measurement and counter exports may share the same sparse file schema."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "mean", "min", "max", "sum", "state", "delta"])
    assert are_columns_valid(my_df)


def test_are_columns_valid_delta_missing_unit() -> None:
    """Test that delta without unit column raises error."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "delta"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("The file must contain the columns 'statistic_id', 'start' and 'unit' (check delimiter)"),
    ):
        are_columns_valid(my_df)
