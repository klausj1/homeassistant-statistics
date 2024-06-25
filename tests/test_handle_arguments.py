"""Unit tests for handle_arguments function."""

from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.prepare_data import handle_arguments
from custom_components.import_statistics.const import ATTR_DECIMAL, ATTR_TIMEZONE_IDENTIFIER, ATTR_DELIMITER, ATTR_DATETIME_FORMAT, DATETIME_DEFAULT_FORMAT, ATTR_UNIT_FROM_ENTITY

def test_handle_arguments_all_valid():
    """Test the handle_arguments function with a valid timezone identifier and a valid file path, no optional parameters."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: ",",
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(file_path, call)

    assert decimal == ","
    assert timezone_identifier == "Europe/London"
    assert delimiter == ","
    assert datetime_format == DATETIME_DEFAULT_FORMAT
    assert unit_from_entity is True

def test_handle_arguments_all_valid_other_parameters():
    """Test the handle_arguments function with a valid timezone identifier and a valid file path, with some changed parameters."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: False,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "/t",
        ATTR_DATETIME_FORMAT: "%Y-%m-%d %H:%M:%S",
        ATTR_UNIT_FROM_ENTITY: True
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(file_path, call)

    assert decimal == "."
    assert timezone_identifier == "Europe/London"
    assert delimiter == "/t"
    assert datetime_format == "%Y-%m-%d %H:%M:%S"
    assert unit_from_entity is True

def test_handle_arguments_invalid_timezone():
    """Test the handle_arguments function with an invalid timezone identifier."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Invalid/Timezone",
        ATTR_DELIMITER: ","
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    try:
        handle_arguments(file_path, call)
        assert False, "Expected an exception to be raised for invalid timezone identifier"
    except HomeAssistantError as e:
        assert str(e) == "Invalid timezone_identifier: Invalid/Timezone"


def test_handle_arguments_file_not_found():
    """Test the handle_arguments function with a file that does not exist."""
    file_path = "/path/to/nonexistent_file.csv"
    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: ","
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    try:
        handle_arguments(file_path, call)
        assert False, "Expected an exception to be raised for non-existent file"
    except HomeAssistantError as e:
        assert str(e) == f"path {file_path} does not exist."

def test_handle_arguments_attr_from_entity_false():
    """Test the handle_arguments function with a valid timezone identifier and a valid file path, with some changed parameters."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: False,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "/t",
        ATTR_DATETIME_FORMAT: "%Y-%m-%d %H:%M:%S",
        ATTR_UNIT_FROM_ENTITY: False
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(file_path, call)

    assert decimal == "."
    assert timezone_identifier == "Europe/London"
    assert delimiter == "/t"
    assert datetime_format == "%Y-%m-%d %H:%M:%S"
    assert unit_from_entity is False
