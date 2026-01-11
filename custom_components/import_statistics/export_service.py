"""Export statistics functionality."""

import datetime as dt
import zoneinfo

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import get_metadata, statistics_during_period
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.import_statistics import helpers
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
)
from custom_components.import_statistics.export_service_helper import prepare_export_data, prepare_export_json, write_export_file, write_export_json
from custom_components.import_statistics.helpers import _LOGGER


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


async def handle_export_statistics_impl(hass: HomeAssistant, call: ServiceCall) -> None:
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
