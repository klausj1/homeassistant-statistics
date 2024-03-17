"""Unit tests for _handle_arguments function."""

from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import _handle_arguments
from custom_components.import_statistics.const import ATTR_DECIMAL, ATTR_TIMEZONE_IDENTIFIER, ATTR_DELIMITER

def test_handle_arguments_all_valid():
    """Test the _handle_arguments function with a valid timezone identifier and a valid file path."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: ","
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    decimal, timezone_identifier, delimiter = _handle_arguments(file_path, call)

    assert decimal == ","
    assert timezone_identifier == "Europe/London"
    assert delimiter == ","

def test_handle_arguments_all_valid_other_parameters():
    """Test the _handle_arguments function with a valid timezone identifier and a valid file path, with some changed parameters."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: False,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "/t"
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    decimal, timezone_identifier, delimiter = _handle_arguments(file_path, call)

    assert decimal == "."
    assert timezone_identifier == "Europe/London"
    assert delimiter == "/t"

def test_handle_arguments_invalid_timezone():
    """Test the _handle_arguments function with an invalid timezone identifier."""
    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Invalid/Timezone",
        ATTR_DELIMITER: ","
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    try:
        _handle_arguments(file_path, call)
        assert False, "Expected an exception to be raised for invalid timezone identifier"
    except HomeAssistantError as e:
        assert str(e) == "Invalid timezone_identifier: Invalid/Timezone"


def test_handle_arguments_file_not_found():
    """Test the _handle_arguments function with a file that does not exist."""
    file_path = "/path/to/nonexistent_file.csv"
    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: ","
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    try:
        _handle_arguments(file_path, call)
        assert False, "Expected an exception to be raised for non-existent file"
    except HomeAssistantError as e:
        assert str(e) == f"path {file_path} does not exist."
