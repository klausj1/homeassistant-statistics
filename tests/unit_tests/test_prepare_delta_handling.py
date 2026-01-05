"""Unit tests for prepare_delta_handling function."""

import datetime as dt
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.const import DATETIME_DEFAULT_FORMAT
from custom_components.import_statistics.helpers import DeltaReferenceType
from custom_components.import_statistics.import_service import prepare_delta_handling


class TestPrepareDeltaHandlingSingleStatistic:
    """Test cases for single statistic with delta data."""

    @pytest.mark.asyncio
    async def test_single_statistic_older_reference(self) -> None:
        """
        Test prepare_delta_handling with a single statistic having OLDER_REFERENCE.

        Input DataFrame:
            - statistic_id: sensor.energy
            - timestamps: 01.01.2022 12:00, 02.01.2022 12:00
            - timezone: UTC

        Expected output:
            - references dict with sensor.energy key
            - ref_type: OLDER_REFERENCE
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.energy", "01.01.2022 12:00", 10],
                ["sensor.energy", "02.01.2022 12:00", 20],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        oldest_import = dt.datetime(2022, 1, 1, 12, 0, tzinfo=dt.UTC)
        newest_import = dt.datetime(2022, 1, 2, 12, 0, tzinfo=dt.UTC)
        ref_older = dt.datetime(2022, 1, 1, 11, 0, tzinfo=dt.UTC)

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:
            mock_process.return_value = (
                {
                    "reference": {
                        "start": ref_older,
                        "sum": 50.0,
                        "state": 50.0,
                    },
                    "ref_type": DeltaReferenceType.OLDER_REFERENCE,
                },
                None,
            )

            result = await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)

            assert "sensor.energy" in result
            assert result["sensor.energy"]["ref_type"] == DeltaReferenceType.OLDER_REFERENCE
            assert result["sensor.energy"]["reference"]["start"] == ref_older
            assert result["sensor.energy"]["reference"]["sum"] == 50.0
            assert result["sensor.energy"]["reference"]["state"] == 50.0

            # Verify the function was called with correct arguments
            mock_process.assert_called_once()
            call_args = mock_process.call_args
            assert call_args[0][1] == "sensor.energy"
            assert call_args[0][2] == oldest_import
            assert call_args[0][3] == newest_import

    @pytest.mark.asyncio
    async def test_single_statistic_newer_reference(self) -> None:
        """
        Test prepare_delta_handling with a single statistic having NEWER_REFERENCE.

        Input DataFrame:
            - statistic_id: sensor.power
            - timestamps: 01.01.2022 12:00, 02.01.2022 12:00
            - timezone: UTC

        Expected output:
            - references dict with sensor.power key
            - ref_type: NEWER_REFERENCE
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.power", "01.01.2022 12:00", 5],
                ["sensor.power", "02.01.2022 12:00", 8],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        ref_newer = dt.datetime(2022, 1, 2, 13, 0, tzinfo=dt.UTC)

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:
            mock_process.return_value = (
                {
                    "reference": {
                        "start": ref_newer,
                        "sum": 100.0,
                        "state": 100.0,
                    },
                    "ref_type": DeltaReferenceType.NEWER_REFERENCE,
                },
                None,
            )

            result = await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)

            assert "sensor.power" in result
            assert result["sensor.power"]["ref_type"] == DeltaReferenceType.NEWER_REFERENCE
            assert result["sensor.power"]["reference"]["start"] == ref_newer


class TestPrepareDeltaHandlingMultipleStatistics:
    """Test cases for multiple statistics with delta data."""

    @pytest.mark.asyncio
    async def test_multiple_statistics_different_references(self) -> None:
        """
        Test prepare_delta_handling with multiple statistics having different reference types.

        Input DataFrame:
            - sensor.energy (timestamps: 01.01, 02.01)
            - sensor.power (timestamps: 01.01, 02.01)
            - timezone: UTC

        Expected output:
            - Both statistics in references dict
            - Different reference types per statistic
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.energy", "01.01.2022 12:00", 10],
                ["sensor.energy", "02.01.2022 12:00", 20],
                ["sensor.power", "01.01.2022 12:00", 5],
                ["sensor.power", "02.01.2022 12:00", 8],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        ref_older_energy = dt.datetime(2022, 1, 1, 11, 0, tzinfo=dt.UTC)
        ref_newer_power = dt.datetime(2022, 1, 2, 13, 0, tzinfo=dt.UTC)

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:

            def side_effect_func(hass, stat_id: str, oldest, newest) -> tuple[dict | None, str | None]:  # noqa: ARG001, ANN001
                if stat_id == "sensor.energy":
                    return (
                        {
                            "reference": {
                                "start": ref_older_energy,
                                "sum": 50.0,
                                "state": 50.0,
                            },
                            "ref_type": DeltaReferenceType.OLDER_REFERENCE,
                        },
                        None,
                    )
                return (
                    {
                        "reference": {
                            "start": ref_newer_power,
                            "sum": 100.0,
                            "state": 100.0,
                        },
                        "ref_type": DeltaReferenceType.NEWER_REFERENCE,
                    },
                    None,
                )

            mock_process.side_effect = side_effect_func

            result = await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)

            assert len(result) == 2
            assert "sensor.energy" in result
            assert "sensor.power" in result
            assert result["sensor.energy"]["ref_type"] == DeltaReferenceType.OLDER_REFERENCE
            assert result["sensor.power"]["ref_type"] == DeltaReferenceType.NEWER_REFERENCE

    @pytest.mark.asyncio
    async def test_multiple_statistics_same_timestamps_different_ids(self) -> None:
        """
        Test prepare_delta_handling with multiple statistics sharing the same timestamps.

        Input DataFrame:
            - sensor.temp (timestamps: 01.01, 02.01, 03.01)
            - sensor.humidity (timestamps: 01.01, 02.01, 03.01)
            - timezone: UTC

        Expected output:
            - Both statistics processed independently
            - Each gets its own reference data
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.temp", "01.01.2022 12:00", 1.5],
                ["sensor.temp", "02.01.2022 12:00", 2.5],
                ["sensor.temp", "03.01.2022 12:00", 3.5],
                ["sensor.humidity", "01.01.2022 12:00", 10],
                ["sensor.humidity", "02.01.2022 12:00", 20],
                ["sensor.humidity", "03.01.2022 12:00", 30],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:
            mock_process.return_value = (
                {
                    "reference": {
                        "start": dt.datetime(2022, 1, 1, 11, 0, tzinfo=dt.UTC),
                        "sum": 100.0,
                        "state": 100.0,
                    },
                    "ref_type": DeltaReferenceType.OLDER_REFERENCE,
                },
                None,
            )

            result = await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)

            assert len(result) == 2
            assert mock_process.call_count == 2

            # Verify both statistics are in the result
            assert "sensor.temp" in result
            assert "sensor.humidity" in result


class TestPrepareDeltaHandlingTimezoneHandling:
    """Test cases for timezone handling and datetime parsing."""

    @pytest.mark.asyncio
    async def test_timezone_conversion_utc(self) -> None:
        """
        Test that timestamps are correctly converted from local timezone to UTC.

        Input DataFrame timestamps in UTC format: 01.01.2022 12:00
        Expected: Parsed as UTC and converted to UTC for database query
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.energy", "01.01.2022 12:00", 10],
                ["sensor.energy", "02.01.2022 12:00", 20],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        expected_oldest = dt.datetime(2022, 1, 1, 12, 0, tzinfo=dt.UTC)
        expected_newest = dt.datetime(2022, 1, 2, 12, 0, tzinfo=dt.UTC)

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:
            mock_process.return_value = ({"reference": {}, "ref_type": DeltaReferenceType.OLDER_REFERENCE}, None)

            await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)

            call_args = mock_process.call_args
            assert call_args[0][2] == expected_oldest
            assert call_args[0][3] == expected_newest

    @pytest.mark.asyncio
    async def test_timezone_conversion_europe_berlin(self) -> None:
        """
        Test timezone conversion with Europe/Berlin timezone.

        Input DataFrame timestamps: 01.01.2022 12:00 (interpreted as Europe/Berlin)
        Expected: Converted to UTC (subtract 1 hour in winter)
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.energy", "01.01.2022 12:00", 10],
                ["sensor.energy", "02.01.2022 12:00", 20],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        # 01.01.2022 12:00 in Europe/Berlin = 11:00 UTC
        expected_oldest = dt.datetime(2022, 1, 1, 11, 0, tzinfo=dt.UTC)
        expected_newest = dt.datetime(2022, 1, 2, 11, 0, tzinfo=dt.UTC)

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:
            mock_process.return_value = ({"reference": {}, "ref_type": DeltaReferenceType.OLDER_REFERENCE}, None)

            await prepare_delta_handling(hass, df, "Europe/Berlin", DATETIME_DEFAULT_FORMAT)

            call_args = mock_process.call_args
            assert call_args[0][2] == expected_oldest
            assert call_args[0][3] == expected_newest

    @pytest.mark.asyncio
    async def test_custom_datetime_format(self) -> None:
        """
        Test handling of custom datetime format.

        Input DataFrame with format: "01-01-2022 12:00" (d-m-Y H:M)
        Expected: Correctly parsed and converted to UTC
        """
        hass = MagicMock()
        custom_format = "%d-%m-%Y %H:%M"
        df = pd.DataFrame(
            [
                ["sensor.energy", "01-01-2022 12:00", 10],
                ["sensor.energy", "02-01-2022 12:00", 20],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        expected_oldest = dt.datetime(2022, 1, 1, 12, 0, tzinfo=dt.UTC)
        expected_newest = dt.datetime(2022, 1, 2, 12, 0, tzinfo=dt.UTC)

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:
            mock_process.return_value = ({"reference": {}, "ref_type": DeltaReferenceType.OLDER_REFERENCE}, None)

            await prepare_delta_handling(hass, df, "UTC", custom_format)

            call_args = mock_process.call_args
            assert call_args[0][2] == expected_oldest
            assert call_args[0][3] == expected_newest


class TestPrepareDeltaHandlingErrorHandling:
    """Test cases for error handling in prepare_delta_handling."""

    @pytest.mark.asyncio
    async def test_error_from_process_delta_references(self) -> None:
        """
        Test that errors from _process_delta_references_for_statistic are handled.

        When _process_delta_references_for_statistic returns an error message,
        prepare_delta_handling should raise HomeAssistantError.
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.energy", "01.01.2022 12:00", 10],
                ["sensor.energy", "02.01.2022 12:00", 20],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        error_msg = "Entity 'sensor.energy': No statistics found in database for this entity"

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:
            mock_process.return_value = (None, error_msg)

            with pytest.raises(HomeAssistantError, match="No statistics found in database"):
                await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)

    @pytest.mark.asyncio
    async def test_error_invalid_timestamp_format(self) -> None:
        """
        Test that invalid timestamp format raises HomeAssistantError.

        Input DataFrame with malformed timestamp: "invalid-date"
        Expected: HomeAssistantError raised during parsing
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.energy", "invalid-date", 10],
                ["sensor.energy", "02.01.2022 12:00", 20],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        with pytest.raises(HomeAssistantError, match="Invalid timestamp format"):
            await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)

    @pytest.mark.asyncio
    async def test_error_invalid_timezone(self) -> None:
        """
        Test that invalid timezone identifier raises an error.

        Input: Invalid timezone identifier "Invalid/Timezone"
        Expected: Error raised during ZoneInfo initialization
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.energy", "01.01.2022 12:00", 10],
                ["sensor.energy", "02.01.2022 12:00", 20],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        with pytest.raises(Exception, match="No time zone found"):
            await prepare_delta_handling(hass, df, "Invalid/Timezone", DATETIME_DEFAULT_FORMAT)

    @pytest.mark.asyncio
    async def test_error_one_statistic_fails_propagates(self) -> None:
        """
        Test that if one statistic fails, error is propagated.

        Input DataFrame with two statistics:
            - sensor.energy: will succeed
            - sensor.power: will return error

        Expected: HomeAssistantError is raised
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.energy", "01.01.2022 12:00", 10],
                ["sensor.energy", "02.01.2022 12:00", 20],
                ["sensor.power", "01.01.2022 12:00", 5],
                ["sensor.power", "02.01.2022 12:00", 8],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:

            def side_effect_func(hass, stat_id: str, oldest, newest) -> tuple[dict | None, str | None]:  # noqa: ARG001, ANN001
                if stat_id == "sensor.energy":
                    return ({"reference": {}, "ref_type": DeltaReferenceType.OLDER_REFERENCE}, None)
                return (None, "Error for sensor.power")

            mock_process.side_effect = side_effect_func

            with pytest.raises(HomeAssistantError, match=r"Error for sensor\.power"):
                await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)


class TestPrepareDeltaHandlingEdgeCases:
    """Test cases for edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_single_row_dataframe(self) -> None:
        """
        Test prepare_delta_handling with a DataFrame containing only one row.

        Input DataFrame:
            - Single row with oldest_import == newest_import
            - timezone: UTC

        Expected output:
            - Single entry in references dict
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [["sensor.energy", "01.01.2022 12:00", 10]],
            columns=["statistic_id", "start", "delta"],
        )

        expected_timestamp = dt.datetime(2022, 1, 1, 12, 0, tzinfo=dt.UTC)

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:
            mock_process.return_value = (
                {
                    "reference": {
                        "start": dt.datetime(2022, 1, 1, 11, 0, tzinfo=dt.UTC),
                        "sum": 50.0,
                        "state": 50.0,
                    },
                    "ref_type": DeltaReferenceType.OLDER_REFERENCE,
                },
                None,
            )

            result = await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)

            assert len(result) == 1
            assert "sensor.energy" in result

            call_args = mock_process.call_args
            assert call_args[0][2] == expected_timestamp
            assert call_args[0][3] == expected_timestamp

    @pytest.mark.asyncio
    async def test_many_statistics_same_timestamp_range(self) -> None:
        """
        Test prepare_delta_handling with many statistics having the same timestamp range.

        Input DataFrame with 5 different statistics all having timestamps 01.01 and 02.01
        Expected output: All 5 statistics in references dict
        """
        hass = MagicMock()

        data = []
        stats = ["sensor.energy", "sensor.power", "sensor.temp", "sensor.humidity", "sensor.pressure"]
        for stat in stats:
            data.append([stat, "01.01.2022 12:00", 10])
            data.append([stat, "02.01.2022 12:00", 20])

        df = pd.DataFrame(data, columns=["statistic_id", "start", "delta"])

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:
            mock_process.return_value = (
                {
                    "reference": {
                        "start": dt.datetime(2022, 1, 1, 11, 0, tzinfo=dt.UTC),
                        "sum": 50.0,
                        "state": 50.0,
                    },
                    "ref_type": DeltaReferenceType.OLDER_REFERENCE,
                },
                None,
            )

            result = await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)

            assert len(result) == 5
            for stat in stats:
                assert stat in result

    @pytest.mark.asyncio
    async def test_statistics_with_different_timestamp_ranges(self) -> None:
        """
        Test prepare_delta_handling where each statistic has different timestamp ranges.

        Input DataFrame:
            - sensor.energy: 01.01 to 05.01
            - sensor.power: 02.01 to 04.01
            - sensor.temp: 01.01 to 03.01

        Expected output:
            - Each statistic gets correct oldest/newest timestamps
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.energy", "01.01.2022 12:00", 10],
                ["sensor.energy", "05.01.2022 12:00", 50],
                ["sensor.power", "02.01.2022 12:00", 5],
                ["sensor.power", "04.01.2022 12:00", 40],
                ["sensor.temp", "01.01.2022 12:00", 1],
                ["sensor.temp", "03.01.2022 12:00", 30],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        call_args_list: list[tuple[str, dt.datetime, dt.datetime]] = []

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:

            def capture_call(hass, stat_id: str, oldest, newest) -> tuple[dict | None, str | None]:  # noqa: ARG001, ANN001
                call_args_list.append((stat_id, oldest, newest))
                return (
                    {
                        "reference": {
                            "start": dt.datetime(2022, 1, 1, 11, 0, tzinfo=dt.UTC),
                            "sum": 50.0,
                            "state": 50.0,
                        },
                        "ref_type": DeltaReferenceType.OLDER_REFERENCE,
                    },
                    None,
                )

            mock_process.side_effect = capture_call

            result = await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)

            assert len(result) == 3
            assert len(call_args_list) == 3

            # Verify each statistic was called with correct range
            energy_call = next((c for c in call_args_list if c[0] == "sensor.energy"), None)
            power_call = next((c for c in call_args_list if c[0] == "sensor.power"), None)
            temp_call = next((c for c in call_args_list if c[0] == "sensor.temp"), None)

            assert energy_call is not None
            assert energy_call[1] == dt.datetime(2022, 1, 1, 12, 0, tzinfo=dt.UTC)
            assert energy_call[2] == dt.datetime(2022, 1, 5, 12, 0, tzinfo=dt.UTC)

            assert power_call is not None
            assert power_call[1] == dt.datetime(2022, 1, 2, 12, 0, tzinfo=dt.UTC)
            assert power_call[2] == dt.datetime(2022, 1, 4, 12, 0, tzinfo=dt.UTC)

            assert temp_call is not None
            assert temp_call[1] == dt.datetime(2022, 1, 1, 12, 0, tzinfo=dt.UTC)
            assert temp_call[2] == dt.datetime(2022, 1, 3, 12, 0, tzinfo=dt.UTC)

    @pytest.mark.asyncio
    async def test_none_reference_allowed_in_result(self) -> None:
        """
        Test that None reference values are allowed in the result.

        When _process_delta_references_for_statistic returns None with no error,
        the references dict should contain None for that statistic.

        This is a valid scenario for future enhancements.
        """
        hass = MagicMock()
        df = pd.DataFrame(
            [
                ["sensor.energy", "01.01.2022 12:00", 10],
                ["sensor.energy", "02.01.2022 12:00", 20],
            ],
            columns=["statistic_id", "start", "delta"],
        )

        with patch("custom_components.import_statistics.import_service._process_delta_references_for_statistic") as mock_process:
            mock_process.return_value = (None, None)

            result = await prepare_delta_handling(hass, df, "UTC", DATETIME_DEFAULT_FORMAT)

            assert "sensor.energy" in result
            assert result["sensor.energy"] is None
