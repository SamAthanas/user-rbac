"""RBAC Sensor Platform."""
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RBACBaseSensor(SensorEntity):
    """Base class for RBAC sensors."""
    
    def __init__(self, hass, device_id=None):
        """Initialize the sensor."""
        self._hass = hass
        self._device_id = device_id
        
    @property
    def device_info(self):
        """Return device info."""
        if self._device_id:
            return {
                "identifiers": {(DOMAIN, "rbac_middleware")},
                "name": "RBAC Middleware",
            }
        return None


class RBACConfigURLSensor(RBACBaseSensor):
    """RBAC Configuration URL Sensor."""
    
    def __init__(self, hass, device_id=None):
        """Initialize the sensor."""
        super().__init__(hass, device_id)
        self._attr_name = "RBAC Configuration URL"
        self._attr_unique_id = f"{DOMAIN}_config_url"
        self._attr_device_class = "url"
        self._attr_icon = "mdi:web"
        
    @property
    def state(self):
        """Return the state of the sensor."""
        base_url = self._hass.config.external_url or self._hass.config.internal_url
        if not base_url:
            base_url = f"http://{self._hass.config.api.host}:{self._hass.config.api.port}"
        return f"{base_url}/local/community/rbac/config.html"


class RBACEnabledSensor(RBACBaseSensor):
    """RBAC Enabled Status Sensor."""
    
    def __init__(self, hass, device_id=None):
        """Initialize the sensor."""
        super().__init__(hass, device_id)
        self._attr_name = "RBAC Enabled"
        self._attr_unique_id = f"{DOMAIN}_enabled"
        self._attr_icon = "mdi:shield-check"
        
    @property
    def state(self):
        """Return the state of the sensor."""
        access_config = self._hass.data.get(DOMAIN, {}).get("access_config", {})
        enabled = access_config.get("enabled", True)
        self._attr_icon = "mdi:shield-check" if enabled else "mdi:shield-off"
        return "on" if enabled else "off"


class RBACShowNotificationsSensor(RBACBaseSensor):
    """RBAC Show Notifications Sensor."""
    
    def __init__(self, hass, device_id=None):
        """Initialize the sensor."""
        super().__init__(hass, device_id)
        self._attr_name = "RBAC Show Notifications"
        self._attr_unique_id = f"{DOMAIN}_show_notifications"
        self._attr_icon = "mdi:bell"
        
    @property
    def state(self):
        """Return the state of the sensor."""
        access_config = self._hass.data.get(DOMAIN, {}).get("access_config", {})
        show_notifications = access_config.get("show_notifications", True)
        self._attr_icon = "mdi:bell" if show_notifications else "mdi:bell-off"
        return "on" if show_notifications else "off"


class RBACSendEventsSensor(RBACBaseSensor):
    """RBAC Send Events Sensor."""
    
    def __init__(self, hass, device_id=None):
        """Initialize the sensor."""
        super().__init__(hass, device_id)
        self._attr_name = "RBAC Send Events"
        self._attr_unique_id = f"{DOMAIN}_send_events"
        self._attr_icon = "mdi:send"
        
    @property
    def state(self):
        """Return the state of the sensor."""
        access_config = self._hass.data.get(DOMAIN, {}).get("access_config", {})
        send_event = access_config.get("send_event", True)
        self._attr_icon = "mdi:send" if send_event else "mdi:send-lock"
        return "on" if send_event else "off"


class RBACLastRejectionSensor(RBACBaseSensor):
    """RBAC Last Rejection Sensor."""
    
    def __init__(self, hass, device_id=None):
        """Initialize the sensor."""
        super().__init__(hass, device_id)
        self._attr_name = "RBAC Last Rejection"
        self._attr_unique_id = f"{DOMAIN}_last_rejection"
        self._attr_icon = "mdi:clock-alert"
        
    @property
    def state(self):
        """Return the state of the sensor."""
        access_config = self._hass.data.get(DOMAIN, {}).get("access_config", {})
        return access_config.get("last_rejection", "Never")


class RBACLastUserRejectedSensor(RBACBaseSensor):
    """RBAC Last User Rejected Sensor."""
    
    def __init__(self, hass, device_id=None):
        """Initialize the sensor."""
        super().__init__(hass, device_id)
        self._attr_name = "RBAC Last User Rejected"
        self._attr_unique_id = f"{DOMAIN}_last_user_rejected"
        self._attr_icon = "mdi:account-alert"
        
    @property
    def state(self):
        """Return the state of the sensor."""
        access_config = self._hass.data.get(DOMAIN, {}).get("access_config", {})
        return access_config.get("last_user_rejected", "None")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the RBAC sensor platform from a config entry."""
    _LOGGER.info("Setting up RBAC sensor platform from config entry")
    
    # Get device ID from hass.data
    device_id = hass.data.get(DOMAIN, {}).get("device_id")
    
    # Create all sensors
    sensors = [
        RBACConfigURLSensor(hass, device_id),
        RBACEnabledSensor(hass, device_id),
        RBACShowNotificationsSensor(hass, device_id),
        RBACSendEventsSensor(hass, device_id),
        RBACLastRejectionSensor(hass, device_id),
        RBACLastUserRejectedSensor(hass, device_id),
    ]
    
    async_add_entities(sensors, True)
    _LOGGER.info(f"Added {len(sensors)} RBAC sensors")
