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
from custom_components.import_statistics.import_service_helper import handle_arguments


def test_handle_arguments_all_valid() -> None:
    """Test the handle_arguments function with a valid timezone identifier and a valid file path, no optional parameters."""
    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: ",",
    }

    call = ServiceCall("hass", "domain_name", "service_name", data)

    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(call)

    assert decimal == ","
    assert timezone_identifier == "Europe/London"
    assert delimiter == ","
    assert datetime_format == DATETIME_DEFAULT_FORMAT
    assert unit_from_entity is UnitFrom.TABLE


def test_handle_arguments_all_valid_other_parameters() -> None:
    """Test the handle_arguments function with a valid timezone identifier and a valid file path, with some changed parameters."""
    data = {
        ATTR_DECIMAL: False,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: ";",
        ATTR_DATETIME_FORMAT: "%Y-%m-%d %H:%M:%S",
        ATTR_UNIT_FROM_ENTITY: True,
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(call)

    assert decimal == "."
    assert timezone_identifier == "Europe/London"
    assert delimiter == ";"
    assert datetime_format == "%Y-%m-%d %H:%M:%S"
    assert unit_from_entity is UnitFrom.ENTITY


def test_handle_arguments_invalid_timezone() -> None:
    """Test the handle_arguments function with an invalid timezone identifier."""
    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Invalid/Timezone",
        ATTR_DELIMITER: ",",
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Invalid timezone_identifier: Invalid/Timezone"),
    ):
        handle_arguments(call)


def test_handle_arguments_file_not_found() -> None:
    """Test the handle_arguments function with a file that does not exist."""
    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: ",",
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    # This test should not raise an error for file existence
    # File existence checking is done in prepare_data_to_import, not handle_arguments
    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(call)

    assert decimal == ","
    assert timezone_identifier == "Europe/London"
    assert delimiter == ","
    assert datetime_format == DATETIME_DEFAULT_FORMAT
    assert unit_from_entity is UnitFrom.TABLE


def test_handle_arguments_attr_from_entity_false() -> None:
    """Test the handle_arguments function with a valid timezone identifier and a valid file path, with some changed parameters."""
    data = {
        ATTR_DECIMAL: False,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: ";",
        ATTR_DATETIME_FORMAT: "%Y-%m-%d %H:%M:%S",
        ATTR_UNIT_FROM_ENTITY: False,
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(call)

    assert decimal == "."
    assert timezone_identifier == "Europe/London"
    assert delimiter == ";"
    assert datetime_format == "%Y-%m-%d %H:%M:%S"
    assert unit_from_entity is UnitFrom.TABLE


def test_handle_arguments_delimiter_tab_literal() -> None:
    r"""Test the handle_arguments function with literal \t delimiter."""
    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\\t",
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(call)

    assert decimal == ","
    assert timezone_identifier == "Europe/London"
    assert delimiter == "\t"  # Should be converted to actual tab character
    assert datetime_format == DATETIME_DEFAULT_FORMAT
    assert unit_from_entity is UnitFrom.TABLE


def test_handle_arguments_delimiter_invalid_two_chars() -> None:
    """Test the handle_arguments function with invalid 2-character delimiter."""
    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "ab",
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Delimiter must be exactly 1 character or \\t, got: 'ab'"),
    ):
        handle_arguments(call)


def test_handle_arguments_delimiter_invalid_empty() -> None:
    """Test the handle_arguments function with empty delimiter."""
    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "",
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Delimiter must be exactly 1 character or \\t, got: ''"),
    ):
        handle_arguments(call)


def test_handle_arguments_delimiter_none_default() -> None:
    """Test the handle_arguments function with None delimiter defaults to tab."""
    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(call)

    assert decimal == ","
    assert timezone_identifier == "Europe/London"
    assert delimiter == "\t"  # Should default to tab
    assert datetime_format == DATETIME_DEFAULT_FORMAT
    assert unit_from_entity is UnitFrom.TABLE
