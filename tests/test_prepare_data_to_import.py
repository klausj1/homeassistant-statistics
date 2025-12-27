"""Unit tests for prepare_data_to_import function."""

import datetime
import re
import zoneinfo

import pandas as pd
import pytest
from homeassistant.components.recorder.models import StatisticMeanType
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
from custom_components.import_statistics.prepare_data import prepare_data_to_import


def test_prepare_data_to_import_valid_file_dot() -> None:
    """
    Test prepare_data_to_import function with a valid file.

    This function calls the prepare_data_to_import function with the file path, and checks that the returned statistics match the expected result.
    """
    # Define the expected output
    expected_stats = {
        "sensor.esp32_soundroom_bathroomtempsensor": (
            {
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "statistic_id": "sensor.esp32_soundroom_bathroomtempsensor",
                "name": None,
                "source": "recorder",
                "unit_class": None,
                "unit_of_measurement": "°C",
            },
            [
                {
                    "start": pd.to_datetime("26.01.2024 00:00", format=DATETIME_DEFAULT_FORMAT).tz_localize("Europe/London"),
                    "min": 1131.3,
                    "max": 1231.5,
                    "mean": 1181,
                }
            ],
        ),
    }

    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: True,  # True is ','
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t",
        ATTR_UNIT_FROM_ENTITY: False,
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    # Call the function
    stats, unit_from_entity = prepare_data_to_import(file_path, call)

    # Check the output
    assert stats == expected_stats
    assert unit_from_entity is UnitFrom.TABLE


def test_prepare_data_to_import_valid_file_comma() -> None:
    """
    Test prepare_data_to_import function with a valid file.

    This function calls the prepare_data_to_import function with the file path, and checks that the returned statistics match the expected result.
    """
    # Define the expected output
    expected_stats = {
        "sensor.esp32_soundroom_bathroomtempsensor": (
            {
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "statistic_id": "sensor.esp32_soundroom_bathroomtempsensor",
                "name": None,
                "source": "recorder",
                "unit_class": None,
                "unit_of_measurement": "°C",
            },
            [
                {
                    "start": pd.to_datetime("26.01.2024 00:00", format=DATETIME_DEFAULT_FORMAT).tz_localize("Europe/London"),
                    "min": 1131.3,
                    "max": 1231.5,
                    "mean": 1181,
                }
            ],
        ),
    }

    file_path = "tests/testfiles/correctcolumnsdot.csv"

    data = {
        ATTR_DECIMAL: False,  # True is ','
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t",
        ATTR_UNIT_FROM_ENTITY: False,
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    # Call the function
    stats, unit_from_entity = prepare_data_to_import(file_path, call)

    # Check the output
    assert stats == expected_stats
    assert unit_from_entity is UnitFrom.TABLE


def test_prepare_data_to_import_wrong_separator() -> None:
    """
    Test prepare_data_to_import function with a valid file.

    This function calls the prepare_data_to_import function with the file path, and checks that the returned statistics match the expected result.
    """
    file_path = "tests/testfiles/correctcolumnscomma.csv"

    data = {
        ATTR_DECIMAL: False,  # True: ','
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t",
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Invalid float value: 1131,3. Check the decimal separator."),
    ):
        prepare_data_to_import(file_path, call)


def test_prepare_data_to_import_invalid_file() -> None:
    """
    Test prepare_data_to_import function with an invalid file.

    This function calls the prepare_data_to_import function with a non-existent file path and checks that a FileNotFoundError is raised.
    """
    # Define the non-existent file path
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
    """
    Test prepare_data_to_import function with invalid data in the file.

    This function creates a temporary CSV file with invalid data,
        calls the prepare_data_to_import function with the file path, and checks that a HomeAssistantError is raised.
    """
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
        # Call the function
        prepare_data_to_import(file_path, call)


def test_prepare_data_to_import_valid_file_dot_unit_from_entity() -> None:
    """
    Test prepare_data_to_import function with a valid file where unit comes from entity.

    This function calls the prepare_data_to_import function with a file that doesn't contain
    a unit column (unit_from_entity=True), and checks that the returned statistics match the expected result.
    """
    # Define the expected output
    expected_stats = {
        "sensor.esp32_soundroom_bathroomtempsensor": (
            {
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "statistic_id": "sensor.esp32_soundroom_bathroomtempsensor",
                "name": None,
                "source": "recorder",
                "unit_class": None,
                "unit_of_measurement": "",
            },
            [
                {
                    "start": datetime.datetime.strptime("26.01.2024 00:00", DATETIME_DEFAULT_FORMAT).replace(tzinfo=zoneinfo.ZoneInfo("Europe/London")),
                    "min": 1131.3,
                    "max": 1231.5,
                    "mean": 1181,
                }
            ],
        ),
    }

    # Use a file without unit column since unit comes from entity
    file_path = "tests/testfiles/correctcolumns_no_unit.csv"

    data = {
        ATTR_DECIMAL: True,  # True is ','
        ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
        ATTR_DELIMITER: "\t",
        ATTR_UNIT_FROM_ENTITY: True,
    }

    call = ServiceCall("domain_name", "service_name", data, data)

    # Call the function
    stats, unit_from_entity = prepare_data_to_import(file_path, call)

    # Check the output
    assert stats == expected_stats
    assert unit_from_entity is UnitFrom.ENTITY


def test_prepare_data_to_import_with_unknown_columns() -> None:
    """
    Test prepare_data_to_import function with unknown column headers.

    This test verifies that the function rejects files with unknown columns
    and returns an error to the user.
    """
    # Create a DataFrame with valid columns plus unknown columns
    my_df = pd.DataFrame(
        [
            ["sensor.temperature", "26.01.2024 00:00", "°C", 20.1, 25.5, 22.8, "extra_data_1", "notes"],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean", "unknown_field", "comments"],
    )

    # Save to a temporary CSV file
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, "test_unknown_columns.csv")
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
    """
    Test prepare_data_to_import function with unit_from_entity=True and a unit column.

    This test verifies that the function rejects files that contain a unit column
    when unit_from_entity is True, since unit should come from the entity in that case.
    """
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
        match=re.escape("Unknown columns in file: unit."),
    ):
        prepare_data_to_import(file_path, call)
