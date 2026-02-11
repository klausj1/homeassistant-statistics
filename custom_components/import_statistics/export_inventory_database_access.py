"""Database access functions for export_inventory service."""

import datetime as dt
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.recorder.db_schema import States, StatesMeta, Statistics, StatisticsMeta
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


def _query_active_entity_ids(hass: HomeAssistant) -> set[str]:
    """
    Query states_meta table to get all active entity IDs.

    Returns a set of entity_id strings that exist in states_meta.
    """
    with session_scope(hass=hass, read_only=True) as session:
        stmt = select(StatesMeta.entity_id).where(StatesMeta.entity_id.isnot(None))
        rows = session.execute(stmt).scalars().all()
        return set(rows)


def _query_orphaned_entity_ids(hass: HomeAssistant) -> set[str]:
    """
    Query states table to find entity IDs whose most recent state is NULL.

    An orphaned entity is one that Home Assistant no longer claims via an integration.
    Shortly after restart, HA writes a NULL state for such entities.

    Uses a subquery to find the maximum last_updated_ts per metadata_id, then joins
    back to get the corresponding state value. This avoids a correlated subquery
    and performs well even on large states tables.

    Returns a set of entity_id strings whose latest state is NULL.
    """
    with session_scope(hass=hass, read_only=True) as session:
        # Step 1: find the latest last_updated_ts per metadata_id
        latest_ts = (
            select(
                States.metadata_id,
                func.max(States.last_updated_ts).label("max_ts"),
            )
            .where(States.metadata_id.isnot(None))
            .group_by(States.metadata_id)
            .subquery()
        )

        # Step 2: join back to states to get the state value at that timestamp,
        # then join states_meta to get the entity_id, filtering for NULL state
        stmt = (
            select(StatesMeta.entity_id)
            .join(latest_ts, StatesMeta.metadata_id == latest_ts.c.metadata_id)
            .join(
                States,
                (States.metadata_id == latest_ts.c.metadata_id) & (States.last_updated_ts == latest_ts.c.max_ts),
            )
            .where(States.state.is_(None))
        )

        rows = session.execute(stmt).scalars().all()
        return set(rows)


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
    active_entity_ids: set[str]
    orphaned_entity_ids: set[str]
    entity_registry_ids: set[str]
    aggregates: dict[int, StatisticAggregates]
    id_mapping: dict[str, int]


async def fetch_inventory_data(hass: HomeAssistant) -> InventoryData:
    """
    Fetch all data needed for inventory export.

    Performs database queries:
    1. statistics_meta: all statistic IDs with metadata
    2. states_meta: all active entity IDs (for deleted detection)
    3. states: orphaned entity IDs (last state is NULL)
    4. statistics: aggregated counts and timestamps per metadata_id

    Args:
        hass: Home Assistant instance

    Returns:
        InventoryData with all queried data

    """
    recorder_instance = get_instance(hass)

    _LOGGER.debug("Fetching statistics metadata")
    metadata_rows = await recorder_instance.async_add_executor_job(_query_statistics_meta, hass)
    _LOGGER.debug("Found %d statistics in metadata", len(metadata_rows))

    _LOGGER.debug("Fetching active entity IDs from states_meta")
    active_entity_ids = await recorder_instance.async_add_executor_job(_query_active_entity_ids, hass)
    _LOGGER.debug("Found %d active entity IDs", len(active_entity_ids))

    _LOGGER.debug("Fetching orphaned entity IDs from states")
    orphaned_entity_ids = await recorder_instance.async_add_executor_job(_query_orphaned_entity_ids, hass)
    _LOGGER.debug("Found %d orphaned entity IDs", len(orphaned_entity_ids))

    entity_registry = er.async_get(hass)
    entity_registry_ids = {entry.entity_id for entry in entity_registry.entities.values()}
    _LOGGER.debug("Found %d entity IDs in entity registry", len(entity_registry_ids))

    _LOGGER.debug("Fetching metadata_id mapping")
    id_mapping = await recorder_instance.async_add_executor_job(_query_metadata_id_mapping, recorder_instance)
    _LOGGER.debug("Found %d metadata_id mappings", len(id_mapping))

    _LOGGER.debug("Fetching statistics aggregates")
    aggregates = await recorder_instance.async_add_executor_job(_query_statistics_aggregates, recorder_instance)
    _LOGGER.debug("Found aggregates for %d statistics", len(aggregates))

    return InventoryData(
        metadata_rows=metadata_rows,
        active_entity_ids=active_entity_ids,
        orphaned_entity_ids=orphaned_entity_ids,
        entity_registry_ids=entity_registry_ids,
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
