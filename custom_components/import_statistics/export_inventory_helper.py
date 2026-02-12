"""Helper functions for export_inventory service."""

import csv
import datetime as dt
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

from custom_components.import_statistics.export_inventory_database_access import (
    InventoryData,
    get_global_time_range,
)
from custom_components.import_statistics.helpers import _LOGGER, handle_error, validate_delimiter, validate_filename


class Category(Enum):
    """Category classification for statistics."""

    ACTIVE = "Active"
    ORPHAN = "Orphan"
    DELETED = "Deleted"
    EXTERNAL = "External"


class StatType(Enum):
    """Type classification for statistics."""

    MEASUREMENT = "Measurement"
    COUNTER = "Counter"


@dataclass
class InventoryRow:
    """A single row in the inventory output."""

    statistic_id: str
    unit_of_measurement: str
    source: str
    category: Category
    stat_type: StatType
    samples_count: int
    first_seen: dt.datetime | None
    last_seen: dt.datetime | None
    days_span: float


INVENTORY_COLUMNS = [
    "statistic_id",
    "unit_of_measurement",
    "source",
    "category",
    "type",
    "samples_count",
    "first_seen",
    "last_seen",
    "days_span",
]


def classify_category(
    statistic_id: str,
    source: str,
    entity_registry_ids: set[str],
    deleted_entity_orphan_timestamps: dict[str, float | None],
) -> Category:
    """
    Classify a statistic into Active, Orphan, Deleted, or External category.

    Args:
        statistic_id: The statistic ID to classify
        source: The source field from statistics_meta
        entity_registry_ids: Set of entity IDs present in the entity registry
        deleted_entity_orphan_timestamps: Mapping of deleted entity_id to orphaned_timestamp (if any)

    Returns:
        Category enum value

    """
    # External: source is not 'recorder' OR statistic_id contains ':'
    if source != "recorder" or ":" in statistic_id:
        return Category.EXTERNAL

    # If the entity is still registered in Home Assistant, it should not be reported as deleted.
    if statistic_id in entity_registry_ids:
        return Category.ACTIVE

    if statistic_id in deleted_entity_orphan_timestamps:
        return Category.ORPHAN if deleted_entity_orphan_timestamps[statistic_id] is not None else Category.DELETED

    return Category.DELETED


def classify_type(*, has_sum: bool) -> StatType:
    """
    Classify a statistic as Measurement or Counter based on has_sum.

    Args:
        has_sum: The has_sum field from statistics_meta

    Returns:
        StatType enum value

    """
    return StatType.COUNTER if has_sum else StatType.MEASUREMENT


def compute_days_span(first_seen: dt.datetime | None, last_seen: dt.datetime | None) -> float:
    """
    Compute the number of days spanned by the statistics.

    Args:
        first_seen: First sample timestamp
        last_seen: Last sample timestamp

    Returns:
        Number of days as float, rounded to 1 decimal place. Returns 0.0 if either is None.

    """
    if first_seen is None or last_seen is None:
        return 0.0

    delta = last_seen - first_seen
    days = delta.total_seconds() / 86400.0
    return round(days, 1)


def format_datetime(timestamp: dt.datetime | None, tz: ZoneInfo, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """
    Format a datetime in the specified timezone.

    Args:
        timestamp: UTC datetime to format
        tz: Target timezone
        fmt: strftime format string

    Returns:
        Formatted datetime string, or empty string if timestamp is None

    """
    if timestamp is None:
        return ""
    local_dt = timestamp.astimezone(tz)
    return local_dt.strftime(fmt)


def build_inventory_rows(
    inventory_data: InventoryData,
    tz: ZoneInfo,  # noqa: ARG001
) -> list[InventoryRow]:
    """
    Build inventory rows from database data.

    Args:
        inventory_data: Data from database queries
        tz: Timezone for formatting timestamps

    Returns:
        List of InventoryRow objects

    """
    rows: list[InventoryRow] = []

    for meta in inventory_data.metadata_rows:
        # Get aggregates for this statistic
        metadata_id = inventory_data.id_mapping.get(meta.statistic_id)
        aggregates = None if metadata_id is None else inventory_data.aggregates.get(metadata_id)

        # Classification
        category = classify_category(
            meta.statistic_id,
            meta.source,
            inventory_data.entity_registry_ids,
            inventory_data.deleted_entity_orphan_timestamps,
        )
        stat_type = classify_type(has_sum=meta.has_sum)

        # Timestamps and counts
        if aggregates is not None:
            samples_count = aggregates.samples_count
            first_seen = dt.datetime.fromtimestamp(aggregates.first_seen_ts, tz=dt.UTC) if aggregates.first_seen_ts else None
            last_seen = dt.datetime.fromtimestamp(aggregates.last_seen_ts, tz=dt.UTC) if aggregates.last_seen_ts else None
        else:
            samples_count = 0
            first_seen = None
            last_seen = None

        days_span = compute_days_span(first_seen, last_seen)

        rows.append(
            InventoryRow(
                statistic_id=meta.statistic_id,
                unit_of_measurement=meta.unit_of_measurement or "",
                source=meta.source,
                category=category,
                stat_type=stat_type,
                samples_count=samples_count,
                first_seen=first_seen,
                last_seen=last_seen,
                days_span=days_span,
            )
        )

    # Sort by statistic_id for consistent output
    rows.sort(key=lambda r: r.statistic_id)

    return rows


@dataclass
class InventorySummary:
    """Summary statistics for the inventory."""

    total_statistics: int
    measurements_count: int
    counters_count: int
    total_samples: int
    global_start: dt.datetime | None
    global_end: dt.datetime | None
    active_count: int
    orphan_count: int
    deleted_count: int
    external_count: int


def build_summary(rows: list[InventoryRow], inventory_data: InventoryData) -> InventorySummary:
    """
    Build summary statistics from inventory rows.

    Args:
        rows: List of inventory rows
        inventory_data: Original inventory data for global time range

    Returns:
        InventorySummary with counts and global timestamps

    """
    measurements_count = sum(1 for r in rows if r.stat_type == StatType.MEASUREMENT)
    counters_count = sum(1 for r in rows if r.stat_type == StatType.COUNTER)
    total_samples = sum(r.samples_count for r in rows)
    active_count = sum(1 for r in rows if r.category == Category.ACTIVE)
    orphan_count = sum(1 for r in rows if r.category == Category.ORPHAN)
    deleted_count = sum(1 for r in rows if r.category == Category.DELETED)
    external_count = sum(1 for r in rows if r.category == Category.EXTERNAL)

    global_start, global_end = get_global_time_range(inventory_data)

    return InventorySummary(
        total_statistics=len(rows),
        measurements_count=measurements_count,
        counters_count=counters_count,
        total_samples=total_samples,
        global_start=global_start,
        global_end=global_end,
        active_count=active_count,
        orphan_count=orphan_count,
        deleted_count=deleted_count,
        external_count=external_count,
    )


def format_summary_lines(summary: InventorySummary, tz: ZoneInfo) -> list[str]:
    """
    Format summary as comment lines for the output file.

    Args:
        summary: Summary statistics
        tz: Timezone for formatting timestamps

    Returns:
        List of lines starting with '# '

    """
    global_start_str = format_datetime(summary.global_start, tz, "%Y-%m-%d %H:%M:%S") if summary.global_start else "N/A"
    global_end_str = format_datetime(summary.global_end, tz, "%Y-%m-%d %H:%M:%S") if summary.global_end else "N/A"

    return [
        f"# Total statistics: {summary.total_statistics}",
        f"# Measurements: {summary.measurements_count}",
        f"# Counters: {summary.counters_count}",
        f"# Total samples: {summary.total_samples}",
        f"# Global start: {global_start_str}",
        f"# Global end: {global_end_str}",
        f"# Active statistics: {summary.active_count}",
        f"# Orphan statistics: {summary.orphan_count}",
        f"# Deleted statistics: {summary.deleted_count}",
        f"# External statistics: {summary.external_count}",
    ]


def write_inventory_file(
    filepath: Path,
    rows: list[InventoryRow],
    summary: InventorySummary,
    delimiter: str,
    tz: ZoneInfo,
) -> None:
    """
    Write inventory to file with summary header and data rows.

    Args:
        filepath: Output file path
        rows: Inventory rows to write
        summary: Summary statistics
        delimiter: Field delimiter
        tz: Timezone for formatting timestamps

    """
    _LOGGER.info("Writing inventory to %s with %d rows", filepath, len(rows))

    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with filepath.open("w", encoding="utf-8-sig", newline="") as f:
            # Write summary lines
            for line in format_summary_lines(summary, tz):
                f.write(line + "\n")

            # Write blank line between summary and table
            f.write("\n")

            # Write CSV/TSV table
            writer = csv.writer(f, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)

            # Header
            writer.writerow(INVENTORY_COLUMNS)

            # Data rows
            for row in rows:
                writer.writerow(
                    [
                        row.statistic_id,
                        row.unit_of_measurement,
                        row.source,
                        row.category.value,
                        row.stat_type.value,
                        row.samples_count,
                        format_datetime(row.first_seen, tz),
                        format_datetime(row.last_seen, tz),
                        row.days_span,
                    ]
                )
    except PermissionError as e:
        handle_error(
            f"Cannot write inventory file to '{filepath}': {e}. "
            "Please check that the Home Assistant user has write permission to the config directory, "
            "and that the target file is not owned by another user or marked read-only."
        )
    except OSError as e:
        handle_error(f"Cannot write inventory file to '{filepath}': {e}")

    _LOGGER.info("Inventory file written successfully")


def validate_inventory_params(filename: str, delimiter: str, config_dir: str) -> tuple[Path, str]:
    """
    Validate and resolve inventory export parameters.

    Args:
        filename: Filename from service call
        delimiter: Delimiter from service call
        config_dir: Home Assistant config directory

    Returns:
        Tuple of (resolved filepath, validated delimiter)

    Raises:
        HomeAssistantError: If validation fails

    """
    # Validate filename (security check)
    validate_filename(filename, config_dir)

    # Validate and normalize delimiter
    validated_delimiter = validate_delimiter(delimiter)

    # Resolve full path
    filepath = Path(config_dir) / filename

    return filepath, validated_delimiter
