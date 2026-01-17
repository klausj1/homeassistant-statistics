"""
Helper functions for import service - data preparation from files/JSON.

No hass object needed.
"""

import datetime as dt
import zoneinfo
from pathlib import Path
from typing import cast

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


def _validate_and_detect_delta(df: "pd.DataFrame", unit_from_entity: UnitFrom) -> bool:
    """
    Validate DataFrame columns and detect delta mode.

    Args:
    ----
        df: DataFrame to validate
        unit_from_entity: Source of unit values (TABLE or ENTITY)

    Returns:
    -------
        True if delta mode is detected, False otherwise

    Raises:
    ------
        HomeAssistantError: If column validation fails

    """
    _LOGGER.debug("Columns: %s", df.columns)

    if not helpers.are_columns_valid(df, unit_from_entity):
        helpers.handle_error(
            "Implementation error. helpers.are_columns_valid returned false, this should never happen, because helpers.are_columns_valid throws an exception!"
        )

    return "delta" in df.columns


def prepare_data_to_import(file_path: str, call: ServiceCall) -> tuple:
    """
    Load and prepare data from CSV/TSV file for import.

    Args:
    ----
        file_path: Path to the file with the data to be imported.
        call: The call data containing the necessary information.

    Returns:
    -------
        Tuple of (df, timezone_identifier, datetime_format, unit_from_entity, is_delta)

    Raises:
    ------
        FileNotFoundError: If the specified file does not exist.
        HomeAssistantError: If there is a validation error.

    """
    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(call)

    _LOGGER.info("Importing statistics from file: %s", file_path)
    if not Path(file_path).exists():
        helpers.handle_error(f"path {file_path} does not exist.")

    # Validate file encoding before attempting to read
    helpers.validate_file_encoding(file_path)

    my_df = pd.read_csv(file_path, sep=delimiter, decimal=decimal, engine="python", encoding="utf-8")

    is_delta = _validate_and_detect_delta(my_df, unit_from_entity)

    return my_df, timezone_identifier, datetime_format, unit_from_entity, is_delta


def prepare_json_data_to_import(call: ServiceCall) -> tuple:
    """
    Prepare data from JSON service call for import.

    Args:
    ----
        call: The service call data containing entities.

    Returns:
    -------
        Tuple of (df, timezone_identifier, datetime_format, unit_from_entity, is_delta)

    Raises:
    ------
        HomeAssistantError: If there is a validation error.

    """
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

    is_delta = _validate_and_detect_delta(my_df, unit_from_entity)

    return my_df, timezone_identifier, datetime_format, unit_from_entity, is_delta


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
        HomeAssistantError: If the timezone identifier is invalid.

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


def handle_dataframe_no_delta(
    df: pd.DataFrame,
    timezone_identifier: str,
    datetime_format: str,
    unit_from_where: UnitFrom,
) -> dict:
    """
    Process non-delta statistics from DataFrame.

    Args:
    ----
        df: DataFrame with statistic_id, start, and value columns
        timezone_identifier: IANA timezone string
        datetime_format: Format string for parsing timestamps
        unit_from_where: Source of unit values (TABLE or ENTITY)

    Returns:
    -------
        Dictionary mapping statistic_id to (metadata, statistics_list)

    Raises:
    ------
        HomeAssistantError: On validation errors

    """
    columns = df.columns

    stats = {}
    timezone = zoneinfo.ZoneInfo(timezone_identifier)

    # Validate that newest timestamp is not too recent
    # Parse all timestamps first to find true newest chronologically
    # Using string max would give alphabetical order, not chronological
    newest_dt: dt.datetime | None = None
    for timestamp_str in df["start"]:
        try:
            dt_obj = dt.datetime.strptime(timestamp_str, datetime_format).replace(tzinfo=timezone)
            if newest_dt is None or dt_obj > newest_dt:
                newest_dt = dt_obj
        except (ValueError, TypeError) as e:
            helpers.handle_error(f"Invalid timestamp format: {timestamp_str}: {e}")

    if newest_dt is None:
        helpers.handle_error("No valid timestamps found in import data")

    # At this point, newest_dt is guaranteed to be a datetime (not None)
    # Cast to satisfy type checker after the None check above
    helpers.is_not_in_future(cast("dt.datetime", newest_dt))

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

        new_stat = {}
        if has_mean:
            new_stat = helpers.get_mean_stat(row, timezone, datetime_format)
        elif has_sum:
            new_stat = helpers.get_sum_stat(row, timezone, datetime_format)
        if new_stat:
            stats[statistic_id][1].append(new_stat)

    return stats
