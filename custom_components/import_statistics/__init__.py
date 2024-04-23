"""The import_statistics integration."""

from datetime import datetime
import os
import time
import zoneinfo

import pandas as pd

from homeassistant.components.recorder.history import state_changes_during_period
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
)
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from custom_components.import_statistics.helpers import _LOGGER
import custom_components.import_statistics.prepare_data as prepare_data
from custom_components.import_statistics.const import ATTR_FILENAME, DOMAIN

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

# This can be used to check if an entity exists
        entity_id = "sensor.sun_solar_azimuth"
        x: hass.State

        x = hass.states.get(entity_id)
        _LOGGER.debug(f"State of {entity_id}: {x}")
        if x is not None:
            _LOGGER.debug("x != None")
        _LOGGER.debug(f"State of {entity_id}: {x.state}")
        _LOGGER.debug(f"Unit of {entity_id}: {x.attributes['unit_of_measurement']}")

        datetime_str = '09/19/22 13:55:26'

        datetime_object = datetime.strptime(datetime_str, '%m/%d/%y %H:%M:%S').replace(tzinfo=zoneinfo.ZoneInfo("Europe/Vienna"))

# This can be used to get the first value of an entity in the history
        _LOGGER.debug("Start query")
        z = hass.components.recorder.get_instance(hass).async_add_executor_job(state_changes_during_period, hass, datetime_object, None, entity_id, False, False, 1)
        # z is a future
        while not z.done():
            time.sleep(0.001)
        _LOGGER.debug(f"History of {entity_id}: {z.result()}")

        stats = prepare_data.prepare_data_to_import(file_path, call)

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
