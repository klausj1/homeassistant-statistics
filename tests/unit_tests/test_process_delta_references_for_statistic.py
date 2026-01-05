"""Unit tests for _process_delta_references_for_statistic function."""

import datetime as dt
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.import_statistics.helpers import DeltaReferenceType
from custom_components.import_statistics.import_service import _process_delta_references_for_statistic


# Test fixtures for timestamps
@pytest.fixture
def base_time():
    """Base UTC time for tests."""
    return dt.datetime(2025, 1, 15, 12, 0, 0, tzinfo=dt.UTC)


@pytest.fixture
def hass_mock():
    """Mock Home Assistant instance."""
    return AsyncMock()


class TestProcessDeltaReferencesNoStatisticsFound:
    """Test error case: No statistics found in database."""

    @pytest.mark.asyncio
    async def test_no_statistics_found_for_entity(self, hass_mock, base_time):
        """Should return error when no statistics exist for entity."""
        statistic_id = "sensor.temperature"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=5)

        with patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest:
            mock_newest.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert ref_data is None
            assert error_msg == "Entity 'sensor.temperature': No statistics found in database for this entity"
            mock_newest.assert_called_once_with(hass_mock, statistic_id)


class TestProcessDeltaReferencesNewerThanNewestDb:
    """Test error case: Importing newer than newest DB value."""

    @pytest.mark.asyncio
    async def test_import_newer_than_newest_db(self, hass_mock, base_time):
        """Should error when t_newest_import < t_newest_db (import is older than DB)."""
        # Timeline visualization (base_time = 12:00):
        #
        # Import|=========================|
        #       DB   |==================================================|
        #
        #       12:00 13:00       17:00                           22:00
        #
        # Note: "newer" means newer in time. Here t_newest_import (17:00) is NOT newer
        # than t_newest_db (22:00) - it's older. You cannot import data older than what exists.
        #
        # Oldest DB: 13:00 (oldest import + 1h, inferred from delta processing logic)
        # Newest DB: 22:00 (newest/furthest point in database)
        # Oldest Import: 12:00
        # Newest Import: 17:00 (newest/furthest point in import - OLDER than DB newest)
        # Oldest Reference: None
        # Newest Reference: None
        # ERROR: Import's newest point (17:00) is older than DB's newest point (22:00)
        statistic_id = "sensor.power"
        t_newest_db = base_time + dt.timedelta(hours=10)
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=5)

        with patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest:
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert ref_data is None
            assert "Importing values newer than the newest value in the database" in error_msg
            assert str(t_newest_db) in error_msg


class TestProcessDeltaReferencesOlderReference:
    """Test success case: Using OLDER_REFERENCE (reference is 1+ hour before oldest import)."""

    @pytest.mark.asyncio
    async def test_older_reference_exactly_1_hour_before(self, hass_mock, base_time):
        """Should accept OLDER_REFERENCE when exactly 1 hour before oldest import."""
        statistic_id = "sensor.energy"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=15)
        t_oldest_reference = base_time - dt.timedelta(hours=1)
        t_newest_db = base_time + dt.timedelta(hours=10)

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
                "start": t_oldest_reference,
                "sum": 50.0,
                "state": 50.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE
            assert ref_data["reference"]["start"] == t_oldest_reference
            assert ref_data["reference"]["sum"] == 50.0
            assert ref_data["reference"]["state"] == 50.0

    @pytest.mark.asyncio
    async def test_older_reference_2_hours_before(self, hass_mock, base_time):
        """Should accept OLDER_REFERENCE when more than 1 hour before."""
        statistic_id = "sensor.temperature"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=10)
        t_oldest_reference = base_time - dt.timedelta(hours=2)
        t_newest_db = base_time + dt.timedelta(hours=5)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 200.0,
                "state": 200.0,
            }
            mock_before.return_value = {
                "start": t_oldest_reference,
                "sum": 100.0,
                "state": 100.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_older_reference_less_than_1_hour_before_rejected(self, hass_mock, base_time):
        """Should reject when reference is less than 1 hour before oldest import."""
        statistic_id = "sensor.humidity"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=10)
        t_oldest_reference = base_time - dt.timedelta(minutes=30)  # Only 30 min before
        t_newest_db = base_time + dt.timedelta(hours=5)

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
                "start": t_oldest_reference,
                "sum": 50.0,
                "state": 50.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert ref_data is None
            assert "Reference is less than 1 hour before oldest import" in error_msg


class TestProcessDeltaReferencesCompletelyNewer:
    """Test error case: Imported timerange is completely newer than DB."""

    @pytest.mark.asyncio
    async def test_imported_timerange_completely_newer_than_db(self, hass_mock, base_time):
        """Should error when t_newest_db <= t_oldest_import and no older reference found."""
        statistic_id = "sensor.test"
        t_newest_db = base_time  # 12:00
        t_oldest_import = base_time + dt.timedelta(hours=1)  # 13:00 - after t_newest_db
        t_newest_import = base_time + dt.timedelta(hours=3)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = None  # No reference before oldest import

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert ref_data is None
            assert "imported timerange is completely newer than timerange in DB" in error_msg
            assert "database newest" in error_msg

    @pytest.mark.asyncio
    async def test_imported_timerange_equal_to_newest_db_no_reference(self, hass_mock, base_time):
        """Should error when t_newest_db == t_oldest_import and no older reference."""
        # TODO: Check if this is the desired behavior
        statistic_id = "sensor.power"
        t_newest_db = base_time
        t_oldest_import = base_time  # Equal to t_newest_db
        t_newest_import = base_time + dt.timedelta(hours=2)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert ref_data is None
            assert "imported timerange is completely newer than timerange in DB" in error_msg


class TestProcessDeltaReferencesNewerReference:
    """Test success case: Using NEWER_REFERENCE (reference at or after newest import)."""

    @pytest.mark.asyncio
    async def test_newer_reference_exactly_at_newest_import(self, hass_mock, base_time):
        """Should accept NEWER_REFERENCE when at newest import."""
        # Timeline visualization (base_time = 12:00):
        #
        # DB    |=========================|
        # Import|=========================|
        #
        #       12:00                 17:00
        #
        # Oldest DB: 12:00 (same as oldest import, since no mock_before)
        # Newest DB: 17:00
        # Oldest Import: 12:00
        # Newest Import: 17:00
        # Oldest Reference: None
        # Newest Reference: 17:00 (found at newest import)
        statistic_id = "sensor.temperature"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=5)
        t_newest_reference = base_time + dt.timedelta(hours=5)  # Exactly at newest import
        t_newest_db = base_time + dt.timedelta(hours=5)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 150.0,
                "state": 150.0,
            }
            mock_before.side_effect = [None, None]  # No reference before oldest or newest import
            mock_at_after.return_value = {
                "start": t_newest_reference,
                "sum": 120.0,
                "state": 120.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.NEWER_REFERENCE
            assert ref_data["reference"]["start"] == t_newest_reference

    @pytest.mark.asyncio
    async def test_newer_reference_1_hour_after_newest_import(self, hass_mock, base_time):
        """Should accept NEWER_REFERENCE when 1+ hour after newest import."""
        # Timeline visualization (base_time = 12:00):
        #
        # DB    |=========================|
        # Import|=========================|
        #
        #       12:00                 17:00      18:00
        #
        # Oldest DB: 12:00 (same as oldest import, since no mock_before)
        # Newest DB: 17:00
        # Oldest Import: 12:00
        # Newest Import: 17:00
        # Oldest Reference: None
        # Newest Reference: 18:00 (found 1 hour after newest import)
        statistic_id = "sensor.energy"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=5)
        t_newest_reference = base_time + dt.timedelta(hours=6)  # 1 hour after
        t_newest_db = base_time + dt.timedelta(hours=5)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 200.0,
                "state": 200.0,
            }
            mock_before.side_effect = [None, None]
            mock_at_after.return_value = {
                "start": t_newest_reference,
                "sum": 180.0,
                "state": 180.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.NEWER_REFERENCE

    @pytest.mark.asyncio
    async def test_reference_less_than_1_hour_before_newest_import_becomes_older_ref(self, hass_mock, base_time):
        """Should reject when reference is less than 1 hour before newest import."""
        statistic_id = "sensor.temperature"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=10)
        t_reference = base_time + dt.timedelta(hours=9, minutes=30)  # 30 min before newest
        t_newest_db = base_time + dt.timedelta(hours=8)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            # First call for before oldest_import, second call for before newest_import
            mock_before.side_effect = [
                None,
                {
                    "start": t_reference,
                    "sum": 90.0,
                    "state": 90.0,
                },
            ]
            mock_at_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert ref_data is None
            assert "Reference is less than 1 hour before newest import" in error_msg


class TestProcessDeltaReferencesCompletelyOlder:
    """Test error case: Imported timerange completely overlaps DB."""

    @pytest.mark.asyncio
    async def test_imported_timerange_completely_overlaps_no_reference(self, hass_mock, base_time):
        """
        Should error when no reference before or at/after newest import (design scenario #4).

        Error: "imported timerange completely overlaps timerange in DB (cannot find reference before or after import)"
        """
        statistic_id = "sensor.overlap_test"
        t_oldest_import = base_time - dt.timedelta(hours=10)
        t_newest_import = base_time + dt.timedelta(hours=5)
        t_newest_db = base_time

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]  # No reference before oldest or newest
            mock_at_after.return_value = None  # No reference at or after newest

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert ref_data is None
            assert "imported timerange completely overlaps timerange in DB" in error_msg
            assert "cannot find reference before or after import" in error_msg

    @pytest.mark.asyncio
    async def test_imported_timerange_completely_older_than_db(self, hass_mock, base_time):
        """Should error when no reference before newest import and no reference at/after."""
        statistic_id = "sensor.test"
        t_oldest_import = base_time - dt.timedelta(hours=5)
        t_newest_import = base_time + dt.timedelta(hours=2)
        t_newest_db = base_time

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]  # No reference before oldest or newest
            mock_at_after.return_value = None  # No reference at or after newest

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert ref_data is None
            assert "imported timerange completely overlaps timerange in DB" in error_msg
            assert "cannot find reference before or after import" in error_msg


class TestProcessDeltaReferencesComplexTimingScenarios:
    """Test complex combinations of timing relationships."""

    @pytest.mark.asyncio
    async def test_oldest_import_newer_than_newest_db_by_more_than_1_hour(self, hass_mock, base_time):
        """Test case: t_oldest_import is between t_newest_db - 3h and t_newest_db - 1h."""
        statistic_id = "sensor.complex1"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=5)
        t_newest_db = base_time + dt.timedelta(hours=3)  # t_newest_db is 3 hours after t_oldest_import
        t_reference_before_newest = base_time + dt.timedelta(hours=2)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            # First call for before oldest_import, second for before newest_import
            mock_before.side_effect = [
                None,
                {
                    "start": t_reference_before_newest,
                    "sum": 80.0,
                    "state": 80.0,
                },
            ]
            mock_at_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_oldest_import_exactly_1_hour_before_newest_db_no_reference(self, hass_mock, base_time):
        """Test: t_oldest_import is exactly 1 hour before t_newest_db, no older reference."""
        statistic_id = "sensor.complex2"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=3)
        t_newest_db = base_time + dt.timedelta(hours=1)
        t_reference_before_newest = base_time + dt.timedelta(hours=0.5)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [
                None,
                {
                    "start": t_reference_before_newest,
                    "sum": 90.0,
                    "state": 90.0,
                },
            ]
            mock_at_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            # Should return OLDER_REFERENCE since we have a reference before newest
            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_oldest_newest_import_equal(self, hass_mock, base_time):
        """Test special case: t_oldest_import == t_newest_import (single hour import)."""
        statistic_id = "sensor.single_hour"
        t_import = base_time
        t_oldest_import = t_import
        t_newest_import = t_import
        t_reference_before = base_time - dt.timedelta(hours=1)
        t_newest_db = base_time

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
                "start": t_reference_before,
                "sum": 50.0,
                "state": 50.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_reference_1_hour_after_newest_import(self, hass_mock, base_time):
        """Test: reference is exactly 1 hour after newest import."""
        statistic_id = "sensor.future_ref"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=5)
        t_reference = base_time + dt.timedelta(hours=6)  # 1 hour after newest
        t_newest_db = base_time + dt.timedelta(hours=5)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]
            mock_at_after.return_value = {
                "start": t_reference,
                "sum": 110.0,
                "state": 110.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.NEWER_REFERENCE

    @pytest.mark.asyncio
    async def test_reference_2_hours_after_newest_import(self, hass_mock, base_time):
        """Test: reference is far in future (2 hours) after newest import."""
        statistic_id = "sensor.far_future"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=6)
        t_reference = base_time + dt.timedelta(hours=8)  # 2 hours after
        t_newest_db = base_time + dt.timedelta(hours=6)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]
            mock_at_after.return_value = {
                "start": t_reference,
                "sum": 115.0,
                "state": 115.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.NEWER_REFERENCE


class TestProcessDeltaReferencesTimingMatrixComprehensive:
    """Comprehensive test matrix comparing all combinations of t_oldest_import vs database times."""

    @pytest.mark.asyncio
    async def test_matrix_oldest_import_equal_newest_db_with_older_ref(self, hass_mock, base_time):
        """t_oldest_import == t_newest_db, with older reference available."""
        statistic_id = "sensor.matrix1"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=5)
        t_newest_db = base_time  # Same as oldest_import
        t_reference = base_time - dt.timedelta(hours=2)

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
                "start": t_reference,
                "sum": 50.0,
                "state": 50.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_matrix_oldest_import_between_db_times_with_refs(self, hass_mock, base_time):
        """t_oldest_import is between database times, references available."""
        statistic_id = "sensor.matrix2"
        t_db_oldest = base_time - dt.timedelta(hours=2)
        t_oldest_import = base_time  # Between t_db_oldest and t_newest_import
        t_newest_import = base_time + dt.timedelta(hours=15)
        t_newest_db = base_time + dt.timedelta(hours=10)
        t_ref_before_oldest = base_time - dt.timedelta(hours=3)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 200.0,
                "state": 200.0,
            }
            mock_before.return_value = {
                "start": t_ref_before_oldest,
                "sum": 100.0,
                "state": 100.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_matrix_newest_import_equal_newest_db(self, hass_mock, base_time):
        """t_newest_import == t_newest_db with newer reference at that point."""
        statistic_id = "sensor.matrix3"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=5)
        t_newest_db = base_time + dt.timedelta(hours=5)  # Same as newest_import
        t_reference = base_time + dt.timedelta(hours=5)  # Exactly at both

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]
            mock_at_after.return_value = {
                "start": t_reference,
                "sum": 100.0,
                "state": 100.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.NEWER_REFERENCE

    @pytest.mark.asyncio
    async def test_matrix_newest_import_older_than_newest_db_by_1h(self, hass_mock, base_time):
        """t_newest_import is 1 hour older than t_newest_db."""
        statistic_id = "sensor.matrix4"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=5)
        t_newest_db = base_time + dt.timedelta(hours=5)  # Same as newest_import
        t_ref_before = base_time + dt.timedelta(hours=2)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [
                None,
                {
                    "start": t_ref_before,
                    "sum": 80.0,
                    "state": 80.0,
                },
            ]
            mock_at_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_matrix_newest_import_newer_than_newest_db_by_2h(self, hass_mock, base_time):
        """t_newest_import is 2 hours newer than t_newest_db."""
        statistic_id = "sensor.matrix5"
        t_oldest_import = base_time
        t_newest_import = base_time + dt.timedelta(hours=7)
        t_newest_db = base_time + dt.timedelta(hours=5)  # 2 hours before newest_import
        t_ref_after = base_time + dt.timedelta(hours=8)

        with (
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic") as mock_newest,
            patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before,
            patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after,
        ):
            mock_newest.return_value = {
                "start": t_newest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]
            mock_at_after.return_value = {
                "start": t_ref_after,
                "sum": 120.0,
                "state": 120.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(hass_mock, statistic_id, t_oldest_import, t_newest_import)

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.NEWER_REFERENCE
