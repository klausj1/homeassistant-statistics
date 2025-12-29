# Implementation: `get_statistics_after_time()` - Custom Recorder Helper

> Probably its not a good idea to do that in this way. Database-dependent, ...

## Overview
This document provides a complete implementation of `get_statistics_after_time()`, a mirror function to the internal `_statistics_at_time()` method. This function retrieves the **first (youngest) statistic record at or after a given timestamp** for one or more statistic IDs.

---

## Why This Function?

The Home Assistant recorder API has `_statistics_at_time()` (private) to find values **BEFORE** a timestamp, but no public equivalent for finding values **AFTER** a timestamp. This implementation fills that gap.

### Use Cases:
- Finding the next state change after a specific moment
- Interpolating missing data points
- Delta calculations going forward in time
- Analyzing state transitions

---

## Implementation Code

### Part 1: Statement Generators

```python
def _generate_statistics_after_time_stmt_group_by(
    table: type[StatisticsBase],
    metadata_ids: set[int],
    start_time_ts: float,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> StatementLambdaElement:
    """Create the statement for finding the statistics at or after a given time using GROUP BY.

    This is the MySQL-optimized version. Uses a subquery with min(start_ts) to find
    the earliest record >= the target time for each metadata_id.

    Must use less than MAX_IDS_FOR_INDEXED_GROUP_BY metadata_ids in the IN clause.
    """
    return _generate_select_columns_for_types_stmt(table, types) + (
        lambda q: q.join(
            next_statistic_ids := (
                select(
                    func.min(table.start_ts).label("min_start_ts"),
                    table.metadata_id.label("min_metadata_id"),
                )
                .filter(table.start_ts >= start_time_ts)  # KEY DIFFERENCE: >= instead of <
                .filter(table.metadata_id.in_(metadata_ids))
                .group_by(table.metadata_id)
                .subquery()
            ),
            and_(
                table.start_ts == next_statistic_ids.c.min_start_ts,
                table.metadata_id == next_statistic_ids.c.min_metadata_id,
            ),
        )
    )


def _generate_statistics_after_time_stmt_dependent_sub_query(
    table: type[StatisticsBase],
    metadata_ids: set[int],
    start_time_ts: float,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> StatementLambdaElement:
    """Create the statement for finding the statistics at or after a given time using dependent subquery.

    This is the preferred method for PostgreSQL and SQLite. Uses a correlated subquery
    to find the first (minimum) start_ts >= target_time for each entity.

    Based on the pattern from _generate_statistics_at_time_stmt_dependent_sub_query
    but inverted to find AFTER instead of BEFORE.

    Reference: https://github.com/home-assistant/core/issues/132865
    An ascending index scan with LIMIT 1 is efficient for finding the first record
    at or after a time point.
    """
    return _generate_select_columns_for_types_stmt(table, types) + (
        lambda q: q.select_from(StatisticsMeta)
        .join(
            table,
            and_(
                table.start_ts
                == (
                    select(table.start_ts)
                    .where(
                        (StatisticsMeta.id == table.metadata_id)
                        & (table.start_ts >= start_time_ts)  # KEY DIFFERENCE: >= instead of <
                    )
                    .order_by(table.start_ts.asc())  # KEY DIFFERENCE: ascending to get minimum
                    .limit(1)
                )
                .scalar_subquery()
                .correlate(StatisticsMeta),
                table.metadata_id == StatisticsMeta.id,
            ),
        )
        .where(table.metadata_id.in_(metadata_ids))
    )
```

### Part 2: Core Query Function

```python
def _statistics_after_time(
    instance: Recorder,
    session: Session,
    metadata_ids: set[int],
    table: type[StatisticsBase],
    start_time: datetime,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> Sequence[Row] | None:
    """Return first known statistics, at or after start_time, for the metadata_ids.

    This is the mirror function to _statistics_at_time() and follows the same pattern.

    Args:
        instance: Recorder instance
        session: Database session
        metadata_ids: Set of metadata IDs to query
        table: Statistics table (Statistics or StatisticsShortTerm)
        start_time: Target datetime (timezone-aware UTC)
        types: Set of statistic types to retrieve

    Returns:
        Sequence of database rows or None if no statistics found
    """
    start_time_ts = start_time.timestamp()
    if TYPE_CHECKING:
        assert instance.database_engine is not None

    # Use dependent subquery approach (faster for most databases)
    if not instance.database_engine.optimizer.slow_dependent_subquery:
        stmt = _generate_statistics_after_time_stmt_dependent_sub_query(
            table=table,
            metadata_ids=metadata_ids,
            start_time_ts=start_time_ts,
            types=types,
        )
        return cast(list[Row], execute_stmt_lambda_element(session, stmt))

    # Fallback to group-by approach for MySQL
    rows: list[Row] = []
    # Limit metadata_ids per query to avoid MySQL optimizer issues
    # (same pattern as _statistics_at_time)
    for metadata_ids_chunk in chunked_or_all(
        metadata_ids, MAX_IDS_FOR_INDEXED_GROUP_BY
    ):
        stmt = _generate_statistics_after_time_stmt_group_by(
            table=table,
            metadata_ids=metadata_ids_chunk,
            start_time_ts=start_time_ts,
            types=types,
        )
        row_chunk = cast(list[Row], execute_stmt_lambda_element(session, stmt))
        if rows:
            rows += row_chunk
        else:
            rows = row_chunk
    return rows
```

### Part 3: Public API Wrapper

```python
def get_statistics_after_time(
    hass: HomeAssistant,
    statistic_id: str,
    timestamp: datetime,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]] | None = None,
    units: dict[str, str] | None = None,
) -> dict[str, list[StatisticsRow]]:
    """Return the first statistic at or after the given timestamp for a statistic_id.

    This is a public API wrapper that retrieves the youngest (earliest occurring after)
    statistic record for a given statistic_id at or after the specified timestamp.

    Args:
        hass: Home Assistant instance
        statistic_id: The statistic ID to query (e.g., "sensor.temperature")
        timestamp: The target timestamp (must be timezone-aware UTC)
        types: Set of types to retrieve. If None, returns all available.
               Options: "last_reset", "max", "mean", "min", "state", "sum"
        units: Optional unit conversion mapping {unit_class: target_unit}

    Returns:
        Dictionary with statistic_id as key and list of StatisticsRow as value.
        If no data found after timestamp, returns empty dict.

    Example:
        >>> from homeassistant.util import dt as dt_util
        >>> result = get_statistics_after_time(
        ...     hass,
        ...     "sensor.temperature",
        ...     dt_util.utcnow(),
        ...     types={"mean", "min", "max"}
        ... )
        >>> if result and "sensor.temperature" in result:
        ...     first_stat = result["sensor.temperature"][0]
        ...     print(f"Value at {first_stat['start']}: {first_stat['mean']}")
    """
    statistic_ids = {statistic_id}
    if types is None:
        types = {"last_reset", "max", "mean", "min", "state", "sum"}

    with session_scope(hass=hass, read_only=True) as session:
        # Fetch metadata for the statistic_id
        metadata = get_instance(hass).statistics_meta_manager.get_many(
            session, statistic_ids=statistic_ids
        )
        if not metadata:
            return {}

        # Extract metadata IDs and discard impossible columns
        metadata_ids = _extract_metadata_and_discard_impossible_columns(metadata, types)
        if not metadata_ids:
            return {}

        # Query statistics (uses both hourly and short-term tables)
        # Try hourly first, then short-term if available
        stats: list[Row] = []
        for table in [Statistics, StatisticsShortTerm]:
            result = _statistics_after_time(
                get_instance(hass),
                session,
                set(metadata_ids),
                table,
                timestamp,
                types,
            )
            if result:
                stats.extend(result)
                break  # Use first table with results

        if not stats:
            return {}

        # Convert results to statistics dictionary format
        return _sorted_statistics_to_dict(
            hass,
            stats,
            statistic_ids,
            metadata,
            convert_units=True,
            table=Statistics,  # Use Statistics for output structure
            units=units,
            types=types,
        )
```

---

## Integration with Custom Component

To use this in your import_statistics component, add to [`custom_components/import_statistics/helpers.py`](../../custom_components/import_statistics/helpers.py):

### Step 1: Add to helpers.py

```python
from homeassistant.components.recorder.statistics import (
    get_statistics_after_time,
)


def get_next_statistic_value(
    hass: HomeAssistant,
    statistic_id: str,
    after_timestamp: datetime,
) -> float | None:
    """Get the next statistic value after a timestamp.

    Args:
        hass: Home Assistant instance
        statistic_id: The statistic ID to look up
        after_timestamp: Find the first value at or after this time

    Returns:
        The sum or mean value of the next statistic, or None if not found

    Raises:
        HomeAssistantError: If statistic_id is invalid or timestamp has no timezone
    """
    if after_timestamp.tzinfo is None:
        handle_error(
            f"Timestamp for {statistic_id} must be timezone-aware UTC",
            "Invalid timestamp timezone"
        )

    try:
        result = get_statistics_after_time(
            hass,
            statistic_id,
            after_timestamp,
            types={"sum", "mean"},
        )
    except Exception as err:
        handle_error(
            f"Failed to query next statistic for {statistic_id}: {err}",
            "Recorder query failed"
        )

    if not result or statistic_id not in result or not result[statistic_id]:
        return None

    first_stat = result[statistic_id][0]
    return first_stat.get("sum") or first_stat.get("mean")
```

### Step 2: Use in import logic

```python
def calculate_delta_between_timestamps(
    hass: HomeAssistant,
    statistic_id: str,
    start_ts: datetime,
    end_ts: datetime,
) -> float | None:
    """Calculate the change in statistic between two timestamps.

    Args:
        hass: Home Assistant instance
        statistic_id: The statistic ID to analyze
        start_ts: Start timestamp (timezone-aware UTC)
        end_ts: End timestamp (timezone-aware UTC)

    Returns:
        The delta (end_value - start_value), or None if data unavailable
    """
    start_value = get_next_statistic_value(hass, statistic_id, start_ts)
    end_value = get_next_statistic_value(hass, statistic_id, end_ts)

    if start_value is not None and end_value is not None:
        return end_value - start_value
    return None
```

---

## Key Differences from `_statistics_at_time()`

| Aspect | `_statistics_at_time()` | `get_statistics_after_time()` |
|--------|------------------------|------------------------------|
| **Purpose** | Last value BEFORE timestamp | First value AFTER timestamp |
| **Filter** | `table.start_ts < start_time_ts` | `table.start_ts >= start_time_ts` |
| **Order** | `.order_by(table.start_ts.desc())` | `.order_by(table.start_ts.asc())` |
| **Use Case** | Computing change (old → new) | Forward interpolation |
| **Access** | Private (`_statistics_at_time`) | Public wrapper (`get_statistics_after_time`) |

---

## Database Query Optimization

### Dependent Subquery (PostgreSQL/SQLite preferred)
```sql
-- Finds first record at or after timestamp using ascending index scan
SELECT * FROM statistics
WHERE start_ts = (
    SELECT start_ts FROM statistics
    WHERE metadata_id = ? AND start_ts >= ?
    ORDER BY start_ts ASC
    LIMIT 1
)
AND metadata_id = ?
```
**Performance**: O(log n) with B-tree index on (metadata_id, start_ts)

### Group-by Subquery (MySQL fallback)
```sql
-- Uses MIN aggregate to find earliest matching record per entity
SELECT s.* FROM statistics s
INNER JOIN (
    SELECT MIN(start_ts) as min_start_ts, metadata_id
    FROM statistics
    WHERE metadata_id IN (...)
    AND start_ts >= ?
    GROUP BY metadata_id
) AS next_stats
ON s.start_ts = next_stats.min_start_ts
AND s.metadata_id = next_stats.metadata_id
```
**Performance**: Good with proper indexing, scales to 1000+ metadata_ids per query

---

## Caveats & Limitations

1. **Timezone Handling**: The `timestamp` parameter must be timezone-aware UTC. Non-UTC timestamps will not work correctly.

2. **Short-term vs Long-term**: The implementation checks both `StatisticsShortTerm` and `Statistics` tables. For efficiency, consider limiting to one table type based on your use case.

3. **Exact Timestamp Matching**: If no record exists exactly at or after the timestamp, returns the next available record. Use the returned `start` field to verify the actual timestamp of the returned data.

4. **Database Engine Differences**: The function automatically selects the best query strategy based on the database engine optimizer characteristics.

5. **Large Metadata ID Sets**: If querying many statistics simultaneously (>100), the function chunks queries for MySQL compatibility (typically ~1000 IDs per query).

6. **No Data After Timestamp**: If the timestamp is after all available statistics, returns empty dict. Caller must handle this case.

---

## Testing Recommendations

```python
import pytest
from datetime import datetime, timedelta
from homeassistant.util import dt as dt_util
from homeassistant.components.recorder.statistics import async_import_statistics

@pytest.mark.asyncio
async def test_get_statistics_after_time(hass, setup_recorder):
    """Test retrieving statistics after a specific timestamp."""
    test_time = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)

    # Import test statistics
    await async_import_statistics(
        hass,
        {
            "statistic_id": "sensor.test",
            "unit_of_measurement": "°C",
            "mean_type": "arithmetic",
            "unit_class": "temperature",
            "source": "recorder",
        },
        [
            {"start": test_time, "mean": 20.0, "min": 19.5, "max": 20.5},
            {"start": test_time + timedelta(hours=1), "mean": 21.0, "min": 20.5, "max": 21.5},
            {"start": test_time + timedelta(hours=2), "mean": 22.0, "min": 21.5, "max": 22.5},
        ],
    )

    # Test: Get statistics after specific time (30 min into first hour)
    result = await hass.async_add_executor_job(
        get_statistics_after_time,
        hass,
        "sensor.test",
        test_time + timedelta(minutes=30),
        {"mean"},
    )

    # Assert: Should get the second statistic (21.0)
    assert result
    assert "sensor.test" in result
    assert len(result["sensor.test"]) == 1
    assert result["sensor.test"][0]["mean"] == 21.0
    assert result["sensor.test"][0]["start"] == (test_time + timedelta(hours=1)).timestamp()
```

---

## Future Enhancements

1. **Add `limit` parameter**: Retrieve N statistics after a timestamp
2. **Add `direction` parameter**: "next", "prev", "both" to search in multiple directions
3. **Add caching**: Cache query results for frequently accessed statistics
4. **Add async version**: `async_get_statistics_after_time()` for use in async contexts
5. **Add batching**: Accept multiple statistic_ids to reduce query count
