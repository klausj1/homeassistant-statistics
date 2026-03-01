"""Performance tests for handle_dataframe_no_delta function."""

import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from custom_components.import_statistics.import_service_helper import handle_dataframe_no_delta

_LOGGER = logging.getLogger(__name__)


class TestHandleDataframePerformance:
    """Test performance of handle_dataframe_no_delta with large datasets."""

    def test_performance_large_dataset_mean(self) -> None:
        """Test performance with 10,000 rows of mean data."""
        # Create 10,000 rows with 10 unique statistic_ids
        data = []
        base_date = datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))

        for stat_id in range(10):
            for hour in range(1000):
                timestamp = base_date + timedelta(hours=hour)
                data.append(
                    {
                        "statistic_id": f"sensor.test_{stat_id}",
                        "start": timestamp,
                        "unit": "kWh",
                        "min": float(hour),
                        "max": float(hour + 10),
                        "mean": float(hour + 5),
                    }
                )

        df = pd.DataFrame(data)

        # Measure performance
        start = time.perf_counter()
        result = handle_dataframe_no_delta(df)
        elapsed = time.perf_counter() - start

        # Verify correctness
        assert len(result) == 10, "Should have 10 unique statistic_ids"
        for stat_id in range(10):
            key = f"sensor.test_{stat_id}"
            assert key in result
            metadata, stats_list = result[key]
            assert len(stats_list) == 1000, f"Should have 1000 records for {key}"
            assert metadata["unit_of_measurement"] == "kWh"

        # Performance assertion: should complete in < 1 second for 10k rows
        # This is a reasonable target after optimization
        assert elapsed < 1.0, f"Too slow: {elapsed:.3f}s for 10k rows (expected < 1.0s)"

    def test_performance_large_dataset_sum(self) -> None:
        """Test performance with 10,000 rows of sum data."""
        # Create 10,000 rows with 5 unique statistic_ids
        data = []
        base_date = datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))

        for stat_id in range(5):
            for hour in range(2000):
                timestamp = base_date + timedelta(hours=hour)
                data.append(
                    {
                        "statistic_id": f"sensor.counter_{stat_id}",
                        "start": timestamp,
                        "unit": "kWh",
                        "sum": float(hour * 10),
                        "state": float(hour),
                    }
                )

        df = pd.DataFrame(data)

        # Measure performance
        start = time.perf_counter()
        result = handle_dataframe_no_delta(df)
        elapsed = time.perf_counter() - start

        # Verify correctness
        assert len(result) == 5, "Should have 5 unique statistic_ids"
        for stat_id in range(5):
            key = f"sensor.counter_{stat_id}"
            assert key in result
            metadata, stats_list = result[key]
            assert len(stats_list) == 2000, f"Should have 2000 records for {key}"
            assert metadata["has_sum"] is True

        # Performance assertion
        assert elapsed < 1.0, f"Too slow: {elapsed:.3f}s for 10k rows (expected < 1.0s)"

    def test_performance_many_statistics(self) -> None:
        """Test performance with many unique statistic_ids."""
        # Create 5,000 rows with 100 unique statistic_ids (50 rows each)
        data = []
        base_date = datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))

        for stat_id in range(100):
            for hour in range(50):
                timestamp = base_date + timedelta(hours=hour)
                data.append(
                    {
                        "statistic_id": f"sensor.metric_{stat_id}",
                        "start": timestamp,
                        "unit": "°C",
                        "min": float(hour),
                        "max": float(hour + 5),
                        "mean": float(hour + 2.5),
                    }
                )

        df = pd.DataFrame(data)

        # Measure performance
        start = time.perf_counter()
        result = handle_dataframe_no_delta(df)
        elapsed = time.perf_counter() - start

        # Verify correctness
        assert len(result) == 100, "Should have 100 unique statistic_ids"
        for stat_id in range(100):
            key = f"sensor.metric_{stat_id}"
            assert key in result
            _metadata, stats_list = result[key]
            assert len(stats_list) == 50, f"Should have 50 records for {key}"

        # Performance assertion
        assert elapsed < 0.5, f"Too slow: {elapsed:.3f}s for 5k rows (expected < 0.5s)"

    def test_performance_very_large_dataset(self) -> None:
        """Test performance with 100,000 rows (marked as slow test)."""
        # Create 100,000 rows with 10 unique statistic_ids
        data = []
        base_date = datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))

        for stat_id in range(10):
            for hour in range(10000):
                timestamp = base_date + timedelta(hours=hour)
                data.append(
                    {
                        "statistic_id": f"sensor.large_{stat_id}",
                        "start": timestamp,
                        "unit": "W",
                        "sum": float(hour * 100),
                    }
                )

        df = pd.DataFrame(data)

        # Measure performance
        start = time.perf_counter()
        result = handle_dataframe_no_delta(df)
        elapsed = time.perf_counter() - start

        # Verify correctness
        assert len(result) == 10, "Should have 10 unique statistic_ids"

        # Performance assertion: should complete in < 10 seconds for 100k rows
        assert elapsed < 10.0, f"Too slow: {elapsed:.3f}s for 100k rows (expected < 10.0s)"
