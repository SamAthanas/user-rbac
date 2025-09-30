"""Config flow for RBAC integration."""
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

class RBACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RBAC."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return self.async_create_entry(title="RBAC Middleware", data={})
