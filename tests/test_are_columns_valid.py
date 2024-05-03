"""Test component setup."""

from homeassistant.exceptions import HomeAssistantError

import pandas as pd
from custom_components.import_statistics.helpers import are_columns_valid

def test_are_columns_valid_valid_columns():
    """Test the are_columns_valid function with valid columns."""
    columns = pd.Index(["statistic_id", "start", "unit", "mean", "min", "max"])
    assert are_columns_valid(columns, False)

def test_are_columns_valid_missing_required_columns():
    """Test the are_columns_valid function with missing required columns."""
    columns = pd.Index(["statistic_id", "start"])
    try:
        are_columns_valid(columns, False)
        assert False, "Expected an exception to be raised for missing required columns"
    except HomeAssistantError as e:
        assert str(e) == "The file must contain the columns 'statistic_id', 'start' and 'unit' ('unit' is needed only if unit_from_entity is false) (check delimiter)"

def test_are_columns_valid_missing_optional_columns():
    """Test the are_columns_valid function with missing optional columns."""
    columns = pd.Index(["statistic_id", "start", "unit", "sum"])
    assert are_columns_valid(columns, False)

def test_are_columns_valid_invalid_columns_combination():
    """Test the are_columns_valid function with invalid combination of columns."""
    columns = pd.Index(["statistic_id", "start", "unit", "mean", "sum"])
    try:
        are_columns_valid(columns, False)
        assert False, "Expected an exception to be raised for invalid combination of columns"
    except HomeAssistantError as e:
        assert str(e) == "The file must not contain the columns 'sum' and 'mean'/'min'/'max' (check delimiter)"

# ToDo: Test with unit_from_entity is True
