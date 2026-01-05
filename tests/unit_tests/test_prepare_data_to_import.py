"""Unit tests for prepare_data_to_import function."""

import re
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.const import (
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_TIMEZONE_IDENTIFIER,
    ATTR_UNIT_FROM_ENTITY,
    DATETIME_DEFAULT_FORMAT,
)
from custom_components.import_statistics.helpers import UnitFrom
from custom_components.import_statistics.import_service_helper import prepare_data_to_import


def test_prepare_data_to_import_valid_file_dot() -> None:
    """Test prepare_data_to_import function with a valid file using dot decimal separator."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: True,  # True is ','
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t",
        ATTR_UNIT_FROM_ENTITY: False,
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    # Call the function
    df, timezone_id, datetime_format, unit_from_entity, is_delta = prepare_data_to_import(file_path, call)

    # Check the return types and values
    assert isinstance(df, pd.DataFrame)
    assert timezone_id == "Europe/London"
    assert datetime_format == DATETIME_DEFAULT_FORMAT
    assert unit_from_entity is UnitFrom.TABLE
    assert is_delta is False
    assert len(df) > 0
    assert "statistic_id" in df.columns
    assert "start" in df.columns
    assert "unit" in df.columns


def test_prepare_data_to_import_valid_file_comma() -> None:
    """Test prepare_data_to_import function with a valid file using comma decimal separator."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: False,  # False is '.'
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t",
        ATTR_UNIT_FROM_ENTITY: False,
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    # Call the function
    df, timezone_id, datetime_format, unit_from_entity, is_delta = prepare_data_to_import(file_path, call)

    # Check the return types and values
    assert isinstance(df, pd.DataFrame)
    assert timezone_id == "Europe/London"
    assert datetime_format == DATETIME_DEFAULT_FORMAT
    assert unit_from_entity is UnitFrom.TABLE
    assert is_delta is False
    assert len(df) > 0


def test_prepare_data_to_import_invalid_file() -> None:
    """Test prepare_data_to_import function with an invalid file."""
    file_path = "nonexistent.csv"

    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t",
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"path {file_path} does not exist."),
    ):
        prepare_data_to_import(file_path, call)


def test_prepare_data_to_import_invalid_data() -> None:
    """Test prepare_data_to_import function with invalid data in the file."""
    file_path = "tests/testfiles/wrongcolumns.csv"

    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t",
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            "The file must contain the columns 'statistic_id', 'start' and 'unit' ('unit' is needed only if unit_from_entity is false) (check delimiter)"
        ),
    ):
        prepare_data_to_import(file_path, call)


def test_prepare_data_to_import_valid_file_dot_unit_from_entity() -> None:
    """Test prepare_data_to_import function where unit comes from entity."""
    file_path = "tests/testfiles/correctcolumns_no_unit.csv"

    data = {
        ATTR_DECIMAL: True,  # True is ','
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t",
        ATTR_UNIT_FROM_ENTITY: True,
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    # Call the function
    df, timezone_id, datetime_format, unit_from_entity, is_delta = prepare_data_to_import(file_path, call)

    # Check the return types and values
    assert isinstance(df, pd.DataFrame)
    assert timezone_id == "Europe/London"
    assert datetime_format == DATETIME_DEFAULT_FORMAT
    assert unit_from_entity is UnitFrom.ENTITY
    assert is_delta is False
    assert len(df) > 0
    assert "statistic_id" in df.columns
    assert "start" in df.columns
    assert "unit" not in df.columns  # No unit column when unit_from_entity=True


def test_prepare_data_to_import_with_unknown_columns() -> None:
    """Test prepare_data_to_import function with unknown column headers."""
    # Create a DataFrame with valid columns plus unknown columns
    my_df = pd.DataFrame(
        [
            ["sensor.temperature", "26.01.2024 00:00", "°C", 20.1, 25.5, 22.8, "extra_data_1", "notes"],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean", "unknown_field", "comments"],
    )

    # Save to a temporary CSV file
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = str(Path(temp_dir) / "test_unknown_columns.csv")
        my_df.to_csv(file_path, sep="\t", index=False, decimal=",")

        data = {
            ATTR_DECIMAL: True,
            ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
            ATTR_DELIMITER: "\t",
            ATTR_UNIT_FROM_ENTITY: False,
        }

        call = ServiceCall("domain_name", "service_name", data, data)

        # Call the function - should raise an error due to unknown columns
        with pytest.raises(
            HomeAssistantError,
            match=re.escape("Unknown columns in file: comments, unknown_field."),
        ):
            prepare_data_to_import(file_path, call)


def test_prepare_data_to_import_unit_from_entity_with_unit_column() -> None:
    """Test prepare_data_to_import function with unit_from_entity=True and a unit column."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: True,  # True is ','
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t",
        ATTR_UNIT_FROM_ENTITY: True,  # Unit should come from entity, not from file
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    # Call the function - should raise an error because unit column is not allowed when unit_from_entity=True
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("A unit column is not allowed when unit is taken from entity (unit_from_entity is true). Please remove the unit column from the file."),
    ):
        prepare_data_to_import(file_path, call)
