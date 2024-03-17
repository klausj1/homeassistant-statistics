"""Test component setup."""

from homeassistant.exceptions import HomeAssistantError

import pandas as pd
from custom_components.import_statistics import _are_columns_valid

def test_are_columns_valid_valid_columns():
    """
    Test the _are_columns_valid function with valid columns.
    """
    columns = pd.Index(["statistic_id", "start", "unit", "mean", "min", "max"])
    assert _are_columns_valid(columns)

def test_are_columns_valid_missing_required_columns():
    """
    Test the _are_columns_valid function with missing required columns.
    """
    columns = pd.Index(["statistic_id", "start"])
    try:
        _are_columns_valid(columns)
        assert False, "Expected an exception to be raised for missing required columns"
    except HomeAssistantError as e:
        assert str(e) == "The file must contain the columns 'statistic_id', 'start' and 'unit' (check delimiter)"

def test_are_columns_valid_missing_optional_columns():
    """
    Test the _are_columns_valid function with missing optional columns.
    """
    columns = pd.Index(["statistic_id", "start", "unit", "sum"])
    assert _are_columns_valid(columns)

def test_are_columns_valid_invalid_columns_combination():
    """
    Test the _are_columns_valid function with invalid combination of columns.
    """
    columns = pd.Index(["statistic_id", "start", "unit", "mean", "sum"])
    try:
        _are_columns_valid(columns)
        assert False, "Expected an exception to be raised for invalid combination of columns"
    except HomeAssistantError as e:
        assert str(e) == "The file must not contain the columns 'sum' and 'mean'/'min'/'max' (check delimiter)"
