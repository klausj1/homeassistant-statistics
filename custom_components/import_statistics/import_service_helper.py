"""
Helper functions for import service - data preparation from files/JSON.

No hass object needed.
"""

import zoneinfo
from pathlib import Path

import pandas as pd
import pytz
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.core import ServiceCall

from custom_components.import_statistics import helpers
from custom_components.import_statistics.const import (
    ATTR_DATETIME_FORMAT,
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_TIMEZONE_IDENTIFIER,
    DATETIME_DEFAULT_FORMAT,
)
from custom_components.import_statistics.helpers import _LOGGER


def _validate_and_detect_delta(df: "pd.DataFrame") -> bool:
    """
    Validate DataFrame columns and detect delta mode.

    Args:
    ----
        df: DataFrame to validate

    Returns:
    -------
        True if delta mode is detected, False otherwise

    Raises:
    ------
        HomeAssistantError: If column validation fails

    """
    _LOGGER.debug("Columns: %s", df.columns)

    if not helpers.are_columns_valid(df):
        helpers.handle_error(
            "Implementation error. helpers.are_columns_valid returned false, this should never happen, because helpers.are_columns_valid throws an exception!"
        )

    return "delta" in df.columns


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
        df["start"] = df["start"].dt.tz_localize(timezone, nonexistent="raise", ambiguous="NaT")

        # For any NaT values (ambiguous times), re-localize using True (later occurrence)
        if df["start"].isna().any():
            ambiguous_mask = df["start"].isna()
            if ambiguous_mask.any():
                if naive_copy is not None:
                    # CSV/TSV path: Use pre-saved naive timestamps
                    # Create a boolean array: True = use later occurrence (DST ended, standard time)
                    ambiguous_array = pd.Series([True] * ambiguous_mask.sum(), index=df[ambiguous_mask].index)
                    ambiguous_times = naive_copy.loc[ambiguous_mask].dt.tz_localize(timezone, ambiguous=ambiguous_array)
                    df.loc[ambiguous_mask, "start"] = ambiguous_times
                else:
                    # JSON path: This should not happen in practice because JSON data comes pre-parsed
                    # If it does, we cannot recover the original string, so we use 'infer' which defaults to later
                    # Note: This is a fallback and may not work correctly if start column was already NaT
                    helpers.handle_error(
                        "Implementation error: Ambiguous timestamps detected but no naive copy provided. This indicates a bug in timestamp parsing logic."
                    )
    except Exception as e:
        # Provide clear error message for DST issues
        error_msg = str(e)
        if "nonexistent" in error_msg.lower() or "does not exist" in error_msg.lower():
            helpers.handle_error(
                "Timestamp does not exist due to daylight saving time transition (spring forward). "
                "The timestamp falls in the gap when clocks move forward. "
                f"Please adjust your timestamps to avoid the DST gap. Error: {error_msg}"
            )
        raise


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
        Tuple of (df, timezone_identifier, datetime_format, is_delta)

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

    is_delta = _validate_and_detect_delta(my_df)

    return my_df, timezone_identifier, datetime_format, is_delta


def prepare_json_data_to_import(call: ServiceCall, ha_timezone: str) -> tuple:
    """
    Prepare data from JSON service call for import.

    Args:
    ----
        call: The service call data containing entities.
        ha_timezone: Home Assistant's configured timezone identifier.

    Returns:
    -------
        Tuple of (df, timezone_identifier, datetime_format, is_delta)

    Raises:
    ------
        HomeAssistantError: If there is a validation error.

    """
    _, timezone_identifier, _, datetime_format = handle_arguments(call, ha_timezone, filename=None)

    valid_columns = ["state", "sum", "min", "max", "mean"]
    columns = ["statistic_id", "unit", "start"]
    data = []

    input_entities = call.data.get("entities", [])

    for entity in input_entities:
        statistic_id, values, unit = (entity["id"], entity["values"], entity["unit"])
        _LOGGER.info(f"Parsing entity with id: {statistic_id} with {len(values)} values")
        for value in values:
            value_dict = {
                "statistic_id": statistic_id,
                "unit": unit,
                "start": value["datetime"],
            }
            for valid_column in valid_columns:
                if valid_column in value:
                    if valid_column not in columns:
                        columns.append(valid_column)
                    value_dict[valid_column] = value[valid_column]

            data.append(tuple([value_dict[column] for column in columns]))

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

    except Exception as e:
        # Provide clear error message for parsing failures
        error_msg = str(e)
        if "does not match format" in error_msg.lower():
            helpers.handle_error(f"Failed to parse timestamp. Expected format: {datetime_format}. Error: {error_msg}")
        raise

    is_delta = _validate_and_detect_delta(my_df)

    return my_df, timezone_identifier, datetime_format, is_delta


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
    newest_dt = df["start"].max()

    if pd.isna(newest_dt):
        helpers.handle_error("No valid timestamps found in import data")

    # Validate newest timestamp
    helpers.is_not_in_future(newest_dt)

    has_mean = "mean" in columns
    has_sum = "sum" in columns

    # Vectorized validation: validate all timestamps at once
    helpers.validate_timestamps_vectorized(df)

    # Vectorized validation: validate all float columns at once
    if has_mean:
        helpers.validate_floats_vectorized(df, ["min", "max", "mean"])
        helpers.validate_min_max_mean_vectorized(df)
    elif has_sum:
        float_cols = ["sum"]
        if "state" in columns:
            float_cols.append("state")
        helpers.validate_floats_vectorized(df, float_cols)
    else:
        # This should never happen due to column validation, but defensive check
        helpers.handle_error("Implementation error: neither mean nor sum columns found")

    # Pre-allocate stats dictionary with metadata for all unique statistic_ids
    stats = {}
    unique_ids = df["statistic_id"].unique()

    for statistic_id in unique_ids:
        # Get unit from first occurrence of this statistic_id
        unit = df.loc[df["statistic_id"] == statistic_id, "unit"].iloc[0]
        source = helpers.get_source(statistic_id)

        metadata = {
            "mean_type": StatisticMeanType.ARITHMETIC if has_mean else StatisticMeanType.NONE,
            "has_sum": has_sum,
            "source": source,
            "statistic_id": statistic_id,
            "name": None,
            "unit_class": None,
            "unit_of_measurement": helpers.get_unit_from_row(unit, statistic_id),
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
