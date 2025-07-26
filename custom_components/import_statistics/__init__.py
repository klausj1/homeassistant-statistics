"""The import_statistics integration."""

from typing import Any

from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from custom_components.import_statistics import helpers, prepare_data
from custom_components.import_statistics.const import ATTR_FILENAME, DOMAIN
from custom_components.import_statistics.helpers import _LOGGER

# Use empty_config_schema because the component does not have any config options
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:  # pylint: disable=unused-argument  # noqa: ARG001
    """Set up is called when Home Assistant is loading our component."""

    def handle_import_from_file(call: ServiceCall) -> None:
        """
        Handle the service call.

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
            _LOGGER.debug("Calling async_import_statistics / async_add_external_statistics with:")
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # pylint: disable=unused-argument  # noqa: ARG001
    """Set up the device based on a config entry."""
    return True


def check_all_entities_exists(hass: HomeAssistant, stats: dict) -> None:
    """
    Check all entities in stats if they exist.

    Args:
    ----
        hass: home assistant
        stats: dictionary with all statistic data

    Returns:
    -------
        n/a

    Raises:
    ------
        n/a

    """
    for stat in stats.values():
        metadata = stat[0]

        if metadata["source"] == "recorder":
            check_entity_exists(hass, metadata["statistic_id"])


def check_entity_exists(hass: HomeAssistant, entity_id: Any) -> bool:
    """
    Check if a specific entity exists.

    Args:
    ----
        hass: home assistant
        entity_id: id to check for existence

    Returns:
    -------
        bool: True if entity exists, otherwise exception is thrown

    Raises:
    ------
        HomeAssistantError: If entity does not exist

    """
    entity_exists = hass.states.get(entity_id) is not None

    if not entity_exists:
        helpers.handle_error(f"Entity does not exist: '{entity_id}'")
        return False

    return True


def add_unit_for_all_entities(hass: HomeAssistant, stats: dict) -> None:
    """
    Add units for all rows to be imported.

    Args:
    ----
        hass: home assistant
        stats: dictionary with all statistic data

    Returns:
    -------
        n/a

    Raises:
    ------
        n/a

    """
    for stat in stats.values():
        metadata = stat[0]

        if metadata["source"] == "recorder":
            add_unit_for_entity(hass, metadata)


def add_unit_for_entity(hass: HomeAssistant, metadata: dict) -> None:
    """
    Add units for one rows to be imported.

    Args:
    ----
        hass: home assistant
        entity_id: id to check for existence
        metadata: metadata of row to be imported

    Returns:
    -------
        n/a

    Raises:
    ------
        HomeAssistantError: If entity does not exist

    """
    entity_id = metadata["statistic_id"]
    entity = hass.states.get(entity_id)

    if entity is None:
        helpers.handle_error(f"Entity does not exist: '{entity_id}'")
    elif metadata["unit_of_measurement"] == "":
        metadata["unit_of_measurement"] = entity.attributes["unit_of_measurement"]
        _LOGGER.debug(
            "Adding unit '%s' for entity_id: %s",
            metadata["unit_of_measurement"],
            entity_id,
        )
