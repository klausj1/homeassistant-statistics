"""Unit tests for _handle_dataframe function."""

from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import custom_components.import_statistics as impstat

def test_handle_dataframe_mean():
    """
    Test the _handle_dataframe function with a DataFrame that contains 'mean' values.

    This function creates a DataFrame with two rows of data, each representing a different date with 'mean', 'min', and 'max' values.
    It then defines the expected output, calls the _handle_dataframe function with the DataFrame and checks that the output matches the expected result.
    """
    # Create a sample dataframe with 'mean'
    df = pd.DataFrame([
        ["stat1.mean", "01.01.2022 00:00", "unit1", 1, 10, 5],
        ["stat1.mean", "02.01.2022 00:00", "unit1", 2, 20, 15]
    ], columns=["statistic_id", "start", "unit", "min", "max", "mean"])

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
    stats = impstat._handle_dataframe(df, "UTC") # pylint: disable=protected-access

    # Check the output
    assert stats == expected_stats


def test_handle_dataframe_sum():
    """
    Test the _handle_dataframe function with a DataFrame that contains 'sum' values.

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
    stats = impstat._handle_dataframe(df, "UTC") # pylint: disable=protected-access

    # Check the output
    assert stats == expected_stats
