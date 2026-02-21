"""Export inventory service for exporting statistics metadata."""

import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.recorder import get_instance

from custom_components.import_statistics.export_inventory_database_access import fetch_inventory_data, has_long_term_statistics
from custom_components.import_statistics.export_inventory_helper import (
    build_inventory_rows,
    build_summary,
    validate_inventory_params,
    write_inventory_file,
)
from custom_components.import_statistics.helpers import handle_error

_LOGGER = logging.getLogger(__name__)


async def handle_export_inventory_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """
    Handle the export_inventory service call.

    Exports metadata-only inventory of all long-term statistics to a TSV/CSV file.

    Args:
        hass: The Home Assistant instance.
        call: The service call containing filename, delimiter, and optional timezone_identifier.

    """
    filename = call.data.get("filename")
    if not filename or not isinstance(filename, str):
        handle_error("filename is required and must be a string")

    file_suffix = Path(filename).suffix.lower()
    if file_suffix not in {".csv", ".tsv"}:
        handle_error(f"Unsupported filename extension for {Path(filename).name!r}. Supported extensions: .csv, .tsv")

    delimiter = call.data.get("delimiter")
    if delimiter is None:
        delimiter = "," if file_suffix == ".csv" else "\t"
    timezone_identifier = call.data.get("timezone_identifier")

    _LOGGER.info(
        "export_inventory called: filename=%s, delimiter=%r, timezone=%s",
        filename,
        delimiter,
        timezone_identifier or "(HA default)",
    )

    # Validate parameters
    config_dir = hass.config.config_dir
    filepath, validated_delimiter = validate_inventory_params(filename, delimiter, config_dir)

    # Resolve timezone (default to HA configured timezone)
    if timezone_identifier:
        try:
            tz = ZoneInfo(timezone_identifier)
        except KeyError:
            handle_error(f"Invalid timezone identifier: {timezone_identifier}")
    else:
        tz = ZoneInfo(hass.config.time_zone)

    _LOGGER.debug("Using timezone: %s", tz)

    # Ensure recorder is available
    recorder_instance = get_instance(hass)
    if recorder_instance is None:
        handle_error("Recorder component is not running")

    # Fetch all inventory data from database
    inventory_data = await fetch_inventory_data(hass)

    # Check if there are any long-term statistics
    if not has_long_term_statistics(inventory_data):
        if inventory_data.metadata_rows:
            handle_error("No long-term statistics found. Statistics exist but may only have short-term data.")
        handle_error("No statistics found in the database")

    # Build inventory rows with classification
    rows = build_inventory_rows(inventory_data, tz)

    # Build summary
    summary = build_summary(rows, inventory_data)

    # Write output file
    await recorder_instance.async_add_executor_job(
        write_inventory_file,
        filepath,
        rows,
        summary,
        validated_delimiter,
        tz,
    )
    summary_filepath = filepath.with_suffix(".txt")

    _LOGGER.info(
        "Inventory export complete: %d statistics written to %s (summary: %s)",
        len(rows),
        filepath,
        summary_filepath,
    )
