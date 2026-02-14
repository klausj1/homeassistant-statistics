"""Integration tests for export_inventory service."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.export_inventory_database_access import (
    InventoryData,
    StatisticAggregates,
    StatisticMetadataRow,
)
from custom_components.import_statistics.export_inventory_service import handle_export_inventory_impl


def _create_mock_hass(config_dir: str) -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.config = MagicMock()
    hass.config.config_dir = config_dir
    hass.config.time_zone = "UTC"
    return hass


def _create_service_call(filename: str, delimiter: str | None = "\t", timezone: str | None = None) -> ServiceCall:
    """Create a mock service call."""
    call = MagicMock(spec=ServiceCall)
    data = {"filename": filename}
    if delimiter is not None:
        data["delimiter"] = delimiter
    if timezone:
        data["timezone_identifier"] = timezone
    call.data = MagicMock()
    call.data.get = lambda key, default=None: data.get(key, default)
    return call


def _create_inventory_data(
    metadata_rows: list[StatisticMetadataRow] | None = None,
    entity_registry_ids: set[str] | None = None,
    deleted_entity_orphan_timestamps: dict[str, float | None] | None = None,
    stats_data: tuple[dict[int, StatisticAggregates], dict[str, int]] | None = None,
) -> InventoryData:
    """Create mock inventory data."""
    aggregates, id_mapping = stats_data if stats_data is not None else ({}, {})
    return InventoryData(
        metadata_rows=metadata_rows or [],
        entity_registry_ids=entity_registry_ids or set(),
        deleted_entity_orphan_timestamps=deleted_entity_orphan_timestamps or {},
        aggregates=aggregates,
        id_mapping=id_mapping,
    )


class TestExportInventoryService:
    """Tests for handle_export_inventory_impl."""

    @pytest.mark.asyncio
    async def test_export_inventory_infers_delimiter_when_omitted(self) -> None:
        """Test inventory export infers delimiter from filename when omitted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mock_hass(tmpdir)
            call = _create_service_call("inventory.csv", delimiter=None)

            metadata_rows = [
                StatisticMetadataRow("sensor.temperature", "°C", "recorder", has_sum=False),
            ]
            entity_registry_ids = {"sensor.temperature"}
            aggregates = {1: StatisticAggregates(1, 100, 1704067200.0, 1704153600.0)}
            id_mapping = {"sensor.temperature": 1}
            inventory_data = _create_inventory_data(metadata_rows, entity_registry_ids, stats_data=(aggregates, id_mapping))

            mock_recorder = MagicMock()
            mock_recorder.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

            with (
                patch("custom_components.import_statistics.export_inventory_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.export_inventory_service.fetch_inventory_data", return_value=inventory_data),
            ):
                await handle_export_inventory_impl(hass, call)

            output_file = Path(tmpdir) / "inventory.csv"
            assert output_file.exists()
            content = output_file.read_text(encoding="utf-8-sig")
            header_line = next(line for line in content.split("\n") if line.startswith("statistic_id"))
            assert "," in header_line

    @pytest.mark.asyncio
    async def test_export_inventory_rejects_unsupported_extension(self) -> None:
        """Test inventory export rejects unsupported extensions like .txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mock_hass(tmpdir)
            call = _create_service_call("inventory.txt")

            with pytest.raises(HomeAssistantError, match="Unsupported filename extension"):
                await handle_export_inventory_impl(hass, call)

    @pytest.mark.asyncio
    async def test_export_inventory_happy_path(self) -> None:
        """Test successful inventory export with valid data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mock_hass(tmpdir)
            call = _create_service_call("inventory.tsv")

            # Create mock inventory data
            metadata_rows = [
                StatisticMetadataRow("sensor.temperature", "°C", "recorder", has_sum=False),
                StatisticMetadataRow("sensor.energy", "kWh", "recorder", has_sum=True),
            ]
            entity_registry_ids = {"sensor.temperature", "sensor.energy"}
            aggregates = {
                1: StatisticAggregates(1, 100, 1704067200.0, 1704153600.0),  # 2024-01-01 00:00 to 2024-01-02 00:00
                2: StatisticAggregates(2, 200, 1704067200.0, 1704240000.0),  # 2024-01-01 00:00 to 2024-01-03 00:00
            }
            id_mapping = {"sensor.temperature": 1, "sensor.energy": 2}
            inventory_data = _create_inventory_data(metadata_rows, entity_registry_ids, stats_data=(aggregates, id_mapping))

            mock_recorder = MagicMock()
            mock_recorder.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

            with (
                patch("custom_components.import_statistics.export_inventory_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.export_inventory_service.fetch_inventory_data", return_value=inventory_data),
            ):
                await handle_export_inventory_impl(hass, call)

            # Verify file was created
            output_file = Path(tmpdir) / "inventory.tsv"
            assert output_file.exists()

            # Verify content (utf-8-sig to handle BOM)
            content = output_file.read_text(encoding="utf-8-sig")
            lines = content.strip().split("\n")

            # Check summary lines
            assert lines[0].startswith("# Total statistics: 2")
            assert any("# Measurements: 1" in line for line in lines)
            assert any("# Counters: 1" in line for line in lines)
            assert any("# Total samples: 300" in line for line in lines)

            # Check header
            header_line = next(line for line in lines if line.startswith("statistic_id"))
            assert "unit_of_measurement" in header_line
            assert "category" in header_line
            assert "type" in header_line

            # Check data rows
            assert any("sensor.temperature" in line for line in lines)
            assert any("sensor.energy" in line for line in lines)

    @pytest.mark.asyncio
    async def test_export_inventory_no_long_term_statistics(self) -> None:
        """Test error when no long-term statistics exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mock_hass(tmpdir)
            call = _create_service_call("inventory.tsv")

            # Metadata exists but no aggregates (no long-term data)
            metadata_rows = [
                StatisticMetadataRow("sensor.temperature", "°C", "recorder", has_sum=False),
            ]
            inventory_data = _create_inventory_data(metadata_rows=metadata_rows)

            mock_recorder = MagicMock()

            with (
                patch("custom_components.import_statistics.export_inventory_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.export_inventory_service.fetch_inventory_data", return_value=inventory_data),
                pytest.raises(HomeAssistantError, match="No long-term statistics found"),
            ):
                await handle_export_inventory_impl(hass, call)

    @pytest.mark.asyncio
    async def test_export_inventory_no_statistics_at_all(self) -> None:
        """Test error when no statistics exist in database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mock_hass(tmpdir)
            call = _create_service_call("inventory.tsv")

            # Empty database
            inventory_data = _create_inventory_data()

            mock_recorder = MagicMock()

            with (
                patch("custom_components.import_statistics.export_inventory_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.export_inventory_service.fetch_inventory_data", return_value=inventory_data),
                pytest.raises(HomeAssistantError, match="No statistics found"),
            ):
                await handle_export_inventory_impl(hass, call)

    @pytest.mark.asyncio
    async def test_export_inventory_invalid_timezone(self) -> None:
        """Test error with invalid timezone identifier."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mock_hass(tmpdir)
            call = _create_service_call("inventory.tsv", timezone="Invalid/Timezone")

            mock_recorder = MagicMock()

            with (
                patch("custom_components.import_statistics.export_inventory_service.get_instance", return_value=mock_recorder),
                pytest.raises(HomeAssistantError, match="Invalid timezone"),
            ):
                await handle_export_inventory_impl(hass, call)

    @pytest.mark.asyncio
    async def test_export_inventory_classification_active_deleted_external(self) -> None:
        """Test correct classification of Active, Deleted, and External statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mock_hass(tmpdir)
            call = _create_service_call("inventory.tsv")

            metadata_rows = [
                StatisticMetadataRow("sensor.active", "°C", "recorder", has_sum=False),  # Active
                StatisticMetadataRow("sensor.deleted", "°C", "recorder", has_sum=False),  # Deleted
                StatisticMetadataRow("energy:external", "kWh", "energy", has_sum=True),  # External
            ]
            entity_registry_ids = {"sensor.active"}
            deleted_entity_orphan_timestamps = {"sensor.deleted": None}
            aggregates = {
                1: StatisticAggregates(1, 10, 1704067200.0, 1704067200.0),
                2: StatisticAggregates(2, 20, 1704067200.0, 1704067200.0),
                3: StatisticAggregates(3, 30, 1704067200.0, 1704067200.0),
            }
            id_mapping = {"sensor.active": 1, "sensor.deleted": 2, "energy:external": 3}
            inventory_data = _create_inventory_data(
                metadata_rows,
                entity_registry_ids,
                deleted_entity_orphan_timestamps,
                stats_data=(aggregates, id_mapping),
            )

            mock_recorder = MagicMock()
            mock_recorder.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

            with (
                patch("custom_components.import_statistics.export_inventory_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.export_inventory_service.fetch_inventory_data", return_value=inventory_data),
            ):
                await handle_export_inventory_impl(hass, call)

            output_file = Path(tmpdir) / "inventory.tsv"
            content = output_file.read_text(encoding="utf-8-sig")

            # Check classifications
            assert "Active" in content
            assert "Orphan" in content
            assert "External" in content

            # Check summary counts
            assert "# Active statistics: 1" in content
            assert "# Orphan statistics: 1" in content
            assert "# External statistics: 1" in content

    @pytest.mark.asyncio
    async def test_export_inventory_type_classification(self) -> None:
        """Test correct classification of Measurement and Counter types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mock_hass(tmpdir)
            call = _create_service_call("inventory.tsv")

            metadata_rows = [
                StatisticMetadataRow("sensor.temperature", "°C", "recorder", has_sum=False),  # Measurement
                StatisticMetadataRow("sensor.energy", "kWh", "recorder", has_sum=True),  # Counter
            ]
            entity_registry_ids = {"sensor.temperature", "sensor.energy"}
            aggregates = {
                1: StatisticAggregates(1, 10, 1704067200.0, 1704067200.0),
                2: StatisticAggregates(2, 20, 1704067200.0, 1704067200.0),
            }
            id_mapping = {"sensor.temperature": 1, "sensor.energy": 2}
            inventory_data = _create_inventory_data(metadata_rows, entity_registry_ids, stats_data=(aggregates, id_mapping))

            mock_recorder = MagicMock()
            mock_recorder.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

            with (
                patch("custom_components.import_statistics.export_inventory_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.export_inventory_service.fetch_inventory_data", return_value=inventory_data),
            ):
                await handle_export_inventory_impl(hass, call)

            output_file = Path(tmpdir) / "inventory.tsv"
            content = output_file.read_text(encoding="utf-8-sig")

            # Check type classifications
            assert "Measurement" in content
            assert "Counter" in content

            # Check summary counts
            assert "# Measurements: 1" in content
            assert "# Counters: 1" in content

    @pytest.mark.asyncio
    async def test_export_inventory_custom_timezone(self) -> None:
        """Test export with custom timezone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mock_hass(tmpdir)
            call = _create_service_call("inventory.tsv", timezone="Europe/Paris")

            metadata_rows = [
                StatisticMetadataRow("sensor.temperature", "°C", "recorder", has_sum=False),
            ]
            entity_registry_ids = {"sensor.temperature"}
            # 2024-01-15 12:00:00 UTC = 2024-01-15 13:00:00 Paris
            aggregates = {1: StatisticAggregates(1, 10, 1705320000.0, 1705320000.0)}
            id_mapping = {"sensor.temperature": 1}
            inventory_data = _create_inventory_data(metadata_rows, entity_registry_ids, stats_data=(aggregates, id_mapping))

            mock_recorder = MagicMock()
            mock_recorder.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

            with (
                patch("custom_components.import_statistics.export_inventory_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.export_inventory_service.fetch_inventory_data", return_value=inventory_data),
            ):
                await handle_export_inventory_impl(hass, call)

            output_file = Path(tmpdir) / "inventory.tsv"
            content = output_file.read_text(encoding="utf-8-sig")

            # Timestamps should be in Paris timezone (UTC+1 in January)
            assert "2024-01-15 13:00" in content

    @pytest.mark.asyncio
    async def test_export_inventory_orphan_classification(self) -> None:
        """Test correct classification of Orphan statistics (last state is NULL)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mock_hass(tmpdir)
            call = _create_service_call("inventory.tsv")

            metadata_rows = [
                StatisticMetadataRow("sensor.active", "°C", "recorder", has_sum=False),  # Active
                StatisticMetadataRow("sensor.orphaned", "kWh", "recorder", has_sum=True),  # Orphan
                StatisticMetadataRow("sensor.deleted", "W", "recorder", has_sum=False),  # Deleted
                StatisticMetadataRow("energy:external", "kWh", "energy", has_sum=True),  # External
            ]
            entity_registry_ids = {"sensor.active"}
            deleted_entity_orphan_timestamps = {"sensor.orphaned": 1704067200.0, "sensor.deleted": None}
            aggregates = {
                1: StatisticAggregates(1, 10, 1704067200.0, 1704067200.0),
                2: StatisticAggregates(2, 20, 1704067200.0, 1704067200.0),
                3: StatisticAggregates(3, 30, 1704067200.0, 1704067200.0),
                4: StatisticAggregates(4, 40, 1704067200.0, 1704067200.0),
            }
            id_mapping = {"sensor.active": 1, "sensor.orphaned": 2, "sensor.deleted": 3, "energy:external": 4}
            inventory_data = _create_inventory_data(
                metadata_rows,
                entity_registry_ids,
                deleted_entity_orphan_timestamps,
                stats_data=(aggregates, id_mapping),
            )

            mock_recorder = MagicMock()
            mock_recorder.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

            with (
                patch("custom_components.import_statistics.export_inventory_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.export_inventory_service.fetch_inventory_data", return_value=inventory_data),
            ):
                await handle_export_inventory_impl(hass, call)

            output_file = Path(tmpdir) / "inventory.tsv"
            content = output_file.read_text(encoding="utf-8-sig")

            # Check all three classifications appear in rows
            assert "Active" in content
            assert "Orphan" in content
            assert "External" in content

            # Check summary counts
            assert "# Active statistics: 1" in content
            assert "# Orphan statistics: 2" in content
            assert "# Deleted statistics: 0" in content
            assert "# External statistics: 1" in content

            # Verify the orphaned entity row has Orphan category
            data_lines = [line for line in content.split("\n") if "sensor.orphaned" in line]
            assert len(data_lines) == 1
            assert "Orphan" in data_lines[0]

            # Verify the deleted entity row is categorized as Orphan (deleted entity registry entry)
            deleted_lines = [line for line in content.split("\n") if "sensor.deleted" in line]
            assert len(deleted_lines) == 1
            assert "\tOrphan\t" in deleted_lines[0]
