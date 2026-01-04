"""Delta statistics import helper functions."""

import datetime as dt
from typing import Any

from homeassistant.components.recorder import get_instance, statistics
from homeassistant.components.recorder.db_schema import Statistics
from homeassistant.components.recorder.statistics import _statistics_at_time, get_metadata
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.import_statistics.helpers import _LOGGER


def _get_reference_stats(mid: int, ts: dt.datetime, inst: Any) -> tuple | None:
    """Query database for reference statistics."""
    with session_scope(session=inst.get_session(), read_only=True) as sess:
        result = _statistics_at_time(
            instance=inst,
            session=sess,
            metadata_ids={mid},
            table=Statistics,
            start_time=ts,
            types={"sum", "state"},
        )
        # Return the first row if it exists, otherwise None
        # Result is a Sequence[Row] or None
        if result and len(result) > 0:
            return result[0]
        return None


def _extract_row_start_datetime(row: Any) -> dt.datetime:
    """Extract start datetime from a statistics row."""
    if hasattr(row, "start_ts"):
        return dt_util.utc_from_timestamp(row.start_ts)
    if hasattr(row, "start"):
        return dt_util.utc_from_timestamp(row.start)
    # Try accessing as dict-like object
    return dt_util.utc_from_timestamp(row["start_ts"] if "start_ts" in row else row["start"])


def _get_row_sum_value(row: Any) -> Any:
    """Extract sum value from row."""
    return row.sum if hasattr(row, "sum") else row["sum"]


def _get_row_state_value(row: Any) -> Any:
    """Extract state value from row."""
    return row.state if hasattr(row, "state") else row["state"]


def _process_reference_row(statistic_id: str, row: Any, before_timestamp: dt.datetime, result: dict) -> None:
    """Process a reference row and update result dict."""
    try:
        # Convert timestamp back to datetime for comparison
        row_start_dt = _extract_row_start_datetime(row)
        row_sum = _get_row_sum_value(row)
        row_state = _get_row_state_value(row)

        # Validate: record must be strictly before the import start timestamp
        # (i.e., earlier than the first delta to be imported)
        if row_start_dt < before_timestamp:
            result[statistic_id] = {
                "start": row_start_dt,
                "sum": row_sum,
                "state": row_state,
            }
            _LOGGER.debug(
                "Found reference for %s: start=%s, sum=%s, state=%s",
                statistic_id,
                row_start_dt,
                row_sum,
                row_state,
            )
        else:
            result[statistic_id] = None
            _LOGGER.debug(
                "Reference for %s exists but is not before import start time",
                statistic_id,
            )
    except (AttributeError, KeyError, TypeError) as exc:
        _LOGGER.error("Error processing reference row for %s: %s", statistic_id, exc)
        result[statistic_id] = None


async def get_youngest_statistic_after(hass: HomeAssistant, statistic_id: str, timestamp: dt.datetime) -> dict | None:
    """
    Query database for first statistic record >= 1 hour after timestamp.

    Uses get_last_statistics() public API to fetch the most recent statistic
    and validates it's at least 1 hour after the given timestamp.

    Args:
    ----
        hass: Home Assistant instance
        statistic_id: The statistic ID to query
        timestamp: The reference timestamp (UTC) - find records >= 1 hour after this

    Returns:
    -------
        dict: {start: datetime, sum: float, state: float} or None if not found

    Raises:
    ------
        HomeAssistantError: On database query failure or metadata lookup failure

    """
    _LOGGER.debug("Querying youngest statistic after %s for %s", timestamp, statistic_id)

    # Use get_last_statistics() to get the most recent statistic
    # This is automatically the newest entry in the database
    try:
        result_dict = await get_instance(hass).async_add_executor_job(
            lambda: statistics.get_last_statistics(
                hass,
                number_of_stats=1,  # We only need the newest one
                statistic_id=statistic_id,
                convert_units=False,
                types={"sum", "state"},
            )
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error("Failed to query youngest statistics for %s: %s", statistic_id, exc)
        return None

    if not result_dict or statistic_id not in result_dict:
        _LOGGER.debug("No statistics found for %s", statistic_id)
        return None

    stats_list = result_dict[statistic_id]
    if not stats_list:
        _LOGGER.debug("Empty statistics list for %s", statistic_id)
        return None

    # Get the first (and only) entry from the list
    youngest_stat = stats_list[0]
    result_dt = dt.datetime.fromtimestamp(youngest_stat["start"], tz=dt.UTC)

    # Validate that result is at least 1 hour after timestamp
    time_diff = result_dt - timestamp
    if time_diff < dt.timedelta(hours=1):
        _LOGGER.debug(
            "Youngest statistic for %s exists but is not at least 1 hour after %s (only %s difference)",
            statistic_id,
            timestamp,
            time_diff,
        )
        return None

    result_sum = youngest_stat.get("sum")
    result_state = youngest_stat.get("state")

    _LOGGER.debug(
        "Found youngest reference for %s: start=%s, sum=%s, state=%s",
        statistic_id,
        result_dt,
        result_sum,
        result_state,
    )

    return {
        "start": result_dt,
        "sum": result_sum,
        "state": result_state,
    }


async def get_oldest_statistics_before(hass: HomeAssistant, references_needed: dict) -> dict:  # noqa: PLR0912
    """
    Query recorder for oldest statistics before given timestamps and youngest after.

    For Case 1 (older reference): queries for records before tImportOldest
    For Case 2 (younger reference): queries for records after tImportYoungest

    Queries each statistic_id separately with its own timestamps, since the oldest
    record can be different for each statistic_id.

    Args:
    ----
        hass: Home Assistant instance
        references_needed: dict mapping {statistic_id: (oldest_timestamp, youngest_timestamp)} (both UTC)
                          Tuple contains: (tImportOldest, tImportYoungest)

    Returns:
    -------
        dict: {statistic_id: {start, sum, state} or None}
        Returns None for statistic_ids where no valid reference found or < 1 hour before/after target.

    Raises:
    ------
        HomeAssistantError: On metadata lookup failure or database query failure

    """
    _LOGGER.debug("Querying oldest statistics before given timestamps")

    if not references_needed:
        return {}

    recorder_instance = get_instance(hass)
    if recorder_instance is None:
        from custom_components.import_statistics import helpers

        helpers.handle_error("Recorder component is not running")

    # Get metadata for all statistic_ids in one call
    statistic_ids = list(references_needed.keys())
    _LOGGER.debug("Getting metadata for %d statistics", len(statistic_ids))

    try:
        metadata_dict = await recorder_instance.async_add_executor_job(lambda: get_metadata(hass, statistic_ids=set(statistic_ids)))
    except Exception as exc:  # noqa: BLE001
        from custom_components.import_statistics import helpers

        helpers.handle_error(f"Failed to get metadata: {exc}")

    if not metadata_dict:
        from custom_components.import_statistics import helpers

        helpers.handle_error(f"No metadata found for statistics: {statistic_ids}")

    # Query each statistic_id separately with its own timestamps
    result = {}
    for statistic_id, timestamps in references_needed.items():
        # timestamps is a tuple: (oldest_timestamp, youngest_timestamp)
        oldest_timestamp, youngest_timestamp = timestamps
        _LOGGER.debug("Querying reference for %s before %s", statistic_id, oldest_timestamp)

        if statistic_id not in metadata_dict:
            result[statistic_id] = None
            _LOGGER.debug("No metadata found for %s", statistic_id)
            continue

        metadata_id, _meta_data = metadata_dict[statistic_id]

        try:
            # Case 1: Query statistics for this specific ID up to its oldest_timestamp
            statistics_at_time = await recorder_instance.async_add_executor_job(
                _get_reference_stats,
                metadata_id,
                oldest_timestamp,
                recorder_instance,
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Failed to query statistics for %s: %s", statistic_id, exc)
            result[statistic_id] = None
            continue

        # Extract the result for this statistic_id
        if statistics_at_time:
            _process_reference_row(statistic_id, statistics_at_time, oldest_timestamp, result)
        else:
            result[statistic_id] = None
            _LOGGER.debug("No reference found for %s", statistic_id)

    # Second pass: for missing references, query for younger references (Case 2)
    # Use tImportYoungest (newest timestamp from import data) to find records after it
    missing_refs = {k: v for k, v in references_needed.items() if result.get(k) is None}
    _LOGGER.debug("Missing references after first pass: %d", len(missing_refs))
    if missing_refs:
        _LOGGER.debug("Querying for younger references for %d missing statistics", len(missing_refs))
        for statistic_id, timestamps in missing_refs.items():
            _oldest_timestamp, youngest_timestamp = timestamps
            try:
                # Case 2: Query for youngest reference after tImportYoungest
                youngest_ref = await get_youngest_statistic_after(hass, statistic_id, youngest_timestamp)
                if youngest_ref:
                    result[statistic_id] = youngest_ref
                    _LOGGER.debug("Found Case 2 (younger) reference for %s", statistic_id)
                else:
                    result[statistic_id] = None
            except Exception as exc:  # noqa: BLE001
                _LOGGER.error("Error querying younger reference for %s: %s", statistic_id, exc)
                result[statistic_id] = None

    _LOGGER.debug(
        "Query complete: found %d / %d references",
        sum(1 for v in result.values() if v is not None),
        len(result),
    )

    return result
