"""Mock integration tests for the import statistics service response."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.import_statistics.import_service import import_stats


class TestImportServiceResponse:
    """Test that import_stats returns the correct status per statistic."""

    @pytest.mark.asyncio
    async def test_import_stats_returns_new_data_status(self) -> None:
        """Test that a newer import is reported as 'new data'."""
        hass = MagicMock()
        metadata = {"statistic_id": "custom:energy", "source": "custom"}
        import_start = dt.datetime(2025, 1, 2, 12, 0, tzinfo=dt.UTC)
        db_start = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        statistics = [{"start": import_start, "sum": 10.0}]
        stats = {"custom:energy": (metadata, statistics)}

        with (
            patch("custom_components.import_statistics.import_service.validate_entities_and_units", new=AsyncMock()),
            patch(
                "custom_components.import_statistics.import_service._get_newest_db_statistic",
                new=AsyncMock(return_value={"start": db_start}),
            ),
            patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_add,
            patch(
                "custom_components.import_statistics.import_service.get_instance",
                return_value=MagicMock(async_block_till_done=AsyncMock()),
            ),
        ):
            result = await import_stats(hass, stats)

        assert result["results"]["custom:energy"]["status"] == "new data"
        assert result["results"]["custom:energy"]["newest_import_start"] == "2025-01-02T12:00:00+00:00"
        assert result["results"]["custom:energy"]["newest_db_start"] == "2025-01-01T12:00:00+00:00"
        assert mock_add.called

    @pytest.mark.asyncio
    async def test_import_stats_returns_existing_data_status(self) -> None:
        """Test that an older/equal import is reported as 'existing data'."""
        hass = MagicMock()
        metadata = {"statistic_id": "custom:energy", "source": "custom"}
        import_start = dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.UTC)
        db_start = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
        statistics = [{"start": import_start, "sum": 10.0}]
        stats = {"custom:energy": (metadata, statistics)}

        with (
            patch("custom_components.import_statistics.import_service.validate_entities_and_units", new=AsyncMock()),
            patch(
                "custom_components.import_statistics.import_service._get_newest_db_statistic",
                new=AsyncMock(return_value={"start": db_start}),
            ),
            patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_add,
            patch(
                "custom_components.import_statistics.import_service.get_instance",
                return_value=MagicMock(async_block_till_done=AsyncMock()),
            ),
        ):
            result = await import_stats(hass, stats)

        assert result["results"]["custom:energy"]["status"] == "existing data"
        assert result["results"]["custom:energy"]["newest_import_start"] == "2025-01-01T10:00:00+00:00"
        assert result["results"]["custom:energy"]["newest_db_start"] == "2025-01-01T12:00:00+00:00"
        assert mock_add.called
