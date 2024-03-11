from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import custom_components.import_statistics as impstat

def test_handle_dataframe_mean():
    # Create a sample dataframe with 'mean'
    df = pd.DataFrame({
        "statistic_id": ["stat1.mean", "stat1.mean"],
        "start": ["01.01.2022 00:00", "02.01.2022 00:00"],
        "unit": ["unit1", "unit1"],
        "min": [1, 2],
        "max": [10, 20],
        "mean": [5, 15],
    })

    # Define the expected output
    expected_stats = {
        "stat1.mean": (
            {
                "has_mean": True,
                "has_sum": False,
                "statistic_id": "stat1.mean",
                "name": None,
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
    stats = impstat._handle_dataframe(df, ["mean"], "UTC")

    # Check the output
    assert stats == expected_stats


def test_handle_dataframe_sum():
    # Create a sample dataframe with 'sum'
    df = pd.DataFrame({
        "statistic_id": ["stat2.sum"],
        "start": ["01.01.2022 00:00"],
        "unit": ["unit2"],
        "sum": [100],
        "state": ["state2"]
    })

    # Define the expected output
    expected_stats = {
        "stat2.sum": (
            {
                "has_mean": False,
                "has_sum": True,
                "statistic_id": "stat2.sum",
                "name": None,
                "unit_of_measurement": "unit2",
            },
            [
                {
                    "start": datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    "sum": 100,
                    "state": "state2",
                }
            ],
        ),
    }

    # Call the function
    stats = impstat._handle_dataframe(df, ["sum"], "UTC")

    # Check the output
    assert stats == expected_stats