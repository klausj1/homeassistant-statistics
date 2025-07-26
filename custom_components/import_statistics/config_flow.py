"""Handle a config flow initialized from UI."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class ImportStatisticsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the Import Statistics integration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle a config flow initialized from UI."""
        if user_input is not None:
            return self.async_create_entry(title="Import Statistics", data={})

        return self.async_show_form(step_id="user")

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a config flow from configuration.yaml."""
        return await self.async_step_user(import_data)
