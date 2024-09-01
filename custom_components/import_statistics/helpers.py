"""Helpers for the import_statistics integration."""

import datetime as dt
import logging
import zoneinfo
from enum import Enum

import pandas as pd
from homeassistant.components.recorder.statistics import valid_statistic_id
from homeassistant.core import valid_entity_id
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.const import DATETIME_DEFAULT_FORMAT

_LOGGER = logging.getLogger(__name__)


class UnitFrom(Enum):
    """Where is the unit taken from."""

    TABLE = 1
    ENTITY = 2


def get_source(statistic_id: str) -> str:
    """
    Get the source of a statistic based on the given statistic_id.

    Args:
    ----
        statistic_id (str): The ID of the statistic.

    Returns:
    -------
        str: The source of the statistic.

    Raises:
    ------
        ValueError: If the statistic_id is invalid.

    """
    if valid_entity_id(statistic_id):
        source = statistic_id.split(".")[0]
        if source == "recorder":
            handle_error(f"Invalid statistic_id {statistic_id}. DOMAIN 'recorder' is not allowed.")
        source = "recorder"
    elif valid_statistic_id(statistic_id):
        source = statistic_id.split(":")[0]
        if len(source) == 0:
            handle_error(f"Implementation error, this must not happen. Invalid statistic_id. (must not start with ':'): {statistic_id}")
        if source == "recorder":
            handle_error(f"Invalid statistic_id {statistic_id}. DOMAIN 'recorder' is not allowed.")
    else:
        handle_error(f"Statistic_id {statistic_id} is invalid. Use either an existing entity ID (containing a '.'), or a statistic id (containing a ':')")

    return source


def get_mean_stat(row: pd.Series, timezone: zoneinfo.ZoneInfo, datetime_format: str = DATETIME_DEFAULT_FORMAT) -> dict:
    """
    Process a row and extract mean statistics based on the specified columns and timezone.

    Args:
    ----
        row (pandas.Series): The input row containing the statistics data.
        timezone (zoneinfo.ZoneInfo): The timezone to convert the timestamps.
        datetime_format (str): The format of the provided datetimes, e.g. "%d.%m.%Y %H:%M"

    Returns:
    -------
        dict: A dictionary containing the extracted mean statistics.

    """
    if (
        is_full_hour(row["start"], datetime_format)
        and is_valid_float(row["min"])
        and is_valid_float(row["max"])
        and is_valid_float(row["mean"])
        and min_max_mean_are_valid(row["min"], row["max"], row["mean"])
    ):
        return {
            "start": dt.datetime.strptime(row["start"], datetime_format).replace(tzinfo=timezone),
            "min": row["min"],
            "max": row["max"],
            "mean": row["mean"],
        }
    return {}


def get_sum_stat(row: pd.Series, timezone: zoneinfo.ZoneInfo, datetime_format: str = DATETIME_DEFAULT_FORMAT) -> dict:
    """
    Process a row and extract sum statistics based on the specified columns and timezone.

    Args:
    ----
        row (pandas.Series): The input row containing the statistics data.
        timezone (zoneinfo.ZoneInfo): The timezone to convert the timestamps.
        datetime_format (str): The format of the provided datetimes, e.g. "%d.%m.%Y %H:%M"

    Returns:
    -------
        dict: A dictionary containing the extracted sum statistics.

    """
    if is_full_hour(row["start"], datetime_format) and is_valid_float(row["sum"]):
        if "state" in row.index:
            if is_valid_float(row["state"]):
                return {
                    "start": dt.datetime.strptime(row["start"], datetime_format).replace(tzinfo=timezone),
                    "sum": row["sum"],
                    "state": row["state"],
                }
        else:
            return {
                "start": dt.datetime.strptime(row["start"], datetime_format).replace(tzinfo=timezone),
                "sum": row["sum"],
            }

    return {}


def is_full_hour(timestamp_str: str, datetime_format: str = DATETIME_DEFAULT_FORMAT) -> bool:
    """
    Check if the given timestamp is a full hour.

    Args:
    ----
        timestamp_str (str): The timestamp string
        datetime_format (str): The format of the provided timestamp_str, e.g. "%d.%m.%Y %H:%M"

    Returns:
    -------
        bool: True if the timestamp is a full hour, False is never returned.

    Raises:
    ------
        HomeAssistantError: If the timestamp is not a full hour.

    """
    try:
        dt1 = dt.datetime.strptime(timestamp_str, datetime_format).astimezone(dt.UTC)
    except ValueError as exc:
        msg = f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '{datetime_format}'."
        raise HomeAssistantError(msg) from exc

    if dt1.minute != 0 or dt1.second != 0:
        msg = f"Invalid timestamp: {timestamp_str}. The timestamp must be a full hour."
        raise HomeAssistantError(msg)

    return True


def is_valid_float(value: str) -> bool:
    """
    Check if the given value is a valid float.

    Args:
    ----
        value: The value to check.

    Returns:
    -------
        bool: True if the value is a valid float, False otherwise.

    """
    try:
        float(value)
    except ValueError as exc:
        msg = f"Invalid float value: {value}. Check the decimal separator."
        raise HomeAssistantError(msg) from exc
    else:
        return True


def min_max_mean_are_valid(min_value: float, max_value: float, mean_value: float) -> bool:
    """
    Check if the given min, max, and mean values are valid.

    Args:
    ----
        min_value (float): The minimum value.
        max_value (float): The maximum value.
        mean_value (float): The mean value.

    Returns:
    -------
        bool: True if the values are valid, False otherwise.

    """
    if min_value <= mean_value <= max_value:
        return True
    msg = f"Invalid values: min: {min_value}, max: {max_value}, mean: {mean_value}, mean must be between min and max."
    raise HomeAssistantError(msg)


def are_columns_valid(df: pd.DataFrame, unit_from_where: UnitFrom) -> bool:
    """
    Check if the given DataFrame columns meet the required criteria.

    Args:
    ----
        df: dataFrame.
        unit_from_where: ENTITY if the unit is taken from the entity, TABLE if taken from input file.

    Returns:
    -------
        bool: True if the columns meet the required criteria, False otherwise.

    """
    columns = df.columns
    if not ("statistic_id" in columns and "start" in columns and ("unit" in columns or unit_from_where == UnitFrom.ENTITY)):
        handle_error(
            "The file must contain the columns 'statistic_id', 'start' and 'unit' ('unit' is needed only if unit_from_entity is false) (check delimiter)"
        )
    if not (("mean" in columns and "min" in columns and "max" in columns) or ("sum" in columns)):
        handle_error("The file must contain either the columns 'mean', 'min' and 'max' or the column 'sum' (check delimiter)")
    if ("mean" in columns or "min" in columns or "max" in columns) and "sum" in columns:
        handle_error("The file must not contain the columns 'sum' and 'mean'/'min'/'max' (check delimiter)")
    return True


def handle_error(error_string: str) -> None:
    """
    Handle an error by logging a warning and raising a HomeAssistantError.

    Args:
    ----
        error_string (str): The error message.

    Raises:
    ------
        HomeAssistantError: The raised exception containing the error message.

    """
    _LOGGER.warning(error_string)
    raise HomeAssistantError(error_string)


def add_unit_to_dataframe(source: str, unit_from_where: UnitFrom, unit_from_row: str, statistic_id: str) -> str:
    """
    Add unit to dataframe, or leave it empty for now if unit_from_entity is true.

    Args:
    ----
        source: "recorder" for internal statistics
        unit_from_where: ENTITY if the unit is taken from the entity, TABLE if taken from input file.
        unit_from_row: The unit from the imported file
        statistic_id: The statistic id from the imported file

    Returns:
    -------
        str: unit, or empty if unit_from_entity is true

    Raises:
    ------
        HomeAssistantError: The raised exception containing the error message.

    """
    if source == "recorder":
        if unit_from_where == UnitFrom.ENTITY:
            return ""
        if unit_from_row != "":
            return unit_from_row
        handle_error(f"Unit does not exist. Statistic ID: {statistic_id}.")
        return ""
    if unit_from_where == UnitFrom.ENTITY:
        handle_error(f"Unit_from_entity set to TRUE is not allowed for external statistics (statistic_id with a ':'). Statistic ID: {statistic_id}.")
        return ""
    if unit_from_row == "":
        handle_error(f"Unit does not exist. Statistic ID: {statistic_id}.")
        return ""
    return unit_from_row
