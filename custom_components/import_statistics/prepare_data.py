"""Main methods for the import_statistics integration."""

import csv
import datetime
import json
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
    ATTR_UNIT_FROM_ENTITY,
    DATETIME_DEFAULT_FORMAT,
)
from custom_components.import_statistics.helpers import _LOGGER, UnitFrom


def prepare_data_to_import(file_path: str, call: ServiceCall) -> tuple:
    """
    Prepare data to import statistics from a file.

    Args:
    ----
        file_path: Path to the file with the data to be imported.
        call: The call data containing the necessary information.

    Returns:
    -------
        A dictionary containing the imported statistics.

    Raises:
    ------
        FileNotFoundError: If the specified file does not exist.
        ValueError: If there is an implementation error.

    """
    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(call)

    _LOGGER.info("Importing statistics from file: %s", file_path)
    if not Path(file_path).exists():
        helpers.handle_error(f"path {file_path} does not exist.")

    my_df = pd.read_csv(file_path, sep=delimiter, decimal=decimal, engine="python")

    stats = handle_dataframe(my_df, timezone_identifier, datetime_format, unit_from_entity)
    return stats, unit_from_entity


def prepare_json_entities(call: ServiceCall) -> tuple:
    """Prepare json entities for import."""
    timezone_identifier = call.data.get("timezone_identifier")

    if timezone_identifier not in pytz.all_timezones:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    timezone = zoneinfo.ZoneInfo(timezone_identifier)
    entities = call.data.get("entities", [])

    return timezone, entities


def prepare_json_data_to_import(call: ServiceCall) -> tuple:
    """Parse json data to import statistics from."""
    _, timezone_identifier, _, datetime_format, unit_from_entity = handle_arguments(call)

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
    stats = handle_dataframe(my_df, timezone_identifier, datetime_format, unit_from_entity)
    return stats, unit_from_entity


def handle_arguments(call: ServiceCall) -> tuple:
    """
    Handle the arguments for importing statistics from a file.

    Args:
    ----
        call (ServiceCall): The service call object containing additional data.

    Returns:
    -------
        tuple: A tuple containing the decimal separator, timezone identifier, and delimiter.

    Raises:
    ------
        ValueError: If the timezone identifier is invalid.

    """
    decimal = "," if call.data.get(ATTR_DECIMAL, True) else "."

    datetime_format = call.data.get(ATTR_DATETIME_FORMAT) if ATTR_DATETIME_FORMAT in call.data else DATETIME_DEFAULT_FORMAT

    unit_from_entity = UnitFrom.ENTITY if call.data.get(ATTR_UNIT_FROM_ENTITY) is True else UnitFrom.TABLE

    timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER)

    if timezone_identifier not in pytz.all_timezones:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    delimiter = call.data.get(ATTR_DELIMITER)
    delimiter = helpers.validate_delimiter(delimiter)

    _LOGGER.debug("Timezone_identifier: %s", timezone_identifier)
    _LOGGER.debug("Delimiter: %s", delimiter)
    _LOGGER.debug("Decimal separator: %s", decimal)
    _LOGGER.debug("Datetime format: %s", datetime_format)
    _LOGGER.debug("Unit from entity: %s", unit_from_entity)

    return decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity


def handle_dataframe(
    df: pd.DataFrame,
    timezone_identifier: str,
    datetime_format: str,
    unit_from_where: UnitFrom,
) -> dict:
    """
    Process a dataframe and extract statistics based on the specified columns and timezone.

    Args:
    ----
        df (pandas.DataFrame): The input dataframe containing the statistics data.
        columns (list): The list of columns to extract from the dataframe.
        timezone_identifier (str): The timezone identifier to convert the timestamps.
        datetime_format (str): The format of the provided datetimes, e.g. "%d.%m.%Y %H:%M"
        unit_from_where: ENTITY if the unit is taken from the entity, TABLE if taken from input file.

    Returns:
    -------
        dict: A dictionary containing the extracted statistics, organized by statistic_id.

    Raises:
    ------
        ImplementationError: If both 'mean' and 'sum' columns are present in the columns list.

    """
    columns = df.columns
    _LOGGER.debug("Columns:")
    _LOGGER.debug(columns)
    if not helpers.are_columns_valid(df, unit_from_where):
        helpers.handle_error(
            "Implementation error. helpers.are_columns_valid returned false, this should never happen, because helpers.are_columns_valid throws an exception!"
        )
    stats = {}
    timezone = zoneinfo.ZoneInfo(timezone_identifier)
    has_mean = "mean" in columns
    has_sum = "sum" in columns
    for _index, row in df.iterrows():
        statistic_id = row["statistic_id"]
        if statistic_id not in stats:  # New statistic id found
            source = helpers.get_source(statistic_id)
            metadata = {
                "mean_type": StatisticMeanType.ARITHMETIC if has_mean else StatisticMeanType.NONE,
                "has_sum": has_sum,
                "source": source,
                "statistic_id": statistic_id,
                "name": None,
                "unit_class": None,
                "unit_of_measurement": helpers.add_unit_to_dataframe(source, unit_from_where, row.get("unit", ""), statistic_id),
            }
            stats[statistic_id] = (metadata, [])

        if has_mean:
            new_stat = helpers.get_mean_stat(row, timezone, datetime_format)
        if has_sum:
            new_stat = helpers.get_sum_stat(row, timezone, datetime_format)
        stats[statistic_id][1].append(new_stat)
    return stats


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
        with file_obj.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=delimiter)
            writer.writerow(columns)
            writer.writerows(rows)

        _LOGGER.info("Export file written successfully: %s", file_path)
    except OSError as e:
        helpers.handle_error(f"Failed to write export file {file_path}: {e}")


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
        "start": _format_datetime(stat_record["start"], timezone, datetime_format),
    }

    # Add sensor columns (empty for counters)
    if "mean" in stat_record:
        row_dict["min"] = _format_decimal(stat_record.get("min"), use_comma=decimal_comma)
        row_dict["max"] = _format_decimal(stat_record.get("max"), use_comma=decimal_comma)
        row_dict["mean"] = _format_decimal(stat_record["mean"], use_comma=decimal_comma)
        if "min" not in all_columns:
            all_columns.extend(["min", "max", "mean"])

    # Add counter columns (empty for sensors)
    if "sum" in stat_record:
        row_dict["sum"] = _format_decimal(stat_record["sum"], use_comma=decimal_comma)
        if "sum" not in all_columns:
            all_columns.append("sum")

    if "state" in stat_record:
        row_dict["state"] = _format_decimal(stat_record["state"], use_comma=decimal_comma)
        if "state" not in all_columns:
            all_columns.append("state")

    return row_dict


def prepare_export_data(
    statistics_dict: dict,
    timezone_identifier: str,
    datetime_format: str,
    *,
    decimal_comma: bool = False,
    units_dict: dict | None = None,
) -> tuple:
    """
    Prepare statistics data for export (TSV/CSV format).

    Args:
        statistics_dict: Raw data from recorder API
        timezone_identifier: Timezone for timestamp output
        datetime_format: Format string for timestamps
        decimal_comma: Use comma (True) or dot (False) for decimals
        units_dict: Mapping of statistic_id to unit_of_measurement

    Returns:
        tuple: (columns list, data rows list)

    """
    _LOGGER.info("Preparing export data")

    if timezone_identifier not in pytz.all_timezones:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    timezone = zoneinfo.ZoneInfo(timezone_identifier)

    # Default to empty dict if not provided (for backwards compatibility)
    if units_dict is None:
        units_dict = {}

    # Analyze what types of statistics we have (sensors vs counters)
    has_sensors = False  # mean/min/max
    has_counters = False  # sum/state

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
            has_sensors = True
        elif stat_type == "counter":
            has_counters = True

        for stat_record in statistics_list:
            row_dict = _process_statistic_record(
                stat_record,
                statistic_id,
                unit,
                {
                    "timezone": timezone,
                    "datetime_format": datetime_format,
                    "decimal_comma": decimal_comma,
                },
                all_columns=all_columns,
            )
            rows.append(row_dict)

    # Validate if sensors and counters are mixed
    if has_sensors and has_counters:
        _LOGGER.info("Export contains both sensor (mean/min/max) and counter (sum/state) statistics. Sensor columns will be empty for counters and vice versa.")

    # Build column list: always include statistic_id, unit, start
    # Then conditionally add sensor or counter columns
    column_order = ["statistic_id", "unit", "start"]
    if has_sensors:
        column_order.extend(["min", "max", "mean"])
    if has_counters:
        column_order.extend(["sum", "state"])

    # Convert row dicts to tuples in column order, filling empty cells
    data_rows = [tuple(row_dict.get(col, "") for col in column_order) for row_dict in rows]

    _LOGGER.debug("Export data prepared with columns: %s", column_order)
    return column_order, data_rows


def _detect_statistic_type(statistics_list: list) -> str:
    """
    Detect if statistics are sensor (mean/min/max) or counter (sum/state) type.

    Args:
        statistics_list: List of statistic records from recorder

    Returns:
        str: "sensor", "counter", or "unknown"

    """
    for stat_record in statistics_list:
        # Check if this is a sensor (has non-None mean/min/max values)
        if stat_record.get("mean") is not None or stat_record.get("min") is not None or stat_record.get("max") is not None:
            return "sensor"
        # Check if this is a counter (has non-None sum/state values)
        if stat_record.get("sum") is not None or stat_record.get("state") is not None:
            return "counter"

    return "unknown"


def _format_datetime(dt_obj: datetime.datetime | float, timezone: zoneinfo.ZoneInfo, format_str: str) -> str:
    """
    Format a datetime object to string in specified timezone and format.

    Args:
        dt_obj: Datetime object (may be UTC or already localized) or Unix timestamp (float)
        timezone: Target timezone
        format_str: Format string

    Returns:
        str: Formatted datetime string

    """
    # Handle Unix timestamp (float) from recorder API
    if isinstance(dt_obj, float):
        dt_obj = datetime.datetime.fromtimestamp(dt_obj, tz=datetime.UTC)
    elif dt_obj.tzinfo is None:
        # Assume UTC if naive
        dt_obj = dt_obj.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))

    # Convert to target timezone
    local_dt = dt_obj.astimezone(timezone)

    return local_dt.strftime(format_str)


def _format_decimal(value: float | None, *, use_comma: bool = False) -> str:
    """
    Format a numeric value with specified decimal separator.

    Args:
        value: Numeric value to format
        use_comma: Use comma (True) or dot (False) as decimal separator

    Returns:
        str: Formatted number string

    """
    if value is None:
        return ""

    formatted = f"{float(value):.10g}"  # Avoid scientific notation, remove trailing zeros

    if use_comma:
        formatted = formatted.replace(".", ",")

    return formatted


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

    for statistic_id, data in statistics_dict.items():
        # Data format from recorder API: {"statistic_id": [...]}
        statistics_list = data
        unit = units_dict.get(statistic_id, "")  # Get unit from metadata

        if not statistics_list:
            continue

        entity_obj = {"id": statistic_id, "unit": unit, "values": []}

        for stat_record in statistics_list:
            value_obj = {"datetime": _format_datetime(stat_record["start"], timezone, datetime_format)}

            # Add all available fields
            if "mean" in stat_record:
                value_obj["mean"] = stat_record["mean"]
            if "min" in stat_record:
                value_obj["min"] = stat_record["min"]
            if "max" in stat_record:
                value_obj["max"] = stat_record["max"]
            if "sum" in stat_record:
                value_obj["sum"] = stat_record["sum"]
            if "state" in stat_record:
                value_obj["state"] = stat_record["state"]

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
