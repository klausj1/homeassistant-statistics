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
        t_youngest_import = base_time + dt.timedelta(hours=5)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest:
            mock_youngest.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert ref_data is None
            assert error_msg == "Entity 'sensor.temperature': No statistics found in database for this entity"
            mock_youngest.assert_called_once_with(hass_mock, statistic_id)


class TestProcessDeltaReferencesYoungerThanYoungestDb:
    """Test error case: Importing younger than youngest DB value."""

    @pytest.mark.asyncio
    async def test_import_younger_than_youngest_db(self, hass_mock, base_time):
        """Should error when t_youngest_import < t_youngest_db."""
        statistic_id = "sensor.power"
        t_youngest_db = base_time + dt.timedelta(hours=10)
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=5)  # Younger than DB

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert ref_data is None
            assert "Importing values younger than the youngest value in the database" in error_msg
            assert str(t_youngest_db) in error_msg


class TestProcessDeltaReferencesOlderReference:
    """Test success case: Using OLDER_REFERENCE (reference is 1+ hour before oldest import)."""

    @pytest.mark.asyncio
    async def test_older_reference_exactly_1_hour_before(self, hass_mock, base_time):
        """Should accept OLDER_REFERENCE when exactly 1 hour before oldest import."""
        statistic_id = "sensor.energy"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=15)
        t_oldest_reference = base_time - dt.timedelta(hours=1)
        t_youngest_db = base_time + dt.timedelta(hours=10)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = {
                "start": t_oldest_reference,
                "sum": 50.0,
                "state": 50.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

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
        t_youngest_import = base_time + dt.timedelta(hours=10)
        t_oldest_reference = base_time - dt.timedelta(hours=2)
        t_youngest_db = base_time + dt.timedelta(hours=5)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 200.0,
                "state": 200.0,
            }
            mock_before.return_value = {
                "start": t_oldest_reference,
                "sum": 100.0,
                "state": 100.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_older_reference_less_than_1_hour_before_rejected(self, hass_mock, base_time):
        """Should reject when reference is less than 1 hour before oldest import."""
        statistic_id = "sensor.humidity"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=10)
        t_oldest_reference = base_time - dt.timedelta(minutes=30)  # Only 30 min before
        t_youngest_db = base_time + dt.timedelta(hours=5)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = {
                "start": t_oldest_reference,
                "sum": 50.0,
                "state": 50.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert ref_data is None
            assert "Reference is less than 1 hour before oldest import" in error_msg


class TestProcessDeltaReferencesCompletelyNewer:
    """Test error case: Imported timerange is completely newer than DB."""

    @pytest.mark.asyncio
    async def test_imported_timerange_completely_newer_than_db(self, hass_mock, base_time):
        """Should error when t_youngest_db <= t_oldest_import and no older reference found."""
        statistic_id = "sensor.test"
        t_youngest_db = base_time  # 12:00
        t_oldest_import = base_time + dt.timedelta(hours=1)  # 13:00 - after t_youngest_db
        t_youngest_import = base_time + dt.timedelta(hours=3)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = None  # No reference before oldest import

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert ref_data is None
            assert "imported timerange is completely newer than timerange in DB" in error_msg
            assert "database youngest" in error_msg

    @pytest.mark.asyncio
    async def test_imported_timerange_equal_to_youngest_db_no_reference(self, hass_mock, base_time):
        """Should error when t_youngest_db == t_oldest_import and no older reference."""
        # ToDo: Check if this is the desired behavior
        statistic_id = "sensor.power"
        t_youngest_db = base_time
        t_oldest_import = base_time  # Equal to t_youngest_db
        t_youngest_import = base_time + dt.timedelta(hours=2)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert ref_data is None
            assert "imported timerange is completely newer than timerange in DB" in error_msg


class TestProcessDeltaReferencesYoungerReference:
    """Test success case: Using YOUNGER_REFERENCE (reference at or after youngest import)."""

    @pytest.mark.asyncio
    async def test_younger_reference_exactly_at_youngest_import(self, hass_mock, base_time):
        """Should accept YOUNGER_REFERENCE when at youngest import."""
        statistic_id = "sensor.temperature"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=5)
        t_youngest_reference = base_time + dt.timedelta(hours=5)  # Exactly at youngest import
        t_youngest_db = base_time + dt.timedelta(hours=5)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 150.0,
                "state": 150.0,
            }
            mock_before.side_effect = [None, None]  # No reference before oldest or youngest import
            mock_at_after.return_value = {
                "start": t_youngest_reference,
                "sum": 120.0,
                "state": 120.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.YOUNGER_REFERENCE
            assert ref_data["reference"]["start"] == t_youngest_reference

    @pytest.mark.asyncio
    async def test_younger_reference_1_hour_after_youngest_import(self, hass_mock, base_time):
        """Should accept YOUNGER_REFERENCE when 1+ hour after youngest import."""
        statistic_id = "sensor.energy"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=5)
        t_youngest_reference = base_time + dt.timedelta(hours=6)  # 1 hour after
        t_youngest_db = base_time + dt.timedelta(hours=5)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 200.0,
                "state": 200.0,
            }
            mock_before.side_effect = [None, None]
            mock_at_after.return_value = {
                "start": t_youngest_reference,
                "sum": 180.0,
                "state": 180.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.YOUNGER_REFERENCE

    @pytest.mark.asyncio
    async def test_reference_less_than_1_hour_before_youngest_import_becomes_older_ref(self, hass_mock, base_time):
        """Should reject when reference is less than 1 hour before youngest import."""
        statistic_id = "sensor.temperature"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=10)
        t_reference = base_time + dt.timedelta(hours=9, minutes=30)  # 30 min before youngest
        t_youngest_db = base_time + dt.timedelta(hours=8)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            # First call for before oldest_import, second call for before youngest_import
            mock_before.side_effect = [None, {
                "start": t_reference,
                "sum": 90.0,
                "state": 90.0,
            }]
            mock_at_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert ref_data is None
            assert "Reference is less than 1 hour before youngest import" in error_msg


class TestProcessDeltaReferencesCompletelyOlder:
    """Test error case: Imported timerange completely overlaps DB."""

    @pytest.mark.asyncio
    async def test_imported_timerange_completely_overlaps_no_reference(self, hass_mock, base_time):
        """Should error when no reference before or at/after youngest import (design scenario #4).

        Error: "imported timerange completely overlaps timerange in DB (cannot find reference before or after import)"
        """
        statistic_id = "sensor.overlap_test"
        t_oldest_import = base_time - dt.timedelta(hours=10)
        t_youngest_import = base_time + dt.timedelta(hours=5)
        t_youngest_db = base_time

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]  # No reference before oldest or youngest
            mock_at_after.return_value = None  # No reference at or after youngest

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert ref_data is None
            assert "imported timerange completely overlaps timerange in DB" in error_msg
            assert "cannot find reference before or after import" in error_msg

    @pytest.mark.asyncio
    async def test_imported_timerange_completely_older_than_db(self, hass_mock, base_time):
        """Should error when no reference before youngest import and no reference at/after."""
        statistic_id = "sensor.test"
        t_oldest_import = base_time - dt.timedelta(hours=5)
        t_youngest_import = base_time + dt.timedelta(hours=2)
        t_youngest_db = base_time

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]  # No reference before oldest or youngest
            mock_at_after.return_value = None  # No reference at or after youngest

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert ref_data is None
            assert "imported timerange completely overlaps timerange in DB" in error_msg
            assert "cannot find reference before or after import" in error_msg


class TestProcessDeltaReferencesComplexTimingScenarios:
    """Test complex combinations of timing relationships."""

    @pytest.mark.asyncio
    async def test_oldest_import_younger_than_youngest_db_by_more_than_1_hour(self, hass_mock, base_time):
        """Test case: t_oldest_import is between t_youngest_db - 3h and t_youngest_db - 1h."""
        statistic_id = "sensor.complex1"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=5)
        t_youngest_db = base_time + dt.timedelta(hours=3)  # t_youngest_db is 3 hours after t_oldest_import
        t_reference_before_youngest = base_time + dt.timedelta(hours=2)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            # First call for before oldest_import, second for before youngest_import
            mock_before.side_effect = [None, {
                "start": t_reference_before_youngest,
                "sum": 80.0,
                "state": 80.0,
            }]
            mock_at_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_oldest_import_exactly_1_hour_before_youngest_db_no_reference(self, hass_mock, base_time):
        """Test: t_oldest_import is exactly 1 hour before t_youngest_db, no older reference."""
        statistic_id = "sensor.complex2"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=3)
        t_youngest_db = base_time + dt.timedelta(hours=1)
        t_reference_before_youngest = base_time + dt.timedelta(hours=0.5)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, {
                "start": t_reference_before_youngest,
                "sum": 90.0,
                "state": 90.0,
            }]
            mock_at_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            # Should return OLDER_REFERENCE since we have a reference before youngest
            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_oldest_youngest_import_equal(self, hass_mock, base_time):
        """Test special case: t_oldest_import == t_youngest_import (single hour import)."""
        statistic_id = "sensor.single_hour"
        t_import = base_time
        t_oldest_import = t_import
        t_youngest_import = t_import
        t_reference_before = base_time - dt.timedelta(hours=1)
        t_youngest_db = base_time

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = {
                "start": t_reference_before,
                "sum": 50.0,
                "state": 50.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_reference_1_hour_after_youngest_import(self, hass_mock, base_time):
        """Test: reference is exactly 1 hour after youngest import."""
        statistic_id = "sensor.future_ref"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=5)
        t_reference = base_time + dt.timedelta(hours=6)  # 1 hour after youngest
        t_youngest_db = base_time + dt.timedelta(hours=5)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]
            mock_at_after.return_value = {
                "start": t_reference,
                "sum": 110.0,
                "state": 110.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.YOUNGER_REFERENCE

    @pytest.mark.asyncio
    async def test_reference_2_hours_after_youngest_import(self, hass_mock, base_time):
        """Test: reference is far in future (2 hours) after youngest import."""
        statistic_id = "sensor.far_future"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=6)
        t_reference = base_time + dt.timedelta(hours=8)  # 2 hours after
        t_youngest_db = base_time + dt.timedelta(hours=6)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]
            mock_at_after.return_value = {
                "start": t_reference,
                "sum": 115.0,
                "state": 115.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.YOUNGER_REFERENCE


class TestProcessDeltaReferencesTimingMatrixComprehensive:
    """Comprehensive test matrix comparing all combinations of t_oldest_import vs database times."""

    @pytest.mark.asyncio
    async def test_matrix_oldest_import_equal_youngest_db_with_older_ref(self, hass_mock, base_time):
        """t_oldest_import == t_youngest_db, with older reference available."""
        statistic_id = "sensor.matrix1"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=5)
        t_youngest_db = base_time  # Same as oldest_import
        t_reference = base_time - dt.timedelta(hours=2)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.return_value = {
                "start": t_reference,
                "sum": 50.0,
                "state": 50.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_matrix_oldest_import_between_db_times_with_refs(self, hass_mock, base_time):
        """t_oldest_import is between database times, references available."""
        statistic_id = "sensor.matrix2"
        t_db_oldest = base_time - dt.timedelta(hours=2)
        t_oldest_import = base_time  # Between t_db_oldest and t_youngest_import
        t_youngest_import = base_time + dt.timedelta(hours=15)
        t_youngest_db = base_time + dt.timedelta(hours=10)
        t_ref_before_oldest = base_time - dt.timedelta(hours=3)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 200.0,
                "state": 200.0,
            }
            mock_before.return_value = {
                "start": t_ref_before_oldest,
                "sum": 100.0,
                "state": 100.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_matrix_youngest_import_equal_youngest_db(self, hass_mock, base_time):
        """t_youngest_import == t_youngest_db with younger reference at that point."""
        statistic_id = "sensor.matrix3"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=5)
        t_youngest_db = base_time + dt.timedelta(hours=5)  # Same as youngest_import
        t_reference = base_time + dt.timedelta(hours=5)  # Exactly at both

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]
            mock_at_after.return_value = {
                "start": t_reference,
                "sum": 100.0,
                "state": 100.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.YOUNGER_REFERENCE

    @pytest.mark.asyncio
    async def test_matrix_youngest_import_older_than_youngest_db_by_1h(self, hass_mock, base_time):
        """t_youngest_import is 1 hour older than t_youngest_db."""
        statistic_id = "sensor.matrix4"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=5)
        t_youngest_db = base_time + dt.timedelta(hours=5)  # Same as youngest_import
        t_ref_before = base_time + dt.timedelta(hours=2)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, {
                "start": t_ref_before,
                "sum": 80.0,
                "state": 80.0,
            }]
            mock_at_after.return_value = None

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.OLDER_REFERENCE

    @pytest.mark.asyncio
    async def test_matrix_youngest_import_newer_than_youngest_db_by_2h(self, hass_mock, base_time):
        """t_youngest_import is 2 hours newer than t_youngest_db."""
        statistic_id = "sensor.matrix5"
        t_oldest_import = base_time
        t_youngest_import = base_time + dt.timedelta(hours=7)
        t_youngest_db = base_time + dt.timedelta(hours=5)  # 2 hours before youngest_import
        t_ref_after = base_time + dt.timedelta(hours=8)

        with patch("custom_components.import_statistics.import_service._get_youngest_db_statistic") as mock_youngest, \
             patch("custom_components.import_statistics.import_service._get_reference_before_timestamp") as mock_before, \
             patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp") as mock_at_after:
            mock_youngest.return_value = {
                "start": t_youngest_db,
                "sum": 100.0,
                "state": 100.0,
            }
            mock_before.side_effect = [None, None]
            mock_at_after.return_value = {
                "start": t_ref_after,
                "sum": 120.0,
                "state": 120.0,
            }

            ref_data, error_msg = await _process_delta_references_for_statistic(
                hass_mock, statistic_id, t_oldest_import, t_youngest_import
            )

            assert error_msg is None
            assert ref_data is not None
            assert ref_data["ref_type"] == DeltaReferenceType.YOUNGER_REFERENCE
