"""Unit tests for handle_arguments function."""

import re

import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.const import (
    ATTR_DATETIME_FORMAT,
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_TIMEZONE_IDENTIFIER,
    ATTR_UNIT_FROM_ENTITY,
    DATETIME_DEFAULT_FORMAT,
)
from custom_components.import_statistics.helpers import UnitFrom
from custom_components.import_statistics.prepare_data import handle_arguments


def test_handle_arguments_all_valid() -> None:
    """Test the handle_arguments function with a valid timezone identifier and a valid file path, no optional parameters."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: ",",
    }

    call = ServiceCall("domain_name", "service_name", data, None)

    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(file_path, call)

    assert decimal == ","
    assert timezone_identifier == "Europe/London"
    assert delimiter == ","
    assert datetime_format == DATETIME_DEFAULT_FORMAT
    assert unit_from_entity is UnitFrom.TABLE


def test_handle_arguments_all_valid_other_parameters() -> None:
    """Test the handle_arguments function with a valid timezone identifier and a valid file path, with some changed parameters."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: False,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "/t",
        ATTR_DATETIME_FORMAT: "%Y-%m-%d %H:%M:%S",
        ATTR_UNIT_FROM_ENTITY: True,
    }

    call = ServiceCall("domain_name", "service_name", data, None)

    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(file_path, call)

    assert decimal == "."
    assert timezone_identifier == "Europe/London"
    assert delimiter == "/t"
    assert datetime_format == "%Y-%m-%d %H:%M:%S"
    assert unit_from_entity is UnitFrom.ENTITY


def test_handle_arguments_invalid_timezone() -> None:
    """Test the handle_arguments function with an invalid timezone identifier."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Invalid/Timezone",
        ATTR_DELIMITER: ",",
    }

    call = ServiceCall("domain_name", "service_name", data, None)

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Invalid timezone_identifier: Invalid/Timezone"),
    ):
        handle_arguments(file_path, call)


def test_handle_arguments_file_not_found() -> None:
    """Test the handle_arguments function with a file that does not exist."""
    file_path = "/path/to/nonexistent_file.csv"
    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: ",",
    }

    call = ServiceCall("domain_name", "service_name", data, None)

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"path {file_path} does not exist."),
    ):
        handle_arguments(file_path, call)


def test_handle_arguments_attr_from_entity_false() -> None:
    """Test the handle_arguments function with a valid timezone identifier and a valid file path, with some changed parameters."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: False,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "/t",
        ATTR_DATETIME_FORMAT: "%Y-%m-%d %H:%M:%S",
        ATTR_UNIT_FROM_ENTITY: False,
    }

    call = ServiceCall("domain_name", "service_name", data, None)

    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(file_path, call)

    assert decimal == "."
    assert timezone_identifier == "Europe/London"
    assert delimiter == "/t"
    assert datetime_format == "%Y-%m-%d %H:%M:%S"
    assert unit_from_entity is UnitFrom.TABLE
