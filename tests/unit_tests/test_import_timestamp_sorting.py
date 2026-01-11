"""
Unit tests for import timestamp sorting with problematic formats.

These tests verify that import correctly handles timestamp ordering when
datetime formats could cause string-based sorting to fail.
"""

import pandas as pd

from custom_components.import_statistics.helpers import UnitFrom
from custom_components.import_statistics.import_service_helper import handle_dataframe_no_delta


class TestImportNonDeltaTimestampOrdering:
    """Test that non-delta imports correctly identify newest timestamp chronologically."""

    def test_handle_dataframe_no_delta_finds_newest_chronologically(self) -> None:
        """
        Test that newest timestamp validation uses chronological order, not alphabetical.

        With format "%d.%m.%Y %H:%M", string max would give wrong result:
        - max("01.01.2024 10:00", "31.12.2023 09:00") = "31.12.2023 09:00" (WRONG)
        - Chronologically newest should be 2024-01-01
        """
        # Create a DataFrame where string max would pick the wrong timestamp
        df = pd.DataFrame(
            [
                {
                    "statistic_id": "sensor.test",
                    "unit": "°C",
                    "start": "31.12.2023 09:00",  # Older chronologically, but larger alphabetically
                    "mean": 10.0,
                    "min": 9.0,
                    "max": 11.0,
                },
                {
                    "statistic_id": "sensor.test",
                    "unit": "°C",
                    "start": "01.01.2024 10:00",  # Newer chronologically, but smaller alphabetically
                    "mean": 20.0,
                    "min": 19.0,
                    "max": 21.0,
                },
            ]
        )

        # This should work correctly - it should identify 01.01.2024 as newest
        result = handle_dataframe_no_delta(df, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE)

        # Should have processed both records
        assert "sensor.test" in result
        _metadata, statistics = result["sensor.test"]
        assert len(statistics) == 2

    def test_handle_dataframe_no_delta_with_multiple_statistics(self) -> None:
        """Test that each statistic's newest timestamp is found correctly."""
        df = pd.DataFrame(
            [
                # sensor.a: newest is 15.01.2024 (not 05.01.2024 despite being larger alphabetically)
                {
                    "statistic_id": "sensor.a",
                    "unit": "°C",
                    "start": "05.01.2024 10:00",
                    "mean": 50.0,
                    "min": 49.0,
                    "max": 51.0,
                },
                {
                    "statistic_id": "sensor.a",
                    "unit": "°C",
                    "start": "15.01.2024 11:00",
                    "mean": 100.0,
                    "min": 99.0,
                    "max": 101.0,
                },
                # sensor.b: newest is 20.01.2024
                {
                    "statistic_id": "sensor.b",
                    "unit": "°C",
                    "start": "10.01.2024 12:00",
                    "mean": 150.0,
                    "min": 149.0,
                    "max": 151.0,
                },
                {
                    "statistic_id": "sensor.b",
                    "unit": "°C",
                    "start": "20.01.2024 13:00",
                    "mean": 200.0,
                    "min": 199.0,
                    "max": 201.0,
                },
            ]
        )

        # Should process all records correctly
        result = handle_dataframe_no_delta(df, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE)

        assert "sensor.a" in result
        assert "sensor.b" in result

        _, stats_a = result["sensor.a"]
        _, stats_b = result["sensor.b"]

        assert len(stats_a) == 2
        assert len(stats_b) == 2


class TestImportTimestampEdgeCases:
    """Test edge cases for timestamp handling in imports."""

    def test_year_boundary_timestamps(self) -> None:
        """Test timestamps around year boundary where string sorting would fail."""
        df = pd.DataFrame(
            [
                {
                    "statistic_id": "sensor.test",
                    "unit": "kWh",
                    "start": "31.12.2023 23:00",  # Last hour of 2023
                    "sum": 100.0,
                },
                {
                    "statistic_id": "sensor.test",
                    "unit": "kWh",
                    "start": "01.01.2024 00:00",  # First hour of 2024
                    "sum": 150.0,
                },
            ]
        )

        result = handle_dataframe_no_delta(df, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE)

        assert "sensor.test" in result
        _, statistics = result["sensor.test"]
        assert len(statistics) == 2

        # Verify both timestamps were processed
        start_times = [stat["start"] for stat in statistics]
        assert len(start_times) == 2

    def test_month_boundary_timestamps(self) -> None:
        """Test timestamps around month boundary."""
        df = pd.DataFrame(
            [
                {
                    "statistic_id": "sensor.test",
                    "unit": "°C",
                    "start": "28.02.2024 23:00",  # End of February
                    "mean": 10.0,
                    "min": 9.0,
                    "max": 11.0,
                },
                {
                    "statistic_id": "sensor.test",
                    "unit": "°C",
                    "start": "01.03.2024 00:00",  # Start of March
                    "mean": 20.0,
                    "min": 19.0,
                    "max": 21.0,
                },
            ]
        )

        result = handle_dataframe_no_delta(df, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE)

        assert "sensor.test" in result
        _, statistics = result["sensor.test"]
        assert len(statistics) == 2

    def test_day_ordering_within_month(self) -> None:
        """Test that days are ordered correctly (01, 02, ..., 30, 31) not alphabetically."""
        df = pd.DataFrame(
            [
                {
                    "statistic_id": "sensor.test",
                    "unit": "°C",
                    "start": "09.01.2024 10:00",  # Would come after "10." alphabetically
                    "mean": 90.0,
                    "min": 89.0,
                    "max": 91.0,
                },
                {
                    "statistic_id": "sensor.test",
                    "unit": "°C",
                    "start": "10.01.2024 10:00",
                    "mean": 100.0,
                    "min": 99.0,
                    "max": 101.0,
                },
                {
                    "statistic_id": "sensor.test",
                    "unit": "°C",
                    "start": "31.01.2024 10:00",  # Largest day number
                    "mean": 310.0,
                    "min": 309.0,
                    "max": 311.0,
                },
            ]
        )

        result = handle_dataframe_no_delta(df, "UTC", "%d.%m.%Y %H:%M", UnitFrom.TABLE)

        assert "sensor.test" in result
        _, statistics = result["sensor.test"]
        assert len(statistics) == 3


class TestAlternativeDateFormats:
    """Test various datetime formats that could cause sorting issues."""

    def test_mm_dd_yyyy_format(self) -> None:
        """Test American format MM/DD/YYYY where string sorting would fail."""
        df = pd.DataFrame(
            [
                {
                    "statistic_id": "sensor.test",
                    "unit": "°C",
                    "start": "12/31/2023 09:00",  # December 31, 2023
                    "mean": 10.0,
                    "min": 9.0,
                    "max": 11.0,
                },
                {
                    "statistic_id": "sensor.test",
                    "unit": "°C",
                    "start": "01/01/2024 10:00",  # January 1, 2024 (newer but "01" < "12")
                    "mean": 20.0,
                    "min": 19.0,
                    "max": 21.0,
                },
            ]
        )

        result = handle_dataframe_no_delta(df, "UTC", "%m/%d/%Y %H:%M", UnitFrom.TABLE)

        assert "sensor.test" in result
        _, statistics = result["sensor.test"]
        assert len(statistics) == 2

    def test_dd_mon_yyyy_format(self) -> None:
        """Test format with abbreviated month names (e.g., "31-Dec-2023")."""
        df = pd.DataFrame(
            [
                {
                    "statistic_id": "sensor.test",
                    "unit": "°C",
                    "start": "31-Dec-2023 09:00",
                    "mean": 10.0,
                    "min": 9.0,
                    "max": 11.0,
                },
                {
                    "statistic_id": "sensor.test",
                    "unit": "°C",
                    "start": "01-Jan-2024 10:00",
                    "mean": 20.0,
                    "min": 19.0,
                    "max": 21.0,
                },
            ]
        )

        result = handle_dataframe_no_delta(df, "UTC", "%d-%b-%Y %H:%M", UnitFrom.TABLE)

        assert "sensor.test" in result
        _, statistics = result["sensor.test"]
        assert len(statistics) == 2
