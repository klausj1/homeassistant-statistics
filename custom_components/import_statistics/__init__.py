"""The import_statistics integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from custom_components.import_statistics.const import DOMAIN
from custom_components.import_statistics.export_service import handle_export_statistics_impl
from custom_components.import_statistics.import_service import handle_import_from_file_impl, handle_import_from_json_impl

# Use empty_config_schema because the component does not have any config options
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:  # pylint: disable=unused-argument  # noqa: ARG001
    """Set up is called when Home Assistant is loading our component."""

    async def handle_import_from_file(call: ServiceCall) -> None:
        """Handle the service call."""
        await handle_import_from_file_impl(hass, call)

    hass.services.register(DOMAIN, "import_from_file", handle_import_from_file)

    async def handle_import_from_json(call: ServiceCall) -> None:
        """Handle the json service call."""
        await handle_import_from_json_impl(hass, call)

    hass.services.register(DOMAIN, "import_from_json", handle_import_from_json)

    async def handle_export_statistics(call: ServiceCall) -> None:
        """Handle the export statistics service call."""
        await handle_export_statistics_impl(hass, call)

    hass.services.register(DOMAIN, "export_statistics", handle_export_statistics)

    # Return boolean to indicate that initialization was successful.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # pylint: disable=unused-argument  # noqa: ARG001
    """Set up the device based on a config entry."""
    return True
