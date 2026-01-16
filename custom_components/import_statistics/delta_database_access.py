"""Delta statistics import database access helper functions using recorder."""

import datetime as dt
from typing import Any

from homeassistant.components.recorder import statistics
from homeassistant.components.recorder.db_schema import Statistics
from homeassistant.components.recorder.statistics import _statistics_at_time, get_metadata, statistics_during_period
from homeassistant.core import HomeAssistant
from homeassistant.helpers.recorder import get_instance, session_scope
from homeassistant.util import dt as dt_util

from custom_components.import_statistics.helpers import _LOGGER, handle_error


def _get_reference_stats(mid: int, ts: dt.datetime, inst: Any) -> Any:
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


async def _get_newest_db_statistic(hass: HomeAssistant, statistic_id: str) -> dict | None:
    """
    Fetch the newest statistic from database for given statistic_id.

    Args:
    ----
        hass: Home Assistant instance
        statistic_id: The statistic ID to query

    Returns:
    -------
        Dict with keys: start (datetime), sum (float), state (float)
        Or None if no statistics exist for this ID

    """
    _LOGGER.debug("Querying newest statistic for %s", statistic_id)

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
        _LOGGER.error("Failed to query newest statistics for %s: %s", statistic_id, exc)
        return None

    if not result_dict or statistic_id not in result_dict:
        _LOGGER.debug("No statistics found for %s", statistic_id)
        return None

    stats_list = result_dict[statistic_id]
    if not stats_list:
        _LOGGER.debug("Empty statistics list for %s", statistic_id)
        return None

    # Get the first (and only) entry from the list
    newest_stat = stats_list[0]
    result_dt = dt.datetime.fromtimestamp(newest_stat.get("start", 0), tz=dt.UTC)
    result_sum = newest_stat.get("sum")
    result_state = newest_stat.get("state")

    _LOGGER.debug(
        "Found newest statistic for %s: start=%s, sum=%s, state=%s",
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


async def _get_reference_before_timestamp(
    hass: HomeAssistant,
    statistic_id: str,
    timestamp: dt.datetime,
) -> dict | None:
    """
    Fetch the newest statistic before given timestamp.

    Args:
    ----
        hass: Home Assistant instance
        statistic_id: The statistic to query
        timestamp: Find records before this time

    Returns:
    -------
        Dict with keys: start (datetime), sum (float), state (float)
        Or None if no matching record exists

    """
    _LOGGER.debug("Querying reference before %s for %s", timestamp, statistic_id)

    recorder_instance = get_instance(hass)
    if recorder_instance is None:
        handle_error("Recorder component is not running")

    # Get metadata for this statistic_id
    try:
        metadata_dict = await recorder_instance.async_add_executor_job(lambda: get_metadata(hass, statistic_ids={statistic_id}))
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error("Failed to get metadata for %s: %s", statistic_id, exc)
        return None

    if not metadata_dict or statistic_id not in metadata_dict:
        _LOGGER.debug("No metadata found for %s", statistic_id)
        return None

    metadata_id, _meta_data = metadata_dict[statistic_id]

    try:
        # Query statistics for this specific ID up to its timestamp
        statistics_at_time = await recorder_instance.async_add_executor_job(
            _get_reference_stats,
            metadata_id,
            timestamp,
            recorder_instance,
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error("Failed to query statistics for %s: %s", statistic_id, exc)
        return None

    # Extract the result for this statistic_id
    if not statistics_at_time:
        _LOGGER.debug("No reference found before %s for %s", timestamp, statistic_id)
        return None

    try:
        row_start_dt = _extract_row_start_datetime(statistics_at_time)
        row_sum = _get_row_sum_value(statistics_at_time)
        row_state = _get_row_state_value(statistics_at_time)

        # Validate: record must be strictly before the timestamp
        if row_start_dt < timestamp:
            _LOGGER.debug(
                "Found reference before %s for %s: start=%s, sum=%s, state=%s",
                timestamp,
                statistic_id,
                row_start_dt,
                row_sum,
                row_state,
            )
            return {
                "start": row_start_dt,
                "sum": row_sum,
                "state": row_state,
            }
        _LOGGER.debug("Reference for %s exists but is not before timestamp %s", statistic_id, timestamp)
    except (AttributeError, KeyError, TypeError) as exc:
        _LOGGER.error("Error processing reference row for %s: %s", statistic_id, exc)

    return None


async def _get_reference_at_or_after_timestamp(
    hass: HomeAssistant,
    statistic_id: str,
    timestamp: dt.datetime,
) -> dict | None:
    """
    Fetch the oldest statistic at or after given timestamp.

    Args:
    ----
        hass: Home Assistant instance
        statistic_id: The statistic to query
        timestamp: Find records at or after this time

    Returns:
    -------
        Dict with keys: start (datetime), sum (float), state (float)
        Or None if no matching record exists

    """
    _LOGGER.debug("Querying reference at or after %s for %s", timestamp, statistic_id)

    # First, get the newest statistic in the database to determine the upper bound
    try:
        newest_dict = await get_instance(hass).async_add_executor_job(
            lambda: statistics.get_last_statistics(
                hass,
                number_of_stats=1,
                statistic_id=statistic_id,
                convert_units=False,
                types={"sum", "state"},
            )
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error("Failed to query newest statistics for %s: %s", statistic_id, exc)
        return None

    if not newest_dict or statistic_id not in newest_dict or not newest_dict[statistic_id]:
        _LOGGER.debug("No statistics found for %s", statistic_id)
        return None

    newest_stat = newest_dict[statistic_id][0]
    t_newest_db = dt.datetime.fromtimestamp(newest_stat.get("start", 0), tz=dt.UTC)

    # Query all statistics between timestamp and the newest DB record + 1 hour
    # The +1 hour is needed because statistics_during_period uses inclusive lower bound and exclusive upper bound
    try:
        stats_dict = await get_instance(hass).async_add_executor_job(
            lambda: statistics_during_period(
                hass,
                timestamp,
                t_newest_db + dt.timedelta(hours=1),
                {statistic_id},
                "hour",
                None,
                {"sum", "state"},
            )
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error("Failed to query statistics during period for %s: %s", statistic_id, exc)
        return None

    if not stats_dict or statistic_id not in stats_dict or not stats_dict[statistic_id]:
        _LOGGER.debug("No statistics found in period for %s", statistic_id)
        return None

    # Take the oldest value from the period (which is the oldest value >= timestamp)
    oldest_in_period = stats_dict[statistic_id][0]  # First element is oldest in the period
    result_dt = dt.datetime.fromtimestamp(oldest_in_period.get("start", 0), tz=dt.UTC)
    result_sum = oldest_in_period.get("sum")
    result_state = oldest_in_period.get("state")
    _LOGGER.debug(
        "Found reference at or after %s for %s: start=%s, sum=%s, state=%s",
        timestamp,
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
