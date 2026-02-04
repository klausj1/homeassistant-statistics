"""Export statistics functionality."""

import datetime as dt
import fnmatch
import zoneinfo
from typing import TYPE_CHECKING, cast

import pytz
from homeassistant.components.recorder.statistics import get_metadata, list_statistic_ids, statistics_during_period
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.recorder import get_instance

if TYPE_CHECKING:
    from homeassistant.components.recorder.core import Recorder

from custom_components.import_statistics import helpers
from custom_components.import_statistics.const import (
    ATTR_DATETIME_FORMAT,
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_END_TIME,
    ATTR_ENTITIES,
    ATTR_FILENAME,
    ATTR_SPLIT_BY,
    ATTR_START_TIME,
    ATTR_TIMEZONE_IDENTIFIER,
    DATETIME_DEFAULT_FORMAT,
    DATETIME_INPUT_FORMAT,
)
from custom_components.import_statistics.export_database_access import get_global_statistics_time_range
from custom_components.import_statistics.export_service_helper import (
    prepare_export_data,
    prepare_export_json,
    split_statistics_by_type,
    write_export_file,
    write_export_json,
)
from custom_components.import_statistics.helpers import _LOGGER

_BROAD_PATTERN_SINGLE_WILDCARD_COUNT = 1
_BROAD_PATTERN_MIN_LEN = 2


def _parse_and_validate_time(time_str: str | None, tz: zoneinfo.ZoneInfo, time_name: str) -> dt.datetime | None:
    """Parse and validate a time string to datetime."""
    if time_str is None:
        return None

    if not isinstance(time_str, str):
        helpers.handle_error(f"{time_name} must be a string")

    try:
        time_dt = dt.datetime.strptime(time_str, DATETIME_INPUT_FORMAT).replace(tzinfo=tz).astimezone(dt.UTC)
    except ValueError as e:
        helpers.handle_error(f"Invalid datetime format. Expected 'YYYY-MM-DD HH:MM:SS': {e}")

    if time_dt.minute != 0 or time_dt.second != 0:
        helpers.handle_error(f"{time_name} must be a full hour (minutes and seconds must be 0)")

    return time_dt


async def _get_statistic_ids(hass: HomeAssistant, entities_input: list[str] | None, recorder_instance: "Recorder") -> list[str]:
    """Get statistic IDs from entities input or fetch all from database."""
    if entities_input is None or len(entities_input) == 0:
        _LOGGER.info("No entities specified, fetching all statistics from database")
        all_stats = await recorder_instance.async_add_executor_job(lambda: list_statistic_ids(hass))
        statistic_ids = [stat["statistic_id"] for stat in all_stats]
        _LOGGER.info("Found %d statistics in database", len(statistic_ids))
        return statistic_ids

    if "*" in entities_input and len(entities_input) > 1:
        helpers.handle_error("'*' cannot be combined with other entities. Omit the entities field to export all statistics.")

    def _is_broad_domain_pattern(pattern: str) -> bool:
        return (
            pattern.count("*") == _BROAD_PATTERN_SINGLE_WILDCARD_COUNT
            and pattern.endswith("*")
            and len(pattern) >= _BROAD_PATTERN_MIN_LEN
            and pattern[-2] in {".", ":"}
        )

    broad_patterns = [pattern for pattern in entities_input if "*" in pattern and _is_broad_domain_pattern(pattern)]
    if broad_patterns and len(entities_input) > 1:
        helpers.handle_error(
            f"Broad pattern(s) {broad_patterns!r} cannot be combined with other entities. Use only the pattern, or omit entities to export all statistics."
        )

    for entry in entities_input:
        if entry == "*":
            helpers.handle_error("Pattern cannot be just '*'")
        if "*" not in entry:
            helpers.get_source(entry)

    all_stats = await recorder_instance.async_add_executor_job(lambda: list_statistic_ids(hass))
    all_statistic_ids = [stat["statistic_id"] for stat in all_stats]

    statistic_ids: list[str] = []
    for entry in entities_input:
        if "*" in entry:
            matched_ids = [sid for sid in all_statistic_ids if fnmatch.fnmatchcase(sid, entry)]
            if not matched_ids:
                _LOGGER.warning("Pattern %s matched no statistics", entry)
            statistic_ids.extend(matched_ids)
            continue

        if entry not in all_statistic_ids:
            _LOGGER.warning("Statistic ID %s not found", entry)
            continue
        statistic_ids.append(entry)

    statistic_ids = list(dict.fromkeys(statistic_ids))

    if not statistic_ids:
        helpers.handle_error("No statistics found for the provided entities/patterns")

    return statistic_ids


async def _resolve_time_range(
    hass: HomeAssistant,
    start_dt: dt.datetime | None,
    end_dt: dt.datetime | None,
    metadata: dict,
) -> tuple[dt.datetime, dt.datetime]:
    """Resolve start and end times, fetching from database if needed."""
    if start_dt is None or end_dt is None:
        metadata_ids = {meta_id for _stat_id, (meta_id, _meta_data) in metadata.items()}
        db_start_dt, db_end_dt = await get_global_statistics_time_range(hass, metadata_ids=metadata_ids)

        if db_start_dt.minute != 0 or db_start_dt.second != 0:
            helpers.handle_error("Earliest available statistic timestamp is not a full hour (unexpected)")
        if db_end_dt.minute != 0 or db_end_dt.second != 0:
            helpers.handle_error("Most recent available statistic timestamp is not a full hour (unexpected)")

        start_dt = start_dt or db_start_dt
        end_dt = end_dt or db_end_dt

    if start_dt is None or end_dt is None:
        helpers.handle_error("Implementation error: start/end time resolution failed")

    if start_dt > end_dt:
        helpers.handle_error(f"start_time ({start_dt}) must be before or equal to end_time ({end_dt})")

    return start_dt, end_dt


async def get_statistics_from_recorder(
    hass: HomeAssistant,
    entities_input: list[str] | None,
    start_time_str: str | None,
    end_time_str: str | None,
    timezone_identifier: str = "Europe/Vienna",
) -> tuple[dict, dict]:
    """
    Fetch statistics from Home Assistant recorder API.

    Uses the recorder API to avoid direct database access.

    Args:
        hass: Home Assistant instance
        entities_input: List of entity IDs or statistic IDs, or None to export all statistics
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

    try:
        tz = zoneinfo.ZoneInfo(timezone_identifier)
    except zoneinfo.ZoneInfoNotFoundError:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier!r}")

    # Parse and validate time strings
    start_dt = _parse_and_validate_time(start_time_str, tz, "start_time")
    end_dt = _parse_and_validate_time(end_time_str, tz, "end_time")

    # Get recorder instance
    recorder_instance = get_instance(hass)
    if recorder_instance is None:
        helpers.handle_error("Recorder component is not running")

    # Get statistic IDs
    statistic_ids = await _get_statistic_ids(hass, entities_input, recorder_instance)

    # Fetch metadata to get units
    metadata = await recorder_instance.async_add_executor_job(lambda: get_metadata(hass, statistic_ids=set(statistic_ids)))

    # Extract units from metadata
    units_dict = {statistic_id: meta_data.get("unit_of_measurement", "") for statistic_id, (_meta_id, meta_data) in metadata.items()}

    # Resolve time range
    start_dt, end_dt = await _resolve_time_range(hass, start_dt, end_dt, metadata)

    # statistics_during_period returns data as:
    # {"statistic_id": [{"start": datetime, "end": datetime, "mean": ..., ...}]}
    # Log the requested time range and statistic IDs for debugging purposes
    _LOGGER.debug("Fetching statistics from %s to %s for %s", start_dt, end_dt, statistic_ids)

    # Use recorder's executor for blocking database call
    # Calculate end_dt_plus_hour as datetime (not timedelta)
    end_dt_plus_hour = cast("dt.datetime", end_dt + dt.timedelta(hours=1))
    statistics_dict = await recorder_instance.async_add_executor_job(
        lambda: statistics_during_period(
            hass,
            start_dt,
            end_dt_plus_hour,  # We always use 1h interval, so e.g. endtime 04:00 contains the value valid between 04:00 and 05:00,
            # and this value should be included
            set(statistic_ids),
            "hour",  # period
            None,  # units
            {"max", "mean", "min", "state", "sum"},  # types
        )
    )

    _LOGGER.debug("Statistics fetched: %s", statistics_dict)
    # if len of statistics_dict is 0, log a warning
    if not statistics_dict:
        helpers.handle_error("No statistics found for the given parameters. Did not create any export file.")
    return statistics_dict, units_dict


def _validate_service_parameters(call: ServiceCall) -> tuple[str, list[str] | None, str | None, str | None, str]:
    """Validate and extract service call parameters."""
    filename_raw = call.data.get(ATTR_FILENAME)
    entities_input_raw = call.data.get(ATTR_ENTITIES)
    start_time_str_raw = call.data.get(ATTR_START_TIME)
    end_time_str_raw = call.data.get(ATTR_END_TIME)
    split_by_raw = call.data.get(ATTR_SPLIT_BY, "none")

    # Validate required parameters
    if not filename_raw or not isinstance(filename_raw, str):
        helpers.handle_error("filename is required and must be a string")
    if entities_input_raw is not None and not isinstance(entities_input_raw, list):
        helpers.handle_error("entities must be a list")
    if start_time_str_raw is not None and not isinstance(start_time_str_raw, str):
        helpers.handle_error("start_time must be a string")
    if end_time_str_raw is not None and not isinstance(end_time_str_raw, str):
        helpers.handle_error("end_time must be a string")
    if split_by_raw is not None and not isinstance(split_by_raw, str):
        helpers.handle_error("split_by must be a string")

    # Type narrowing
    filename: str = cast("str", filename_raw)
    entities_input: list[str] | None = None if entities_input_raw is None else cast("list[str]", entities_input_raw)
    start_time_str: str | None = None if start_time_str_raw is None else cast("str", start_time_str_raw)
    end_time_str: str | None = None if end_time_str_raw is None else cast("str", end_time_str_raw)
    split_by: str = "none" if split_by_raw is None else cast("str", split_by_raw)

    # Backwards compatible rename: 'sensor' -> 'measurement'
    if split_by == "sensor":
        split_by = "measurement"

    valid_split_values = {"none", "measurement", "counter", "both"}
    if split_by not in valid_split_values:
        helpers.handle_error(f"split_by must be one of {sorted(valid_split_values)}, got {split_by!r}")

    return filename, entities_input, start_time_str, end_time_str, split_by


def _filename_with_suffix(input_filename: str, suffix: str) -> str:
    """Add suffix to filename before extension."""
    if "." in input_filename:
        base, ext = input_filename.rsplit(".", 1)
        return f"{base}{suffix}.{ext}"
    return f"{input_filename}{suffix}"


async def _export_split_file(  # noqa: PLR0913
    hass: HomeAssistant,
    filename: str,
    stats_dict: dict,
    units_dict: dict,
    suffix: str,
    timezone_identifier: str,
    datetime_format: str,
    *,
    delimiter: str,
    decimal_separator: str,
) -> None:
    """Export a single split file (measurement or counter)."""
    if not stats_dict:
        return

    output_filename = _filename_with_suffix(filename, suffix)
    file_path = helpers.validate_filename(output_filename, hass.config.config_dir)

    if filename.lower().endswith(".json"):
        json_data = await hass.async_add_executor_job(lambda: prepare_export_json(stats_dict, timezone_identifier, datetime_format, units_dict))
        await hass.async_add_executor_job(lambda: write_export_json(file_path, json_data))
    else:
        columns, rows = await hass.async_add_executor_job(
            lambda: prepare_export_data(stats_dict, timezone_identifier, datetime_format, decimal_separator=decimal_separator, units_dict=units_dict)
        )
        await hass.async_add_executor_job(lambda: write_export_file(file_path, columns, rows, delimiter))


async def _export_split_statistics(  # noqa: PLR0913
    hass: HomeAssistant,
    filename: str,
    statistics_dict: dict,
    units_dict: dict,
    split_by: str,
    timezone_identifier: str,
    datetime_format: str,
    decimal_separator: str,
    delimiter: str,
) -> None:
    """Export statistics split by type."""
    measurement_stats, counter_stats, measurement_units, counter_units = split_statistics_by_type(statistics_dict, units_dict=units_dict)

    write_measurements = split_by in {"measurement", "both"}
    write_counters = split_by in {"counter", "both"}

    if write_measurements:
        await _export_split_file(
            hass,
            filename,
            measurement_stats,
            measurement_units,
            "_measurements",
            timezone_identifier,
            datetime_format,
            decimal_separator=decimal_separator,
            delimiter=delimiter,
        )

    if write_counters:
        await _export_split_file(
            hass,
            filename,
            counter_stats,
            counter_units,
            "_counters",
            timezone_identifier,
            datetime_format,
            decimal_separator=decimal_separator,
            delimiter=delimiter,
        )


async def _export_single_file(  # noqa: PLR0913
    hass: HomeAssistant,
    filename: str,
    statistics_dict: dict,
    units_dict: dict,
    timezone_identifier: str,
    datetime_format: str,
    decimal_separator: str,
    delimiter: str,
) -> None:
    """Export all statistics to a single file."""
    file_path = helpers.validate_filename(filename, hass.config.config_dir)
    if filename.lower().endswith(".json"):
        json_data = await hass.async_add_executor_job(lambda: prepare_export_json(statistics_dict, timezone_identifier, datetime_format, units_dict))
        await hass.async_add_executor_job(lambda: write_export_json(file_path, json_data))
    else:
        columns, rows = await hass.async_add_executor_job(
            lambda: prepare_export_data(statistics_dict, timezone_identifier, datetime_format, decimal_separator=decimal_separator, units_dict=units_dict)
        )
        await hass.async_add_executor_job(lambda: write_export_file(file_path, columns, rows, delimiter))


async def handle_export_statistics_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle export_statistics service implementation."""
    # Validate and extract parameters
    filename, entities_input, start_time_str, end_time_str, split_by = _validate_service_parameters(call)

    # Extract other parameters (with defaults)
    # Use HA timezone as default instead of hardcoded "Europe/Vienna"
    timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER, hass.config.time_zone)
    if timezone_identifier not in pytz.all_timezones:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    delimiter = helpers.validate_delimiter(call.data.get(ATTR_DELIMITER, "\t"))

    # Get decimal separator from service call (default is "dot ('.')")
    decimal_input = call.data.get(ATTR_DECIMAL, "dot ('.')")

    # Map UI-friendly values to actual separators
    decimal_map = {
        "dot ('.')": ".",
        "comma (',')": ",",
        ".": ".",  # Support old format for backward compatibility
        ",": ",",  # Support old format for backward compatibility
    }

    decimal_separator = decimal_map.get(decimal_input)
    if decimal_separator is None:
        helpers.handle_error(f"Invalid decimal separator: {decimal_input}. Must be \"dot ('.')\" or \"comma (',')\"")

    # Type narrowing: handle_error raises exception, so after this point decimal_separator is str
    decimal_separator = cast("str", decimal_separator)

    datetime_format = call.data.get(ATTR_DATETIME_FORMAT, DATETIME_DEFAULT_FORMAT)

    _LOGGER.info("Service handle_export_statistics called")
    _LOGGER.info("Exporting entities: %s", entities_input if entities_input else "ALL")
    _LOGGER.info("Time range: %s to %s", start_time_str if start_time_str is not None else "AUTO", end_time_str if end_time_str is not None else "AUTO")
    _LOGGER.info("Output file: %s", filename)

    # Get statistics from recorder API
    statistics_dict, units_dict = await get_statistics_from_recorder(hass, entities_input, start_time_str, end_time_str, timezone_identifier)

    # Export based on split_by parameter
    if split_by != "none":
        await _export_split_statistics(
            hass,
            filename,
            statistics_dict,
            units_dict,
            split_by,
            timezone_identifier,
            datetime_format,
            decimal_separator=decimal_separator,
            delimiter=delimiter,
        )
    else:
        await _export_single_file(
            hass, filename, statistics_dict, units_dict, timezone_identifier, datetime_format, decimal_separator=decimal_separator, delimiter=delimiter
        )

    hass.states.async_set("import_statistics.export_statistics", "OK")
    _LOGGER.info("Export completed successfully")
