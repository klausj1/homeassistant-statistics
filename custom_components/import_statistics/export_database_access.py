"""Export statistics database access helper functions using recorder."""

import datetime as dt
from typing import Any

from homeassistant.components.recorder.db_schema import Statistics, StatisticsShortTerm
from homeassistant.core import HomeAssistant
from homeassistant.helpers.recorder import get_instance, session_scope
from homeassistant.util import dt as dt_util
from sqlalchemy import func

from custom_components.import_statistics.helpers import _LOGGER, handle_error


def _get_min_max_start_ts(metadata_ids: set[int], inst: Any) -> tuple[float | None, float | None]:
    """Return min/max start_ts for the given metadata IDs from the Statistics table."""
    with session_scope(session=inst.get_session(), read_only=True) as sess:
        min_ts, max_ts = (
            sess.query(func.min(Statistics.start_ts), func.max(Statistics.start_ts))
            .filter(Statistics.metadata_id.in_(metadata_ids))
            .one()
        )
        return min_ts, max_ts


def _get_min_max_start_ts_short_term(metadata_ids: set[int], inst: Any) -> tuple[float | None, float | None]:
    """Return min/max start_ts for the given metadata IDs from the StatisticsShortTerm table."""
    with session_scope(session=inst.get_session(), read_only=True) as sess:
        min_ts, max_ts = (
            sess.query(func.min(StatisticsShortTerm.start_ts), func.max(StatisticsShortTerm.start_ts))
            .filter(StatisticsShortTerm.metadata_id.in_(metadata_ids))
            .one()
        )
        return min_ts, max_ts


async def get_global_statistics_time_range(hass: HomeAssistant, *, metadata_ids: set[int]) -> tuple[dt.datetime, dt.datetime]:
    """Get the global (min start, max start) time range for the given metadata IDs.

    Returns datetimes in UTC.
    """
    if not metadata_ids:
        handle_error("No statistics metadata IDs provided")

    recorder_instance = get_instance(hass)
    if recorder_instance is None:
        handle_error("Recorder component is not running")

    min_ts, max_ts = await recorder_instance.async_add_executor_job(_get_min_max_start_ts, metadata_ids, recorder_instance)

    if min_ts is None or max_ts is None:
        short_min_ts, short_max_ts = await recorder_instance.async_add_executor_job(_get_min_max_start_ts_short_term, metadata_ids, recorder_instance)

        if short_min_ts is not None or short_max_ts is not None:
            handle_error(
                "No long-term (hourly) statistics found yet. Only short-term statistics are available. "
                "Please wait until Home Assistant has generated long-term statistics, or provide explicit start_time and end_time."
            )

        handle_error("No statistics found in database for the selected entities")

    start_dt = dt_util.utc_from_timestamp(min_ts)
    end_dt = dt_util.utc_from_timestamp(max_ts)

    _LOGGER.debug("Global statistics time range determined: start=%s end=%s", start_dt, end_dt)
    return start_dt, end_dt
