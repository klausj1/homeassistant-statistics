"""Export statistics functionality."""

import datetime as dt
import zoneinfo
from typing import cast

from homeassistant.components.recorder.statistics import get_metadata, list_statistic_ids, statistics_during_period
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.recorder import get_instance

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

    tz = zoneinfo.ZoneInfo(timezone_identifier)

    # Validate/parse provided start/end strings early, before any awaited DB calls.
    # This keeps error behavior consistent even in unit tests where recorder is mocked.
    start_dt: dt.datetime | None = None
    end_dt: dt.datetime | None = None

    if start_time_str is not None:
        if not isinstance(start_time_str, str):
            helpers.handle_error("start_time must be a string")
        try:
            start_dt = dt.datetime.strptime(start_time_str, DATETIME_INPUT_FORMAT).replace(tzinfo=tz).astimezone(dt.UTC)
        except ValueError as e:
            helpers.handle_error(f"Invalid datetime format. Expected 'YYYY-MM-DD HH:MM:SS': {e}")

        if start_dt.minute != 0 or start_dt.second != 0:
            helpers.handle_error("start_time must be a full hour (minutes and seconds must be 0)")

    if end_time_str is not None:
        if not isinstance(end_time_str, str):
            helpers.handle_error("end_time must be a string")
        try:
            end_dt = dt.datetime.strptime(end_time_str, DATETIME_INPUT_FORMAT).replace(tzinfo=tz).astimezone(dt.UTC)
        except ValueError as e:
            helpers.handle_error(f"Invalid datetime format. Expected 'YYYY-MM-DD HH:MM:SS': {e}")

        if end_dt.minute != 0 or end_dt.second != 0:
            helpers.handle_error("end_time must be a full hour (minutes and seconds must be 0)")

    # Get recorder instance
    recorder_instance = get_instance(hass)
    if recorder_instance is None:
        helpers.handle_error("Recorder component is not running")

    # Convert string entity/statistic IDs to statistic_ids for recorder API
    # If no entities specified, fetch all available statistic IDs from database
    if entities_input is None or len(entities_input) == 0:
        _LOGGER.info("No entities specified, fetching all statistics from database")
        # Get all statistic IDs from recorder
        all_stats = await recorder_instance.async_add_executor_job(lambda: list_statistic_ids(hass))
        statistic_ids = [stat["statistic_id"] for stat in all_stats]
        _LOGGER.info("Found %d statistics in database", len(statistic_ids))
    else:
        # Validate and use provided entities
        statistic_ids = []
        for entity in entities_input:
            # Both "sensor.temperature" and "sensor:external_temp" formats supported
            # The get_source() helper validates the format
            helpers.get_source(entity)  # Validate
            statistic_ids.append(entity)

    # Use recorder API to get statistics (recorder_instance already obtained above)

    # Fetch metadata to get units (single call for all entities) - use recorder executor for database access
    metadata = await recorder_instance.async_add_executor_job(lambda: get_metadata(hass, statistic_ids=set(statistic_ids)))

    # Extract units from metadata
    units_dict = {}
    for statistic_id, (_meta_id, meta_data) in metadata.items():
        units_dict[statistic_id] = meta_data.get("unit_of_measurement", "")

    if start_dt is None or end_dt is None:
        metadata_ids = {meta_id for _stat_id, (meta_id, _meta_data) in metadata.items()}
        db_start_dt, db_end_dt = await get_global_statistics_time_range(hass, metadata_ids=metadata_ids)

        if db_start_dt.minute != 0 or db_start_dt.second != 0:
            helpers.handle_error("Earliest available statistic timestamp is not a full hour (unexpected)")
        if db_end_dt.minute != 0 or db_end_dt.second != 0:
            helpers.handle_error("Most recent available statistic timestamp is not a full hour (unexpected)")

        if start_dt is None:
            start_dt = db_start_dt
        if end_dt is None:
            end_dt = db_end_dt

    if start_dt is None or end_dt is None:
        helpers.handle_error("Implementation error: start/end time resolution failed")

    if start_dt > end_dt:
        helpers.handle_error(f"start_time ({start_dt}) must be before or equal to end_time ({end_dt})")

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
    return statistics_dict, units_dict


async def handle_export_statistics_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle export_statistics service implementation."""
    # Get parameters from service call
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

    # Type narrowing: after validation, we know these are the correct types
    filename: str = cast("str", filename_raw)
    entities_input: list[str] | None
    if entities_input_raw is None:
        entities_input = None
    else:
        entities_input = cast("list[str]", entities_input_raw)
    start_time_str: str | None
    end_time_str: str | None
    if start_time_str_raw is None:
        start_time_str = None
    else:
        start_time_str = cast("str", start_time_str_raw)
    if end_time_str_raw is None:
        end_time_str = None
    else:
        end_time_str = cast("str", end_time_str_raw)

    split_by: str
    if split_by_raw is None:
        split_by = "none"
    else:
        split_by = cast("str", split_by_raw)
    valid_split_values = {"none", "sensor", "counter", "both"}
    if split_by not in valid_split_values:
        helpers.handle_error(f"split_by must be one of {sorted(valid_split_values)}, got {split_by!r}")

    # Extract other parameters (with defaults matching services.yaml)
    timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER, "Europe/Vienna")
    delimiter = call.data.get(ATTR_DELIMITER, "\t")
    decimal = call.data.get(ATTR_DECIMAL, False)
    datetime_format = call.data.get(ATTR_DATETIME_FORMAT, DATETIME_DEFAULT_FORMAT)

    _LOGGER.info("Service handle_export_statistics called")
    _LOGGER.info("Exporting entities: %s", entities_input if entities_input else "ALL")
    _LOGGER.info("Time range: %s to %s", start_time_str if start_time_str is not None else "AUTO", end_time_str if end_time_str is not None else "AUTO")
    _LOGGER.info("Output file: %s", filename)

    def _filename_with_suffix(input_filename: str, suffix: str) -> str:
        if "." in input_filename:
            base, ext = input_filename.rsplit(".", 1)
            return f"{base}{suffix}.{ext}"
        return f"{input_filename}{suffix}"

    # Validate delimiter and set default
    delimiter = helpers.validate_delimiter(delimiter)

    # Get statistics from recorder API (using user's timezone for start/end times)
    statistics_dict, units_dict = await get_statistics_from_recorder(hass, entities_input, start_time_str, end_time_str, timezone_identifier)

    if split_by != "none":
        sensor_stats, counter_stats, sensor_units, counter_units = split_statistics_by_type(statistics_dict, units_dict=units_dict)

        write_sensors = split_by in {"sensor", "both"}
        write_counters = split_by in {"counter", "both"}

        if filename.lower().endswith(".json"):
            if write_sensors and sensor_stats:
                sensor_filename = _filename_with_suffix(filename, "_sensors")
                sensor_file_path = helpers.validate_filename(sensor_filename, hass.config.config_dir)
                sensor_json_data = await hass.async_add_executor_job(
                    lambda: prepare_export_json(sensor_stats, timezone_identifier, datetime_format, sensor_units)
                )
                await hass.async_add_executor_job(lambda: write_export_json(sensor_file_path, sensor_json_data))

            if write_counters and counter_stats:
                counter_filename = _filename_with_suffix(filename, "_counters")
                counter_file_path = helpers.validate_filename(counter_filename, hass.config.config_dir)
                counter_json_data = await hass.async_add_executor_job(
                    lambda: prepare_export_json(counter_stats, timezone_identifier, datetime_format, counter_units)
                )
                await hass.async_add_executor_job(lambda: write_export_json(counter_file_path, counter_json_data))

        else:
            if write_sensors and sensor_stats:
                sensor_filename = _filename_with_suffix(filename, "_sensors")
                sensor_file_path = helpers.validate_filename(sensor_filename, hass.config.config_dir)
                sensor_columns, sensor_rows = await hass.async_add_executor_job(
                    lambda: prepare_export_data(
                        sensor_stats,
                        timezone_identifier,
                        datetime_format,
                        decimal_comma=decimal,
                        units_dict=sensor_units,
                    )
                )
                await hass.async_add_executor_job(lambda: write_export_file(sensor_file_path, sensor_columns, sensor_rows, delimiter))

            if write_counters and counter_stats:
                counter_filename = _filename_with_suffix(filename, "_counters")
                counter_file_path = helpers.validate_filename(counter_filename, hass.config.config_dir)
                counter_columns, counter_rows = await hass.async_add_executor_job(
                    lambda: prepare_export_data(
                        counter_stats,
                        timezone_identifier,
                        datetime_format,
                        decimal_comma=decimal,
                        units_dict=counter_units,
                    )
                )
                await hass.async_add_executor_job(lambda: write_export_file(counter_file_path, counter_columns, counter_rows, delimiter))

        hass.states.async_set("import_statistics.export_statistics", "OK")
        _LOGGER.info("Export completed successfully")
        return

    # Prepare data for export (HA-independent)
    file_path = helpers.validate_filename(filename, hass.config.config_dir)
    if filename.lower().endswith(".json"):
        # Export as JSON - run in executor to avoid blocking I/O
        json_data = await hass.async_add_executor_job(lambda: prepare_export_json(statistics_dict, timezone_identifier, datetime_format, units_dict))
        await hass.async_add_executor_job(lambda: write_export_json(file_path, json_data))
    else:
        # Export as CSV/TSV (default) - run in executor to avoid blocking I/O
        columns, rows = await hass.async_add_executor_job(
            lambda: prepare_export_data(statistics_dict, timezone_identifier, datetime_format, decimal_comma=decimal, units_dict=units_dict)
        )
        await hass.async_add_executor_job(lambda: write_export_file(file_path, columns, rows, delimiter))

    hass.states.async_set("import_statistics.export_statistics", "OK")
    _LOGGER.info("Export completed successfully")
