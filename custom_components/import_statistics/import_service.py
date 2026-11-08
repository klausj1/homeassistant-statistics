"""Import statistics functionality."""

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import pandas as pd
from homeassistant.components.recorder.statistics import async_add_external_statistics, async_import_statistics, get_metadata
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.recorder import get_instance

from custom_components.import_statistics.const import ATTR_COUNTER_MODE, ATTR_FILENAME, ATTR_IGNORE_UNKNOWN_ENTITIES
from custom_components.import_statistics.delta_database_access import (
    _get_newest_db_statistic,
    _get_reference_at_or_after_timestamp,
    _get_reference_before_timestamp,
)
from custom_components.import_statistics.helpers import (
    _LOGGER,
    AggregatedValidationError,
    DeltaReferenceType,
    get_source,
    get_unit_from_row,
    handle_error,
    handle_errors,
    is_not_in_future,
)
from custom_components.import_statistics.import_service_delta_helper import handle_dataframe_delta
from custom_components.import_statistics.import_service_helper import (
    CounterDataType,
    ImportDataClassification,
    ImportDataType,
    _split_dataframe_by_type,
    collect_dataframe_validation_errors,
    collect_unit_validation_errors,
    handle_dataframe_no_delta,
    prepare_data_to_import,
    prepare_json_data_to_import,
    resolve_counter_mode,
    split_dataframe_by_type,
    validate_counter_mode,
    validate_ignore_unknown_entities,
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
    errors = []

    for statistic_id in df["statistic_id"].unique():
        group = df[df["statistic_id"] == statistic_id]
        row_numbers = [int(index) + 2 for index in group.index]

        # Use vectorized min/max on datetime column (no parsing needed!)
        oldest_dt = group["start"].min()
        newest_dt = group["start"].max()

        if pd.isna(oldest_dt) or pd.isna(newest_dt):
            errors.append(f"No valid timestamps found for statistic_id {statistic_id} at rows {row_numbers}.")
            continue

        # Validate that newest timestamp is not too recent
        try:
            is_not_in_future(newest_dt)
        except HomeAssistantError as err:
            row_message = f"Statistic '{statistic_id}' at rows {row_numbers}: "
            errors.extend(f"{row_message}{message}" for message in _validation_errors_from_exception(err))
            continue

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

    handle_errors(errors)

    # Step 2: For each statistic_id, fetch database records and validate time ranges
    references = {}
    errors = []

    for statistic_id, import_range in import_ranges.items():
        t_oldest_import = import_range["oldest_import"]
        t_newest_import = import_range["newest_import"]

        _LOGGER.debug("Processing references for %s", statistic_id)

        ref_data, error_msg = await _process_delta_references_for_statistic(hass, statistic_id, t_oldest_import, t_newest_import)

        if error_msg:
            row_numbers = [int(index) + 2 for index in df.index[df["statistic_id"] == statistic_id]]
            errors.append(f"{error_msg} Imported rows: {row_numbers}.")
            continue

        _LOGGER.debug("Reference data for %s found: %s", statistic_id, ref_data)

        references[statistic_id] = ref_data

    handle_errors(errors)

    _LOGGER.info("Delta handling preparation complete: %d statistics", len(references))
    return references


@dataclass
class PreparedImportData:
    """Data prepared for import from file or JSON."""

    df: Any
    timezone_id: str
    datetime_format: str
    classification: ImportDataClassification
    counter_mode: str = "strict"
    ignore_unknown_entities: bool = False


def _prepare_counter_dataframe(df: pd.DataFrame, counter_type: CounterDataType) -> pd.DataFrame:
    """Select the requested counter representation while preserving sparse rows."""
    if counter_type == CounterDataType.SUM_STATE:
        columns = ["statistic_id", "unit", "start"]
        columns.extend(col for col in ("sum", "state") if col in df.columns)
        return df[columns].copy()

    if counter_type == CounterDataType.DELTA:
        columns = ["statistic_id", "unit", "start"]
        if "delta" in df.columns:
            columns.append("delta")
        return df[columns].copy()

    return handle_error("Counter representation is ambiguous; select either sum/state or delta data.")


async def _process_counter_dataframe(hass: HomeAssistant, df: pd.DataFrame, counter_mode: str) -> dict:
    """Convert counter data using the representation selected by counter_mode."""
    selected_mode = resolve_counter_mode(df, counter_mode)
    selected_df = _prepare_counter_dataframe(df, selected_mode)
    if selected_mode == CounterDataType.DELTA:
        references = await prepare_delta_handling(hass, selected_df)
        return await hass.async_add_executor_job(lambda: handle_dataframe_delta(selected_df, references))
    return await hass.async_add_executor_job(lambda: handle_dataframe_no_delta(selected_df))


def _validation_errors_from_exception(error: HomeAssistantError) -> list[str]:
    """Return all messages carried by a validation exception."""
    return error.errors if isinstance(error, AggregatedValidationError) else [str(error)]


async def _raise_import_error(hass: HomeAssistant, error: HomeAssistantError) -> NoReturn:
    """Raise the first import error and write additional errors to the config directory."""
    errors = list(dict.fromkeys(_validation_errors_from_exception(error)))
    if not errors:
        raise error

    message = errors[0]
    if len(errors) > 1:
        row_pattern = re.compile(r"\b(?:source\s+|imported\s+)?rows?\s*:?\s*\[?(\d+(?:\s*,\s*\d+)*)\]?", re.IGNORECASE)
        ordered_log_lines = []
        for error_order, validation_error in enumerate(errors):
            row_numbers = sorted({int(row_number) for match in row_pattern.finditer(validation_error) for row_number in match.group(1).split(",")})
            if row_numbers:
                ordered_log_lines.append((row_numbers[0], error_order, f"{', '.join(map(str, row_numbers))}: {validation_error}"))
            else:
                ordered_log_lines.append((float("inf"), error_order, f"No source row: {validation_error}"))

        log_path = Path(hass.config.config_dir) / "import_errors.log"
        try:
            log_lines = [line for _, _, line in sorted(ordered_log_lines)]
            await hass.async_add_executor_job(lambda: log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8"))
        except OSError as write_error:
            message += f"\nAdditional validation errors could not be written to {log_path}: {write_error}"
        else:
            message += "\nAdditional validation errors are listed in import_errors.log in the Home Assistant config folder."

    raise HomeAssistantError(message) from None


async def _validate_dataframe_entities(hass: HomeAssistant, df: pd.DataFrame, *, ignore_unknown_entities: bool) -> list[str]:
    """Validate each statistic's entity and stored unit independently of row processing."""
    validation_stats = {}
    errors = []
    row_numbers = {}
    unit_rows = {}
    for statistic_id in df["statistic_id"].unique():
        statistic_rows = df.loc[df["statistic_id"] == statistic_id]
        rows = [int(index) + 2 for index in statistic_rows.index]
        row_numbers[statistic_id] = rows
        try:
            source = get_source(statistic_id)
        except HomeAssistantError as err:
            errors.extend(f"{error} Rows: {rows}." for error in _validation_errors_from_exception(err))
            continue
        units_and_rows: dict[str | None, list[int]] = {}
        for index, raw_unit in statistic_rows["unit"].items():
            row_number = int(index) + 2
            try:
                unit = get_unit_from_row(raw_unit, statistic_id, row_number=row_number)
            except HomeAssistantError as err:
                errors.extend(_validation_errors_from_exception(err))
                continue
            units_and_rows.setdefault(unit, []).append(row_number)
        unit_rows[statistic_id] = list(units_and_rows.items())
        unit = next(iter(units_and_rows), None)
        validation_stats[statistic_id] = (
            {"statistic_id": statistic_id, "source": source, "unit_of_measurement": unit},
            [],
        )

    if ignore_unknown_entities:
        validation_stats = {
            statistic_id: stat
            for statistic_id, stat in validation_stats.items()
            if stat[0]["source"] != "recorder" or hass.states.get(statistic_id) is not None
        }
    if validation_stats:
        try:
            await validate_entities_and_units(hass, validation_stats, row_numbers=row_numbers, unit_rows=unit_rows)
        except HomeAssistantError as err:
            errors.extend(_validation_errors_from_exception(err))
    return errors


def _validate_local_import_data(data: PreparedImportData) -> list[str]:  # noqa: PLR0912
    """Collect all row-level validation errors before processing or database writes."""
    df = data.df
    errors = list(df.attrs.get("validation_errors", []))
    errors.extend(collect_unit_validation_errors(df))

    if data.classification.import_type == ImportDataType.MIXED:
        sensor_df, counter_df, split_errors = _split_dataframe_by_type(df)
        errors.extend(split_errors)
    elif data.classification.import_type == ImportDataType.SENSOR:
        sensor_df, counter_df = df, pd.DataFrame()
    else:
        sensor_df, counter_df = pd.DataFrame(), df

    if not sensor_df.empty:
        errors.extend(collect_dataframe_validation_errors(sensor_df, ["min", "max", "mean"], include_units=False))

    if not counter_df.empty:
        for statistic_id in counter_df["statistic_id"].unique():
            statistic_df = counter_df[counter_df["statistic_id"] == statistic_id]
            try:
                selected_mode = resolve_counter_mode(statistic_df, data.counter_mode)
            except HomeAssistantError as err:
                errors.extend(_validation_errors_from_exception(err))
                selected_mode = None

            if selected_mode == CounterDataType.SUM_STATE:
                value_columns = [column for column in ("sum", "state") if column in statistic_df.columns]
                value_df = statistic_df[statistic_df[value_columns].notna().any(axis=1)]
                errors.extend(collect_dataframe_validation_errors(value_df, value_columns, include_units=False))
            elif selected_mode == CounterDataType.DELTA:
                delta_df = statistic_df[statistic_df["delta"].notna()]
                errors.extend(collect_dataframe_validation_errors(delta_df, ["delta"], include_units=False))
            else:
                if {"sum", "state"} & set(statistic_df.columns):
                    sum_columns = [column for column in ("sum", "state") if column in statistic_df.columns]
                    sum_df = statistic_df[statistic_df[sum_columns].notna().any(axis=1)]
                    if sum_columns:
                        errors.extend(collect_dataframe_validation_errors(sum_df, sum_columns, include_units=False))
                if "delta" in statistic_df.columns:
                    delta_df = statistic_df[statistic_df["delta"].notna()]
                    errors.extend(collect_dataframe_validation_errors(delta_df, ["delta"], include_units=False))
    return errors


async def _build_import_statistics(hass: HomeAssistant, data: PreparedImportData) -> tuple[dict, list[str]]:
    """Process each statistic type independently and collect processing errors."""
    errors = []
    stats = {}
    if data.classification.import_type == ImportDataType.MIXED:
        _LOGGER.info("Mixed mode detected, splitting by statistic type")
        sensor_df, counter_df = split_dataframe_by_type(data.df)
        if not sensor_df.empty:
            _LOGGER.info("Processing sensor data (no delta conversion needed)")
            try:
                stats.update(await hass.async_add_executor_job(lambda: handle_dataframe_no_delta(sensor_df)))
            except HomeAssistantError as err:
                errors.extend(_validation_errors_from_exception(err))
        if not counter_df.empty:
            _LOGGER.info("Processing counter data (delta conversion may be needed)")
            try:
                stats.update(await _process_counter_dataframe(hass, counter_df, data.counter_mode))
            except HomeAssistantError as err:
                errors.extend(_validation_errors_from_exception(err))
    elif data.classification.import_type == ImportDataType.COUNTER:
        _LOGGER.info("Counter mode detected, processing with counter handling (delta conversion may be needed)")
        try:
            stats = await _process_counter_dataframe(hass, data.df, data.counter_mode)
        except HomeAssistantError as err:
            errors.extend(_validation_errors_from_exception(err))
    else:
        _LOGGER.info("Measurement-only mode detected, processing directly")
        try:
            stats = await hass.async_add_executor_job(lambda: handle_dataframe_no_delta(data.df))
        except HomeAssistantError as err:
            errors.extend(_validation_errors_from_exception(err))
    return stats, errors


async def _process_import(hass: HomeAssistant, data: PreparedImportData) -> dict:
    """
    Process import after DataFrame is prepared.

    This is the common logic shared between file and JSON imports.

    Args:
    ----
        hass: Home Assistant instance
        data: Prepared import data containing DataFrame and settings

    """
    errors = _validate_local_import_data(data)
    errors.extend(await _validate_dataframe_entities(hass, data.df, ignore_unknown_entities=data.ignore_unknown_entities))
    handle_errors(errors)
    stats, processing_errors = await _build_import_statistics(hass, data)
    handle_errors(processing_errors)
    return await import_stats(hass, stats, ignore_unknown_entities=data.ignore_unknown_entities, validate_entities=False)


async def handle_import_from_file_impl(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Handle a file import and raise validation failures."""
    try:
        return await _handle_import_from_file(hass, call)
    except HomeAssistantError as err:
        await _raise_import_error(hass, err)


async def _handle_import_from_file(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Handle import_from_file service implementation."""
    _LOGGER.info("Service handle_import_from_file called")
    file_path = f"{hass.config.config_dir}/{call.data.get(ATTR_FILENAME)}"

    hass.states.async_set("import_statistics.import_from_file", file_path)

    counter_mode = validate_counter_mode(call.data.get(ATTR_COUNTER_MODE, "strict"))
    ignore_unknown_entities = validate_ignore_unknown_entities(call.data.get(ATTR_IGNORE_UNKNOWN_ENTITIES, False))

    # Extract HA timezone once
    ha_timezone = hass.config.time_zone

    _LOGGER.info("Preparing data for import ...")
    df, timezone_id, datetime_format, classification = await hass.async_add_executor_job(lambda: prepare_data_to_import(file_path, call, ha_timezone))

    return await _process_import(
        hass,
        PreparedImportData(
            df=df,
            timezone_id=timezone_id,
            datetime_format=datetime_format,
            classification=classification,
            counter_mode=counter_mode,
            ignore_unknown_entities=ignore_unknown_entities,
        ),
    )


async def handle_import_from_json_impl(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Handle a JSON import and raise validation failures."""
    try:
        return await _handle_import_from_json(hass, call)
    except HomeAssistantError as err:
        await _raise_import_error(hass, err)


async def _handle_import_from_json(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Handle import_from_json service implementation."""
    _LOGGER.info("Service handle_import_from_json called")
    counter_mode = validate_counter_mode(call.data.get(ATTR_COUNTER_MODE, "strict"))
    ignore_unknown_entities = validate_ignore_unknown_entities(call.data.get(ATTR_IGNORE_UNKNOWN_ENTITIES, False))

    # Extract HA timezone once
    ha_timezone = hass.config.time_zone

    _LOGGER.info("Preparing data for import")
    df, timezone_id, datetime_format, classification = await hass.async_add_executor_job(lambda: prepare_json_data_to_import(call, ha_timezone))

    return await _process_import(
        hass,
        PreparedImportData(
            df=df,
            timezone_id=timezone_id,
            datetime_format=datetime_format,
            classification=classification,
            counter_mode=counter_mode,
            ignore_unknown_entities=ignore_unknown_entities,
        ),
    )


def _write_skipped_unknown_entities(config_dir: str, skipped_ids: list[str]) -> Path:
    """Write skipped recorder statistic IDs to an automatically named CSV file."""
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S_%f")
    skipped_path = Path(config_dir) / f"skipped_unknown_entities_{timestamp}.csv"
    pd.DataFrame({"statistic_id": skipped_ids}).to_csv(skipped_path, index=False)
    _LOGGER.info("Wrote skipped unknown recorder entities to %s", skipped_path)
    return skipped_path


def _filter_unknown_recorder_entities(hass: HomeAssistant, stats: dict) -> tuple[dict, list[str]]:
    """Remove missing recorder entities before validation or writing statistics."""
    filtered_stats = {}
    skipped_ids: list[str] = []
    for statistic_id, stat in stats.items():
        metadata = stat[0]
        # External statistics do not correspond to Home Assistant entities.
        if metadata.get("source") == "recorder" and hass.states.get(statistic_id) is None:
            skipped_ids.append(statistic_id)
            _LOGGER.warning("Skipping recorder statistic '%s' because its entity is missing in Home Assistant.", statistic_id)
            continue
        filtered_stats[statistic_id] = stat

    if skipped_ids:
        # Record skipped IDs explicitly; validation errors for retained data still abort the import.
        _write_skipped_unknown_entities(hass.config.config_dir, skipped_ids)

    return filtered_stats, skipped_ids


async def import_stats(hass: HomeAssistant, stats: dict, *, ignore_unknown_entities: bool = False, validate_entities: bool = True) -> dict:
    """Import statistics into Home Assistant and wait for recorder to commit."""
    skipped_ids: list[str] = []
    skipped_value_count = 0
    if ignore_unknown_entities:
        value_counts = {statistic_id: len(stat[1]) for statistic_id, stat in stats.items()}
        stats, skipped_ids = _filter_unknown_recorder_entities(hass, stats)
        skipped_value_count = sum(value_counts[statistic_id] for statistic_id in skipped_ids)

    if validate_entities:
        _LOGGER.info("Validating entities and units")
        await validate_entities_and_units(hass, stats)

    _LOGGER.info("Calculate import status counts (new, existing, no data)")
    status_counts = await _get_import_status_counts(hass, stats)

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

    imported_value_count = sum(len(stat[1]) for stat in stats.values())
    _LOGGER.info("Finished importing data - %d statistic values imported and committed to database", imported_value_count)

    response = {"imported_values": imported_value_count, **status_counts}
    if ignore_unknown_entities:
        response["skipped_values"] = skipped_value_count
        response["skipped_statistics"] = skipped_ids
    return response


async def _get_import_status_counts(hass: HomeAssistant, stats: dict) -> dict[str, int]:
    """Count imported statistics by whether their data is new, existing, or empty."""
    status_counts = {"new_data": 0, "existing_data": 0, "no_data": 0}
    for metadata, statistics in stats.values():
        if not statistics:
            status_counts["no_data"] += 1
            continue

        statistic_id = metadata["statistic_id"]
        newest_import_start = max(statistic["start"].astimezone(dt.UTC) for statistic in statistics)
        newest_db_record = await _get_newest_db_statistic(hass, statistic_id)
        newest_db_start = newest_db_record["start"] if newest_db_record else None
        if newest_db_start is None or newest_import_start > newest_db_start:
            status_counts["new_data"] += 1
        else:
            status_counts["existing_data"] += 1

    return status_counts


async def validate_entities_and_units(
    hass: HomeAssistant,
    stats: dict,
    *,
    row_numbers: dict[str, list[int]] | None = None,
    unit_rows: dict[str, list[tuple[str | None, list[int]]]] | None = None,
) -> None:
    """
    Validate that entities exist and units match both entity state and statistic_meta.

    Args:
    ----
        hass: Home Assistant instance
        stats: Dictionary with all statistic data

    Raises:
    ------
        HomeAssistantError: If entity doesn't exist or unit doesn't match

    Keyword Args:
    ------------
        row_numbers: Source row numbers for each imported statistic.
        unit_rows: Normalized input units paired with the source rows containing each unit.

    """
    errors = []
    row_numbers = row_numbers or {}

    def row_context(statistic_id: str) -> str:
        """Format source row numbers for a statistic-specific validation message."""
        rows = row_numbers.get(statistic_id)
        return f" at rows {rows}" if rows else ""

    def units_for_statistic(statistic_id: str, metadata: dict) -> list[tuple[str | None, list[int] | None]]:
        """Return each distinct normalized input unit and the rows where it occurs."""
        if unit_rows is not None and statistic_id in unit_rows:
            return [(unit, rows) for unit, rows in unit_rows[statistic_id]]
        return [(metadata.get("unit_of_measurement"), row_numbers.get(statistic_id))]

    def unit_row_context(rows: list[int] | None) -> str:
        """Format source rows specific to one input unit value."""
        if not rows:
            return ""
        if len(rows) == 1:
            return f" at row {rows[0]}"
        return f" at rows {rows}"

    # Collect all statistic_ids to query metadata
    statistic_ids = set()
    for stat in stats.values():
        metadata = stat[0]
        statistic_id = metadata["statistic_id"]
        statistic_ids.add(statistic_id)

        # Check entity exists for recorder statistics and validate unit matches entity's current unit
        if metadata["source"] == "recorder":
            entity_state = hass.states.get(statistic_id)
            if entity_state is None:
                errors.append(
                    f"Entity does not exist: '{statistic_id}'{row_context(statistic_id)}. To skip missing recorder entities, set ignore_unknown_entities: true."
                )
            else:
                entity_unit = entity_state.attributes.get("unit_of_measurement")

                # Normalize entity_unit (convert empty string to None)
                if entity_unit == "":
                    entity_unit = None

                for input_unit, input_rows in units_for_statistic(statistic_id, metadata):
                    if input_unit != entity_unit:
                        input_display = input_unit if input_unit is not None else "(empty)"
                        entity_display = entity_unit if entity_unit is not None else "(empty)"

                        errors.append(
                            f"Unit mismatch for '{statistic_id}'{unit_row_context(input_rows) or row_context(statistic_id)}: "
                            f"input file has '{input_display}' but entity has '{entity_display}'. "
                            f"Units must match the entity's current unit_of_measurement."
                        )

    # Get existing metadata from database
    recorder_instance = get_instance(hass)
    if recorder_instance is None:
        handle_error("Recorder component is not running")

    existing_metadata = await recorder_instance.async_add_executor_job(lambda: get_metadata(hass, statistic_ids=statistic_ids))

    # Validate units match for existing statistics in database
    for stat in stats.values():
        metadata = stat[0]
        statistic_id = metadata["statistic_id"]

        # Check if this statistic already exists in the database
        if statistic_id in existing_metadata:
            _metadata_id, existing_meta = existing_metadata[statistic_id]
            db_unit = existing_meta.get("unit_of_measurement")  # Don't default to ""

            for input_unit, input_rows in units_for_statistic(statistic_id, metadata):
                if input_unit != db_unit:
                    input_display = input_unit if input_unit is not None else "(empty)"
                    db_display = db_unit if db_unit is not None else "(empty)"

                    errors.append(
                        f"Unit mismatch for '{statistic_id}'{unit_row_context(input_rows) or row_context(statistic_id)}: "
                        f"input file has '{input_display}' but statistic_meta has '{db_display}'. Units must match exactly."
                    )

                _LOGGER.debug("Unit validation passed for %s: %s", statistic_id, input_unit)

    handle_errors(errors)


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
        error = "Entity does not exist: '{entity_id}'. "
        error += "To skip missing entities, set ignore_unknown_entities: true. Or import as external statistics (including a ':' instead of a '.')."
        handle_error(error.format(entity_id=entity_id))
        return False

    return True
