"""Database access functions for export_inventory service."""

import datetime as dt
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.recorder.db_schema import Statistics, StatisticsMeta
from homeassistant.components.recorder.statistics import list_statistic_ids
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import get_instance, session_scope
from sqlalchemy import func, select

from custom_components.import_statistics.helpers import _LOGGER

if TYPE_CHECKING:
    from homeassistant.components.recorder import Recorder


@dataclass
class StatisticMetadataRow:
    """Metadata for a single statistic_id."""

    statistic_id: str
    unit_of_measurement: str | None
    source: str
    has_sum: bool


@dataclass
class StatisticAggregates:
    """Aggregated statistics data for a single statistic_id."""

    metadata_id: int
    samples_count: int
    first_seen_ts: float | None
    last_seen_ts: float | None


def _query_statistics_meta(hass: HomeAssistant) -> list[StatisticMetadataRow]:
    """
    Query statistics_meta table for all statistic IDs and their metadata.

    Returns a list of StatisticMetadataRow with statistic_id, unit, source, has_sum.
    """
    all_stats = list_statistic_ids(hass)
    return [
        StatisticMetadataRow(
            statistic_id=stat["statistic_id"],
            unit_of_measurement=stat.get("statistics_unit_of_measurement"),
            source=stat.get("source", "recorder"),
            has_sum=stat.get("has_sum", False),
        )
        for stat in all_stats
    ]


def _query_statistics_aggregates(recorder_instance: "Recorder") -> dict[int, StatisticAggregates]:
    """
    Query long-term statistics table for aggregated counts and timestamps.

    Groups by metadata_id and returns COUNT(*), MIN(start_ts), MAX(start_ts).
    Returns a dict mapping metadata_id -> StatisticAggregates.
    """
    with session_scope(session=recorder_instance.get_session(), read_only=True) as session:
        stmt = select(
            Statistics.metadata_id,
            func.count(Statistics.id).label("samples_count"),
            func.min(Statistics.start_ts).label("first_seen_ts"),
            func.max(Statistics.start_ts).label("last_seen_ts"),
        ).group_by(Statistics.metadata_id)
        rows = session.execute(stmt).all()

        result = {}
        for row in rows:
            result[row.metadata_id] = StatisticAggregates(
                metadata_id=row.metadata_id,
                samples_count=row.samples_count,
                first_seen_ts=row.first_seen_ts,
                last_seen_ts=row.last_seen_ts,
            )
        return result


def _query_metadata_id_mapping(recorder_instance: "Recorder") -> dict[str, int]:
    """
    Query statistics_meta to get mapping from statistic_id to metadata_id.

    Returns a dict mapping statistic_id -> metadata_id.
    """
    with session_scope(session=recorder_instance.get_session(), read_only=True) as session:
        stmt = select(StatisticsMeta.id, StatisticsMeta.statistic_id)
        rows = session.execute(stmt).all()
        return {row.statistic_id: row.id for row in rows}


@dataclass
class InventoryData:
    """Complete inventory data from database queries."""

    metadata_rows: list[StatisticMetadataRow]
    entity_registry_ids: set[str]
    deleted_entity_orphan_timestamps: dict[str, float | None]
    aggregates: dict[int, StatisticAggregates]
    id_mapping: dict[str, int]


async def fetch_inventory_data(hass: HomeAssistant) -> InventoryData:
    """
    Fetch all data needed for inventory export.

    Performs data collection:
    1. recorder statistics: all statistic IDs with metadata
    2. entity registry: active and deleted entity IDs (incl. orphaned_timestamp)
    3. recorder long-term statistics: aggregated counts and timestamps per metadata_id

    Args:
        hass: Home Assistant instance

    Returns:
        InventoryData with all queried data

    """
    recorder_instance = get_instance(hass)

    _LOGGER.debug("Fetching statistics metadata")
    metadata_rows = await recorder_instance.async_add_executor_job(_query_statistics_meta, hass)
    _LOGGER.debug("Found %d statistics in metadata", len(metadata_rows))

    entity_registry = er.async_get(hass)
    entity_registry_ids = {entry.entity_id for entry in entity_registry.entities.values()}
    _LOGGER.debug("Found %d entity IDs in entity registry", len(entity_registry_ids))

    deleted_entity_orphan_timestamps: dict[str, float | None] = {}
    for entry in entity_registry.deleted_entities.values():
        deleted_entity_orphan_timestamps[entry.entity_id] = getattr(entry, "orphaned_timestamp", None)
    _LOGGER.debug("Found %d deleted entity IDs in entity registry", len(deleted_entity_orphan_timestamps))

    metadata_statistic_ids = {row.statistic_id for row in metadata_rows}
    deleted_ids = set(deleted_entity_orphan_timestamps)
    deleted_in_metadata = metadata_statistic_ids & deleted_ids
    if deleted_in_metadata:
        sample = ", ".join(sorted(deleted_in_metadata)[:10])
        _LOGGER.debug(
            "Deleted entity IDs that also exist as statistics_meta statistic_id: %d (sample: %s)",
            len(deleted_in_metadata),
            sample,
        )
    else:
        _LOGGER.debug("No deleted entity IDs found in statistics_meta statistic_id list")

    _LOGGER.debug("Fetching metadata_id mapping")
    id_mapping = await recorder_instance.async_add_executor_job(_query_metadata_id_mapping, recorder_instance)
    _LOGGER.debug("Found %d metadata_id mappings", len(id_mapping))

    deleted_in_long_term = set(id_mapping) & deleted_ids
    if deleted_in_long_term:
        sample = ", ".join(sorted(deleted_in_long_term)[:10])
        _LOGGER.debug(
            "Deleted entity IDs that also have long-term statistics: %d (sample: %s)",
            len(deleted_in_long_term),
            sample,
        )
    else:
        _LOGGER.debug("No deleted entity IDs found among statistic_ids that have long-term statistics")

    _LOGGER.debug("Fetching statistics aggregates")
    aggregates = await recorder_instance.async_add_executor_job(_query_statistics_aggregates, recorder_instance)
    _LOGGER.debug("Found aggregates for %d statistics", len(aggregates))

    return InventoryData(
        metadata_rows=metadata_rows,
        entity_registry_ids=entity_registry_ids,
        deleted_entity_orphan_timestamps=deleted_entity_orphan_timestamps,
        aggregates=aggregates,
        id_mapping=id_mapping,
    )


def has_long_term_statistics(inventory_data: InventoryData) -> bool:
    """Check if there are any long-term statistics in the database."""
    return len(inventory_data.aggregates) > 0


def get_global_time_range(inventory_data: InventoryData) -> tuple[dt.datetime | None, dt.datetime | None]:
    """
    Get the global first_seen and last_seen timestamps across all statistics.

    Returns:
        Tuple of (global_first_seen, global_last_seen) as UTC datetimes, or (None, None) if no data.

    """
    if not inventory_data.aggregates:
        return None, None

    min_ts = None
    max_ts = None

    for agg in inventory_data.aggregates.values():
        if agg.first_seen_ts is not None and (min_ts is None or agg.first_seen_ts < min_ts):
            min_ts = agg.first_seen_ts
        if agg.last_seen_ts is not None and (max_ts is None or agg.last_seen_ts > max_ts):
            max_ts = agg.last_seen_ts

    global_first = dt.datetime.fromtimestamp(min_ts, tz=dt.UTC) if min_ts is not None else None
    global_last = dt.datetime.fromtimestamp(max_ts, tz=dt.UTC) if max_ts is not None else None

    return global_first, global_last
