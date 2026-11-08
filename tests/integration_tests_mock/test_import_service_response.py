"""Mock integration tests for the import statistics service response."""

import datetime as dt
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.import_service import check_entity_exists, import_stats, validate_entities_and_units


class TestImportServiceResponse:
    """Test that imports return concise status counts and skipped value counts."""

    @pytest.mark.asyncio
    async def test_import_stats_returns_imported_value_and_status_counts(self, caplog: pytest.LogCaptureFixture) -> None:
        """Return aggregate status counts rather than per-statistic status objects."""
        caplog.set_level(logging.INFO, logger="custom_components.import_statistics.import_service")
        hass = MagicMock()
        stats = {
            "custom:new": (
                {"statistic_id": "custom:new", "source": "custom"},
                [{"start": dt.datetime(2024, 1, 3, tzinfo=dt.UTC)}],
            ),
            "custom:existing": (
                {"statistic_id": "custom:existing", "source": "custom"},
                [{"start": dt.datetime(2024, 1, 2, tzinfo=dt.UTC)}],
            ),
            "custom:empty": ({"statistic_id": "custom:empty", "source": "custom"}, []),
        }

        with (
            patch("custom_components.import_statistics.import_service.validate_entities_and_units", new=AsyncMock()),
            patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_add,
            patch(
                "custom_components.import_statistics.import_service._get_newest_db_statistic",
                new=AsyncMock(
                    side_effect=lambda _hass, statistic_id: {
                        "custom:new": {"start": dt.datetime(2024, 1, 2, tzinfo=dt.UTC)},
                        "custom:existing": {"start": dt.datetime(2024, 1, 2, tzinfo=dt.UTC)},
                    }.get(statistic_id)
                ),
            ),
            patch(
                "custom_components.import_statistics.import_service.get_instance",
                return_value=MagicMock(async_block_till_done=AsyncMock()),
            ),
        ):
            result = await import_stats(hass, stats)

        assert result == {
            "imported_values": 2,
            "new_data": 1,
            "existing_data": 1,
            "no_data": 1,
        }
        assert mock_add.called
        assert "2 statistic values imported" in caplog.text

    @pytest.mark.asyncio
    async def test_import_stats_counts_skipped_values_when_ignoring_unknown_entities(self, tmp_path: Path) -> None:
        """Report skipped row count and statistic IDs when missing entities are ignored."""
        hass = SimpleNamespace(
            config=SimpleNamespace(config_dir=str(tmp_path)),
            states=MagicMock(),
        )
        hass.states.get.return_value = None
        stats = {
            "sensor.missing": (
                {"statistic_id": "sensor.missing", "source": "recorder"},
                [{"start": dt.datetime(2024, 1, 1, tzinfo=dt.UTC)}] * 3,
            ),
            "custom:energy": (
                {"statistic_id": "custom:energy", "source": "custom"},
                [{"start": dt.datetime(2024, 1, 1, tzinfo=dt.UTC)}] * 2,
            ),
        }

        with (
            patch("custom_components.import_statistics.import_service.validate_entities_and_units", new=AsyncMock()),
            patch("custom_components.import_statistics.import_service.async_add_external_statistics"),
            patch("custom_components.import_statistics.import_service._get_newest_db_statistic", new=AsyncMock(return_value=None)),
            patch(
                "custom_components.import_statistics.import_service.get_instance",
                return_value=MagicMock(async_block_till_done=AsyncMock()),
            ),
        ):
            result = await import_stats(hass, stats, ignore_unknown_entities=True)

        assert result == {
            "imported_values": 2,
            "new_data": 1,
            "existing_data": 0,
            "no_data": 0,
            "skipped_values": 3,
            "skipped_statistics": ["sensor.missing"],
        }

    def test_check_entity_exists_suggests_ignore_unknown_entities(self) -> None:
        """Missing recorder entities explain how to skip them."""
        hass = MagicMock()
        hass.states.get.return_value = None

        with pytest.raises(
            HomeAssistantError,
            match=r"Entity does not exist: 'sensor.missing'.*ignore_unknown_entities: true",
        ):
            check_entity_exists(hass, "sensor.missing")

    @pytest.mark.asyncio
    async def test_entity_validation_suggests_ignore_unknown_entities(self) -> None:
        """Entity validation errors tell users how to skip missing recorder entities."""
        hass = MagicMock()
        hass.states.get.return_value = None
        stats = {
            "sensor.missing": (
                {"statistic_id": "sensor.missing", "source": "recorder"},
                [{"start": 1}],
            )
        }
        recorder = MagicMock()
        recorder.async_add_executor_job = AsyncMock(return_value={})

        with (
            patch("custom_components.import_statistics.import_service.get_instance", return_value=recorder),
            patch("custom_components.import_statistics.import_service.get_metadata", return_value={}),
            pytest.raises(
                HomeAssistantError,
                match=r"Entity does not exist: 'sensor.missing'.*ignore_unknown_entities: true",
            ),
        ):
            await validate_entities_and_units(hass, stats)
