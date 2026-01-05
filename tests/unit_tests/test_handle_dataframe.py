"""Unit tests for _handle_dataframe function."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.const import DATETIME_DEFAULT_FORMAT
from custom_components.import_statistics.helpers import UnitFrom
from custom_components.import_statistics.import_service_helper import handle_dataframe_no_delta


def test_handle_dataframe_mean() -> None:
    """
    Test the _handle_dataframe function with a DataFrame that contains 'mean' values.

    This function creates a DataFrame with two rows of data, each representing a different date with 'mean', 'min', and 'max' values.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'mean'
    my_df = pd.DataFrame(
        [
            ["stat1.mean", "01.01.2022 00:00", "unit1", 1, 10, 5],
            ["stat1.mean", "02.01.2022 00:00", "unit1", 2, 20, 15],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean"],
    )

    # Define the expected output
    expected_stats = {
        "stat1.mean": (
            {
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "statistic_id": "stat1.mean",
                "name": None,
                "source": "recorder",
                "unit_class": None,
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
    stats = handle_dataframe_no_delta(my_df, "UTC", DATETIME_DEFAULT_FORMAT, UnitFrom.TABLE)

    # Check the output
    assert stats == expected_stats


def test_handle_dataframe_mean_other_datetime_format() -> None:
    """
    Test the _handle_dataframe function with a DataFrame that contains 'mean' values with another datetime format.

    This function creates a DataFrame with two rows of data, each representing a different date with 'mean', 'min', and 'max' values.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'mean'
    my_df = pd.DataFrame(
        [
            ["stat1.mean", "01-01-2022 00:00", "unit1", 1, 10, 5],
            ["stat1.mean", "02-01-2022 00:00", "unit1", 2, 20, 15],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean"],
    )

    datetime_format = "%d-%m-%Y %H:%M"

    # Define the expected output
    expected_stats = {
        "stat1.mean": (
            {
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "statistic_id": "stat1.mean",
                "name": None,
                "source": "recorder",
                "unit_class": None,
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
    stats = handle_dataframe_no_delta(my_df, "UTC", datetime_format, UnitFrom.TABLE)

    # Check the output
    assert stats == expected_stats


def test_handle_dataframe_sum_state() -> None:
    """
    Test the _handle_dataframe function with a DataFrame that contains 'sum' values.

    This function creates a DataFrame with one row of data, representing a date with a 'sum' value and a 'state'.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'sum'
    my_df = pd.DataFrame(
        [["stat2.sum", "01.01.2022 00:00", "unit2", 100, 200]],
        columns=["statistic_id", "start", "unit", "sum", "state"],
    )

    # Define the expected output
    expected_stats = {
        "stat2.sum": (
            {
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
                "statistic_id": "stat2.sum",
                "name": None,
                "source": "recorder",
                "unit_class": None,
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
    stats = handle_dataframe_no_delta(my_df, "UTC", DATETIME_DEFAULT_FORMAT, UnitFrom.TABLE)

    # Check the output
    assert stats == expected_stats


def test_handle_dataframe_sum_state_other_format() -> None:
    """
    Test the _handle_dataframe function with a DataFrame that contains 'sum' values.

    This function creates a DataFrame with one row of data, representing a date with a 'sum' value and a 'state'.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'sum'
    my_df = pd.DataFrame(
        [["stat2.sum", "01-01-2022 00:00", "unit2", 100, 200]],
        columns=["statistic_id", "start", "unit", "sum", "state"],
    )

    datetime_format = "%d-%m-%Y %H:%M"

    # Define the expected output
    expected_stats = {
        "stat2.sum": (
            {
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
                "statistic_id": "stat2.sum",
                "name": None,
                "source": "recorder",
                "unit_class": None,
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
    stats = handle_dataframe_no_delta(my_df, "UTC", datetime_format, UnitFrom.TABLE)

    # Check the output
    assert stats == expected_stats


def test_handle_dataframe_sum() -> None:
    """
    Test the _handle_dataframe function with a DataFrame that contains 'sum' values.

    This function creates a DataFrame with one row of data, representing a date with a 'sum' value and a 'state'.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'sum'
    my_df = pd.DataFrame(
        [["stat2.sum", "01.01.2022 00:00", "unit2", 100]],
        columns=["statistic_id", "start", "unit", "sum"],
    )

    # Define the expected output
    expected_stats = {
        "stat2.sum": (
            {
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
                "statistic_id": "stat2.sum",
                "name": None,
                "source": "recorder",
                "unit_class": None,
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
    stats = handle_dataframe_no_delta(my_df, "UTC", DATETIME_DEFAULT_FORMAT, UnitFrom.TABLE)

    # Check the output
    assert stats == expected_stats


def test_handle_dataframe_multiple_mean() -> None:
    """
    Test the _handle_dataframe function with a DataFrame that contains 'mean' values.

    This function creates a DataFrame with two rows of data, each representing a different date with 'mean', 'min', and 'max' values.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'mean'
    my_df = pd.DataFrame(
        [
            ["stat1.temp", "01.01.2022 00:00", "C", 1, 10, 5],
            ["stat1.temp", "02.01.2022 00:00", "C", 2, 20, 15],
            ["stat2.temp", "01.01.2022 00:00", "C", 3, 30, 25],
            ["stat2.temp", "01.01.2022 01:00", "C", 4, 40, 35],
            ["stat1.value", "01.01.2022 00:00", "m", 5, 50, 45],
            ["stat1.value", "01.01.2022 01:00", "m", 6, 60, 55],
            ["stat1.value", "01.01.2022 02:00", "mm", 7, 70, 65],
            ["stat1.temp", "03.01.2022 00:00", "nnn", 8, 80, 75],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean"],
    )

    # Define the expected output
    expected_stats = {
        "stat1.temp": (
            {
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "statistic_id": "stat1.temp",
                "name": None,
                "source": "recorder",
                "unit_class": None,
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
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "statistic_id": "stat2.temp",
                "name": None,
                "source": "recorder",
                "unit_class": None,
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
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "statistic_id": "stat1.value",
                "name": None,
                "source": "recorder",
                "unit_class": None,
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
    stats = handle_dataframe_no_delta(my_df, "Europe/Berlin", DATETIME_DEFAULT_FORMAT, UnitFrom.TABLE)

    # Check the output
    assert stats == expected_stats


def test_handle_dataframe_mean_sum() -> None:
    """
    Test the _handle_dataframe function with a DataFrame that contains 'mean' and 'sum' values.

    This function creates a DataFrame with two rows of data, each representing a different date with 'mean', 'min', and 'max' values.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'mean'
    my_df = pd.DataFrame(
        [
            ["stat1.mean", "01.01.2022 00:00", "unit1", 1, 10, 5],
            ["stat1.mean", "02.01.2022 00:00", "unit1", 2, 20, 15],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "sum"],
    )

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("The file must not contain the columns 'sum/state' together with 'mean'/'min'/'max' (check delimiter)"),
    ):
        _stats = handle_dataframe_no_delta(my_df, "UTC", DATETIME_DEFAULT_FORMAT, UnitFrom.TABLE)


def test_handle_dataframe_mean_unit_from_entity() -> None:
    """
    Test the _handle_dataframe function with a DataFrame that contains 'mean' values.

    This function creates a DataFrame with two rows of data, each representing a different date with 'mean', 'min', and 'max' values.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'mean' without unit column (unit comes from entity)
    my_df = pd.DataFrame(
        [
            ["stat1.mean", "01.01.2022 00:00", 1, 10, 5],
            ["stat1.mean", "02.01.2022 00:00", 2, 20, 15],
        ],
        columns=["statistic_id", "start", "min", "max", "mean"],
    )

    # Define the expected output
    expected_stats = {
        "stat1.mean": (
            {
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "statistic_id": "stat1.mean",
                "name": None,
                "source": "recorder",
                "unit_class": None,
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
    stats = handle_dataframe_no_delta(my_df, "UTC", DATETIME_DEFAULT_FORMAT, UnitFrom.ENTITY)

    # Check the output
    assert stats == expected_stats
