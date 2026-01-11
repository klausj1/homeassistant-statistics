"""Test component setup."""

import re

import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import UnitFrom, are_columns_valid


def test_are_columns_valid_valid_columns() -> None:
    """Test the are_columns_valid function with valid columns."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "mean", "min", "max"])
    assert are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_missing_required_columns() -> None:
    """Test the are_columns_valid function with missing required columns."""
    my_df = pd.DataFrame(columns=["statistic_id", "start"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            "The file must contain the columns 'statistic_id', 'start' and 'unit' ('unit' is needed only if unit_from_entity is false) (check delimiter)"
        ),
    ):
        are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_missing_optional_columns() -> None:
    """Test the are_columns_valid function with missing optional columns."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "sum"])
    assert are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_invalid_columns_combination() -> None:
    """Test the are_columns_valid function with invalid combination of columns."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "mean", "sum"])
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("The file must not contain the columns 'sum/state' together with 'mean'/'min'/'max' (check delimiter)"),
    ):
        are_columns_valid(my_df, UnitFrom.TABLE)


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
        are_columns_valid(my_df, UnitFrom.TABLE)


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
        are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_delta_with_unit() -> None:
    """Test the are_columns_valid function with valid delta-only CSV (with unit column)."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "delta"])
    assert are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_delta_without_unit_from_entity() -> None:
    """Test the are_columns_valid function with valid delta-only CSV (without unit, unit_from_entity=True)."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "delta"])
    assert are_columns_valid(my_df, UnitFrom.ENTITY)


def test_are_columns_valid_delta_with_unit_from_entity_error() -> None:
    """Test that delta with unit column and unit_from_entity=True raises error."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "delta"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("A unit column is not allowed when unit is taken from entity (unit_from_entity is true). Please remove the unit column from the file."),
    ):
        are_columns_valid(my_df, UnitFrom.ENTITY)


def test_are_columns_valid_delta_plus_sum_error() -> None:
    """Test that delta + sum columns raises error."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "delta", "sum"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Delta column cannot be used with 'sum', 'state', 'mean', 'min', or 'max' columns (check delimiter)"),
    ):
        are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_delta_plus_state_error() -> None:
    """Test that delta + state columns raises error."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "delta", "state"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Delta column cannot be used with 'sum', 'state', 'mean', 'min', or 'max' columns (check delimiter)"),
    ):
        are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_delta_plus_mean_error() -> None:
    """Test that delta + mean columns raises error."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "delta", "mean"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Delta column cannot be used with 'sum', 'state', 'mean', 'min', or 'max' columns (check delimiter)"),
    ):
        are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_delta_plus_min_error() -> None:
    """Test that delta + min columns raises error."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "delta", "min"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Delta column cannot be used with 'sum', 'state', 'mean', 'min', or 'max' columns (check delimiter)"),
    ):
        are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_delta_plus_max_error() -> None:
    """Test that delta + max columns raises error."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "delta", "max"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Delta column cannot be used with 'sum', 'state', 'mean', 'min', or 'max' columns (check delimiter)"),
    ):
        are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_delta_missing_unit_table() -> None:
    """Test that delta without unit column and unit_from_entity=False raises error."""
    my_df = pd.DataFrame(columns=["statistic_id", "start", "delta"])

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            "The file must contain the columns 'statistic_id', 'start' and 'unit' ('unit' is needed only if unit_from_entity is false) (check delimiter)"
        ),
    ):
        are_columns_valid(my_df, UnitFrom.TABLE)
