"""The import_statistics integration."""

from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
)
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from custom_components.import_statistics.helpers import _LOGGER
import custom_components.import_statistics.helpers as helpers
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
        _LOGGER.info("Service handle_import_from_file called")
        file_path = f"{hass.config.config_dir}/{call.data.get(ATTR_FILENAME)}"

        hass.states.set("import_statistics.import_from_file", file_path)

        _LOGGER.info("Peparing data for import")
        stats, unit_from_entity = prepare_data.prepare_data_to_import(file_path, call)

        _LOGGER.info("Checking if all entities exist")
        check_all_entities_exists(hass, stats)

        if unit_from_entity:
            _LOGGER.info("Adding units from entities")
            add_unit_for_all_entities(hass, stats)

        _LOGGER.info("Calling hass import methods")
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
                if check_entity_exists(hass, metadata["statistic_id"]):
                    async_import_statistics(hass, metadata, statistics)
            else:
                async_add_external_statistics(hass, metadata, statistics)

        _LOGGER.info("Finished importing data")

    hass.services.register(DOMAIN, "import_from_file", handle_import_from_file)

    # Return boolean to indicate that initialization was successful.
    return True

def check_all_entities_exists(hass: HomeAssistant, stats: dict) -> None:
    """Check all entities in stats if they exist.

    Args:
        hass: home assistant
        stats: dictionary with all statistic data

    Returns:
        n/a

    Raises:
        n/a

    """

    for stat in stats.values():
        metadata = stat[0]

        if metadata["source"] == "recorder":
            check_entity_exists(hass, metadata["statistic_id"])

def check_entity_exists(hass: HomeAssistant, entity_id) -> bool:
    """Check if a specific entity exists.

    Args:
        hass: home assistant
        entity_id: id to check for existence

    Returns:
        bool: True if entity exists, otherwise exception is thrown

    Raises:
        HomeAssistantError: If entity does not exist

    """

    entity_exists = hass.states.get(entity_id) is not None

    if not entity_exists:
        helpers.handle_error(f"Entity does not exist: '{entity_id}'")
        return False

    return True

def add_unit_for_all_entities(hass: HomeAssistant, stats: dict) -> None:
    """Add units for all rows to be imported.

    Args:
        hass: home assistant
        stats: dictionary with all statistic data

    Returns:
        n/a

    Raises:
        n/a

    """

    for stat in stats.values():
        metadata = stat[0]

        # _LOGGER.debug("Metadata all start %s", metadata)
        if metadata["source"] == "recorder":
            add_unit_for_entity(hass, metadata)
        # _LOGGER.debug("Metadata all end %s", metadata)

def add_unit_for_entity(hass: HomeAssistant, metadata: dict) -> None:
    """Add units for one rows to be imported.

    Args:
        hass: home assistant
        entity_id: id to check for existence
        metadata: metadata of row to be imported

    Returns:
        n/a

    Raises:
        HomeAssistantError: If entity does not exist

    """

    # _LOGGER.debug("Metadata one start %s", metadata)

    entity_id = metadata["statistic_id"]
    entity = hass.states.get(entity_id)

    if entity is None:
        helpers.handle_error(f"Entity does not exist: '{entity_id}'")

    if metadata["unit_of_measurement"] == "":

        metadata["unit_of_measurement"] = entity.attributes["unit_of_measurement"]
        _LOGGER.debug("Adding unit '%s' for entity_id: %s", metadata["unit_of_measurement"], entity_id)

    # _LOGGER.debug("Metadata one end %s", metadata)

# This can be used to get the first value of an entity in the history
    # _LOGGER.debug("Start query")
    # z = hass.components.recorder.get_instance(hass).async_add_executor_job(state_changes_during_period, hass, datetime_object, None, entity_id, False, False, 1)
    # # z is a future
    # while not z.done():
    #     time.sleep(0.001)
    # _LOGGER.debug(f"History of {entity_id}: {z.result()}")
