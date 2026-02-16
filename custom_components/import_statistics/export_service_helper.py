"""Helper functions for export service - data formatting and file writing."""

import csv
import json
import zoneinfo
from pathlib import Path

import pytz

from custom_components.import_statistics import helpers
from custom_components.import_statistics.helpers import _LOGGER


def write_export_file(file_path: str, columns: list, rows: list, delimiter: str) -> None:
    """
    Write export data to a TSV/CSV file.

    Args:
         file_path: Absolute path to output file
         columns: List of column headers
         rows: List of row tuples
         delimiter: Column delimiter

    Raises:
         HomeAssistantError: If file cannot be written

    """
    _LOGGER.info("Writing export file: %s", file_path)

    try:
        file_obj = Path(file_path)
        # now using utf-8-sig to add BOM
        with file_obj.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=delimiter)
            writer.writerow(columns)
            writer.writerows(rows)

        _LOGGER.info("Export file written successfully: %s", file_path)
    except OSError as e:
        helpers.handle_error(f"Failed to write export file {file_path}: {e}")


def split_statistics_by_type(statistics_dict: dict, *, units_dict: dict | None = None) -> tuple[dict, dict, dict, dict]:
    """
    Split statistics dictionary into measurement and counter types.

    Args:
        statistics_dict: Dictionary of statistics to split
        units_dict: Optional dictionary mapping statistic_id to unit_of_measurement

    Returns:
        tuple: (measurement_statistics_dict, counter_statistics_dict, measurement_units_dict, counter_units_dict)

    """
    measurement_statistics_dict: dict = {}
    counter_statistics_dict: dict = {}

    if units_dict is None:
        units_dict = {}

    measurement_units_dict: dict = {}
    counter_units_dict: dict = {}

    for statistic_id, statistics_list in statistics_dict.items():
        if not statistics_list:
            continue

        stat_type = _detect_statistic_type(statistics_list)
        if stat_type == "sensor":
            measurement_statistics_dict[statistic_id] = statistics_list
            if statistic_id in units_dict:
                measurement_units_dict[statistic_id] = units_dict[statistic_id]
        elif stat_type == "counter":
            counter_statistics_dict[statistic_id] = statistics_list
            if statistic_id in units_dict:
                counter_units_dict[statistic_id] = units_dict[statistic_id]

    return measurement_statistics_dict, counter_statistics_dict, measurement_units_dict, counter_units_dict


def prepare_export_data(  # noqa: PLR0913, PLR0912
    statistics_dict: dict,
    timezone_identifier: str,
    datetime_format: str,
    *,
    decimal_separator: str,
    units_dict: dict | None = None,
    counter_fields: str = "both",
) -> tuple:
    """
    Prepare statistics data for export (TSV/CSV format).

    Args:
         statistics_dict: Raw data from recorder API
         timezone_identifier: Timezone for timestamp output
         datetime_format: Format string for timestamps
         decimal_comma: Use comma (True) or dot (False) for decimals (deprecated, use decimal_separator)
         decimal_separator: Decimal separator character ("." or ",")
         units_dict: Mapping of statistic_id to unit_of_measurement
         counter_fields: Counter output mode for CSV/TSV exports: "both" (state/sum/delta), "sum" (state/sum), or "delta" (delta only)

    Returns:
         tuple: (columns list, data rows list)

    """
    _LOGGER.info("Preparing export data")

    timezone = zoneinfo.ZoneInfo(timezone_identifier)

    use_comma = decimal_separator == ","

    # Default to empty dict if not provided (for backwards compatibility)
    if units_dict is None:
        units_dict = {}

    valid_counter_fields = {"both", "sum", "delta"}
    if counter_fields not in valid_counter_fields:
        helpers.handle_error(f"counter_fields must be one of {sorted(valid_counter_fields)}, got {counter_fields!r}")

    include_sum_state = counter_fields in {"both", "sum"}
    include_delta = counter_fields in {"both", "delta"}

    # Analyze what types of statistics we have (measurements vs counters)
    has_measurements = False  # mean/min/max
    has_counters = False  # sum/state
    has_deltas = False  # will be set if we calculate deltas

    all_columns = ["statistic_id", "unit", "start"]
    rows = []

    for statistic_id, data in statistics_dict.items():
        # Data format from recorder API: {"statistic_id": [...]}
        statistics_list = data
        unit = units_dict.get(statistic_id, "")  # Get unit from metadata

        if not statistics_list:
            _LOGGER.warning("Empty statistics list for %s", statistic_id)
            continue

        # Determine type from first non-empty record
        stat_type = _detect_statistic_type(statistics_list)

        if stat_type == "sensor":
            has_measurements = True
        elif stat_type == "counter":
            has_counters = True

        # Sort statistics by start timestamp (chronological order) BEFORE formatting
        # This ensures correct chronological order in output, not alphabetical
        sorted_statistics_list = sorted(statistics_list, key=lambda rec: rec["start"])

        for stat_record in sorted_statistics_list:
            row_dict = _process_statistic_record(
                stat_record,
                statistic_id,
                unit,
                {
                    "timezone": timezone,
                    "datetime_format": datetime_format,
                    "decimal_comma": use_comma,
                },
                all_columns=all_columns,
            )
            # Store the original numeric timestamp for sorting
            row_dict["_sort_timestamp"] = stat_record["start"]
            rows.append(row_dict)

    # Calculate deltas for counter exports when requested
    if has_counters and rows and include_delta:
        rows = get_delta_from_stats(rows, decimal_comma=use_comma)
        has_deltas = True

    # For delta-only exports, remove sum/state from output rows
    if has_counters and not include_sum_state:
        for row_dict in rows:
            row_dict.pop("sum", None)
            row_dict.pop("state", None)

    # Validate if measurements and counters are mixed
    if has_measurements and has_counters:
        _LOGGER.info(
            "Export contains both measurement (mean/min/max) and counter (sum/state) statistics. Measurement columns will be empty for counters and vice versa."
        )

    # Build column list: always include statistic_id, unit, start
    # Then conditionally add measurement or counter columns, and delta if present
    column_order = ["statistic_id", "unit", "start"]
    if has_measurements:
        column_order.extend(["min", "max", "mean"])
    if has_counters and include_sum_state:
        column_order.extend(["sum", "state"])
    if has_deltas:
        column_order.append("delta")

    # Sort rows by statistic_id first (alphabetical), then by numeric timestamp (chronological)
    # Use the stored numeric timestamp (_sort_timestamp) to ensure correct chronological order
    # regardless of the datetime format string chosen by the user
    rows = sorted(rows, key=lambda r: (r["statistic_id"], r["_sort_timestamp"]))

    # Convert row dicts to tuples in column order, filling empty cells
    # Exclude the internal _sort_timestamp field from output
    data_rows = [tuple(row_dict.get(col, "") for col in column_order) for row_dict in rows]

    _LOGGER.debug("Export data prepared with columns: %s", column_order)
    return column_order, data_rows


def prepare_export_json(statistics_dict: dict, timezone_identifier: str, datetime_format: str, units_dict: dict | None = None) -> list:
    """
    Prepare statistics data for JSON export.

    Args:
         statistics_dict: Raw data from recorder API
         timezone_identifier: Timezone for timestamp output
         datetime_format: Format string for timestamps
         units_dict: Mapping of statistic_id to unit_of_measurement

    Returns:
         list: List of entity objects in JSON format

    """
    _LOGGER.info("Preparing JSON export data")

    if timezone_identifier not in pytz.all_timezones:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    timezone = zoneinfo.ZoneInfo(timezone_identifier)

    # Default to empty dict if not provided (for backwards compatibility)
    if units_dict is None:
        units_dict = {}

    export_entities = []

    # Sort statistic_ids for consistent output order
    for statistic_id in sorted(statistics_dict.keys()):
        data = statistics_dict[statistic_id]
        # Data format from recorder API: {"statistic_id": [...]}
        statistics_list = data
        unit = units_dict.get(statistic_id, "")  # Get unit from metadata

        if not statistics_list:
            continue

        entity_obj = {"id": statistic_id, "unit": unit, "values": []}

        # Detect if this is a counter (has non-None sum/state) to calculate deltas
        is_counter = any((rec.get("sum") is not None or rec.get("state") is not None) for rec in statistics_list)
        previous_sum = None

        # Sort records by start timestamp (ascending/chronological order)
        sorted_statistics = sorted(statistics_list, key=lambda rec: rec["start"])

        for stat_record in sorted_statistics:
            value_obj = {"datetime": helpers.format_datetime(stat_record["start"], timezone, datetime_format)}

            # Add all available fields (only if not None)
            if stat_record.get("mean") is not None:
                value_obj["mean"] = stat_record["mean"]
            if stat_record.get("min") is not None:
                value_obj["min"] = stat_record["min"]
            if stat_record.get("max") is not None:
                value_obj["max"] = stat_record["max"]
            if stat_record.get("sum") is not None:
                value_obj["sum"] = stat_record["sum"]
            if stat_record.get("state") is not None:
                value_obj["state"] = stat_record["state"]

            # Calculate delta for counters (only if sum is not None)
            if is_counter and stat_record.get("sum") is not None:
                if previous_sum is not None:
                    delta_value = stat_record["sum"] - previous_sum
                    value_obj["delta"] = delta_value
                # Note: first record has no delta (previous_sum is None)
                previous_sum = stat_record["sum"]

            entity_obj["values"].append(value_obj)

        export_entities.append(entity_obj)

    return export_entities


def write_export_json(file_path: str, json_data: list) -> None:
    """
    Write export data to a JSON file.

    Args:
         file_path: Absolute path to output file
         json_data: List of dictionaries to export

    Raises:
         HomeAssistantError: If file cannot be written

    """
    _LOGGER.info("Writing export JSON file: %s", file_path)

    try:
        file_obj = Path(file_path)
        with file_obj.open("w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        _LOGGER.info("Export JSON file written successfully: %s", file_path)
    except OSError as e:
        helpers.handle_error(f"Failed to write export JSON file {file_path}: {e}")


def _process_statistic_record(
    stat_record: dict,
    statistic_id: str,
    unit: str,
    format_context: dict,
    *,
    all_columns: list | None = None,
) -> dict:
    """
    Process a single statistic record into a row dictionary.

    Args:
         stat_record: The statistic record to process
         statistic_id: The ID of the statistic
         unit: The unit of measurement
         format_context: Dict with timezone, datetime_format, and decimal_comma
         all_columns: List to track all columns (mutated in place)

    Returns:
         Dictionary representation of the row

    """
    if all_columns is None:
        all_columns = []

    timezone = format_context["timezone"]
    datetime_format = format_context["datetime_format"]
    decimal_comma = format_context["decimal_comma"]

    row_dict = {
        "statistic_id": statistic_id,
        "unit": unit,
        "start": helpers.format_datetime(stat_record["start"], timezone, datetime_format),
    }

    # Add measurement columns (empty for counters)
    if "mean" in stat_record:
        row_dict["min"] = helpers.format_decimal(stat_record.get("min"), use_comma=decimal_comma)
        row_dict["max"] = helpers.format_decimal(stat_record.get("max"), use_comma=decimal_comma)
        row_dict["mean"] = helpers.format_decimal(stat_record["mean"], use_comma=decimal_comma)
        if "min" not in all_columns:
            all_columns.extend(["min", "max", "mean"])

    # Add counter columns (empty for measurements)
    if "sum" in stat_record:
        row_dict["sum"] = helpers.format_decimal(stat_record["sum"], use_comma=decimal_comma)
        if "sum" not in all_columns:
            all_columns.append("sum")

    if "state" in stat_record:
        row_dict["state"] = helpers.format_decimal(stat_record["state"], use_comma=decimal_comma)
        if "state" not in all_columns:
            all_columns.append("state")

    # Add delta column if present
    if "delta" in stat_record:
        row_dict["delta"] = helpers.format_decimal(stat_record["delta"], use_comma=decimal_comma)
        if "delta" not in all_columns:
            all_columns.append("delta")

    return row_dict


def _detect_statistic_type(statistics_list: list) -> str:
    """
    Detect if statistics are measurement (mean/min/max) or counter (sum/state) type.

    Args:
         statistics_list: List of statistic records from recorder

    Returns:
         str: "sensor", "counter", or "unknown"

    """
    for stat_record in statistics_list:
        # Check if this is a measurement (has non-None mean/min/max values)
        if stat_record.get("mean") is not None or stat_record.get("min") is not None or stat_record.get("max") is not None:
            return "sensor"
        # Check if this is a counter (has non-None sum/state values)
        if stat_record.get("sum") is not None or stat_record.get("state") is not None:
            return "counter"

    return "unknown"


def get_delta_from_stats(rows: list[dict], *, decimal_comma: bool = False) -> list[dict]:
    """
    Calculate delta values from a list of records sorted by statistic_id and start.

    For each statistic_id, calculates delta as the difference between consecutive sum values.
    The first counter record of each statistic_id gets delta 0 (no previous value).

    Args:
         rows: List of row dicts with statistic_id, _sort_timestamp (numeric), start (formatted string), sum, and/or state fields
         decimal_comma: Use comma (True) or dot (False) as decimal separator for output

    Returns:
         list[dict]: Rows with delta column added (formatted as string)

    """
    if not rows:
        return []

    # Sort rows by statistic_id first, then by numeric timestamp (_sort_timestamp)
    # This ensures correct chronological order regardless of datetime format string
    sorted_rows = sorted(rows, key=lambda r: (r["statistic_id"], r["_sort_timestamp"]))

    result = []
    previous_sum_by_id = {}

    for row_dict in sorted_rows:
        statistic_id = row_dict["statistic_id"]
        new_row = dict(row_dict)

        # Get previous sum for this statistic_id
        prev_sum = previous_sum_by_id.get(statistic_id)

        # Calculate delta if we have sum/state values and a previous value
        if prev_sum is not None and "sum" in row_dict:
            # sum is already a string (formatted), need to extract numeric value
            sum_str = row_dict["sum"]
            if sum_str:  # Only if sum is not empty
                try:
                    # Convert back to float for calculation
                    decimal_sep = "," if decimal_comma else "."
                    sum_value = float(sum_str.replace(decimal_sep, "."))
                    delta_value = sum_value - prev_sum
                    new_row["delta"] = helpers.format_decimal(delta_value, use_comma=decimal_comma)
                except (ValueError, AttributeError):
                    new_row["delta"] = ""
            else:
                new_row["delta"] = ""
        elif row_dict.get("sum"):
            # First record for this statistic_id: output 0 for counters so re-importing as delta works.
            new_row["delta"] = helpers.format_decimal(0.0, use_comma=decimal_comma)
        else:
            new_row["delta"] = ""

        # Update previous sum for next iteration
        if row_dict.get("sum"):
            try:
                decimal_sep = "," if decimal_comma else "."
                previous_sum_by_id[statistic_id] = float(row_dict["sum"].replace(decimal_sep, "."))
            except (ValueError, AttributeError):
                pass

        result.append(new_row)

    return result
