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
    """
    Set up the import_statistics component when Home Assistant is loading it.

    The setup function is called when Home Assistant loads the import_statistics custom component.
    It registers three services under the component's domain: import_from_file, import_from_json,
    and export_statistics. These services enable users to programmatically import historical statistics
    into Home Assistant's recorder database or export existing statistics to files.
    It should setup all necessary services and return True if the component
    has been successfully initialized.

    The setup function is primarily called during testing to initialize the component in a mock
    Home Assistant environment. Test cases use it to verify that the registered services behave
    correctly when invoked.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config (ConfigType): The configuration of the component.

    Returns:
        bool: True if the component has been successfully initialized, False otherwise.

    """

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
