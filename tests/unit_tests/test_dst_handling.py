"""Unit tests for DST (Daylight Saving Time) handling in timestamp localization."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.const import (
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_TIMEZONE_IDENTIFIER,
)
from custom_components.import_statistics.import_service_helper import (
    _localize_timestamps_with_dst_handling,
    prepare_data_to_import,
    prepare_json_data_to_import,
)


class TestLocalizeDstHandling:
    """Tests for _localize_timestamps_with_dst_handling function."""

    def test_nonexistent_time_spring_forward_raises_error(self) -> None:
        """Test that a non-existent time during spring forward DST gap raises HomeAssistantError."""
        # 2026-03-29 02:00 does not exist in Europe/Berlin (clocks jump from 02:00 to 03:00)
        df = pd.DataFrame(
            {
                "start": pd.to_datetime(["2026-03-29 02:00"]),
                "statistic_id": ["sensor.test"],
                "unit": ["kWh"],
            }
        )
        naive_copy = df["start"].copy()

        with pytest.raises(HomeAssistantError, match="daylight saving time transition"):
            _localize_timestamps_with_dst_handling(df, "Europe/Berlin", naive_copy=naive_copy)

    def test_nonexistent_time_us_spring_forward_raises_error(self) -> None:
        """Test non-existent time in US timezone (America/New_York) raises HomeAssistantError."""
        # 2026-03-08 02:00 does not exist in America/New_York (clocks jump from 02:00 to 03:00)
        df = pd.DataFrame(
            {
                "start": pd.to_datetime(["2026-03-08 02:00"]),
                "statistic_id": ["sensor.test"],
                "unit": ["kWh"],
            }
        )
        naive_copy = df["start"].copy()

        with pytest.raises(HomeAssistantError, match="daylight saving time transition"):
            _localize_timestamps_with_dst_handling(df, "America/New_York", naive_copy=naive_copy)

    def test_valid_time_before_dst_gap_succeeds(self) -> None:
        """Test that a valid time just before the DST gap succeeds."""
        # 2026-03-29 01:00 exists in Europe/Berlin (before the gap)
        df = pd.DataFrame(
            {
                "start": pd.to_datetime(["2026-03-29 01:00"]),
                "statistic_id": ["sensor.test"],
                "unit": ["kWh"],
            }
        )
        naive_copy = df["start"].copy()

        _localize_timestamps_with_dst_handling(df, "Europe/Berlin", naive_copy=naive_copy)

        # Should have timezone info after localization
        assert df["start"].dt.tz is not None

    def test_valid_time_after_dst_gap_succeeds(self) -> None:
        """Test that a valid time just after the DST gap succeeds."""
        # 2026-03-29 03:00 exists in Europe/Berlin (after the gap)
        df = pd.DataFrame(
            {
                "start": pd.to_datetime(["2026-03-29 03:00"]),
                "statistic_id": ["sensor.test"],
                "unit": ["kWh"],
            }
        )
        naive_copy = df["start"].copy()

        _localize_timestamps_with_dst_handling(df, "Europe/Berlin", naive_copy=naive_copy)

        # Should have timezone info after localization
        assert df["start"].dt.tz is not None

    def test_ambiguous_time_fall_back_succeeds(self) -> None:
        """Test that an ambiguous time during fall back DST overlap succeeds (uses later occurrence)."""
        # 2026-10-25 02:00 is ambiguous in Europe/Berlin (clocks fall back from 03:00 to 02:00)
        df = pd.DataFrame(
            {
                "start": pd.to_datetime(["2026-10-25 02:00"]),
                "statistic_id": ["sensor.test"],
                "unit": ["kWh"],
            }
        )
        naive_copy = df["start"].copy()

        _localize_timestamps_with_dst_handling(df, "Europe/Berlin", naive_copy=naive_copy)

        # Should have timezone info after localization
        assert df["start"].dt.tz is not None

    def test_mixed_valid_and_nonexistent_times_raises_error(self) -> None:
        """Test that a mix of valid and non-existent times raises HomeAssistantError."""
        df = pd.DataFrame(
            {
                "start": pd.to_datetime(["2026-03-29 01:00", "2026-03-29 02:00", "2026-03-29 03:00"]),
                "statistic_id": ["sensor.test"] * 3,
                "unit": ["kWh"] * 3,
            }
        )
        naive_copy = df["start"].copy()

        with pytest.raises(HomeAssistantError, match="daylight saving time transition"):
            _localize_timestamps_with_dst_handling(df, "Europe/Berlin", naive_copy=naive_copy)

    def test_pytz_nonexistent_time_error_caught_by_type_name(self) -> None:
        """
        Test that pytz.exceptions.NonExistentTimeError is caught by checking exception type name.

        This simulates the behavior of older pandas versions that raise
        pytz.exceptions.NonExistentTimeError instead of ValueError.
        """

        # Create a custom exception class that mimics pytz.exceptions.NonExistentTimeError
        class NonExistentTimeError(Exception):
            """Simulated pytz NonExistentTimeError - message is just the timestamp."""

        df = pd.DataFrame(
            {
                "start": pd.to_datetime(["2026-03-29 02:00"]),
                "statistic_id": ["sensor.test"],
                "unit": ["kWh"],
            }
        )

        # Mock tz_localize to raise our simulated NonExistentTimeError
        with (
            patch.object(
                pd.core.indexes.accessors.DatetimeProperties,
                "tz_localize",
                side_effect=NonExistentTimeError("2026-03-29 02:00:00"),
            ),
            pytest.raises(HomeAssistantError, match="daylight saving time transition"),
        ):
            _localize_timestamps_with_dst_handling(df, "Europe/Berlin", naive_copy=df["start"].copy())

    def test_unexpected_exception_converted_to_home_assistant_error(self) -> None:
        """Test that unexpected exceptions from tz_localize are converted to HomeAssistantError."""
        df = pd.DataFrame(
            {
                "start": pd.to_datetime(["2026-03-29 01:00"]),
                "statistic_id": ["sensor.test"],
                "unit": ["kWh"],
            }
        )

        # Mock tz_localize to raise an unexpected exception
        with (
            patch.object(
                pd.core.indexes.accessors.DatetimeProperties,
                "tz_localize",
                side_effect=RuntimeError("Unexpected internal error"),
            ),
            pytest.raises(HomeAssistantError, match="Failed to localize timestamps"),
        ):
            _localize_timestamps_with_dst_handling(df, "Europe/Berlin", naive_copy=df["start"].copy())


class TestPrepareDataDstHandling:
    """Tests for DST handling in prepare_data_to_import (CSV/TSV path)."""

    def test_csv_with_nonexistent_dst_time_raises_error(self) -> None:
        """Test that importing a CSV with a non-existent DST time raises HomeAssistantError."""
        my_df = pd.DataFrame(
            [
                ["sensor.temperature", "29.03.2026 02:00", "°C", 20.1, 25.5, 22.8],
            ],
            columns=["statistic_id", "start", "unit", "min", "max", "mean"],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = str(Path(temp_dir) / "test_dst.csv")
            my_df.to_csv(file_path, sep=",", index=False, decimal=".")

            data = {
                ATTR_DECIMAL: "dot ('.')",
                ATTR_TIMEZONE_IDENTIFIER: "Europe/Berlin",
                ATTR_DELIMITER: ",",
            }

            call = ServiceCall("domain_name", "service_name", data, data)
            ha_timezone = "UTC"

            with pytest.raises(HomeAssistantError, match="daylight saving time transition"):
                prepare_data_to_import(file_path, call, ha_timezone)


class TestPrepareJsonDstHandling:
    """Tests for DST handling in prepare_json_data_to_import (JSON path)."""

    def test_json_with_nonexistent_dst_time_raises_error(self) -> None:
        """Test that importing JSON with a non-existent DST time raises HomeAssistantError."""
        data = {
            ATTR_TIMEZONE_IDENTIFIER: "Europe/Berlin",
            "entities": [
                {
                    "id": "sensor.temperature",
                    "unit": "°C",
                    "values": [
                        {
                            "datetime": "29.03.2026 02:00",
                            "mean": 22.8,
                            "min": 20.1,
                            "max": 25.5,
                        },
                    ],
                },
            ],
        }

        call = ServiceCall("domain_name", "service_name", data, data)
        ha_timezone = "UTC"

        with pytest.raises(HomeAssistantError, match="daylight saving time transition"):
            prepare_json_data_to_import(call, ha_timezone)
