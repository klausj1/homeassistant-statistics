"""Unit tests for _handle_dataframe function."""

from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from homeassistant.exceptions import HomeAssistantError
import custom_components.import_statistics.prepare_data as prepare_data
from custom_components.import_statistics.const import DATETIME_DEFAULT_FORMAT

def test_handle_dataframe_mean():
    """Test the _handle_dataframe function with a DataFrame that contains 'mean' values.

    This function creates a DataFrame with two rows of data, each representing a different date with 'mean', 'min', and 'max' values.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'mean'
    df = pd.DataFrame([
                ["stat1.mean", "01.01.2022 00:00", "unit1", 1, 10, 5],
                ["stat1.mean", "02.01.2022 00:00", "unit1", 2, 20, 15]
    ], columns= ["statistic_id", "start", "unit", "min", "max", "mean"])

    # Define the expected output
    expected_stats = {
        "stat1.mean": (
            {
                "has_mean": True,
                "has_sum": False,
                "statistic_id": "stat1.mean",
                "name": None,
                "source": "recorder",
                "unit_of_measurement": "unit1",
            },
            [
                {
                    "start": datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    "min": 1,
                    "max": 10,
                    "mean": 5,
                },
                {
                    "start": datetime(2022, 1, 2, 0, 0, tzinfo=ZoneInfo("UTC")),
                    "min": 2,
                    "max": 20,
                    "mean": 15,
                },
            ],
        ),
    }

    # Call the function
    stats = prepare_data.handle_dataframe(df, "UTC", DATETIME_DEFAULT_FORMAT, False)

    # Check the output
    assert stats == expected_stats

def test_handle_dataframe_mean_other_datetime_format():
    """Test the _handle_dataframe function with a DataFrame that contains 'mean' values with another datetime format.

    This function creates a DataFrame with two rows of data, each representing a different date with 'mean', 'min', and 'max' values.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'mean'
    df = pd.DataFrame([
                ["stat1.mean", "01-01-2022 00:00", "unit1", 1, 10, 5],
                ["stat1.mean", "02-01-2022 00:00", "unit1", 2, 20, 15]
    ], columns= ["statistic_id", "start", "unit", "min", "max", "mean"])

    datetime_format = "%d-%m-%Y %H:%M"

    # Define the expected output
    expected_stats = {
        "stat1.mean": (
            {
                "has_mean": True,
                "has_sum": False,
                "statistic_id": "stat1.mean",
                "name": None,
                "source": "recorder",
                "unit_of_measurement": "unit1",
            },
            [
                {
                    "start": datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    "min": 1,
                    "max": 10,
                    "mean": 5,
                },
                {
                    "start": datetime(2022, 1, 2, 0, 0, tzinfo=ZoneInfo("UTC")),
                    "min": 2,
                    "max": 20,
                    "mean": 15,
                },
            ],
        ),
    }

    # Call the function
    stats = prepare_data.handle_dataframe(df, "UTC", datetime_format, False)

    # Check the output
    assert stats == expected_stats

def test_handle_dataframe_sum_state():
    """Test the _handle_dataframe function with a DataFrame that contains 'sum' values.

    This function creates a DataFrame with one row of data, representing a date with a 'sum' value and a 'state'.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'sum'
    df = pd.DataFrame([
        ["stat2.sum", "01.01.2022 00:00", "unit2", 100, 200]
    ], columns=["statistic_id", "start", "unit", "sum", "state"])

    # Define the expected output
    expected_stats = {
        "stat2.sum": (
            {
                "has_mean": False,
                "has_sum": True,
                "statistic_id": "stat2.sum",
                "name": None,
                "source": "recorder",
                "unit_of_measurement": "unit2",
            },
            [
                {
                    "start": datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    "sum": 100,
                    "state": 200,
                }
            ],
        ),
    }

    # Call the function
    stats = prepare_data.handle_dataframe(df, "UTC", DATETIME_DEFAULT_FORMAT, False)

    # Check the output
    assert stats == expected_stats

def test_handle_dataframe_sum_state_other_format():
    """Test the _handle_dataframe function with a DataFrame that contains 'sum' values.

    This function creates a DataFrame with one row of data, representing a date with a 'sum' value and a 'state'.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'sum'
    df = pd.DataFrame([
        ["stat2.sum", "01-01-2022 00:00", "unit2", 100, 200]
    ], columns=["statistic_id", "start", "unit", "sum", "state"])

    datetime_format = "%d-%m-%Y %H:%M"

    # Define the expected output
    expected_stats = {
        "stat2.sum": (
            {
                "has_mean": False,
                "has_sum": True,
                "statistic_id": "stat2.sum",
                "name": None,
                "source": "recorder",
                "unit_of_measurement": "unit2",
            },
            [
                {
                    "start": datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    "sum": 100,
                    "state": 200,
                }
            ],
        ),
    }

    # Call the function
    stats = prepare_data.handle_dataframe(df, "UTC", datetime_format, False)

    # Check the output
    assert stats == expected_stats

def test_handle_dataframe_sum():
    """Test the _handle_dataframe function with a DataFrame that contains 'sum' values.

    This function creates a DataFrame with one row of data, representing a date with a 'sum' value and a 'state'.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'sum'
    df = pd.DataFrame([
        ["stat2.sum", "01.01.2022 00:00", "unit2", 100]
    ], columns=["statistic_id", "start", "unit", "sum"])

    # Define the expected output
    expected_stats = {
        "stat2.sum": (
            {
                "has_mean": False,
                "has_sum": True,
                "statistic_id": "stat2.sum",
                "name": None,
                "source": "recorder",
                "unit_of_measurement": "unit2",
            },
            [
                {
                    "start": datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    "sum": 100,
                }
            ],
        ),
    }

    # Call the function
    stats = prepare_data.handle_dataframe(df, "UTC", DATETIME_DEFAULT_FORMAT, False)

    # Check the output
    assert stats == expected_stats

def test_handle_dataframe_multiple_mean():
    """Test the _handle_dataframe function with a DataFrame that contains 'mean' values.

    This function creates a DataFrame with two rows of data, each representing a different date with 'mean', 'min', and 'max' values.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'mean'
    df = pd.DataFrame([
                ["stat1.temp", "01.01.2022 00:00", "C", 1, 10, 5],
                ["stat1.temp", "02.01.2022 00:00", "C", 2, 20, 15],
                ["stat2.temp", "01.01.2022 00:00", "C", 3, 30, 25],
                ["stat2.temp", "01.01.2022 01:00", "C", 4, 40, 35],
                ["stat1.value", "01.01.2022 00:00", "m", 5, 50, 45],
                ["stat1.value", "01.01.2022 01:00", "m", 6, 60, 55],
                ["stat1.value", "01.01.2022 02:00", "mm", 7, 70, 65],
                ["stat1.temp", "03.01.2022 00:00", "nnn", 8, 80, 75]
    ], columns= ["statistic_id", "start", "unit", "min", "max", "mean"])

    # df.loc[0, "min"] = 3
    # df.loc[0, "max"] = 30
    # df.loc[0, "mean"] = 25

    # Define the expected output
    expected_stats = {
        "stat1.temp": (
            {
                "has_mean": True,
                "has_sum": False,
                "statistic_id": "stat1.temp",
                "name": None,
                "source": "recorder",
                "unit_of_measurement": "C",
            },
            [
                {
                    "start": datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                    "min": 1,
                    "max": 10,
                    "mean": 5,
                },
                {
                    "start": datetime(2022, 1, 2, 0, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                    "min": 2,
                    "max": 20,
                    "mean": 15,
                },
                {
                    "start": datetime(2022, 1, 3, 0, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                    "min": 8,
                    "max": 80,
                    "mean": 75,
                },
            ],
        ),
        "stat2.temp": (
            {
                "has_mean": True,
                "has_sum": False,
                "statistic_id": "stat2.temp",
                "name": None,
                "source": "recorder",
                "unit_of_measurement": "C",
            },
            [
                {
                    "start": datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                    "min": 3,
                    "max": 30,
                    "mean": 25,
                },
                {
                    "start": datetime(2022, 1, 1, 1, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                    "min": 4,
                    "max": 40,
                    "mean": 35,
                },
            ],
        ),
            "stat1.value": (
            {
                "has_mean": True,
                "has_sum": False,
                "statistic_id": "stat1.value",
                "name": None,
                "source": "recorder",
                "unit_of_measurement": "m",
            },
            [
                {
                    "start": datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                    "min": 5,
                    "max": 50,
                    "mean": 45,
                },
                {
                    "start": datetime(2022, 1, 1, 1, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                    "min": 6,
                    "max": 60,
                    "mean": 55,
                },
                {
                    "start": datetime(2022, 1, 1, 2, 0, tzinfo=ZoneInfo("Europe/Berlin")),
                    "min": 7,
                    "max": 70,
                    "mean": 65,
                },
            ],
        ),
}

    # Call the function
    stats = prepare_data.handle_dataframe(df, "Europe/Berlin", DATETIME_DEFAULT_FORMAT, False)

    # Check the output
    assert stats == expected_stats

def test_handle_dataframe_mean_sum():
    """Test the _handle_dataframe function with a DataFrame that contains 'mean' and 'sum' values.

    This function creates a DataFrame with two rows of data, each representing a different date with 'mean', 'min', and 'max' values.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'mean'
    df = pd.DataFrame([
                ["stat1.mean", "01.01.2022 00:00", "unit1", 1, 10, 5],
                ["stat1.mean", "02.01.2022 00:00", "unit1", 2, 20, 15]
    ], columns= ["statistic_id", "start", "unit", "min", "max", "sum"])

    # Call the function

    try:
        # Call the function
        _stats = prepare_data.handle_dataframe(df, "UTC", DATETIME_DEFAULT_FORMAT, False)
    except HomeAssistantError as e:
        # Check that the raised exception has the same error string
        assert str(e) == "The file must not contain the columns 'sum' and 'mean'/'min'/'max' (check delimiter)"
    else:
        # If no exception is raised, fail the test
        assert False, "Expected HomeAssistantError to be raised"

def test_handle_dataframe_mean_unit_from_entity():
    """Test the _handle_dataframe function with a DataFrame that contains 'mean' values.

    This function creates a DataFrame with two rows of data, each representing a different date with 'mean', 'min', and 'max' values.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'mean'
    df = pd.DataFrame([
                ["stat1.mean", "01.01.2022 00:00", "unit1", 1, 10, 5],
                ["stat1.mean", "02.01.2022 00:00", "unit1", 2, 20, 15]
    ], columns= ["statistic_id", "start", "unit", "min", "max", "mean"])

    # Define the expected output
    expected_stats = {
        "stat1.mean": (
            {
                "has_mean": True,
                "has_sum": False,
                "statistic_id": "stat1.mean",
                "name": None,
                "source": "recorder",
                "unit_of_measurement": "",
            },
            [
                {
                    "start": datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    "min": 1,
                    "max": 10,
                    "mean": 5,
                },
                {
                    "start": datetime(2022, 1, 2, 0, 0, tzinfo=ZoneInfo("UTC")),
                    "min": 2,
                    "max": 20,
                    "mean": 15,
                },
            ],
        ),
    }

    # Call the function
    stats = prepare_data.handle_dataframe(df, "UTC", DATETIME_DEFAULT_FORMAT, True)

    # Check the output
    assert stats == expected_stats
