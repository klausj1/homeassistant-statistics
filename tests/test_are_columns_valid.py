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
        match=re.escape("The file must not contain the columns 'sum' and 'mean'/'min'/'max' (check delimiter)"),
    ):
        are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_unknown_columns_ignored() -> None:
    """Test the are_columns_valid function with unknown column headers.

    This test verifies the current behavior where unknown columns are silently ignored.
    Unknown columns are not validated against and do not cause errors. This allows for
    flexibility in input files with extra columns that are not used for statistics import.
    """
    # Valid columns with an additional unknown column
    my_df = pd.DataFrame(columns=["statistic_id", "start", "unit", "mean", "min", "max", "unknown_column"])
    # Should return True - unknown columns are ignored, not validated
    assert are_columns_valid(my_df, UnitFrom.TABLE)


def test_are_columns_valid_multiple_unknown_columns_ignored() -> None:
    """Test the are_columns_valid function with multiple unknown column headers.

    This test verifies that multiple unknown columns are also silently ignored,
    as long as all required columns are present.
    """
    # Valid columns with multiple additional unknown columns
    my_df = pd.DataFrame(
        columns=["statistic_id", "start", "unit", "mean", "min", "max", "extra_field_1", "extra_field_2", "notes"]
    )
    # Should return True - all unknown columns are ignored
    assert are_columns_valid(my_df, UnitFrom.TABLE)
