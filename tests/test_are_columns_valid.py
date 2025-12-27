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
    """Test the are_columns_valid function with unknown column headers.

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
    """Test the are_columns_valid function with multiple unknown column headers.

    This test verifies that multiple unknown columns are rejected with an error message
    listing all the unknown columns.
    """
    # Valid columns with multiple additional unknown columns
    my_df = pd.DataFrame(
        columns=["statistic_id", "start", "unit", "mean", "min", "max", "extra_field_1", "extra_field_2", "notes"]
    )

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unknown columns in file: extra_field_1, extra_field_2, notes."),
    ):
        are_columns_valid(my_df, UnitFrom.TABLE)
