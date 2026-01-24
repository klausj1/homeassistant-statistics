# ruff: noqa: DTZ001, DTZ007
"""
Unit tests for timestamp sorting edge cases.

These tests verify that timestamps are sorted chronologically, not alphabetically.
This is critical because certain datetime formats (e.g., "%d.%m.%Y %H:%M") would
produce incorrect ordering if sorted as strings.
"""

import datetime

from custom_components.import_statistics.export_service_helper import (
    get_delta_from_stats,
    prepare_export_data,
    prepare_export_json,
)


class TestExportTimestampSorting:
    """Test that export correctly sorts by chronological order, not alphabetical."""

    def test_prepare_export_data_chronological_order_with_dd_mm_yyyy_format(self) -> None:
        """
        Test that timestamps are sorted chronologically when format could mislead string sort.

        With format "%d.%m.%Y %H:%M", alphabetical sorting would be wrong:
        - "01.01.2024 15:00" < "31.12.2023 14:00" (alphabetical - WRONG)
        - 2023-12-31 < 2024-01-01 (chronological - CORRECT)
        """
        # Create test data with timestamps that would sort incorrectly if compared as strings
        statistics_dict = {
            "sensor.test": [
                {
                    "start": datetime.datetime(2023, 12, 31, 14, 0, 0).timestamp(),  # Should be first chronologically
                    "mean": 10.0,
                    "min": 9.0,
                    "max": 11.0,
                },
                {
                    "start": datetime.datetime(2024, 1, 1, 15, 0, 0).timestamp(),  # Should be second chronologically
                    "mean": 20.0,
                    "min": 19.0,
                    "max": 21.0,
                },
                {
                    "start": datetime.datetime(2024, 1, 2, 16, 0, 0).timestamp(),  # Should be third chronologically
                    "mean": 30.0,
                    "min": 29.0,
                    "max": 31.0,
                },
            ]
        }

        units_dict = {"sensor.test": "°C"}

        # Use the problematic datetime format
        _columns, rows = prepare_export_data(statistics_dict, "UTC", "%d.%m.%Y %H:%M", decimal_separator=".", units_dict=units_dict)

        # Verify chronological order (should be 31.12.2023, then 01.01.2024, then 02.01.2024)
        assert len(rows) == 3
        assert rows[0][2] == "31.12.2023 14:00"  # start column for first row
        assert rows[1][2] == "01.01.2024 15:00"  # start column for second row
        assert rows[2][2] == "02.01.2024 16:00"  # start column for third row

        # Verify mean values are in correct order
        assert rows[0][5] == "10"  # mean for first row
        assert rows[1][5] == "20"  # mean for second row
        assert rows[2][5] == "30"  # mean for third row

    def test_prepare_export_data_multiple_entities_chronological_order(self) -> None:
        """Test chronological ordering within each entity when multiple entities present."""
        statistics_dict = {
            "sensor.a": [
                {"start": datetime.datetime(2024, 1, 15, 10, 0, 0).timestamp(), "mean": 100.0, "min": 99.0, "max": 101.0},
                {"start": datetime.datetime(2024, 1, 5, 10, 0, 0).timestamp(), "mean": 50.0, "min": 49.0, "max": 51.0},
            ],
            "sensor.b": [
                {"start": datetime.datetime(2024, 1, 20, 10, 0, 0).timestamp(), "mean": 200.0, "min": 199.0, "max": 201.0},
                {"start": datetime.datetime(2024, 1, 10, 10, 0, 0).timestamp(), "mean": 150.0, "min": 149.0, "max": 151.0},
            ],
        }

        units_dict = {"sensor.a": "°C", "sensor.b": "°C"}

        _columns, rows = prepare_export_data(statistics_dict, "UTC", "%d.%m.%Y %H:%M", decimal_separator=".", units_dict=units_dict)

        # Should be 4 rows total, sorted by statistic_id then chronologically
        assert len(rows) == 4

        # First two rows should be sensor.a in chronological order (05.01 then 15.01)
        assert rows[0][0] == "sensor.a"
        assert rows[0][2] == "05.01.2024 10:00"
        assert rows[0][5] == "50"  # mean

        assert rows[1][0] == "sensor.a"
        assert rows[1][2] == "15.01.2024 10:00"
        assert rows[1][5] == "100"  # mean

        # Next two rows should be sensor.b in chronological order (10.01 then 20.01)
        assert rows[2][0] == "sensor.b"
        assert rows[2][2] == "10.01.2024 10:00"
        assert rows[2][5] == "150"  # mean

        assert rows[3][0] == "sensor.b"
        assert rows[3][2] == "20.01.2024 10:00"
        assert rows[3][5] == "200"  # mean

    def test_prepare_export_json_chronological_order(self) -> None:
        """Test that JSON export maintains chronological order."""
        statistics_dict = {
            "sensor.test": [
                {"start": datetime.datetime(2024, 1, 15, 10, 0, 0).timestamp(), "mean": 100.0, "min": 99.0, "max": 101.0},
                {"start": datetime.datetime(2024, 1, 5, 10, 0, 0).timestamp(), "mean": 50.0, "min": 49.0, "max": 51.0},
                {"start": datetime.datetime(2024, 1, 10, 10, 0, 0).timestamp(), "mean": 75.0, "min": 74.0, "max": 76.0},
            ]
        }

        units_dict = {"sensor.test": "°C"}

        result = prepare_export_json(statistics_dict, "UTC", "%d.%m.%Y %H:%M", units_dict)

        # Should have one entity
        assert len(result) == 1
        entity = result[0]
        assert entity["id"] == "sensor.test"

        # Should have 3 values in chronological order
        values = entity["values"]
        assert len(values) == 3
        assert values[0]["datetime"] == "05.01.2024 10:00"
        assert values[0]["mean"] == 50.0
        assert values[1]["datetime"] == "10.01.2024 10:00"
        assert values[1]["mean"] == 75.0
        assert values[2]["datetime"] == "15.01.2024 10:00"
        assert values[2]["mean"] == 100.0

    def test_get_delta_from_stats_chronological_order(self) -> None:
        """
        Test that delta calculation uses chronological order, not alphabetical.

        If timestamps were sorted alphabetically with format "%d.%m.%Y %H:%M",
        the delta calculations would be completely wrong.
        """
        # Create rows with _sort_timestamp (numeric) and start (formatted string)
        # Intentionally provide them in non-chronological order to test sorting
        rows = [
            {
                "statistic_id": "sensor.counter",
                "_sort_timestamp": datetime.datetime(2024, 1, 15, 10, 0, 0).timestamp(),
                "start": "15.01.2024 10:00",
                "sum": "300",
            },
            {
                "statistic_id": "sensor.counter",
                "_sort_timestamp": datetime.datetime(2024, 1, 5, 10, 0, 0).timestamp(),
                "start": "05.01.2024 10:00",
                "sum": "100",
            },
            {
                "statistic_id": "sensor.counter",
                "_sort_timestamp": datetime.datetime(2024, 1, 10, 10, 0, 0).timestamp(),
                "start": "10.01.2024 10:00",
                "sum": "200",
            },
        ]

        result = get_delta_from_stats(rows, decimal_comma=False)

        # Should be sorted chronologically
        assert len(result) == 3
        assert result[0]["start"] == "05.01.2024 10:00"
        assert result[0]["delta"] == ""  # First record has no delta

        assert result[1]["start"] == "10.01.2024 10:00"
        assert result[1]["delta"] == "100"  # 200 - 100 = 100

        assert result[2]["start"] == "15.01.2024 10:00"
        assert result[2]["delta"] == "100"  # 300 - 200 = 100

    def test_get_delta_from_stats_wrong_order_would_fail(self) -> None:
        """
        Verify that if we used string sorting, delta calculations would be wrong.

        This test documents what would happen with the bug - it should demonstrate
        the issue if sorting were done on the string "start" field instead of
        the numeric "_sort_timestamp" field.
        """
        rows = [
            {
                "statistic_id": "sensor.counter",
                "_sort_timestamp": datetime.datetime(2024, 1, 15, 10, 0, 0).timestamp(),
                "start": "15.01.2024 10:00",
                "sum": "300",
            },
            {
                "statistic_id": "sensor.counter",
                "_sort_timestamp": datetime.datetime(2024, 1, 5, 10, 0, 0).timestamp(),
                "start": "05.01.2024 10:00",
                "sum": "100",
            },
        ]

        result = get_delta_from_stats(rows, decimal_comma=False)

        # With correct chronological sorting:
        assert result[0]["start"] == "05.01.2024 10:00"
        assert result[0]["sum"] == "100"
        assert result[0]["delta"] == ""  # First record

        assert result[1]["start"] == "15.01.2024 10:00"
        assert result[1]["sum"] == "300"
        assert result[1]["delta"] == "200"  # 300 - 100 = 200

        # If we had used alphabetical sorting on "start" strings,
        # the order would be: "05.01..." then "15.01..." which happens to be correct here,
        # but with "31.12.2023" and "01.01.2024", it would be wrong:
        # "01.01.2024" < "31.12.2023" (alphabetically - WRONG!)


class TestImportTimestampRangeDetection:
    """Test that import correctly identifies oldest/newest timestamps chronologically."""

    def test_import_range_detection_with_problematic_format(self) -> None:
        """
        Test that oldest/newest detection works with dd.mm.yyyy format.

        This is tested indirectly through prepare_delta_handling which is
        tested in test_prepare_delta_handling.py. This test serves as
        documentation of the edge case.
        """
        # Create a scenario where string min/max would give wrong results
        timestamps = [
            "31.12.2023 14:00",  # Oldest chronologically, but "31..." > "01..." alphabetically
            "01.01.2024 15:00",  # Newest chronologically, but "01..." < "31..." alphabetically
        ]

        # String sorting would incorrectly identify:
        # min("31.12.2023 14:00", "01.01.2024 15:00") = "01.01.2024 15:00" (WRONG - should be oldest)
        # max("31.12.2023 14:00", "01.01.2024 15:00") = "31.12.2023 14:00" (WRONG - should be newest)

        string_min = min(timestamps)
        string_max = max(timestamps)

        # This demonstrates the bug - string sorting gives wrong results
        assert string_min == "01.01.2024 15:00"  # Should be "31.12.2023 14:00"
        assert string_max == "31.12.2023 14:00"  # Should be "01.01.2024 15:00"

        # The fix is to parse timestamps first, then compare
        dt_format = "%d.%m.%Y %H:%M"
        dt_objects = [datetime.datetime.strptime(ts, dt_format) for ts in timestamps]
        oldest_dt = min(dt_objects)
        newest_dt = max(dt_objects)

        assert oldest_dt.strftime(dt_format) == "31.12.2023 14:00"
        assert newest_dt.strftime(dt_format) == "01.01.2024 15:00"
