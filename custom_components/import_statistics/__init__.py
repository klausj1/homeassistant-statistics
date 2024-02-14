"""The import_statistics integration."""

# import csv
from datetime import datetime
import logging
import os
import zoneinfo

import pandas as pd

# from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
    valid_statistic_id,
)
from homeassistant.core import HomeAssistant, valid_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "import_statistics"
_LOGGER = logging.getLogger(__name__)

# Use empty_config_schema because the component does not have any config options
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

ATTR_FILENAME = "filename"
ATTR_TIMEZONE_IDENTIFIER = "timezone_identifier"
ATTR_DELIMITER = "delimiter"
ATTR_DECIMAL = "decimal"


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up is called when Home Assistant is loading our component."""

    def handle_import_from_file(call):
        """Handle the service call."""
        filename = call.data.get(ATTR_FILENAME)
        if call.data.get(ATTR_DECIMAL, True):
            decimal = ","
        else:
            decimal = "."
        timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER)
        delimiter = call.data.get(ATTR_DELIMITER)
        _LOGGER.info(f"Importing statistics from file: {filename}")  # noqa: G004
        _LOGGER.debug(f"Timezone_identifier: {timezone_identifier}")  # noqa: G004
        _LOGGER.debug(f"Delimiter: {delimiter}")  # noqa: G004
        _LOGGER.debug(f"Decimal separator: {decimal}")  # noqa: G004

        hass.states.set("import_statistics.import_from_file", filename)

        file_path = f"{hass.config.config_dir}/{filename}"

        if not os.path.exists(file_path):
            _handle_error(f"path {file_path} does not exist.")

        with open(file_path, encoding="UTF-8") as csvfile:
            df = pd.read_csv(csvfile, sep=delimiter, decimal=decimal, engine="python")
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


def _check_columns(columns: pd.DataFrame.columns) -> bool:
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
