"""
Helper functions for import service - data preparation from files/JSON.

Most helpers do not need a hass object; status helpers use the hass object for database lookups.
"""

import zoneinfo
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pandas as pd
import pytz
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import helpers
from custom_components.import_statistics.const import (
    ATTR_DATETIME_FORMAT,
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_TIMEZONE_IDENTIFIER,
    DATETIME_DEFAULT_FORMAT,
    VALID_COUNTER_MODES,
)
from custom_components.import_statistics.helpers import _LOGGER


class ImportDataType(Enum):
    """Whether an import contains sensor data, counter data, or both."""

    SENSOR = "sensor"
    COUNTER = "counter"
    MIXED = "mixed"


class CounterDataType(Enum):
    """Counter representation populated in an import."""

    SUM_STATE = "sum_state"
    DELTA = "delta"
    BOTH = "both"


@dataclass(frozen=True)
class ImportDataClassification:
    """Classification of measurement/counter composition and counter representation."""

    import_type: ImportDataType
    counter_type: CounterDataType | None


def _has_populated_columns(df: pd.DataFrame, columns: list[str]) -> bool:
    """Return True when any of the supplied columns has a populated value."""
    return any(column in df.columns and df[column].notna().any() for column in columns)


def validate_counter_mode(counter_mode: str | None) -> str:
    """Normalize and validate the counter_mode parameter."""
    if counter_mode is None:
        counter_mode = "strict"
    if not isinstance(counter_mode, str):
        helpers.handle_error(f"counter_mode must be a string, got {type(counter_mode).__name__}")
    normalized = counter_mode.strip().lower()
    if normalized not in VALID_COUNTER_MODES:
        helpers.handle_error(f"counter_mode must be one of {sorted(VALID_COUNTER_MODES)}, got {counter_mode!r}")
    return normalized


def validate_ignore_unknown_entities(ignore_unknown_entities: object) -> bool:
    """Normalize and validate the ignore_unknown_entities service parameter."""
    if isinstance(ignore_unknown_entities, bool):
        return ignore_unknown_entities
    if isinstance(ignore_unknown_entities, int) and ignore_unknown_entities in {0, 1}:
        return bool(ignore_unknown_entities)
    if isinstance(ignore_unknown_entities, str):
        normalized = ignore_unknown_entities.strip().lower()
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0"}:
            return False
    return helpers.handle_error(f"ignore_unknown_entities must be a boolean, got {ignore_unknown_entities!r}")


def resolve_counter_mode(df: pd.DataFrame, counter_mode: str | None = "strict") -> CounterDataType:
    """Resolve the counter representation based on the populated data in the DataFrame."""
    mode = validate_counter_mode(counter_mode)
    has_sum_state = _has_populated_columns(df, ["sum", "state"])
    has_delta = _has_populated_columns(df, ["delta"])

    if mode == "strict":
        has_sum_columns = "sum" in df.columns or "state" in df.columns
        if has_sum_columns and "delta" in df.columns:
            helpers.handle_error(
                "Counter data is conflicting: both 'sum'/'state' and 'delta' columns were supplied. "
                "Use counter_mode='sum' or counter_mode='delta' to select one representation, or remove the conflicting columns."
            )

    if mode == "sum":
        if not has_sum_state:
            helpers.handle_error(
                "counter_mode='sum' was selected, but no usable 'sum'/'state' counter data was found in the import. "
                "Use counter_mode='delta' for delta-based counters or remove the conflicting representation."
            )
        return CounterDataType.SUM_STATE

    if mode == "delta":
        if not has_delta:
            helpers.handle_error(
                "counter_mode='delta' was selected, but no usable 'delta' counter data was found in the import. "
                "Use counter_mode='sum' for sum/state-based counters or remove the conflicting representation."
            )
        return CounterDataType.DELTA

    if has_sum_state:
        return CounterDataType.SUM_STATE
    if has_delta:
        return CounterDataType.DELTA
    return helpers.handle_error("No populated counter values found in 'sum', 'state', or 'delta' columns.")


def _validate_and_detect_delta(df: "pd.DataFrame") -> ImportDataClassification:
    """
    Validate DataFrame columns and detect import data type.

    Args:
    ----
        df: DataFrame to validate

    Returns:
    -------
        ImportDataClassification describing the data composition

    Raises:
    ------
        HomeAssistantError: If column validation fails or no value data is populated

    """
    _LOGGER.debug("Columns: %s", df.columns)

    if not helpers.are_columns_valid(df):
        return helpers.handle_error(
            "Implementation error. helpers.are_columns_valid returned false, this should never happen, because helpers.are_columns_valid throws an exception!"
        )

    has_measurement = _has_populated_columns(df, ["mean", "min", "max"])
    has_sum_state = _has_populated_columns(df, ["sum", "state"])
    has_delta = _has_populated_columns(df, ["delta"])

    if not (has_measurement or has_sum_state or has_delta):
        helpers.handle_error("No populated values found in any of the expected columns (min, max, mean, sum, state, delta).")

    counter_type = None
    if has_sum_state and has_delta:
        counter_type = CounterDataType.BOTH
    elif has_sum_state:
        counter_type = CounterDataType.SUM_STATE
    elif has_delta:
        counter_type = CounterDataType.DELTA

    if has_measurement and counter_type is not None:
        import_type = ImportDataType.MIXED
    elif has_measurement:
        import_type = ImportDataType.SENSOR
    else:
        import_type = ImportDataType.COUNTER

    return ImportDataClassification(import_type=import_type, counter_type=counter_type)


def _localize_timestamps_with_dst_handling(df: pd.DataFrame, timezone_identifier: str, *, naive_copy: pd.Series | None = None) -> None:
    """
    Localize timestamps in DataFrame with proper DST handling.

    Modifies the 'start' column in-place to add timezone information.
    Handles both non-existent times (spring forward) and ambiguous times (fall back).

    Args:
    ----
        df: DataFrame with 'start' column containing datetime objects
        timezone_identifier: IANA timezone string (e.g., 'America/New_York')
        naive_copy: Optional pre-saved copy of naive timestamps (for CSV/TSV).
                   If None, will attempt to re-parse from string (for JSON).

    Raises:
    ------
        HomeAssistantError: If timestamps fall in DST gap (spring forward)

    """
    timezone = zoneinfo.ZoneInfo(timezone_identifier)

    try:
        # nonexistent='raise': Raise error for non-existent times (spring forward DST gap)
        # ambiguous='NaT': For ambiguous times (fall back DST overlap), mark as NaT then we'll use the later occurrence
        start_series: pd.Series[pd.Timestamp] = df["start"]  # type: ignore[assignment]
        df["start"] = start_series.dt.tz_localize(timezone, nonexistent="raise", ambiguous="NaT")

        # For any NaT values (ambiguous times), re-localize using True (later occurrence)
        if df["start"].isna().any():
            ambiguous_mask = df["start"].isna()
            if ambiguous_mask.any():
                if naive_copy is not None:
                    # CSV/TSV path: Use pre-saved naive timestamps
                    # Create a boolean array: True = use later occurrence (DST ended, standard time)
                    ambiguous_array = pd.Series([True] * ambiguous_mask.sum(), index=df[ambiguous_mask].index)
                    naive_series: pd.Series[pd.Timestamp] = naive_copy.loc[ambiguous_mask]  # type: ignore[assignment]
                    ambiguous_times = naive_series.dt.tz_localize(timezone, ambiguous=ambiguous_array)  # type: ignore[arg-type]
                    df.loc[ambiguous_mask, "start"] = ambiguous_times
                else:
                    # JSON path: This should not happen in practice because JSON data comes pre-parsed
                    # If it does, we cannot recover the original string, so we use 'infer' which defaults to later
                    # Note: This is a fallback and may not work correctly if start column was already NaT
                    helpers.handle_error(
                        "Implementation error: Ambiguous timestamps detected but no naive copy provided. This indicates a bug in timestamp parsing logic."
                    )
    except HomeAssistantError:
        raise
    except Exception as e:  # noqa: BLE001
        # Provide clear error message for DST issues.
        # Different pandas/pytz versions raise different exception types:
        # - pandas with zoneinfo: ValueError with "nonexistent" in message
        # - pandas with pytz: pytz.exceptions.NonExistentTimeError (message is just the timestamp)
        error_msg = str(e)
        exception_type = type(e).__name__
        if "nonexistent" in error_msg.lower() or "does not exist" in error_msg.lower() or exception_type == "NonExistentTimeError":
            helpers.handle_error(
                "Timestamp does not exist due to daylight saving time transition (spring forward). "
                "The timestamp falls in the gap when clocks move forward. "
                f"Please adjust your timestamps to avoid the DST gap. Error: {error_msg}"
            )
        # Catch-all: convert any other unexpected exception to HomeAssistantError
        helpers.handle_error(f"Failed to localize timestamps: {error_msg}")


def prepare_data_to_import(file_path: str, call: ServiceCall, ha_timezone: str) -> tuple:
    """
    Load and prepare data from CSV/TSV file for import.

    Args:
    ----
        file_path: Path to the file with the data to be imported.
        call: The call data containing the necessary information.
        ha_timezone: Home Assistant's configured timezone identifier.

    Returns:
    -------
        Tuple of (df, timezone_identifier, datetime_format, classification)

    Raises:
    ------
        FileNotFoundError: If the specified file does not exist.
        HomeAssistantError: If there is a validation error.

    """
    file_suffix = Path(file_path).suffix.lower()
    if file_suffix not in {".csv", ".tsv"}:
        helpers.handle_error(f"Unsupported filename extension for {Path(file_path).name!r}. Supported extensions: .csv, .tsv")

    decimal, timezone_identifier, delimiter, datetime_format = handle_arguments(call, ha_timezone, filename=Path(file_path).name)

    _LOGGER.info("Importing statistics from file: %s", file_path)
    if not Path(file_path).exists():
        helpers.handle_error(f"path {file_path} does not exist.")

    # Validate file encoding before attempting to read
    helpers.validate_file_encoding(file_path)

    # Parse datetimes during CSV load for performance (avoids parsing 3x later)
    my_df = pd.read_csv(
        file_path,
        sep=delimiter,
        decimal=decimal,
        engine="python",
        encoding="utf-8",
        parse_dates=["start"],  # Parse 'start' column as datetime
        date_format=datetime_format,  # Use user-specified format
    )

    # Validate that parsing succeeded (pandas returns datetime objects)
    if not pd.api.types.is_datetime64_any_dtype(my_df["start"]):
        # Parsing failed - timestamps don't match the format
        sample_value = my_df["start"].iloc[0] if len(my_df) > 0 else "unknown"
        helpers.handle_error(
            f"Invalid timestamp format: {sample_value}. Expected format: {datetime_format}. Please ensure all timestamps match the specified format."
        )

    # Keep a copy of the naive datetime column for handling ambiguous times
    start_naive = my_df["start"].copy()

    # Apply timezone with DST handling
    _localize_timestamps_with_dst_handling(my_df, timezone_identifier, naive_copy=start_naive)

    data_type = _validate_and_detect_delta(my_df)

    return my_df, timezone_identifier, datetime_format, data_type


def prepare_json_data_to_import(call: ServiceCall, ha_timezone: str) -> tuple:
    """
    Prepare data from JSON service call for import.

    Args:
    ----
        call: The service call data containing entities.
        ha_timezone: Home Assistant's configured timezone identifier.

    Returns:
    -------
        Tuple of (df, timezone_identifier, datetime_format, classification)

    Raises:
    ------
        HomeAssistantError: If there is a validation error.

    """
    _, timezone_identifier, _, datetime_format = handle_arguments(call, ha_timezone, filename=None)

    # Required columns that are always present
    required_columns = ["statistic_id", "unit", "start"]

    # Track all columns found across all entities (will be validated later by are_columns_valid)
    all_columns = set(required_columns)
    data = []

    input_entities = call.data.get("entities", [])

    # Validate JSON schema early to provide clear errors for malformed input
    helpers.validate_json_schema(call.data)

    # First pass: collect all unique columns from all entities
    for entity in input_entities:
        values = entity["values"]
        for value in values:
            # Extract all value columns (excluding 'datetime' which maps to 'start')
            value_columns = {key for key in value if key != "datetime"}
            all_columns.update(value_columns)

    # Convert to sorted list for consistent column ordering
    columns = required_columns + sorted(all_columns - set(required_columns))

    # Second pass: build data rows with all columns
    for entity in input_entities:
        statistic_id, values, unit = (entity["id"], entity["values"], entity["unit"])
        _LOGGER.info(f"Parsing entity with id: {statistic_id} with {len(values)} values")
        for value in values:
            value_dict = {
                "statistic_id": statistic_id,
                "unit": unit,
                "start": value["datetime"],
            }
            # Add all value columns found in this row
            for column in columns:
                if column in required_columns:
                    continue  # Already set above
                if column in value:
                    value_dict[column] = value[column]

            data.append(tuple([value_dict.get(column) for column in columns]))

    my_df = pd.DataFrame(data, columns=columns)

    # Parse datetime strings after DataFrame creation (for JSON imports)
    try:
        # Parse timestamps to datetime objects
        my_df["start"] = pd.to_datetime(my_df["start"], format=datetime_format)

        # Validate that parsing succeeded
        if not pd.api.types.is_datetime64_any_dtype(my_df["start"]):
            sample_value = my_df["start"].iloc[0] if len(my_df) > 0 else "unknown"
            helpers.handle_error(
                f"Invalid timestamp format: {sample_value}. Expected format: {datetime_format}. Please ensure all timestamps match the specified format."
            )

        # Keep a copy of the naive datetime column for handling ambiguous times
        start_naive = my_df["start"].copy()

        # Apply timezone with DST handling
        _localize_timestamps_with_dst_handling(my_df, timezone_identifier, naive_copy=start_naive)

    except HomeAssistantError:
        raise
    except Exception as e:
        # Provide clear error message for parsing failures
        error_msg = str(e)
        if "does not match format" in error_msg.lower():
            helpers.handle_error(f"Failed to parse timestamp. Expected format: {datetime_format}. Error: {error_msg}")
        raise

    data_type = _validate_and_detect_delta(my_df)

    return my_df, timezone_identifier, datetime_format, data_type


def handle_arguments(call: ServiceCall, ha_timezone: str, *, filename: str | None = None) -> tuple:
    """
    Handle the arguments for importing statistics from a file.

    Args:
    ----
        call (ServiceCall): The service call object containing additional data.
        ha_timezone: Home Assistant's configured timezone identifier.
        filename: Filename used to infer delimiter when ATTR_DELIMITER is omitted.

    Returns:
    -------
        tuple: A tuple containing the decimal separator, timezone identifier, and delimiter.

    Raises:
    ------
        HomeAssistantError: If the timezone identifier is invalid.

    """
    # Get decimal separator from service call (default is "dot ('.')")
    decimal_input = call.data.get(ATTR_DECIMAL, "dot ('.')")

    # Map UI-friendly values to actual separators
    decimal_map = {
        "dot ('.')": ".",
        "comma (',')": ",",
        ".": ".",  # Support old format for backward compatibility
        ",": ",",  # Support old format for backward compatibility
    }

    decimal = decimal_map.get(decimal_input)
    if decimal is None:
        helpers.handle_error(f"Invalid decimal separator: {decimal_input}. Must be \"dot ('.')\" or \"comma (',')\"")

    datetime_format = call.data.get(ATTR_DATETIME_FORMAT) if ATTR_DATETIME_FORMAT in call.data else DATETIME_DEFAULT_FORMAT

    # Use HA's configured timezone as default, allow override
    timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER, ha_timezone)

    if timezone_identifier not in pytz.all_timezones:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    delimiter_raw = call.data.get(ATTR_DELIMITER)
    if delimiter_raw is None:
        if filename is None:
            delimiter_raw = "\t"
        else:
            suffix = Path(filename).suffix.lower()
            if suffix == ".csv":
                delimiter_raw = ","
            elif suffix == ".tsv":
                delimiter_raw = "\t"
            else:
                helpers.handle_error(f"Unsupported filename extension for {filename!r}. Supported extensions: .csv, .tsv")

    delimiter = helpers.validate_delimiter(delimiter_raw)

    _LOGGER.debug("Timezone_identifier: %s", timezone_identifier)
    _LOGGER.debug("Delimiter: %s", delimiter)
    _LOGGER.debug("Decimal separator: %s", decimal)
    _LOGGER.debug("Datetime format: %s", datetime_format)

    return decimal, timezone_identifier, delimiter, datetime_format


def split_dataframe_by_type(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split a mixed DataFrame into sensor and counter DataFrames by statistic_id.

    Groups by statistic_id and checks which value columns have non-NaN values.
    If a single statistic_id has BOTH sensor AND counter data, raises an error.

    Args:
    ----
        df: DataFrame with mixed sensor and counter columns

    Returns:
    -------
        Tuple of (sensor_df, counter_df) with only the relevant columns for each type.
        sensor_df columns: [statistic_id, unit, start, min, max, mean]
        counter_df columns: [statistic_id, unit, start, sum, state, delta] as available

    Raises:
    ------
        HomeAssistantError: If a single statistic_id has both sensor and counter data

    """
    sensor_columns = {"min", "max", "mean"}
    counter_columns = {"sum", "state", "delta"}

    sensor_ids = []
    counter_ids = []

    for statistic_id, group in df.groupby("statistic_id", sort=False):
        has_sensor_data = any(col in group.columns and group[col].notna().any() for col in sensor_columns)
        has_counter_data = any(col in group.columns and group[col].notna().any() for col in counter_columns)

        if has_sensor_data and has_counter_data:
            helpers.handle_error(
                f"Statistic '{statistic_id}' has both sensor (min/max/mean) and counter (sum/state/delta) data. "
                f"A single statistic_id must be either sensor or counter, not both."
            )

        if has_sensor_data:
            sensor_ids.append(statistic_id)
        elif has_counter_data:
            counter_ids.append(statistic_id)
        else:
            helpers.handle_error(f"Statistic '{statistic_id}' has no value data in any of the expected columns (min, max, mean, sum, state, delta).")

    # Build sensor DataFrame with only the relevant columns.
    sensor_df = df[df["statistic_id"].isin(sensor_ids)][["statistic_id", "unit", "start", "min", "max", "mean"]].copy() if sensor_ids else pd.DataFrame()

    # Build counter DataFrame with the available counter columns.
    if counter_ids:
        counter_cols = ["statistic_id", "unit", "start"]
        counter_cols.extend(col for col in ("sum", "state", "delta") if col in df.columns)
        counter_df = df[df["statistic_id"].isin(counter_ids)][counter_cols].copy()
    else:
        counter_df = pd.DataFrame()

    return sensor_df, counter_df


def _collect_validation_errors(validate: Callable[[], None]) -> list[str]:
    """Run one validator and return its errors instead of stopping validation."""
    try:
        validate()
    except HomeAssistantError as err:
        return err.errors if isinstance(err, helpers.AggregatedValidationError) else [str(err)]
    return []


def _validate_dataframe_for_import(df: pd.DataFrame) -> None:
    """Collect and raise independent row and unit validation errors."""
    errors = []
    newest_dt = df["start"].max()
    if pd.isna(newest_dt):
        errors.append("No valid timestamps found in import data")
    else:
        errors.extend(_collect_validation_errors(lambda: helpers.is_not_in_future(newest_dt)))

    errors.extend(_collect_validation_errors(lambda: helpers.validate_timestamps_vectorized(df)))

    if "mean" in df.columns:
        float_errors = _collect_validation_errors(lambda: helpers.validate_floats_vectorized(df, ["min", "max", "mean"]))
        errors.extend(float_errors)
        if not float_errors:
            errors.extend(_collect_validation_errors(lambda: helpers.validate_min_max_mean_vectorized(df)))
    elif "sum" in df.columns:
        float_columns = ["sum"]
        if "state" in df.columns:
            float_columns.append("state")
        errors.extend(_collect_validation_errors(lambda: helpers.validate_floats_vectorized(df, float_columns)))
    else:
        errors.append("Implementation error: neither mean nor sum columns found")

    for statistic_id in df["statistic_id"].unique():
        unit_series = df.loc[df["statistic_id"] == statistic_id, "unit"]
        errors.extend(_collect_validation_errors(lambda series=unit_series, sid=statistic_id: helpers.validate_unit_consistency(series, sid)))

    helpers.handle_errors(errors)


def handle_dataframe_no_delta(df: pd.DataFrame) -> dict:
    """
    Process non-delta statistics from DataFrame.

    Args:
    ----
        df: DataFrame with statistic_id, start, and value columns
        timezone_identifier: IANA timezone string
        datetime_format: Format string for parsing timestamps

    Returns:
    -------
        Dictionary mapping statistic_id to (metadata, statistics_list)

    Raises:
    ------
        HomeAssistantError: On validation errors

    """
    columns = df.columns

    # Validate that newest timestamp is not too recent
    # With datetime objects, simply get max (no parsing needed!)
    has_mean = "mean" in columns
    has_sum = "sum" in columns
    _validate_dataframe_for_import(df)

    # Pre-allocate stats dictionary with metadata for all unique statistic_ids
    stats = {}
    unique_ids = df["statistic_id"].unique()

    for statistic_id in unique_ids:
        # Get unit from first occurrence of this statistic_id
        unit_series = df.loc[df["statistic_id"] == statistic_id, "unit"]
        unit: str = unit_series.iloc[0]  # type: ignore[assignment]
        source = helpers.get_source(statistic_id)

        unit_of_measurement = helpers.get_unit_from_row(unit, statistic_id)
        metadata = {
            "mean_type": StatisticMeanType.ARITHMETIC if has_mean else StatisticMeanType.NONE,
            "has_sum": has_sum,
            "source": source,
            "statistic_id": statistic_id,
            "name": None,
            "unit_class": helpers.get_unit_class(unit_of_measurement),
            "unit_of_measurement": unit_of_measurement,
        }
        stats[statistic_id] = (metadata, [])

    # Process data using groupby for better performance
    grouped = df.groupby("statistic_id", sort=False)

    for statistic_id, group_df in grouped:
        statistics_list = []

        if has_mean:
            # Build statistics list from group using itertuples (faster than iterrows)
            for row in group_df.itertuples(index=False, name=None):
                # row format: (statistic_id, unit, start, min, max, mean, ...)
                # Map to column names - strict=True ensures columns and row have same length
                row_dict = dict(zip(group_df.columns, row, strict=True))
                statistics_list.append(
                    {
                        "start": row_dict["start"],
                        "min": row_dict["min"],
                        "max": row_dict["max"],
                        "mean": row_dict["mean"],
                    }
                )
        elif has_sum:
            # Build statistics list for sum/state
            has_state = "state" in columns
            for row in group_df.itertuples(index=False, name=None):
                row_dict = dict(zip(group_df.columns, row, strict=True))
                stat_dict = {
                    "start": row_dict["start"],
                    "sum": row_dict["sum"],
                }
                if has_state:
                    stat_dict["state"] = row_dict["state"]
                statistics_list.append(stat_dict)

        stats[statistic_id][1].extend(statistics_list)

    return stats
