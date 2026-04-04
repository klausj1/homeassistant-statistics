"""Import statistics functionality."""

import datetime as dt
from dataclasses import dataclass
from typing import Any

import pandas as pd
from homeassistant.components.recorder.statistics import async_add_external_statistics, async_import_statistics, get_metadata
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.recorder import get_instance

from custom_components.import_statistics.const import ATTR_FILENAME
from custom_components.import_statistics.delta_database_access import (
    _get_newest_db_statistic,
    _get_reference_at_or_after_timestamp,
    _get_reference_before_timestamp,
)
from custom_components.import_statistics.helpers import _LOGGER, DeltaReferenceType, handle_error, is_not_in_future
from custom_components.import_statistics.import_service_delta_helper import handle_dataframe_delta
from custom_components.import_statistics.import_service_helper import (
    handle_dataframe_no_delta,
    prepare_data_to_import,
    prepare_json_data_to_import,
)


async def _process_delta_references_for_statistic(
    hass: HomeAssistant,
    statistic_id: str,
    t_oldest_import: dt.datetime,
    t_newest_import: dt.datetime,
) -> tuple[dict | None, str | None]:
    """
    Find delta references for a single statistic.

    The delta reference is the value in the database that is used to convert delta values to sum and state.
    It must be either:
      - at least one hour older than the oldest imported value (OLDER_REFERENCE)
        In this case, sum and state of the reference are needed to calculate sum and state of the oldest imported value
      - or at or after the newest imported value (NEWER_REFERENCE)
        In this case, sum and state of the reference are needed to calculate sum and state of the newest imported value

    Returns
    -------
        Tuple of (reference_data, error_message)
        Where reference_data is None if error_message is not None

    """
    # Important for understanding:
    # When timestamps are compared, newer means '>'
    # Therefore '<' means older

    # Fetch t_newest_db (most recent record in database)
    t_newest_db_record = await _get_newest_db_statistic(hass, statistic_id)
    _LOGGER.debug("Statistic %s: Newest DB record: %s", statistic_id, t_newest_db_record)
    if t_newest_db_record is None:
        msg = f"Entity '{statistic_id}': No statistics found in database for this entity."
        msg += " Also for external statistics, at least one value must exist in the database to perform delta conversion."
        return None, msg

    t_newest_db = t_newest_db_record["start"]

    # Fetch t_oldest_reference (older reference). If there is one, there is a value in the database which is older than t_oldest_import.
    # In this case we have found a reference of type OLDER_REFERENCE, unless import range is completely newer than DB range
    t_oldest_reference = await _get_reference_before_timestamp(hass, statistic_id, t_oldest_import)
    _LOGGER.debug("Statistic %s: Oldest reference before search for old %s: %s", statistic_id, t_oldest_import, t_oldest_reference)

    if t_oldest_reference is not None:
        # If import range is completely newer than DB, allow import, but change timestamp of reference to exactly t_oldest_import - 1 hour
        if t_newest_db <= t_oldest_import:
            t_oldest_reference["start"] = t_oldest_import - dt.timedelta(hours=1)

        ref_distance = t_oldest_import - t_oldest_reference["start"]
        if ref_distance >= dt.timedelta(hours=1):
            return {
                "reference": t_oldest_reference,
                "ref_type": DeltaReferenceType.OLDER_REFERENCE,
            }, None
        msg = (
            f"Entity '{statistic_id}': Implementation error: Reference is less than 1 hour before oldest import "
            f"({t_oldest_import}), cannot use for delta conversion. That must not happen because in this case "
            "_get_reference_before_timestamp must return None."
        )
        return None, msg

    # Try to find newer reference

    # Fetch the oldest value in the database which is newer or equal than t_newest_import.
    t_newest_reference = await _get_reference_at_or_after_timestamp(hass, statistic_id, t_newest_import)
    _LOGGER.debug("Statistic %s: Newest reference at or after search for new %s: %s", statistic_id, t_newest_import, t_newest_reference)

    # If no such value exists, the import range completely overlaps the DB range
    if t_newest_reference is None:
        msg = f"Entity '{statistic_id}': imported timerange completely overlaps timerange in DB (cannot find reference before or after import)"
        return None, msg

    # Reference is at or after newest import (NEWER_REFERENCE)
    # To allow imported timerange is completely older than timerange in DB as well, set timestamp of reference to exactly t_newest_import
    #   (which is what would be returned also when import and DB overlap)
    t_newest_reference["start"] = t_newest_import
    return {
        "reference": t_newest_reference,
        "ref_type": DeltaReferenceType.NEWER_REFERENCE,
    }, None


async def prepare_delta_handling(
    hass: HomeAssistant,
    df: Any,
) -> dict[str, dict]:
    """
    Fetch and validate delta references for delta import.

    The delta reference is the value in the database that is used to convert delta values to sum and state.
    The reference can be either older or equal/newer than the imported data.

    This method orchestrates all database queries needed for delta processing,
    validates time range intersections, and returns structured reference data.

    Args:
    ----
        hass: Home Assistant instance
        df: DataFrame with delta column
        timezone_identifier: IANA timezone string
        datetime_format: Format string for parsing timestamps

    Returns:
    -------
        Dictionary mapping statistic_id to reference data:
        {
            statistic_id: {
                "reference": {"start": datetime, "sum": float, "state": float},
                "ref_type": DeltaReferenceType.OLDER_REFERENCE or DeltaReferenceType.NEWER_REFERENCE
            } or None if no valid reference found
        }

    Raises:
    ------
        HomeAssistantError: On validation errors or incompatible time ranges

    """
    _LOGGER.info("Preparing delta handling: fetching and validating database references")

    # Step 1: Extract oldest/newest timestamps from df per statistic_id
    import_ranges = {}

    for statistic_id in df["statistic_id"].unique():
        group = df[df["statistic_id"] == statistic_id]

        # Use vectorized min/max on datetime column (no parsing needed!)
        oldest_dt = group["start"].min()
        newest_dt = group["start"].max()

        if pd.isna(oldest_dt) or pd.isna(newest_dt):
            handle_error(f"No valid timestamps found for statistic_id {statistic_id}")

        # Validate that newest timestamp is not too recent
        is_not_in_future(newest_dt)

        # Convert to UTC for database query
        oldest_dt_utc = oldest_dt.astimezone(dt.UTC)
        newest_dt_utc = newest_dt.astimezone(dt.UTC)

        import_ranges[statistic_id] = {
            "oldest_import": oldest_dt_utc,
            "newest_import": newest_dt_utc,
        }

        _LOGGER.debug(
            "Statistic %s import range: oldest=%s, newest=%s",
            statistic_id,
            oldest_dt_utc,
            newest_dt_utc,
        )

    # Step 2: For each statistic_id, fetch database records and validate time ranges
    references = {}

    for statistic_id, import_range in import_ranges.items():
        t_oldest_import = import_range["oldest_import"]
        t_newest_import = import_range["newest_import"]

        _LOGGER.debug("Processing references for %s", statistic_id)

        ref_data, error_msg = await _process_delta_references_for_statistic(hass, statistic_id, t_oldest_import, t_newest_import)

        if error_msg:
            handle_error(error_msg)

        _LOGGER.debug("Reference data for %s found: %s", statistic_id, ref_data)

        references[statistic_id] = ref_data

    _LOGGER.info("Delta handling preparation complete: %d statistics", len(references))
    return references


@dataclass
class PreparedImportData:
    """Data prepared for import from file or JSON."""

    df: Any
    timezone_id: str
    datetime_format: str
    is_delta: bool


async def _process_import(hass: HomeAssistant, data: PreparedImportData) -> None:
    """
    Process import after DataFrame is prepared.

    This is the common logic shared between file and JSON imports.

    Args:
    ----
        hass: Home Assistant instance
        data: Prepared import data containing DataFrame and settings

    """
    if data.is_delta:
        _LOGGER.info("Delta mode detected, fetching references from database")
        references = await prepare_delta_handling(hass, data.df)
        stats = await hass.async_add_executor_job(lambda: handle_dataframe_delta(data.df, references))
    else:
        _LOGGER.info("Non-delta mode, processing directly")
        stats = await hass.async_add_executor_job(lambda: handle_dataframe_no_delta(data.df))

    await import_stats(hass, stats)


async def handle_import_from_file_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle import_from_file service implementation."""
    _LOGGER.info("Service handle_import_from_file called")
    file_path = f"{hass.config.config_dir}/{call.data.get(ATTR_FILENAME)}"

    hass.states.async_set("import_statistics.import_from_file", file_path)

    # Extract HA timezone once
    ha_timezone = hass.config.time_zone

    _LOGGER.info("Preparing data for import ...")
    df, timezone_id, datetime_format, is_delta = await hass.async_add_executor_job(lambda: prepare_data_to_import(file_path, call, ha_timezone))

    await _process_import(hass, PreparedImportData(df, timezone_id, datetime_format, is_delta))


async def handle_import_from_json_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle import_from_json service implementation."""
    _LOGGER.info("Service handle_import_from_json called")

    # Extract HA timezone once
    ha_timezone = hass.config.time_zone

    _LOGGER.info("Preparing data for import")
    df, timezone_id, datetime_format, is_delta = await hass.async_add_executor_job(lambda: prepare_json_data_to_import(call, ha_timezone))

    await _process_import(hass, PreparedImportData(df, timezone_id, datetime_format, is_delta))


async def import_stats(hass: HomeAssistant, stats: dict) -> None:
    """Import statistics into Home Assistant and wait for recorder to commit."""
    _LOGGER.info("Validating entities and units")
    await validate_entities_and_units(hass, stats)

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

    # Wait for the recorder to process all queued statistics and commit to database
    _LOGGER.info("Waiting for recorder to commit imported statistics to database")
    await get_instance(hass).async_block_till_done()
    _LOGGER.info("Finished importing data - all statistics committed to database")


async def validate_entities_and_units(hass: HomeAssistant, stats: dict) -> None:
    """
    Validate that entities exist and units match statistic_meta.

    Args:
    ----
        hass: Home Assistant instance
        stats: Dictionary with all statistic data

    Raises:
    ------
        HomeAssistantError: If entity doesn't exist or unit doesn't match

    """
    # Collect all statistic_ids to query metadata
    statistic_ids = set()
    for stat in stats.values():
        metadata = stat[0]
        statistic_id = metadata["statistic_id"]
        statistic_ids.add(statistic_id)

        # Check entity exists for recorder statistics
        if metadata["source"] == "recorder":
            entity_exists = hass.states.get(statistic_id) is not None
            if not entity_exists:
                handle_error(f"Entity does not exist: '{statistic_id}'")

    # Get existing metadata from database
    recorder_instance = get_instance(hass)
    if recorder_instance is None:
        handle_error("Recorder component is not running")

    existing_metadata = await recorder_instance.async_add_executor_job(lambda: get_metadata(hass, statistic_ids=statistic_ids))

    # Validate units match for existing statistics
    for stat in stats.values():
        metadata = stat[0]
        statistic_id = metadata["statistic_id"]
        input_unit = metadata.get("unit_of_measurement")  # Don't default to ""

        # Check if this statistic already exists in the database
        if statistic_id in existing_metadata:
            _metadata_id, existing_meta = existing_metadata[statistic_id]
            db_unit = existing_meta.get("unit_of_measurement")  # Don't default to ""

            # Both units should already be normalized (None or non-empty string)
            # Compare directly - None == None is True, "kWh" == "kWh" is True
            if input_unit != db_unit:
                # Format units for error message
                input_display = input_unit if input_unit is not None else "(empty)"
                db_display = db_unit if db_unit is not None else "(empty)"

                handle_error(
                    f"Unit mismatch for '{statistic_id}': input file has '{input_display}' but statistic_meta has '{db_display}'. Units must match exactly."
                )

            _LOGGER.debug("Unit validation passed for %s: %s", statistic_id, input_unit)


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
        handle_error(f"Entity does not exist: '{entity_id}'")
        return False

    return True
