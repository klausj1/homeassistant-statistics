"""Unit tests for _prepare_data_to_import function."""

import pandas as pd
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError
from custom_components.import_statistics import _prepare_data_to_import
from custom_components.import_statistics.const import ATTR_DECIMAL, ATTR_TIMEZONE_IDENTIFIER, ATTR_DELIMITER

def test_prepare_data_to_import_valid_file():
    """
    Test _prepare_data_to_import function with a valid file.

    This function calls the _prepare_data_to_import function with the file path, and checks that the returned statistics match the expected result.
    """

    # Define the expected output
    expected_stats = {
        "sensor.esp32_soundroom_bathroomtempsensor": (
            {
                "has_mean": True,
                "has_sum": False,
                "statistic_id": "sensor.esp32_soundroom_bathroomtempsensor",
                "name": None,
                "source": "recorder",
                "unit_of_measurement": "°C",
            },
            [
                {
                    "start": pd.to_datetime("26.01.2024 00:00", format="%d.%m.%Y %H:%M").tz_localize("Europe/London"),
                    "min": 131.3,
                    "max": 231,
                    "mean": 181,
                }
            ],
        ),
    }

    file_path = "tests/testfiles/correctcolumns.csv"

    data = {
        ATTR_DECIMAL: False,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t"
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    # Call the function
    stats = _prepare_data_to_import(file_path, call)

    # Check the output
    assert stats == expected_stats

    # data = {
    #     ATTR_DECIMAL: False,
    #     ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
    #     ATTR_DELIMITER: "\t"
    # }

    # call = ServiceCall("domain_name", "service_name", data, False)

    # try:
    #     # Call the function
    #     _ = _prepare_data_to_import(file_path, call)
    # except HomeAssistantError as e:
    #     assert str(e) == "Invalid float value: 131.3. Check the decimal separator."
    # else:
    #     # If no exception is raised, fail the test
    #     assert False, "Expected HomeAssistantError to be raised"


def test_prepare_data_to_import_invalid_file():
    """
    Test _prepare_data_to_import function with an invalid file.

    This function calls the _prepare_data_to_import function with a non-existent file path and checks that a FileNotFoundError is raised.
    """
    # Define the non-existent file path
    file_path = "nonexistent.csv"

    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t"
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    try:
        # Call the function
        _ = _prepare_data_to_import(file_path, call)
    except HomeAssistantError as e:
        assert str(e) == f"path {file_path} does not exist."
    else:
        # If no exception is raised, fail the test
        assert False, "Expected HomeAssistantError to be raised"

def test_prepare_data_to_import_invalid_data():
    """
    Test _prepare_data_to_import function with invalid data in the file.

    This function creates a temporary CSV file with invalid data, calls the _prepare_data_to_import function with the file path, and checks that a HomeAssistantError is raised.
    """

    file_path = "tests/testfiles/wrongcolumns.csv"

    data = {
        ATTR_DECIMAL: True,
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t"
    }

    call = ServiceCall("domain_name", "service_name", data, False)

    try:
        # Call the function
        _ = _prepare_data_to_import(file_path, call)
    except HomeAssistantError as e:
        assert str(e) == "The file must contain the columns 'statistic_id', 'start' and 'unit' (check delimiter)"
    else:
        # If no exception is raised, fail the test
        assert False, "Expected HomeAssistantError to be raised"