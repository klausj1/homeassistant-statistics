"""The import_statistics integration."""

import datetime as dt
import zoneinfo
from typing import Any

from homeassistant.components.recorder import get_instance, statistics
from homeassistant.components.recorder.db_schema import Statistics
from homeassistant.components.recorder.statistics import (
    _statistics_at_time,
    async_add_external_statistics,
    async_import_statistics,
    get_metadata,
    statistics_during_period,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from custom_components.import_statistics import helpers, prepare_data
from custom_components.import_statistics.const import (
    ATTR_DATETIME_FORMAT,
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_END_TIME,
    ATTR_ENTITIES,
    ATTR_FILENAME,
    ATTR_START_TIME,
    ATTR_TIMEZONE_IDENTIFIER,
    DATETIME_DEFAULT_FORMAT,
    DATETIME_INPUT_FORMAT,
    DOMAIN,
)
from custom_components.import_statistics.helpers import _LOGGER, UnitFrom

# Use empty_config_schema because the component does not have any config options
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

# Minimum tuple length for delta processing marker
_DELTA_MARKER_TUPLE_LENGTH = 6


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
        helpers.handle_error("Recorder component is not running")

    # Get metadata for all statistic_ids in one call
    statistic_ids = list(references_needed.keys())
    _LOGGER.debug("Getting metadata for %d statistics", len(statistic_ids))

    try:
        metadata_dict = await recorder_instance.async_add_executor_job(lambda: get_metadata(hass, statistic_ids=set(statistic_ids)))
    except Exception as exc:  # noqa: BLE001
        helpers.handle_error(f"Failed to get metadata: {exc}")

    if not metadata_dict:
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


async def get_statistics_from_recorder(
    hass: HomeAssistant, entities_input: list[str], start_time_str: str, end_time_str: str, timezone_identifier: str = "Europe/Vienna"
) -> tuple[dict, dict]:
    """
    Fetch statistics from Home Assistant recorder API.

    Uses the recorder API to avoid direct database access.

    Args:
        hass: Home Assistant instance
        entities_input: List of entity IDs or statistic IDs
        start_time_str: Start time in format "YYYY-MM-DD HH:MM:SS" (interpreted in timezone_identifier)
        end_time_str: End time in format "YYYY-MM-DD HH:MM:SS" (interpreted in timezone_identifier)
        timezone_identifier: Timezone for interpreting the start/end times (default: "Europe/Vienna")

    Returns:
        tuple: (statistics_dict, units_dict)
        - statistics_dict: {"statistic_id": [{"start": float, "end": float, "mean": ..., ...}], ...}
          Times in returned data are Unix timestamps (float) in UTC
        - units_dict: {"statistic_id": "unit_of_measurement", ...}

    Raises:
        HomeAssistantError: If time formats are invalid or recorder is not running

    """
    _LOGGER.info("Fetching statistics from recorder API")

    # Parse datetime strings (format: "2025-12-01 12:00:00")
    # Times are provided in the user's selected timezone
    try:
        # Apply the user's timezone to the naive datetimes
        tz = zoneinfo.ZoneInfo(timezone_identifier)
        start_dt = dt.datetime.strptime(start_time_str, DATETIME_INPUT_FORMAT).replace(tzinfo=tz)
        end_dt = dt.datetime.strptime(end_time_str, DATETIME_INPUT_FORMAT).replace(tzinfo=tz)

        # Convert to UTC for the recorder API
        start_dt = start_dt.astimezone(dt.UTC)
        end_dt = end_dt.astimezone(dt.UTC)
    except ValueError as e:
        helpers.handle_error(f"Invalid datetime format. Expected 'YYYY-MM-DD HH:MM:SS': {e}")

    # Normalize to full hours
    if start_dt.minute != 0 or start_dt.second != 0:
        helpers.handle_error("start_time must be a full hour (minutes and seconds must be 0)")
    if end_dt.minute != 0 or end_dt.second != 0:
        helpers.handle_error("end_time must be a full hour (minutes and seconds must be 0)")

    # Convert string entity/statistic IDs to statistic_ids for recorder API
    statistic_ids = []
    for entity in entities_input:
        # Both "sensor.temperature" and "sensor:external_temp" formats supported
        # The get_source() helper validates the format
        helpers.get_source(entity)  # Validate
        statistic_ids.append(entity)

    # Use recorder API to get statistics
    recorder_instance = get_instance(hass)
    if recorder_instance is None:
        helpers.handle_error("Recorder component is not running")

    # Fetch metadata to get units (single call for all entities) - use recorder executor for database access
    metadata = await recorder_instance.async_add_executor_job(lambda: get_metadata(hass, statistic_ids=set(statistic_ids)))

    # Extract units from metadata
    units_dict = {}
    for statistic_id, (_meta_id, meta_data) in metadata.items():
        units_dict[statistic_id] = meta_data.get("unit_of_measurement", "")

    # statistics_during_period returns data as:
    # {"statistic_id": [{"start": datetime, "end": datetime, "mean": ..., ...}]}
    # Log the requested time range and statistic IDs for debugging purposes
    _LOGGER.debug("Fetching statistics from %s to %s for %s", start_dt, end_dt, statistic_ids)

    # Use recorder's executor for blocking database call
    statistics_dict = await recorder_instance.async_add_executor_job(
        lambda: statistics_during_period(
            hass,
            start_dt,
            end_dt
            + dt.timedelta(
                hours=1
            ),  # We always use 1h interval, so e.g. endtime 04:00 contains the value valid between 04:00 and 05:00, and this value should be included
            statistic_ids,
            "hour",  # period
            None,  # units
            ["max", "mean", "min", "state", "sum"],  # types
        )
    )

    _LOGGER.debug("Statistics fetched: %s", statistics_dict)
    return statistics_dict, units_dict


async def _handle_import_from_file_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle import_from_file service implementation."""
    _LOGGER.info("Service handle_import_from_file called")
    file_path = f"{hass.config.config_dir}/{call.data.get(ATTR_FILENAME)}"

    hass.states.async_set("import_statistics.import_from_file", file_path)

    _LOGGER.info("Peparing data for import")
    stats, unit_from_entity = await hass.async_add_executor_job(lambda: prepare_data.prepare_data_to_import(file_path, call, hass=hass))

    # Handle delta processing marker (async operation required)
    if isinstance(stats, tuple) and len(stats) >= _DELTA_MARKER_TUPLE_LENGTH and stats[0] == "_DELTA_PROCESSING_NEEDED":
        _LOGGER.info("Delta processing detected, fetching references from database")
        _marker, df, references_needed, timezone_identifier, datetime_format, unit_from_where = stats[:_DELTA_MARKER_TUPLE_LENGTH]

        # Fetch references from database asynchronously
        references = await get_oldest_statistics_before(hass, references_needed)
        _LOGGER.debug("References fetched: %s", references)

        # Convert delta dataframe with references (run in executor)
        stats = await hass.async_add_executor_job(
            lambda: prepare_data.convert_delta_dataframe_with_references(df, references, timezone_identifier, datetime_format, unit_from_where)
        )

    import_stats(hass, stats, unit_from_entity)


async def _handle_import_from_json_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle import_from_json service implementation."""
    _LOGGER.info("Service handle_import_from_json called")
    stats, unit_from_entity = await hass.async_add_executor_job(lambda: prepare_data.prepare_json_data_to_import(call, hass=hass))

    # Handle delta processing marker (async operation required)
    if isinstance(stats, tuple) and len(stats) >= _DELTA_MARKER_TUPLE_LENGTH and stats[0] == "_DELTA_PROCESSING_NEEDED":
        _LOGGER.info("Delta processing detected, fetching references from database")
        _marker, df, references_needed, timezone_identifier, datetime_format, unit_from_where = stats[:_DELTA_MARKER_TUPLE_LENGTH]

        # Fetch references from database asynchronously
        references = await get_oldest_statistics_before(hass, references_needed)

        # Convert delta dataframe with references (run in executor)
        stats = await hass.async_add_executor_job(
            lambda: prepare_data.convert_delta_dataframe_with_references(df, references, timezone_identifier, datetime_format, unit_from_where)
        )

    import_stats(hass, stats, unit_from_entity)


async def _handle_export_statistics_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle export_statistics service implementation."""
    filename = call.data.get(ATTR_FILENAME)
    entities_input = call.data.get(ATTR_ENTITIES)
    start_time_str = call.data.get(ATTR_START_TIME)
    end_time_str = call.data.get(ATTR_END_TIME)

    # Extract other parameters (with defaults matching services.yaml)
    timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER, "Europe/Vienna")
    delimiter = call.data.get(ATTR_DELIMITER, "\t")
    decimal = call.data.get(ATTR_DECIMAL, False)
    datetime_format = call.data.get(ATTR_DATETIME_FORMAT, DATETIME_DEFAULT_FORMAT)

    _LOGGER.info("Service handle_export_statistics called")
    _LOGGER.info("Exporting entities: %s", entities_input)
    _LOGGER.info("Time range: %s to %s", start_time_str, end_time_str)
    _LOGGER.info("Output file: %s", filename)

    # Validate filename and build safe file path
    file_path = helpers.validate_filename(filename, hass.config.config_dir)

    # Validate delimiter and set default
    delimiter = helpers.validate_delimiter(delimiter)

    # Get statistics from recorder API (using user's timezone for start/end times)
    statistics_dict, units_dict = await get_statistics_from_recorder(hass, entities_input, start_time_str, end_time_str, timezone_identifier)

    # Prepare data for export (HA-independent)
    if filename.lower().endswith(".json"):
        # Export as JSON - run in executor to avoid blocking I/O
        json_data = await hass.async_add_executor_job(
            lambda: prepare_data.prepare_export_json(statistics_dict, timezone_identifier, datetime_format, units_dict)
        )
        await hass.async_add_executor_job(lambda: prepare_data.write_export_json(file_path, json_data))
    else:
        # Export as CSV/TSV (default) - run in executor to avoid blocking I/O
        columns, rows = await hass.async_add_executor_job(
            lambda: prepare_data.prepare_export_data(statistics_dict, timezone_identifier, datetime_format, decimal_comma=decimal, units_dict=units_dict)
        )
        await hass.async_add_executor_job(lambda: prepare_data.write_export_file(file_path, columns, rows, delimiter))

    hass.states.async_set("import_statistics.export_statistics", "OK")
    _LOGGER.info("Export completed successfully")


def setup(hass: HomeAssistant, config: ConfigType) -> bool:  # pylint: disable=unused-argument  # noqa: ARG001
    """Set up is called when Home Assistant is loading our component."""

    async def handle_import_from_file(call: ServiceCall) -> None:
        """Handle the service call."""
        await _handle_import_from_file_impl(hass, call)

    hass.services.register(DOMAIN, "import_from_file", handle_import_from_file)

    async def handle_import_from_json(call: ServiceCall) -> None:
        """Handle the json service call."""
        await _handle_import_from_json_impl(hass, call)

    hass.services.register(DOMAIN, "import_from_json", handle_import_from_json)

    async def handle_export_statistics(call: ServiceCall) -> None:
        """Handle the export statistics service call."""
        await _handle_export_statistics_impl(hass, call)

    hass.services.register(DOMAIN, "export_statistics", handle_export_statistics)

    # Return boolean to indicate that initialization was successful.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # pylint: disable=unused-argument  # noqa: ARG001
    """Set up the device based on a config entry."""
    return True


def import_stats(hass: HomeAssistant, stats: dict, unit_from_entity: UnitFrom) -> None:
    """Import statistics into Home Assistant."""
    _LOGGER.info("Checking if all entities exist")
    check_all_entities_exists(hass, stats)

    if unit_from_entity:
        _LOGGER.info("Adding units from entities")
        add_unit_for_all_entities(hass, stats)

    _LOGGER.info("Calling hass import methods")
    for stat in stats.values():
        metadata = stat[0]
        statistics = stat[1]
        _LOGGER.debug("Calling async_import_statistics / async_add_external_statistics with:")
        _LOGGER.debug("Metadata:")
        _LOGGER.debug(metadata)
        _LOGGER.debug("Statistics:")
        _LOGGER.debug(statistics)

        if metadata["source"] == "recorder":
            if check_entity_exists(hass, metadata["statistic_id"]):
                async_import_statistics(hass, metadata, statistics)
        else:
            async_add_external_statistics(hass, metadata, statistics)

    _LOGGER.info("Finished importing data")


def check_all_entities_exists(hass: HomeAssistant, stats: dict) -> None:
    """
    Check all entities in stats if they exist.

    Args:
    ----
        hass: home assistant
        stats: dictionary with all statistic data

    Returns:
    -------
        n/a

    Raises:
    ------
        n/a

    """
    for stat in stats.values():
        metadata = stat[0]

        if metadata["source"] == "recorder":
            check_entity_exists(hass, metadata["statistic_id"])


def check_entity_exists(hass: HomeAssistant, entity_id: Any) -> bool:
    """
    Check if a specific entity exists.

    Args:
    ----
        hass: home assistant
        entity_id: id to check for existence

    Returns:
    -------
        bool: True if entity exists, otherwise exception is thrown

    Raises:
    ------
        HomeAssistantError: If entity does not exist

    """
    entity_exists = hass.states.get(entity_id) is not None

    if not entity_exists:
        helpers.handle_error(f"Entity does not exist: '{entity_id}'")
        return False

    return True


def add_unit_for_all_entities(hass: HomeAssistant, stats: dict) -> None:
    """
    Add units for all rows to be imported.

    Args:
    ----
        hass: home assistant
        stats: dictionary with all statistic data

    Returns:
    -------
        n/a

    Raises:
    ------
        n/a

    """
    for stat in stats.values():
        metadata = stat[0]

        if metadata["source"] == "recorder":
            add_unit_for_entity(hass, metadata)


def add_unit_for_entity(hass: HomeAssistant, metadata: dict) -> None:
    """
    Add units for one rows to be imported.

    Args:
    ----
        hass: home assistant
        entity_id: id to check for existence
        metadata: metadata of row to be imported

    Returns:
    -------
        n/a

    Raises:
    ------
        HomeAssistantError: If entity does not exist

    """
    entity_id = metadata["statistic_id"]
    entity = hass.states.get(entity_id)

    if entity is None:
        helpers.handle_error(f"Entity does not exist: '{entity_id}'")
    elif metadata.get("unit_of_measurement", "") == "":
        uom = None
        if hasattr(entity, "attributes") and isinstance(entity.attributes, dict):
            uom = entity.attributes.get("unit_of_measurement")
        if uom:
            metadata["unit_of_measurement"] = uom
            _LOGGER.debug(
                "Adding unit '%s' for entity_id: %s",
                metadata["unit_of_measurement"],
                entity_id,
            )
