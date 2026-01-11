"""Unit tests for _process_delta_references_for_statistic function."""

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest

from custom_components.import_statistics.helpers import DeltaReferenceType
from custom_components.import_statistics.import_service import _process_delta_references_for_statistic


class TestProcessDeltaReferencesOlderReference:
    """Test cases for OLDER_REFERENCE scenarios."""

    @pytest.mark.asyncio
    async def test_older_reference_exactly_1_hour_before_oldest_import(self) -> None:
        """
        Test OLDER_REFERENCE when reference is exactly 1 hour before oldest import.

        Timestamps:
            - t_oldest_db    : 10:00
            - t_newest_db    : 14:00
            - t_oldest_import: 12:00
            - t_newest_import: 14:00
            - Reference found: 11:00 (exactly 1 hour before oldest_import)
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        t_newest_db = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        ref_older_before_oldest = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = {
                "start": ref_older_before_oldest,
                "sum": 50.0,
                "state": 50.0,
            }
            mock_after.return_value = None  # Not needed for OLDER_REFERENCE

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE
            assert ref_data["reference"]["start"] == ref_older_before_oldest
            assert ref_data["reference"]["sum"] == 50.0
            assert ref_data["reference"]["state"] == 50.0

    @pytest.mark.asyncio
    async def test_older_reference_more_than_1_hour_before_oldest_import(self) -> None:
        """
        Test OLDER_REFERENCE when reference is more than 1 hour before oldest import.

        Timestamps:
            - t_oldest_db    : 08:00
            - t_newest_db    : 14:00
            - t_oldest_import: 12:00
            - t_newest_import: 14:00
            - Reference found: 10:00 (2 hours before oldest_import)

        This is not possible, as the value at 11:00 would have been found first.
        However, we test this to ensure the logic handles it correctly.
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        t_newest_db = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        ref_older_before_oldest = dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = {
                "start": ref_older_before_oldest,
                "sum": 75.0,
                "state": 75.0,
            }
            mock_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_error_reference_less_than_1_hour_before_oldest_import(self) -> None:
        """
        Test error when reference is less than 1 hour before oldest import.

        Timestamps:
            - t_oldest_db    : 11:00
            - t_newest_db    : 14:00
            - t_oldest_import: 12:00
            - t_newest_import: 14:00
            - Reference found: 11:30 (only 30 minutes before oldest_import - INVALID)
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        ref_too_recent = dt.datetime(2025, 1, 1, 11, 30, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_import,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = {
                "start": ref_too_recent,
                "sum": 95.0,
                "state": 95.0,
            }
            mock_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert ref_data is None
            assert error_msg is not None
            assert "sensor.test" in error_msg
            assert "less than 1 hour before oldest import" in error_msg


class TestProcessDeltaReferencesNewerReference:
    """Test cases for NEWER_REFERENCE scenarios."""

    @pytest.mark.asyncio
    async def test_newer_reference_at_exact_newest_import_timestamp(self) -> None:
        """
        Test NEWER_REFERENCE when reference exists at exact newest import timestamp.

        Timestamps:
            - t_oldest_db    : 12:00
            - t_newest_db    : 16:00
            - t_oldest_import: 12:00
            - t_newest_import: 14:00
            - Reference found: 14:00 (at newest_import)
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        t_newest_db = dt.datetime(2025, 1, 1, 16, 0, tzinfo=dt.UTC)
        ref_newer_at_newest = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        ref_for_overlap_check = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 150.0,
                "state": 150.0,
            }
            mock_before.side_effect = [None, ref_for_overlap_check]  # First call returns None, second call returns 14:00
            mock_after.return_value = {
                "start": ref_newer_at_newest,
                "sum": 110.0,
                "state": 110.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.NEWER_REFERENCE
            assert ref_data["reference"]["start"] == ref_newer_at_newest

    @pytest.mark.asyncio
    async def test_newer_reference_at_newest_import_timestamp(self) -> None:
        """
        Test NEWER_REFERENCE when reference is after newest import timestamp.

        Timestamps:
            - t_oldest_db    : 12:00
            - t_newest_db    : 16:00
            - t_oldest_import: 12:00
            - t_newest_import: 14:00
            - Reference found: 14:00 (at newest_import)
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        ref_newer_after_newest = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        ref_for_overlap_check = dt.datetime(2025, 1, 1, 15, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": dt.datetime(2025, 1, 1, 16, 0, tzinfo=dt.UTC),
                "sum": 150.0,
                "state": 150.0,
            }
            mock_before.side_effect = [None, ref_for_overlap_check]  # First call returns None, second call returns 15:00
            mock_after.return_value = {
                "start": ref_newer_after_newest,
                "sum": 125.0,
                "state": 125.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.NEWER_REFERENCE
            assert ref_data["reference"]["start"] == ref_newer_after_newest
            assert ref_data["reference"]["sum"] == 125.0
            assert ref_data["reference"]["state"] == 125.0


class TestProcessDeltaReferencesCombinedScenarios:
    """Test cases comparing different combinations of timestamps."""

    @pytest.mark.asyncio
    async def test_oldest_import_equal_to_oldest_db_prefer_older_reference(self) -> None:
        """
        Test when oldest_import equals oldest_db - prefer OLDER_REFERENCE if available.

        Timestamps:
            - t_oldest_db    : 12:00
            - t_newest_db    : 15:00
            - t_oldest_import: 12:00
            - t_newest_import: 14:00
            - Reference older found: 11:00 (1 hour before oldest_import)

        11:00 cannot be found if t_oldest_db is 12:00, but we test the logic here.
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        ref_older = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": dt.datetime(2025, 1, 1, 15, 0, tzinfo=dt.UTC),
                "sum": 120.0,
                "state": 120.0,
            }
            mock_before.return_value = {
                "start": ref_older,
                "sum": 80.0,
                "state": 80.0,
            }
            mock_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE
            assert ref_data["reference"]["start"] == ref_older

    @pytest.mark.asyncio
    async def test_newest_import_equal_to_newest_db_accept_at_timestamp(self) -> None:
        """
        Test when newest_import equals newest_db - reference must be at or before.

        Timestamps:
            - t_oldest_db    : 11:00
            - t_newest_db    : 14:00
            - t_oldest_import: 12:00
            - t_newest_import: 14:00
            - Reference newer at newest: 14:00 (at newest_import/newest_db)
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        ref_at_newest = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        ref_for_overlap_check = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_import,
                "sum": 120.0,
                "state": 120.0,
            }
            mock_before.side_effect = [None, ref_for_overlap_check]  # First call returns None, second call returns 14:00
            mock_after.return_value = {
                "start": ref_at_newest,
                "sum": 120.0,
                "state": 120.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.NEWER_REFERENCE
            assert ref_data["reference"]["start"] == ref_at_newest

    @pytest.mark.asyncio
    async def test_newest_import_more_than_1_hour_after_newest_db(self) -> None:
        """
        Test when newest_import is more than 1 hour after newest_db.

        Timestamps:
            - t_oldest_db    : 11:00
            - t_newest_db    : 14:00
            - t_oldest_import: 12:00
            - t_newest_import: 16:00 (2 hours after newest_db)
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 16, 0, tzinfo=dt.UTC)
        t_newest_db = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        t_ref_before = t_oldest_import - dt.timedelta(hours=1)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = {
                "start": t_ref_before,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert ref_data is not None
            assert error_msg is None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE
            assert ref_data["reference"]["start"] == t_ref_before

    @pytest.mark.asyncio
    async def test_oldest_import_more_than_1_hour_after_newest_db(self) -> None:
        """
        Test that import range can be completely newer than db range.

        Timestamps:
            - t_oldest_db    : 10:00
            - t_newest_db    : 11:00 (3 hours before oldest_import)
            - t_oldest_import: 14:00
            - t_newest_import: 16:00

        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 16, 0, tzinfo=dt.UTC)
        t_newest_db = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.UTC)
        ref_older_before_oldest = dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = {
                "start": ref_older_before_oldest,
                "sum": 50.0,
                "state": 50.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE
            assert ref_data["reference"]["start"] == t_oldest_import - dt.timedelta(hours=1)

    @pytest.mark.asyncio
    async def test_newest_import_before_oldest_db(self) -> None:
        """
        Test when newest_import is before oldest_db.

        Timestamps:
            - t_oldest_db    : 12:00
            - t_newest_db    : 14:00
            - t_oldest_import: 08:00
            - t_newest_import: 10:00
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 8, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.UTC)
        t_oldest_db = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC),
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = None
            mock_after.return_value = {
                "start": t_oldest_db,
                "sum": 50.0,
                "state": 50.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert ref_data is not None
            assert error_msg is None
            assert ref_data["ref_type"] == DeltaReferenceType.NEWER_REFERENCE
            assert ref_data["reference"]["start"] == t_newest_import


class TestProcessDeltaReferencesSpecialCases:
    """Test special cases and edge scenarios."""

    @pytest.mark.asyncio
    async def test_no_statistics_found_in_database(self) -> None:
        """
        Test error when no statistics exist in database for this entity.

        Timestamps:
            - t_oldest_import: 12:00
            - t_newest_import: 14:00
            - No database records exist

        Error: "No statistics found in database for this entity"
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = None  # No statistics
            mock_before.return_value = None
            mock_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert ref_data is None
            assert error_msg is not None
            assert "No statistics found in database for this entity" in error_msg
            assert "sensor.test" in error_msg

    @pytest.mark.asyncio
    async def test_no_reference_before_and_no_reference_after_error(self) -> None:
        """
        Test error when no OLDER_REFERENCE and no NEWER_REFERENCE found.

        Timestamps:
            - t_oldest_db    : 13:00 (too recent for OLDER)
            - t_newest_db    : 15:00 (no match for NEWER)
            - t_oldest_import: 12:00
            - t_newest_import: 16:00
            - No reference before oldest_import
            - No reference at/after newest_import

        Error: "imported timerange completely overlaps timerange in DB"
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 16, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": dt.datetime(2025, 1, 1, 15, 0, tzinfo=dt.UTC),
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = None  # No reference before oldest
            mock_after.return_value = None  # No reference at/after newest

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert ref_data is None
            assert error_msg is not None
            assert "imported timerange completely overlaps timerange in DB (cannot find reference before or after import)" in error_msg
            assert "sensor.test" in error_msg

    @pytest.mark.asyncio
    async def test_oldest_and_newest_import_are_same(self) -> None:
        """
        Test when oldest_import equals newest_import (single timestamp).

        Timestamps:
            - t_oldest_db    : 11:00
            - t_newest_db    : 13:00
            - t_oldest_import: 12:00
            - t_newest_import: 12:00 (same)
            - Reference older: 11:00
        """
        hass = MagicMock()
        t_timestamp = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        ref_older = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": dt.datetime(2025, 1, 1, 13, 0, tzinfo=dt.UTC),
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = {
                "start": ref_older,
                "sum": 80.0,
                "state": 80.0,
            }
            mock_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_timestamp,
                t_timestamp,
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE
            assert ref_data["reference"]["start"] == ref_older

    @pytest.mark.asyncio
    async def test_multiple_database_entries_retrieves_correct_reference(self) -> None:
        """
        Test that correct reference is selected from multiple DB entries.

        Timestamps:
            - t_oldest_db    : 10:00
            - t_newest_db    : 20:00
            - t_oldest_import: 12:00
            - t_newest_import: 14:00
            - Reference before: 11:00 (selected)
            - Reference after exists but before should be preferred
        """
        hass = MagicMock()
        t_oldest_import = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        t_newest_import = dt.datetime(2025, 1, 1, 14, 0, tzinfo=dt.UTC)
        ref_older = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.UTC)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_after,
        ):
            mock_newest.return_value = {
                "start": dt.datetime(2025, 1, 1, 20, 0, tzinfo=dt.UTC),
                "sum": 200.0,
                "state": 200.0,
            }
            mock_before.return_value = {
                "start": ref_older,
                "sum": 80.0,
                "state": 80.0,
            }
            # after should not be called if before succeeds
            mock_after.return_value = {
                "start": dt.datetime(2025, 1, 1, 15, 0, tzinfo=dt.UTC),
                "sum": 115.0,
                "state": 115.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass,
                "sensor.test",
                t_oldest_import,
                t_newest_import,
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE
            assert ref_data["reference"]["start"] == ref_older
            assert ref_data["reference"]["sum"] == 80.0
            assert ref_data["reference"]["state"] == 80.0
