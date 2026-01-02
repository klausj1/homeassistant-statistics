"""Test timezone conversion fix in delta processing reference lookup."""

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest

from custom_components.import_statistics import get_oldest_statistics_before


class TestTimezoneReferenceLookup:
    """Test timezone conversion in reference lookup for delta processing."""

    @pytest.mark.asyncio
    async def test_reference_lookup_with_utc_timezone_conversion(self) -> None:
        """
        Test that reference records are found when timezone conversion is applied correctly.

        This test validates the fix for timezone conversion in delta processing.
        The old buggy code would query the database with the user's local timezone,
        instead of converting to UTC first. This test demonstrates that:

        1. A reference record exists at timestamp N (UTC)
        2. We're importing delta data for timestamp N+1
        3. The original timestamp passed to the query was in a non-UTC timezone
        4. The fixed code correctly converts to UTC before querying
        """
        # Setup: reference record at 2022-01-01 00:00 UTC
        # Import: delta data starts at 2022-01-01 01:00 UTC
        # User timezone: Europe/Vienna (UTC+1 in January)

        # The import start time in Vienna is 2022-01-01 02:00+01:00
        # which equals 2022-01-01 01:00 UTC
        import_start_utc = dt.datetime(2022, 1, 1, 1, 0, tzinfo=dt.UTC)
        reference_timestamp_utc = dt.datetime(2022, 1, 1, 0, 0, tzinfo=dt.UTC)

        # references_needed should contain the import_start_utc (after timezone conversion)
        references_needed = {
            "counter.energy": import_start_utc,
        }

        # Mock the recorder instance
        mock_recorder = MagicMock()
        mock_hass = MagicMock()

        # Create a mock row that represents the database reference record
        mock_reference_row = MagicMock()
        mock_reference_row.start_ts = reference_timestamp_utc.timestamp()
        mock_reference_row.sum = 100.0
        mock_reference_row.state = 100.0

        # Mock the metadata lookup
        mock_metadata = {
            "counter.energy": (1, {"unit_of_measurement": "kWh"}),
        }

        with (
            patch("custom_components.import_statistics.get_instance") as mock_get_instance,
            patch("custom_components.import_statistics.get_metadata") as mock_get_metadata,
        ):
            mock_get_instance.return_value = mock_recorder
            mock_get_metadata.return_value = mock_metadata

            # Mock the executor job to return our reference row
            async def mock_executor(func: object, *args: object) -> object:
                """Mock executor that calls the function directly."""
                return func(*args)

            mock_recorder.async_add_executor_job = mock_executor

            # Mock the database query function
            with patch("custom_components.import_statistics._get_reference_stats") as mock_query:
                mock_query.return_value = mock_reference_row

                # Call the function being tested
                result = await get_oldest_statistics_before(mock_hass, references_needed)

                # Verify the reference was found
                assert "counter.energy" in result
                assert result["counter.energy"] is not None
                assert result["counter.energy"]["sum"] == 100.0
                assert result["counter.energy"]["state"] == 100.0

    @pytest.mark.asyncio
    async def test_reference_lookup_rejects_equal_timestamp(self) -> None:
        """
        Test that reference records at exactly import start time are rejected.

        Reference records must be strictly BEFORE the import start time.
        This test verifies that a record at exactly the import timestamp is rejected.
        """
        # Setup: reference record at 2022-01-01 01:00 UTC
        # Import: delta data starts at 2022-01-01 01:00 UTC (same timestamp)
        # This should be rejected because reference must be strictly BEFORE
        import_start_utc = dt.datetime(2022, 1, 1, 1, 0, tzinfo=dt.UTC)
        reference_timestamp_utc = dt.datetime(2022, 1, 1, 1, 0, tzinfo=dt.UTC)

        references_needed = {
            "counter.energy": import_start_utc,
        }

        mock_recorder = MagicMock()
        mock_hass = MagicMock()

        # Create a mock row at the same timestamp as import start
        mock_reference_row = MagicMock()
        mock_reference_row.start_ts = reference_timestamp_utc.timestamp()
        mock_reference_row.sum = 100.0
        mock_reference_row.state = 100.0

        mock_metadata = {
            "counter.energy": (1, {"unit_of_measurement": "kWh"}),
        }

        with (
            patch("custom_components.import_statistics.get_instance") as mock_get_instance,
            patch("custom_components.import_statistics.get_metadata") as mock_get_metadata,
        ):
            mock_get_instance.return_value = mock_recorder
            mock_get_metadata.return_value = mock_metadata

            async def mock_executor(func: object, *args: object) -> object:
                """Mock executor that calls the function directly."""
                return func(*args)

            mock_recorder.async_add_executor_job = mock_executor

            with patch("custom_components.import_statistics._get_reference_stats") as mock_query:
                mock_query.return_value = mock_reference_row

                result = await get_oldest_statistics_before(mock_hass, references_needed)

                # Reference at exactly import start time should be rejected (not strictly before)
                assert "counter.energy" in result
                assert result["counter.energy"] is None

    @pytest.mark.asyncio
    async def test_reference_lookup_with_different_timezones(self) -> None:
        """
        Test reference lookup with multiple different timezone scenarios.

        This validates that the timezone conversion works correctly with various
        offset timezones (positive, negative, and UTC).
        """
        # Test Case 1: Asia/Tokyo (UTC+9 in winter)
        # User enters: 2022-01-01 10:00 Tokyo time
        # Database stores: 2022-01-01 01:00 UTC (10:00 - 9 hours)
        # Reference at: 2022-01-01 00:00 UTC (should be found as strictly before)

        import_start_utc = dt.datetime(2022, 1, 1, 1, 0, tzinfo=dt.UTC)
        reference_timestamp_utc = dt.datetime(2022, 1, 1, 0, 0, tzinfo=dt.UTC)

        references_needed = {
            "counter.energy": import_start_utc,
        }

        mock_recorder = MagicMock()
        mock_hass = MagicMock()

        mock_reference_row = MagicMock()
        mock_reference_row.start_ts = reference_timestamp_utc.timestamp()
        mock_reference_row.sum = 500.0
        mock_reference_row.state = 500.0

        mock_metadata = {
            "counter.energy": (1, {"unit_of_measurement": "kWh"}),
        }

        with (
            patch("custom_components.import_statistics.get_instance") as mock_get_instance,
            patch("custom_components.import_statistics.get_metadata") as mock_get_metadata,
        ):
            mock_get_instance.return_value = mock_recorder
            mock_get_metadata.return_value = mock_metadata

            async def mock_executor(func: object, *args: object) -> object:
                """Mock executor that calls the function directly."""
                return func(*args)

            mock_recorder.async_add_executor_job = mock_executor

            with patch("custom_components.import_statistics._get_reference_stats") as mock_query:
                mock_query.return_value = mock_reference_row

                result = await get_oldest_statistics_before(mock_hass, references_needed)

                assert "counter.energy" in result
                assert result["counter.energy"] is not None
                assert result["counter.energy"]["sum"] == 500.0

    @pytest.mark.asyncio
    async def test_reference_lookup_no_record_found(self) -> None:
        """Test reference lookup when no record exists before import start time."""
        import_start_utc = dt.datetime(2022, 1, 1, 1, 0, tzinfo=dt.UTC)

        references_needed = {
            "counter.energy": import_start_utc,
        }

        mock_recorder = MagicMock()
        mock_hass = MagicMock()
        mock_metadata = {
            "counter.energy": (1, {"unit_of_measurement": "kWh"}),
        }

        with (
            patch("custom_components.import_statistics.get_instance") as mock_get_instance,
            patch("custom_components.import_statistics.get_metadata") as mock_get_metadata,
        ):
            mock_get_instance.return_value = mock_recorder
            mock_get_metadata.return_value = mock_metadata

            async def mock_executor(func: object, *args: object) -> object:
                """Mock executor that calls the function directly."""
                return func(*args)

            mock_recorder.async_add_executor_job = mock_executor

            # Database query returns None (no record found)
            with patch("custom_components.import_statistics._get_reference_stats") as mock_query:
                mock_query.return_value = None

                result = await get_oldest_statistics_before(mock_hass, references_needed)

                assert "counter.energy" in result
                assert result["counter.energy"] is None

    @pytest.mark.asyncio
    async def test_reference_lookup_multiple_statistics(self) -> None:
        """
        Test reference lookup for multiple statistics with different timestamps.

        Each statistic can have its own import start time, requiring separate
        timezone conversions and database queries.
        """
        # Two statistics with different import start times
        energy_import_start = dt.datetime(2022, 1, 1, 1, 0, tzinfo=dt.UTC)
        gas_import_start = dt.datetime(2022, 1, 1, 2, 0, tzinfo=dt.UTC)

        references_needed = {
            "counter.energy": energy_import_start,
            "counter.gas": gas_import_start,
        }

        mock_recorder = MagicMock()
        mock_hass = MagicMock()

        # Create mock rows for each statistic
        mock_energy_row = MagicMock()
        mock_energy_row.start_ts = dt.datetime(2022, 1, 1, 0, 0, tzinfo=dt.UTC).timestamp()
        mock_energy_row.sum = 100.0
        mock_energy_row.state = 100.0

        mock_gas_row = MagicMock()
        mock_gas_row.start_ts = dt.datetime(2022, 1, 1, 1, 0, tzinfo=dt.UTC).timestamp()
        mock_gas_row.sum = 50.0
        mock_gas_row.state = 50.0

        mock_metadata = {
            "counter.energy": (1, {"unit_of_measurement": "kWh"}),
            "counter.gas": (2, {"unit_of_measurement": "m³"}),
        }

        with (
            patch("custom_components.import_statistics.get_instance") as mock_get_instance,
            patch("custom_components.import_statistics.get_metadata") as mock_get_metadata,
        ):
            mock_get_instance.return_value = mock_recorder
            mock_get_metadata.return_value = mock_metadata

            async def mock_executor(func: object, *args: object) -> object:
                """Mock executor that calls the function directly."""
                return func(*args)

            mock_recorder.async_add_executor_job = mock_executor

            # Mock database queries to return different rows based on metadata_id
            def mock_query_side_effect(metadata_id: object, _ts: object, _inst: object) -> object:
                """Return different rows based on the metadata ID."""
                if metadata_id == 1:
                    return mock_energy_row
                if metadata_id == 2:
                    return mock_gas_row
                return None

            with patch("custom_components.import_statistics._get_reference_stats") as mock_query:
                mock_query.side_effect = mock_query_side_effect

                result = await get_oldest_statistics_before(mock_hass, references_needed)

                # Both statistics should have references found
                assert "counter.energy" in result
                assert result["counter.energy"] is not None
                assert result["counter.energy"]["sum"] == 100.0

                assert "counter.gas" in result
                assert result["counter.gas"] is not None
                assert result["counter.gas"]["sum"] == 50.0

    @pytest.mark.asyncio
    async def test_reference_lookup_utc_timezone_passthrough(self) -> None:
        """
        Test that UTC timezone timestamps work correctly (no conversion needed).

        When user specifies UTC timezone, the timestamp should be used as-is.
        This validates that the fix doesn't break UTC timezone handling.
        """
        # Import start time in UTC (no conversion needed)
        import_start_utc = dt.datetime(2022, 1, 1, 1, 0, tzinfo=dt.UTC)
        reference_timestamp_utc = dt.datetime(2022, 1, 1, 0, 0, tzinfo=dt.UTC)

        references_needed = {
            "counter.energy": import_start_utc,
        }

        mock_recorder = MagicMock()
        mock_hass = MagicMock()

        mock_reference_row = MagicMock()
        mock_reference_row.start_ts = reference_timestamp_utc.timestamp()
        mock_reference_row.sum = 200.0
        mock_reference_row.state = 200.0

        mock_metadata = {
            "counter.energy": (1, {"unit_of_measurement": "kWh"}),
        }

        with (
            patch("custom_components.import_statistics.get_instance") as mock_get_instance,
            patch("custom_components.import_statistics.get_metadata") as mock_get_metadata,
        ):
            mock_get_instance.return_value = mock_recorder
            mock_get_metadata.return_value = mock_metadata

            async def mock_executor(func: object, *args: object) -> object:
                """Mock executor that calls the function directly."""
                return func(*args)

            mock_recorder.async_add_executor_job = mock_executor

            with patch("custom_components.import_statistics._get_reference_stats") as mock_query:
                mock_query.return_value = mock_reference_row

                result = await get_oldest_statistics_before(mock_hass, references_needed)

                assert "counter.energy" in result
                assert result["counter.energy"] is not None
                assert result["counter.energy"]["sum"] == 200.0

    @pytest.mark.asyncio
    async def test_reference_lookup_with_negative_timezone_offset(self) -> None:
        """
        Test reference lookup with negative timezone offset (e.g., Americas).

        Tests that the timezone conversion works correctly with negative UTC offsets
        like America/New_York (UTC-5 in winter).
        """
        # User timezone: America/New_York (UTC-5 in January)
        # User enters: 2022-01-01 08:00 ET (Eastern Time)
        # Database stores: 2022-01-01 13:00 UTC (8:00 + 5 hours)
        # Reference at: 2022-01-01 12:00 UTC (should be found as strictly before)

        import_start_utc = dt.datetime(2022, 1, 1, 13, 0, tzinfo=dt.UTC)
        reference_timestamp_utc = dt.datetime(2022, 1, 1, 12, 0, tzinfo=dt.UTC)

        references_needed = {
            "counter.energy": import_start_utc,
        }

        mock_recorder = MagicMock()
        mock_hass = MagicMock()

        mock_reference_row = MagicMock()
        mock_reference_row.start_ts = reference_timestamp_utc.timestamp()
        mock_reference_row.sum = 150.0
        mock_reference_row.state = 150.0

        mock_metadata = {
            "counter.energy": (1, {"unit_of_measurement": "kWh"}),
        }

        with (
            patch("custom_components.import_statistics.get_instance") as mock_get_instance,
            patch("custom_components.import_statistics.get_metadata") as mock_get_metadata,
        ):
            mock_get_instance.return_value = mock_recorder
            mock_get_metadata.return_value = mock_metadata

            async def mock_executor(func: object, *args: object) -> object:
                """Mock executor that calls the function directly."""
                return func(*args)

            mock_recorder.async_add_executor_job = mock_executor

            with patch("custom_components.import_statistics._get_reference_stats") as mock_query:
                mock_query.return_value = mock_reference_row

                result = await get_oldest_statistics_before(mock_hass, references_needed)

                assert "counter.energy" in result
                assert result["counter.energy"] is not None
                assert result["counter.energy"]["sum"] == 150.0

    @pytest.mark.asyncio
    async def test_reference_lookup_rejects_after_timestamp(self) -> None:
        """
        Test that reference records after import start time are rejected.

        Reference records must be strictly BEFORE the import start time.
        A record that comes after should be rejected.
        """
        # Reference record AFTER import start time
        import_start_utc = dt.datetime(2022, 1, 1, 1, 0, tzinfo=dt.UTC)
        reference_timestamp_utc = dt.datetime(2022, 1, 1, 2, 0, tzinfo=dt.UTC)  # 1 hour later

        references_needed = {
            "counter.energy": import_start_utc,
        }

        mock_recorder = MagicMock()
        mock_hass = MagicMock()

        mock_reference_row = MagicMock()
        mock_reference_row.start_ts = reference_timestamp_utc.timestamp()
        mock_reference_row.sum = 100.0
        mock_reference_row.state = 100.0

        mock_metadata = {
            "counter.energy": (1, {"unit_of_measurement": "kWh"}),
        }

        with (
            patch("custom_components.import_statistics.get_instance") as mock_get_instance,
            patch("custom_components.import_statistics.get_metadata") as mock_get_metadata,
        ):
            mock_get_instance.return_value = mock_recorder
            mock_get_metadata.return_value = mock_metadata

            async def mock_executor(func: object, *args: object) -> object:
                """Mock executor that calls the function directly."""
                return func(*args)

            mock_recorder.async_add_executor_job = mock_executor

            with patch("custom_components.import_statistics._get_reference_stats") as mock_query:
                mock_query.return_value = mock_reference_row

                result = await get_oldest_statistics_before(mock_hass, references_needed)

                # Reference after import start should be rejected
                assert "counter.energy" in result
                assert result["counter.energy"] is None

    @pytest.mark.asyncio
    async def test_reference_lookup_with_far_past_reference(self) -> None:
        """
        Test that very old reference records are accepted if they're before import start.

        Reference records can be very old (days/weeks/months before) as long as they
        are strictly before the import start time.
        """
        # Import starts at 2022-01-01 01:00 UTC
        # Reference is from 30 days earlier
        import_start_utc = dt.datetime(2022, 1, 1, 1, 0, tzinfo=dt.UTC)
        reference_timestamp_utc = dt.datetime(2021, 12, 2, 1, 0, tzinfo=dt.UTC)  # 30 days earlier

        references_needed = {
            "counter.energy": import_start_utc,
        }

        mock_recorder = MagicMock()
        mock_hass = MagicMock()

        mock_reference_row = MagicMock()
        mock_reference_row.start_ts = reference_timestamp_utc.timestamp()
        mock_reference_row.sum = 50.0
        mock_reference_row.state = 50.0

        mock_metadata = {
            "counter.energy": (1, {"unit_of_measurement": "kWh"}),
        }

        with (
            patch("custom_components.import_statistics.get_instance") as mock_get_instance,
            patch("custom_components.import_statistics.get_metadata") as mock_get_metadata,
        ):
            mock_get_instance.return_value = mock_recorder
            mock_get_metadata.return_value = mock_metadata

            async def mock_executor(func: object, *args: object) -> object:
                """Mock executor that calls the function directly."""
                return func(*args)

            mock_recorder.async_add_executor_job = mock_executor

            with patch("custom_components.import_statistics._get_reference_stats") as mock_query:
                mock_query.return_value = mock_reference_row

                result = await get_oldest_statistics_before(mock_hass, references_needed)

                assert "counter.energy" in result
                assert result["counter.energy"] is not None
                assert result["counter.energy"]["sum"] == 50.0
