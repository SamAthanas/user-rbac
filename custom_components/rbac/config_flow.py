"""Config flow for RBAC integration."""
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

class RBACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RBAC."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(
                title="RBAC Middleware", 
                data={},
                options={
                    "show_sidebar_panel": user_input.get("show_sidebar_panel", True),
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional("show_sidebar_panel", default=True): cv.boolean,
            })
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return RBACOptionsFlow(config_entry)


class RBACOptionsFlow(config_entries.OptionsFlow):
    """Handle RBAC options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize RBAC options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, any] | None = None
    ) -> FlowResult:
        """Manage the RBAC options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "show_sidebar_panel",
                    default=self.config_entry.options.get("show_sidebar_panel", True)
                ): cv.boolean,
            })
        )