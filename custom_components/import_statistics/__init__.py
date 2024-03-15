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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
import pytz
from custom_components.import_statistics.const import ATTR_FILENAME, ATTR_DECIMAL, ATTR_TIMEZONE_IDENTIFIER, ATTR_DELIMITER, DOMAIN

from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

# Use empty_config_schema because the component does not have any config options
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up is called when Home Assistant is loading our component."""

    def handle_import_from_file(call):
        """
        Handle the service call.
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

            if valid_entity_id(metadata["statistic_id"]):
                async_import_statistics(hass, metadata, statistics)
            elif valid_statistic_id(metadata["statistic_id"]):
                async_add_external_statistics(hass, metadata, statistics)
            else:
                _handle_error(
                    f"statistic_id {metadata['statistic_id']} is valid. Use either an existing entity ID, or a statistic id (containing a ':')"
                )

    hass.services.register(DOMAIN, "import_from_file", handle_import_from_file)

    # Return boolean to indicate that initialization was successful.
    return True

def _prepare_data_to_import(file_path: str, call) -> dict:
    """
    Prepare data to import statistics from a file.

    Args:
        hass: The Home Assistant object.
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

def _handle_arguments(file_path: str, call):

    if call.data.get(ATTR_DECIMAL, True):
        decimal = ","
    else:
        decimal = "."
    timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER)

    if not timezone_identifier in pytz.all_timezones:
        _handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    delimiter = call.data.get(ATTR_DELIMITER)
    _LOGGER.info("Importing statistics from file: %s", file_path)
    _LOGGER.debug("Timezone_identifier: %s", timezone_identifier)
    _LOGGER.debug("Delimiter: %s", delimiter)
    _LOGGER.debug("Decimal separator: %s", decimal)

    if not os.path.exists(file_path):
        _handle_error(f"path {file_path} does not exist.")
    return decimal,timezone_identifier,delimiter

def _handle_dataframe(df, timezone_identifier):
    """
    Process a dataframe and extract statistics based on the specified columns and timezone.

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
    if not _check_columns(columns):
        _handle_error(
            "Implementation error. _check_columns returned false, this should never happen!"
        )
    stats = {}
    timezone = zoneinfo.ZoneInfo(timezone_identifier)
    has_mean = "mean" in columns
    has_sum = "sum" in columns
    if has_mean and has_sum:
        _handle_error(
            "Implementation error. has_mean and has_sum are both true, this should never happen!"
        )
    for _index, row in df.iterrows():
        statistic_id = row["statistic_id"]
        if statistic_id not in stats:
            if "." in statistic_id:
                source = "recorder"
            elif ":" in statistic_id:
                source = statistic_id.split(".")[0]
            else:
                _handle_error(f"invalid statistic_id (must contain either '.' or ':'): {statistic_id}")
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
            new_stat = {
                "start": datetime.strptime(
                    row["start"], "%d.%m.%Y %H:%M"
                ).replace(tzinfo=timezone),
                "min": row["min"],
                "max": row["max"],
                "mean": row["mean"],
            }
        else:
            new_stat = {
                "start": datetime.strptime(
                    row["start"], "%d.%m.%Y %H:%M"
                ).replace(tzinfo=timezone),
                "sum": row["sum"],
                "state": row["state"],
            }
        stats[statistic_id][1].append(new_stat)
    return stats

def _check_columns(columns: pd.DataFrame.columns) -> bool:
    """
    Check if the given DataFrame columns meet the required criteria.

    Args:
        columns (pd.DataFrame.columns): The columns of the DataFrame.

    Returns:
        bool: True if the columns meet the required criteria, False otherwise.
    """
    if not ("statistic_id" in columns and "start" in columns and "unit" in columns):
        _handle_error(
            "The file must contain the columns 'statistic_id', 'start' and 'unit'"
        )
    if not (
        ("mean" in columns and "min" in columns and "max" in columns)
        or ("sum" in columns)
    ):
        _handle_error(
            "The file must contain either the columns 'mean', 'min' and 'max' or the column 'sum'"
        )
    if ("mean" in columns or "min" in columns or "max" in columns) and "sum" in columns:
        _handle_error(
            "The file must not contain the columns 'sum' and 'mean'/'min'/'max'"
        )
    return True

def _handle_error(error_string):
    _LOGGER.warning(error_string)
    raise HomeAssistantError(error_string)
