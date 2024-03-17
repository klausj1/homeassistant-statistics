"""The import_statistics integration."""

from datetime import datetime
import logging
import os
import zoneinfo

import pandas as pd

from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
    valid_statistic_id,
)
from homeassistant.core import HomeAssistant, valid_entity_id
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
import pytz
from custom_components.import_statistics.const import ATTR_FILENAME, ATTR_DECIMAL, ATTR_TIMEZONE_IDENTIFIER, ATTR_DELIMITER, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Use empty_config_schema because the component does not have any config options
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

def setup(hass: HomeAssistant, config: ConfigType) -> bool: # pylint: disable=unused-argument
    """Set up is called when Home Assistant is loading our component."""

    def handle_import_from_file(call: ServiceCall):
        """Handle the service call.

        This method is the only method which needs the hass object, all other methods are independent of it.
        """

        # Get the filename from the call data; done here, because the root path needs the hass object
        file_path = f"{hass.config.config_dir}/{call.data.get(ATTR_FILENAME)}"

        hass.states.set("import_statistics.import_from_file", file_path)

        stats = _prepare_data_to_import(file_path, call)

        for stat in stats.values():
            metadata = stat[0]
            statistics = stat[1]
            _LOGGER.debug(
                "Calling async_import_statistics / async_add_external_statistics with:"
            )
            _LOGGER.debug("Metadata:")
            _LOGGER.debug(metadata)
            _LOGGER.debug("Statistics:")
            _LOGGER.debug(statistics)

            if metadata["source"] == "recorder":
                async_import_statistics(hass, metadata, statistics)
            else:
                async_add_external_statistics(hass, metadata, statistics)

    hass.services.register(DOMAIN, "import_from_file", handle_import_from_file)

    # Return boolean to indicate that initialization was successful.
    return True

def _prepare_data_to_import(file_path: str, call: ServiceCall) -> dict:
    """Prepare data to import statistics from a file.

    Args:
        file_path: Path to the file with the data to be imported.
        call: The call data containing the necessary information.

    Returns:
        A dictionary containing the imported statistics.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If there is an implementation error.

    """
    decimal, timezone_identifier, delimiter = _handle_arguments(file_path, call)

    df = pd.read_csv(file_path, sep=delimiter, decimal=decimal, engine="python")
    stats = _handle_dataframe(df, timezone_identifier)
    return stats

def _handle_arguments(file_path: str, call: ServiceCall) -> tuple:
    """Handle the arguments for importing statistics from a file.

    Args:
        file_path (str): The path of the file to import statistics from.
        call (ServiceCall): The service call object containing additional data.

    Returns:
        tuple: A tuple containing the decimal separator, timezone identifier, and delimiter.

    Raises:
        ValueError: If the timezone identifier is invalid.
        FileNotFoundError: If the file path does not exist.

    """

    if call.data.get(ATTR_DECIMAL, True):
        decimal = ","
    else:
        decimal = "."
    timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER)

    if timezone_identifier not in pytz.all_timezones:
        _handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    delimiter = call.data.get(ATTR_DELIMITER)
    _LOGGER.info("Importing statistics from file: %s", file_path)
    _LOGGER.debug("Timezone_identifier: %s", timezone_identifier)
    _LOGGER.debug("Delimiter: %s", delimiter)
    _LOGGER.debug("Decimal separator: %s", decimal)

    if not os.path.exists(file_path):
        _handle_error(f"path {file_path} does not exist.")
    return decimal,timezone_identifier,delimiter

def _handle_dataframe(df: pd.DataFrame, timezone_identifier: str) -> dict:
    """Process a dataframe and extract statistics based on the specified columns and timezone.

    Args:
        df (pandas.DataFrame): The input dataframe containing the statistics data.
        columns (list): The list of columns to extract from the dataframe.
        timezone_identifier (str): The timezone identifier to convert the timestamps.

    Returns:
        dict: A dictionary containing the extracted statistics, organized by statistic_id.

    Raises:
        ImplementationError: If both 'mean' and 'sum' columns are present in the columns list.

    """
    columns = df.columns
    _LOGGER.debug("Columns:")
    _LOGGER.debug(columns)
    if not _are_columns_valid(columns):
        _handle_error(
            "Implementation error. _are_columns_valid returned false, this should never happen, because _are_columns_valid throws an exception!"
        )
    stats = {}
    timezone = zoneinfo.ZoneInfo(timezone_identifier)
    has_mean = "mean" in columns
    has_sum = "sum" in columns
    for _index, row in df.iterrows():
        statistic_id = row["statistic_id"]
        if statistic_id not in stats: # New statistic id found

            source = _get_source(statistic_id)
            metadata = {
                "has_mean": has_mean,
                "has_sum": has_sum,
                "source": source,
                "statistic_id": statistic_id,
                "name": None,
                "unit_of_measurement": row["unit"],
            }
            stats[statistic_id] = (metadata, [])

        if has_mean:
            new_stat = _get_mean_stat(row, timezone)
        if has_sum:
            new_stat = _get_sum_stat(row, timezone)
        stats[statistic_id][1].append(new_stat)
    return stats

def _get_source(statistic_id: str) -> str:
    """Get the source of a statistic based on the given statistic_id.

    Args:
        statistic_id (str): The ID of the statistic.

    Returns:
        str: The source of the statistic.

    Raises:
        ValueError: If the statistic_id is invalid.

    """
    if valid_entity_id(statistic_id):
        source = statistic_id.split(".")[0]
        if source == "recorder":
            _handle_error(f"Invalid statistic_id {statistic_id}. DOMAIN 'recorder' is not allowed.")
        source = "recorder"
    elif valid_statistic_id(statistic_id):
        source = statistic_id.split(":")[0]
        if len(source) == 0:
            _handle_error(f"Implementation error, this must not happen. Invalid statistic_id. (must not start with ':'): {statistic_id}")
        if source == "recorder":
            _handle_error(f"Invalid statistic_id {statistic_id}. DOMAIN 'recorder' is not allowed.")
    else:
        _handle_error(f"Statistic_id {statistic_id} is invalid. Use either an existing entity ID (containing a '.'), or a statistic id (containing a ':')")

    return source

def _get_mean_stat(row: pd.Series, timezone: zoneinfo.ZoneInfo) -> dict:
    """Process a row and extract mean statistics based on the specified columns and timezone.

    Args:
        row (pandas.Series): The input row containing the statistics data.
        timezone (zoneinfo.ZoneInfo): The timezone to convert the timestamps.

    Returns:
        dict: A dictionary containing the extracted mean statistics.

    """
    if _is_full_hour(row["start"]) and _is_valid_float(row["min"]) and _is_valid_float(row["max"]) and _is_valid_float(row["mean"]):
        if _min_max_mean_are_valid(row["min"], row["max"], row["mean"]):
            return {
                "start": datetime.strptime(row["start"], "%d.%m.%Y %H:%M").replace(tzinfo=timezone),
                "min": row["min"],
                "max": row["max"],
                "mean": row["mean"],
            }
    return { }

def _get_sum_stat(row: pd.Series, timezone: zoneinfo.ZoneInfo) -> dict:
    """Process a row and extract sum statistics based on the specified columns and timezone.

    Args:
        row (pandas.Series): The input row containing the statistics data.
        timezone (zoneinfo.ZoneInfo): The timezone to convert the timestamps.

    Returns:
        dict: A dictionary containing the extracted sum statistics.

    """
    if _is_full_hour(row["start"]) and _is_valid_float(row["sum"]):
        if "state" in row.index:
            if _is_valid_float(row["state"]):
                return {
                    "start": datetime.strptime(row["start"], "%d.%m.%Y %H:%M").replace(tzinfo=timezone),
                    "sum": row["sum"],
                    "state": row["state"],
                }
        else:
            return {
            "start": datetime.strptime(row["start"], "%d.%m.%Y %H:%M").replace(tzinfo=timezone),
            "sum": row["sum"],
        }

    return { }

def _is_full_hour(timestamp_str: str) -> bool:
    """Check if the given timestamp is a full hour.

    Args:
        timestamp_str (str): The timestamp string in the format "%d.%m.%Y %H:%M:%S" or "%d.%m.%Y %H:%M".

    Returns:
        bool: True if the timestamp is a full hour, False is never returned.

    Raises:
        HomeAssistantError: If the timestamp is not a full hour.

    """
    try:
        dt = datetime.strptime(timestamp_str, "%d.%m.%Y %H:%M:%S")
    except ValueError as exc:
        try:
            dt = datetime.strptime(timestamp_str, "%d.%m.%Y %H:%M")
        except ValueError:
            raise HomeAssistantError(f"Invalid timestamp: {timestamp_str}. The timestamp must be in the format '%d.%m.%Y %H:%M' or '%d.%m.%Y %H:%M:%S'.") from exc

    if dt.minute != 0 or dt.second != 0:
        raise HomeAssistantError(f"Invalid timestamp: {timestamp_str}. The timestamp must be a full hour.")

    return True

def _is_valid_float(value: str) -> bool:
    """Check if the given value is a valid float.

    Args:
        value: The value to check.

    Returns:
        bool: True if the value is a valid float, False otherwise.

    """
    try:
        float(value)
        return True
    except ValueError as exc:
        raise HomeAssistantError(f"Invalid float value: {value}. Check the decimal separator.") from exc

def _min_max_mean_are_valid(min_value: str, max_value: str, mean_value: str) -> bool:
    """Check if the given min, max, and mean values are valid.

    Args:
        min_value (float): The minimum value.
        max_value (float): The maximum value.
        mean_value (float): The mean value.

    Returns:
        bool: True if the values are valid, False otherwise.

    """
    if min_value <= mean_value <= max_value:
        return True
    raise HomeAssistantError(f"Invalid values: min: {min_value}, max: {max_value}, mean: {mean_value}, mean must be between min and max.")

def _are_columns_valid(columns: pd.DataFrame.columns) -> bool:
    """Check if the given DataFrame columns meet the required criteria.

    Args:
        columns (pd.DataFrame.columns): The columns of the DataFrame.

    Returns:
        bool: True if the columns meet the required criteria, False otherwise.

    """
    if not ("statistic_id" in columns and "start" in columns and "unit" in columns):
        _handle_error(
            "The file must contain the columns 'statistic_id', 'start' and 'unit' (check delimiter)"
        )
    if not (
        ("mean" in columns and "min" in columns and "max" in columns)
        or ("sum" in columns)
    ):
        _handle_error(
            "The file must contain either the columns 'mean', 'min' and 'max' or the column 'sum' (check delimiter)"
        )
    if ("mean" in columns or "min" in columns or "max" in columns) and "sum" in columns:
        _handle_error(
            "The file must not contain the columns 'sum' and 'mean'/'min'/'max' (check delimiter)"
        )
    return True

def _handle_error(error_string: str) -> None:
    """Handle an error by logging a warning and raising a HomeAssistantError.

    Args:
        error_string (str): The error message.

    Raises:
        HomeAssistantError: The raised exception containing the error message.

    """
    _LOGGER.warning(error_string)
    raise HomeAssistantError(error_string)
