"""Test that handle_dataframe_no_delta works with different column orders."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from custom_components.import_statistics.import_service_helper import handle_dataframe_no_delta


def test_handle_dataframe_different_column_order_mean() -> None:
    """Test that column order doesn't affect results for mean statistics."""
    # Standard order
    df_standard = pd.DataFrame(
        [
            ["sensor.test", "2022-01-01 00:00", "°C", 1.0, 10.0, 5.0],
            ["sensor.test", "2022-01-01 01:00", "°C", 2.0, 20.0, 15.0],
        ],
        columns=["statistic_id", "start", "unit", "min", "max", "mean"],
    )
    df_standard["start"] = pd.to_datetime(df_standard["start"]).dt.tz_localize(ZoneInfo("UTC"))

    # Different order
    df_reordered = pd.DataFrame(
        [
            [5.0, "sensor.test", 1.0, "2022-01-01 00:00", 10.0, "°C"],
            [15.0, "sensor.test", 2.0, "2022-01-01 01:00", 20.0, "°C"],
        ],
        columns=["mean", "statistic_id", "min", "start", "max", "unit"],
    )
    df_reordered["start"] = pd.to_datetime(df_reordered["start"]).dt.tz_localize(ZoneInfo("UTC"))

    # Process both
    result_standard = handle_dataframe_no_delta(df_standard)
    result_reordered = handle_dataframe_no_delta(df_reordered)

    # Verify both produce same results
    assert len(result_standard) == len(result_reordered) == 1
    assert "sensor.test" in result_standard
    assert "sensor.test" in result_reordered

    metadata_std, stats_std = result_standard["sensor.test"]
    metadata_reord, stats_reord = result_reordered["sensor.test"]

    # Metadata should be identical
    assert metadata_std == metadata_reord

    # Statistics should be identical
    assert len(stats_std) == len(stats_reord) == 2
    for i in range(2):
        assert stats_std[i]["start"] == stats_reord[i]["start"]
        assert stats_std[i]["min"] == stats_reord[i]["min"]
        assert stats_std[i]["max"] == stats_reord[i]["max"]
        assert stats_std[i]["mean"] == stats_reord[i]["mean"]


def test_handle_dataframe_different_column_order_sum() -> None:
    """Test that column order doesn't affect results for sum statistics."""
    # Standard order
    df_standard = pd.DataFrame(
        [
            ["counter.energy", "2022-01-01 00:00", "kWh", 100.0, 100.0],
            ["counter.energy", "2022-01-01 01:00", "kWh", 105.0, 105.0],
        ],
        columns=["statistic_id", "start", "unit", "sum", "state"],
    )
    df_standard["start"] = pd.to_datetime(df_standard["start"]).dt.tz_localize(ZoneInfo("UTC"))

    # Different order
    df_reordered = pd.DataFrame(
        [
            [100.0, "kWh", "counter.energy", 100.0, "2022-01-01 00:00"],
            [105.0, "kWh", "counter.energy", 105.0, "2022-01-01 01:00"],
        ],
        columns=["state", "unit", "statistic_id", "sum", "start"],
    )
    df_reordered["start"] = pd.to_datetime(df_reordered["start"]).dt.tz_localize(ZoneInfo("UTC"))

    # Process both
    result_standard = handle_dataframe_no_delta(df_standard)
    result_reordered = handle_dataframe_no_delta(df_reordered)

    # Verify both produce same results
    assert len(result_standard) == len(result_reordered) == 1
    assert "counter.energy" in result_standard
    assert "counter.energy" in result_reordered

    metadata_std, stats_std = result_standard["counter.energy"]
    metadata_reord, stats_reord = result_reordered["counter.energy"]

    # Metadata should be identical
    assert metadata_std == metadata_reord

    # Statistics should be identical
    assert len(stats_std) == len(stats_reord) == 2
    for i in range(2):
        assert stats_std[i]["start"] == stats_reord[i]["start"]
        assert stats_std[i]["sum"] == stats_reord[i]["sum"]
        assert stats_std[i]["state"] == stats_reord[i]["state"]


def test_handle_dataframe_all_permutations_mean() -> None:
    """Test with multiple column permutations for mean statistics."""
    base_data = {
        "statistic_id": "sensor.test",
        "start": datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
        "unit": "°C",
        "min": 1.0,
        "max": 10.0,
        "mean": 5.0,
    }

    # Test several different column orders
    column_orders = [
        ["statistic_id", "start", "unit", "min", "max", "mean"],
        ["mean", "max", "min", "unit", "start", "statistic_id"],
        ["unit", "statistic_id", "mean", "start", "min", "max"],
        ["start", "mean", "statistic_id", "max", "unit", "min"],
    ]

    results = []
    for columns in column_orders:
        # Create DataFrame with specific column order
        data = [[base_data[col] for col in columns]]
        df = pd.DataFrame(data, columns=columns)
        result = handle_dataframe_no_delta(df)
        results.append(result)

    # All results should be identical
    for i in range(1, len(results)):
        metadata_0, stats_0 = results[0]["sensor.test"]
        metadata_i, stats_i = results[i]["sensor.test"]

        assert metadata_0 == metadata_i
        assert len(stats_0) == len(stats_i) == 1
        assert stats_0[0] == stats_i[0]
