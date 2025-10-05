"""RBAC Middleware for Home Assistant."""
import logging
import os
from typing import Any, Dict, Optional
from datetime import datetime

import yaml
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import Platform
from homeassistant.helpers.template import Template
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rbac"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


class RBACConfigURLSensor(SensorEntity):
    """Sensor for RBAC configuration URL."""
    
    def __init__(self, base_url: str = ""):
        """Initialize the sensor."""
        self._attr_name = "RBAC Configuration URL"
        self._attr_unique_id = f"{DOMAIN}_config_url"
        self._attr_icon = "mdi:web"
        self._attr_device_class = "url"
        self._attr_native_value = f"{base_url}/api/rbac/static/config.html" if base_url else "/api/rbac/static/config.html"


async def _load_access_control_config(hass: HomeAssistant) -> Dict[str, Any]:
    """Load access control configuration from YAML file."""
    config_path = os.path.join(hass.config.config_dir, "custom_components", "rbac", "access_control.yaml")
    
    def _load_file():
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            _LOGGER.info(f"Access control configuration not found at {config_path}, creating default configuration")
            # Create default configuration
            default_config = {
                "version": "2.0",
                "description": "RBAC Access Control Configuration",
                "enabled": True,
                "show_notifications": True,
                "send_event": False,
                "frontend_blocking_enabled": False,
                "log_deny_list": False,
                "allow_chained_actions": False,
                "last_rejection": "Never",
                "last_user_rejected": "None",
                "default_restrictions": {
                    "domains": {
                        "homeassistant": {
                            "hide": False,
                            "services": ["restart", "stop", "reload_config_entry", "check_config"]
                        },
                        "system_log": {
                            "hide": True,
                            "services": ["write", "clear"]
                        },
                        "hassio": {
                            "hide": True,
                            "services": ["host_reboot", "host_shutdown", "supervisor_update", "supervisor_restart"]
                        }
                    },
                    "entities": {}
                },
                "users": {},
                "roles": {
                    "admin": {"description": "Administrator with most permissions"},
                    "user": {"description": "Standard user with limited permissions"},
                    "guest": {"description": "Guest with minimal permissions"}
                }
            }
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            # Write default configuration
            with open(config_path, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False, indent=2, sort_keys=False)
            
            _LOGGER.info(f"Created default access control configuration at {config_path}")
            return default_config
        except yaml.YAMLError as e:
            _LOGGER.error(f"Invalid YAML in access control configuration: {e}")
            return {"default_access": "allow", "users": {}}
        except Exception as e:
            _LOGGER.error(f"Error loading access control configuration: {e}")
            return {"default_access": "allow", "users": {}}
    
    # Run file I/O in executor to avoid blocking the event loop
    config = await hass.async_add_executor_job(_load_file)
    _LOGGER.info(f"Loaded access control configuration from {config_path}")
    return config


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the RBAC middleware component from configuration.yaml."""
    _LOGGER.info("Setting up RBAC Middleware from configuration.yaml")
    
    # Load access control configuration
    access_config = await _load_access_control_config(hass)
    
    # Initialize component data
    hass.data[DOMAIN] = {
        "access_config": access_config,
        "original_async_call": None
    }
    
    # Store original async_call method
    hass.data[DOMAIN]["original_async_call"] = hass.services.async_call
    
    # Patch the service call method using a different approach
    # We'll intercept at the service registration level instead
    _patch_service_registry(hass)
    
    # Set up services
    from . import services
    await services.async_setup_services(hass)
    
    # Set up static file serving
    await services.async_setup_static_routes(hass)
    
    # Create RBAC device with config URL entity
    # Skip device setup for YAML-only setup (no config entry)
    _LOGGER.info("Skipping device setup for YAML-only configuration")
    
    user_count = len(access_config.get("users", {}))
    _LOGGER.info(f"RBAC Middleware initialized successfully with {user_count} configured users")
    # Register API endpoints
    from .services import RBACConfigView, RBACUsersView, RBACDomainsView, RBACEntitiesView, RBACServicesView, RBACCurrentUserView, RBACSensorsView, RBACDenyLogView, RBACTemplateEvaluateView, RBACFrontendBlockingView, RBACYamlEditorView
    
    hass.http.register_view(RBACConfigView())
    hass.http.register_view(RBACUsersView())
    hass.http.register_view(RBACDomainsView())
    hass.http.register_view(RBACEntitiesView())
    hass.http.register_view(RBACServicesView())
    hass.http.register_view(RBACCurrentUserView())
    hass.http.register_view(RBACSensorsView())
    hass.http.register_view(RBACDenyLogView())
    hass.http.register_view(RBACTemplateEvaluateView())
    hass.http.register_view(RBACFrontendBlockingView())
    hass.http.register_view(RBACYamlEditorView())
    
    _LOGGER.info("Registered RBAC API endpoints")
    
    # Register sidebar panel (check if we have a config entry with options)
    await _register_sidebar_panel(hass)
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up the RBAC middleware component from a config entry."""
    _LOGGER.info("Setting up RBAC Middleware from config entry")
    
    # Get config data from the entry
    config_data = entry.data if entry.data else {}
    
    # Set up the RBAC device with config entry
    await _setup_rbac_device(hass, entry)
    
    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    # Just call the main setup function with the config data
    return await async_setup(hass, config_data)


async def async_update_options(hass: HomeAssistant, entry) -> None:
    """Update options."""
    _LOGGER.info("RBAC options updated")
    
    # Handle sidebar panel visibility changes
    should_show_panel = entry.options.get("show_sidebar_panel", True)
    
    if should_show_panel:
        # Register the panel if it should be shown
        await _register_sidebar_panel(hass)
    else:
        # Remove the panel if it should be hidden
        try:
            from homeassistant.components.frontend import async_remove_panel
            await async_remove_panel(hass, "rbac-config")
            _LOGGER.info("RBAC sidebar panel removed due to option change")
        except Exception as e:
            _LOGGER.debug(f"Could not remove RBAC sidebar panel: {e}")


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload RBAC config entry."""
    _LOGGER.info("Unloading RBAC Middleware")
    
    # Unregister the sidebar panel
    try:
        from homeassistant.components.frontend import async_remove_panel
        await async_remove_panel(hass, "rbac-config")
        _LOGGER.info("Successfully removed RBAC sidebar panel")
    except Exception as e:
        _LOGGER.debug(f"Could not remove RBAC sidebar panel: {e}")
    
    # Unload sensor platform
    try:
        await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    except Exception as e:
        _LOGGER.debug(f"Could not unload sensor platform: {e}")
    
    return True


async def _setup_rbac_device(hass: HomeAssistant, config_entry):
    """Set up RBAC device and sensors."""
    _LOGGER.info("Setting up RBAC device and sensors...")
    
    try:
        # Import the proper helpers
        from homeassistant.helpers import device_registry as dr, entity_registry as er
        
        # Create device linked to config entry
        device_reg = dr.async_get(hass)
        device = device_reg.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, "rbac_middleware")},
            name="RBAC Middleware",
            manufacturer="Home Assistant",
            model="RBAC Integration",
            sw_version="1.0.0",
        )
        
        # Store device ID for sensor platform to use
        hass.data[DOMAIN]["device_id"] = device.id
        
        # Load the sensor platform
        from homeassistant.config_entries import ConfigEntry
        await hass.config_entries.async_forward_entry_setups(config_entry, ["sensor"])
        
        _LOGGER.info(f"Created RBAC device {device.id} and loaded sensor platform")
        
    except Exception as e:
        _LOGGER.warning(f"Could not create device/sensors properly: {e}")


def _patch_service_registry(hass: HomeAssistant):
    """Patch the service registry to intercept service calls."""
    # Store the original service registry
    original_registry = hass.services
    
    # Create a custom service registry that wraps the original
    class RestrictedServiceRegistry:
        def __init__(self, original_registry, hass):
            self._original = original_registry
            self._hass = hass
            
        def __getattr__(self, name):
            # Delegate all other attributes to the original registry
            return getattr(self._original, name)
            
        async def async_call(self, domain, service, service_data=None, blocking=False, context=None, **kwargs):
            """Intercept service calls for RBAC enforcement."""
            try:
                # Check if this is a chained action from an allowed script/automation
                access_config = self._hass.data.get(DOMAIN, {}).get("access_config", {})
                allow_chained_actions = access_config.get("allow_chained_actions", False)
                
                # If chained actions are enabled, check if this call is from within an allowed script/automation context
                if allow_chained_actions and context:
                    # Initialize allowed_contexts if it doesn't exist
                    if 'allowed_contexts' not in self._hass.data[DOMAIN]:
                        self._hass.data[DOMAIN]['allowed_contexts'] = set()
                    
                    allowed_contexts = self._hass.data[DOMAIN]['allowed_contexts']
                    
                    # Check if this context or its parent context is in the allowed set
                    context_chain = []
                    if hasattr(context, 'id') and context.id:
                        context_chain.append(context.id)
                    if hasattr(context, 'parent_id') and context.parent_id:
                        context_chain.append(context.parent_id)
                    
                    # Check if any context in the chain is allowed
                    for ctx_id in context_chain:
                        if ctx_id in allowed_contexts:
                            _LOGGER.debug(f"Allowing chained action {domain}.{service} from allowed context {ctx_id}")
                            return await self._original.async_call(domain, service, service_data, blocking, context, **kwargs)
                
                # Skip RBAC enforcement for certain domains that are needed for API functionality
                excluded_domains = ['http', 'auth', 'system_log', 'persistent_notification']
                if domain in excluded_domains:
                    _LOGGER.warning(f"Skipping RBAC enforcement for {domain}.{service} (excluded domain)")
                    return await self._original.async_call(domain, service, service_data, blocking, context, **kwargs)
                
                # Get user information
                user = None
                user_id = None
                
                # Try to get user from context first
                if context and hasattr(context, 'user_id') and context.user_id:
                    user = await self._hass.auth.async_get_user(context.user_id)
                    user_id = context.user_id
                    _LOGGER.warning(f"Got user from context: {user_id} ({user.name if user else 'Unknown'})")
                else:
                    # If no direct user_id, this is likely an automation/script call
                    # These should be allowed to proceed without RBAC restrictions
                    user_id = None
                
                # Skip RBAC enforcement for Home Assistant built-in users
                if user_id and _is_builtin_ha_user(user_id, self._hass):
                    _LOGGER.warning(f"Skipping RBAC enforcement for built-in HA user: {user_id} ({user.name if user else 'Unknown'})")
                    return await self._original.async_call(domain, service, service_data, blocking, context, **kwargs)
                
                # Log the service call attempt
                user_name = user.name if user else "Unknown"
                _LOGGER.warning(f"RBAC checking service call: {domain}.{service} by {user_name} (user_id: {user_id})")
                
                # If no user context, allow the call to proceed (likely from automation/script)
                if not user_id or user_id == "null" or user_id is None:
                    _LOGGER.debug(f"No user context for {domain}.{service} - allowing call to proceed (likely automation/script)")
                    return await self._original.async_call(domain, service, service_data, blocking, context, **kwargs)
                
                # Get access config
                access_config = self._hass.data[DOMAIN]["access_config"]
                
                # Check if RBAC is enabled
                rbac_enabled = access_config.get("enabled", True)
                
                if not rbac_enabled:
                    _LOGGER.warning(f"RBAC is disabled - allowing all service calls")
                    return await self._original.async_call(domain, service, service_data, blocking, context, **kwargs)
                
                # RBAC is enabled, enforce restrictions
                if rbac_enabled:
                    # Debug: Log the access config structure
                    _LOGGER.warning(f"Access config for {user_name}: {access_config}")
                    
                    # Check access permissions with detailed logging
                    access_result, reason = _check_service_access_with_reason(domain, service, service_data, user_id, access_config, self._hass)
                    
                    # Debug logging for access result (only for denied calls with entity_id)
                    if not access_result and service_data and "entity_id" in service_data:
                        _LOGGER.warning(f"Access check result for {user_name}: {access_result}, reason: {reason}")
                        _LOGGER.warning(f"Service data: {service_data}")
                    
                    if not access_result:
                        # Only create notifications for service calls with entity_id
                        # Skip notifications for automation/system calls without entity_id
                        if service_data and "entity_id" in service_data:
                            # Get user role for the message
                            user_role = "unknown"
                            if user_id:
                                users = access_config.get("users", {})
                                user_config = users.get(user_id)
                                if user_config:
                                    user_role = user_config.get("role", "unknown")
                            
                            _LOGGER.warning(
                                f"Access denied: {user_name} cannot call {domain}.{service} from role '{user_role}' - {reason}"
                            )
                        else:
                            # Log the denial but don't create notifications for calls without entity_id
                            _LOGGER.debug(f"Access denied for {user_name} calling {domain}.{service} (no entity_id) - {reason}")
                        
                        # Only create notifications, sensors, and events for service calls with entity_id
                        if service_data and "entity_id" in service_data:
                            # Update rejection sensors
                            try:
                                from .services import _update_rejection_sensors
                                _update_rejection_sensors(hass, user_id, f"{domain}.{service}")
                            except Exception as e:
                                _LOGGER.error(f"Error updating rejection sensors: {e}")
                            
                            # Create persistent notification if enabled
                            if access_config.get("show_notifications", True):
                                try:
                                    # Use the service call approach which is more reliable
                                    # Call the original service registry to avoid recursion
                                    await self._original.async_call(
                                        "persistent_notification",
                                        "create",
                                        {
                                            "message": f"Access denied: {user_name} cannot call {domain}.{service} from role '{user_role}'",
                                            "title": "RBAC Access Denied",
                                            "notification_id": f"rbac_denied_{domain}_{service}"
                                        }
                                    )
                                except Exception as e:
                                    _LOGGER.error(f"Failed to create notification: {e}")
                                    _LOGGER.debug(f"Notification error details: {e}", exc_info=True)
                            
                            # Send event if enabled
                            if access_config.get("send_event", False):
                                try:
                                    event_data = {
                                        "user_id": user_id,
                                        "user_name": user_name,
                                        "domain": domain,
                                        "service": service,
                                        "service_data": service_data,
                                        "reason": reason
                                    }
                                    self._hass.bus.async_fire("rbac_access_denied", event_data)
                                    _LOGGER.debug(f"Fired rbac_access_denied event: {event_data}")
                                except Exception as e:
                                    _LOGGER.error(f"Failed to send event: {e}")
                        
                        # Always raise exception to block the call, regardless of entity_id
                        user_role = "unknown"
                        if user_id:
                            users = access_config.get("users", {})
                            user_config = users.get(user_id)
                            if user_config:
                                user_role = user_config.get("role", "unknown")
                        
                        # Log denial to file if logging is enabled
                        if access_config.get("log_deny_list", False):
                            try:
                                _log_denial_to_file(self._hass, user_id or "unknown", user_name, user_role, domain, service, reason)
                            except Exception as log_error:
                                _LOGGER.error(f"Failed to log denial: {log_error}")
                        
                        raise HomeAssistantError(
                            f"Access denied: {user_name} cannot call {domain}.{service} from role '{user_role}' - {reason}"
                        )
                
                # Service is allowed, proceed with original call
                if rbac_enabled:
                    _LOGGER.debug(f"Service call allowed: {domain}.{service} by {user_name}")
                else:
                    _LOGGER.debug(f"Service call allowed (blocking disabled): {domain}.{service} by {user_name}")
                
                # Track allowed script/automation contexts for chained actions
                context_id_added = None
                if allow_chained_actions and context and (domain == 'script' or domain == 'automation'):
                    # Initialize allowed_contexts if it doesn't exist
                    if 'allowed_contexts' not in self._hass.data[DOMAIN]:
                        self._hass.data[DOMAIN]['allowed_contexts'] = set()
                    
                    # Add this specific context to allowed contexts
                    if hasattr(context, 'id') and context.id:
                        self._hass.data[DOMAIN]['allowed_contexts'].add(context.id)
                        context_id_added = context.id
                        _LOGGER.debug(f"Added context {context.id} to allowed contexts for {domain}.{service}")
                
                try:
                    return await self._original.async_call(domain, service, service_data, blocking, context, **kwargs)
                finally:
                    # Remove the specific context from allowed contexts after the script/automation completes
                    if context_id_added:
                        try:
                            self._hass.data[DOMAIN]['allowed_contexts'].discard(context_id_added)
                            _LOGGER.debug(f"Removed context {context_id_added} from allowed contexts for {domain}.{service}")
                        except (KeyError, AttributeError):
                            pass  # Context might have been cleaned up already
                
            except HomeAssistantError:
                # Re-raise access denied errors
                raise
            except Exception as e:
                # Log error and allow service call to proceed
                _LOGGER.warning(
                    f"RBAC error for {domain}.{service}: {e}. Allowing service call to proceed."
                )
                _LOGGER.debug(f"RBAC error details: {e}", exc_info=True)
                
                # Try to clean service_data to avoid validation errors
                try:
                    if service_data and isinstance(service_data, dict):
                        # Remove problematic keys that might cause validation errors
                        cleaned_data = service_data.copy()
                        for key in ['rgb_color', 'xy_color', 'hs_color', 'color_temp']:
                            if key in cleaned_data and not isinstance(cleaned_data[key], (list, tuple)):
                                _LOGGER.debug(f"Removing invalid {key} from service_data: {cleaned_data[key]}")
                                del cleaned_data[key]
                        service_data = cleaned_data
                except Exception as cleanup_error:
                    _LOGGER.debug(f"Failed to clean service_data: {cleanup_error}")
                
                # Allow the service call to proceed with original method
                return await self._original.async_call(domain, service, service_data, blocking, context, **kwargs)
    
    # Replace the service registry
    hass.services = RestrictedServiceRegistry(original_registry, hass)
    _LOGGER.warning("RBAC service registry patching applied successfully")
    
    # Patch service registry to filter restricted services
    _patch_service_list(hass)
    
    # Patch search functionality to filter restricted entities
    _patch_search(hass)
    




def _is_entity_restricted_for_user(entity_id: str, user_id: str, hass: HomeAssistant) -> bool:
    """Check if an entity is restricted for a specific user."""
    _LOGGER.warning(f"Checking if entity {entity_id} is restricted for user {user_id}")
    
    if DOMAIN not in hass.data:
        _LOGGER.debug(f"RBAC domain not in hass.data for entity {entity_id}")
        return False
    
    access_config = hass.data[DOMAIN].get("access_config", {})
    _LOGGER.warning(f"Access config loaded for entity {entity_id}: {bool(access_config)}")
    
    # Get user configuration
    users = access_config.get("users", {})
    user_config = users.get(user_id)
    _LOGGER.warning(f"User {user_id} config found: {bool(user_config)}")
    
    # If user not in config, check default restrictions
    if not user_config:
        _LOGGER.warning(f"User {user_id} not in config, checking default restrictions for {entity_id}")
        default_restrictions = access_config.get("default_restrictions", {})
        _LOGGER.debug(f"Default restrictions: {default_restrictions}")
        if default_restrictions and isinstance(default_restrictions, dict):
            # Check domain-level hide setting
            domain = entity_id.split('.')[0]
            default_domains = default_restrictions.get("domains", {})
            _LOGGER.debug(f"Default domains: {default_domains}")
            if default_domains and isinstance(default_domains, dict):
                _LOGGER.debug(f"Checking domain {domain} in default restrictions: {domain in default_domains}")
                if domain in default_domains:
                    domain_config = default_domains[domain]
                    hide_domain = domain_config.get("hide", False)
                    _LOGGER.debug(f"Domain {domain} hide setting: {hide_domain}")
                    if hide_domain:
                        _LOGGER.debug(f"Entity {entity_id} is hidden by default domain restriction for {domain}")
                        return True
                else:
                    _LOGGER.debug(f"Domain {domain} not found in default restrictions")
            
            # Check entity-level restrictions
            default_entities = default_restrictions.get("entities", {})
            if default_entities is None:
                default_entities = {}
            if default_entities and isinstance(default_entities, dict):
                _LOGGER.debug(f"Checking entity {entity_id} in default entities: {entity_id in default_entities}")
                if entity_id in default_entities:
                    entity_config = default_entities[entity_id]
                    hide_entity = entity_config.get("hide", False)
                    _LOGGER.debug(f"Entity {entity_id} hide setting: {hide_entity}")
                    if hide_entity:
                        _LOGGER.warning(f"Entity {entity_id} is hidden by default entity restriction")
                        return True
        _LOGGER.warning(f"No default restrictions found for entity {entity_id}")
        return False
    
    # Check user-specific restrictions
    restrictions = user_config.get("restrictions", {})
    _LOGGER.warning(f"User {user_id} restrictions: {bool(restrictions)}")
    
    # Check domain-level hide setting
    domain = entity_id.split('.')[0]
    domains = restrictions.get("domains", {})
    _LOGGER.debug(f"Checking domain {domain} in user restrictions: {domain in domains}")
    if domain in domains:
        domain_config = domains[domain]
        hide_domain = domain_config.get("hide", False)
        _LOGGER.debug(f"User domain {domain} hide setting: {hide_domain}")
        if hide_domain:
            _LOGGER.warning(f"Entity {entity_id} is hidden by user domain restriction for {domain}")
            return True
    
    # Check entity-level restrictions
    entities = restrictions.get("entities", {})
    _LOGGER.debug(f"Checking entity {entity_id} in user entities: {entity_id in entities}")
    if entity_id in entities:
        entity_config = entities[entity_id]
        hide_entity = entity_config.get("hide", False)
        _LOGGER.debug(f"User entity {entity_id} hide setting: {hide_entity}")
        if hide_entity:
            _LOGGER.warning(f"Entity {entity_id} is hidden by user entity restriction")
            return True
    
    _LOGGER.debug(f"Entity {entity_id} is NOT restricted for user {user_id}")
    return False


def _patch_service_list(hass: HomeAssistant):
    """Patch the service registry to filter restricted services from service lists."""
    original_registry = hass.services
    
    class FilteredServiceRegistry:
        def __init__(self, original_registry, hass):
            self._original = original_registry
            self._hass = hass
            
        def __getattr__(self, name):
            return getattr(self._original, name)
            
        async def async_call(self, domain, service, service_data=None, blocking=False, context=None, **kwargs):
            """Intercept service calls for RBAC enforcement."""
            return await self._original.async_call(domain, service, service_data, blocking, context, **kwargs)
        
        def services_for_domain(self, domain):
            """Get services for a domain, filtering restricted services for users."""
            try:
                # Get current user context
                user_id = None
                try:
                    from homeassistant.core import Context
                    context = Context()
                    if hasattr(context, 'user_id') and context.user_id:
                        user_id = context.user_id
                except:
                    pass
                
                # If no user context, return all services
                if not user_id:
                    return self._original.services_for_domain(domain)
                
                # Entity hiding is disabled - return all services
                    # Get all services for the domain
                    all_services = self._original.services_for_domain(domain)
                    
                    # Filter out restricted services
                    filtered_services = {}
                    for service_name, service_info in all_services.items():
                        if not _is_service_restricted_for_user(domain, service_name, user_id, hass):
                            filtered_services[service_name] = service_info
                        else:
                            _LOGGER.debug(f"Filtering out restricted service {domain}.{service_name} for user {user_id}")
                    
                    return filtered_services
                else:
                    # Return all services if hiding is disabled
                    return self._original.services_for_domain(domain)
            except Exception as e:
                _LOGGER.warning(f"RBAC error in services.services_for_domain({domain}): {e}. Showing all services to prevent lockout.")
                _LOGGER.debug(f"RBAC error details: {e}", exc_info=True)
                return self._original.services_for_domain(domain)
        
        def async_services(self):
            """Get all services, filtering restricted services for users."""
            try:
                # Get current user context
                user_id = None
                try:
                    from homeassistant.core import Context
                    context = Context()
                    if hasattr(context, 'user_id') and context.user_id:
                        user_id = context.user_id
                except:
                    pass
                
                # If no user context, return all services
                if not user_id:
                    return self._original.async_services()
                
                # Entity hiding is disabled - return all services
                    # Get all services
                    all_services = self._original.async_services()
                    
                    # Filter out restricted services
                    filtered_services = {}
                    for domain, services in all_services.items():
                        filtered_domain_services = {}
                        for service_name, service_info in services.items():
                            if not _is_service_restricted_for_user(domain, service_name, user_id, hass):
                                filtered_domain_services[service_name] = service_info
                            else:
                                _LOGGER.debug(f"Filtering out restricted service {domain}.{service_name} for user {user_id}")
                        
                        if filtered_domain_services:
                            filtered_services[domain] = filtered_domain_services
                    
                    return filtered_services
                else:
                    # Return all services if hiding is disabled
                    return self._original.async_services()
            except Exception as e:
                _LOGGER.warning(f"RBAC error in services.async_services(): {e}. Showing all services to prevent lockout.")
                _LOGGER.debug(f"RBAC error details: {e}", exc_info=True)
                return self._original.async_services()
    
    hass.services = FilteredServiceRegistry(original_registry, hass)


def _patch_search(hass: HomeAssistant):
    """Patch the search functionality to filter restricted entities."""
    try:
        # Try to patch the search component if it exists
        if hasattr(hass, 'components') and hasattr(hass.components, 'search'):
            original_search = hass.components.search
            
            class FilteredSearch:
                def __init__(self, original_search, hass):
                    self._original = original_search
                    self._hass = hass
                    
                def __getattr__(self, name):
                    return getattr(self._original, name)
                
                async def async_search(self, query, context=None):
                    """Filter search results to exclude restricted entities."""
                    try:
                        # Get current user context
                        user_id = None
                        if context and hasattr(context, 'user_id') and context.user_id:
                            user_id = context.user_id
                        
                        # If no user context, return all results
                        if not user_id:
                            return await self._original.async_search(query, context)
                        
                        # Get search results
                        results = await self._original.async_search(query, context)
                        
                        # Entity hiding is disabled - return all results
                        hide_blocked_entities = False
                        
                        if hide_blocked_entities:
                            filtered_results = []
                            for result in results:
                                if hasattr(result, 'entity_id'):
                                    if not _is_entity_restricted_for_user(result.entity_id, user_id, self._hass):
                                        filtered_results.append(result)
                                    else:
                                        _LOGGER.debug(f"Filtering out restricted entity {result.entity_id} from search results for user {user_id}")
                                else:
                                    filtered_results.append(result)
                            return filtered_results
                        else:
                            return results
                            
                    except Exception as e:
                        _LOGGER.warning(f"RBAC error in search: {e}. Showing all search results to prevent lockout.")
                        _LOGGER.debug(f"RBAC error details: {e}", exc_info=True)
                        return await self._original.async_search(query, context)
            
            hass.components.search = FilteredSearch(original_search, hass)
            _LOGGER.debug("Patched search component to filter restricted entities")
    except Exception as e:
        _LOGGER.debug(f"Could not patch search component: {e}")




def _is_service_restricted_for_user(domain: str, service: str, user_id: str, hass: HomeAssistant) -> bool:
    """Check if a service is restricted for a specific user."""
    if DOMAIN not in hass.data:
        return False
    
    access_config = hass.data[DOMAIN].get("access_config", {})
    
    # Get user configuration
    users = access_config.get("users", {})
    user_config = users.get(user_id)
    
    # If user not in config, check default restrictions
    if not user_config:
        default_restrictions = access_config.get("default_restrictions", {})
        if default_restrictions:
            default_domains = default_restrictions.get("domains", {})
            if domain in default_domains:
                domain_config = default_domains[domain]
                # If domain is hidden, hide all services
                if domain_config.get("hide", False):
                    return True
                # Check specific service restrictions
                default_services = domain_config.get("services", [])
                if service in default_services:
                    return True
        return False
    
    # Check user-specific restrictions
    restrictions = user_config.get("restrictions", {})
    domains = restrictions.get("domains", {})
    
    if domain in domains:
        domain_config = domains[domain]
        # If domain is hidden, hide all services
        if domain_config.get("hide", False):
            return True
        # Check specific service restrictions
        services = domain_config.get("services", [])
        if service in services:
            return True
    
    return False


def _is_builtin_ha_user(user_id: str, hass: HomeAssistant = None) -> bool:
    """Check if a user is a built-in Home Assistant user that should be excluded from RBAC.
    
    This function checks if the user has a corresponding person.* entity.
    Built-in HA users (like Supervisor, Home Assistant Content, etc.) don't have person entities.
    """
    if not hass:
        # Fallback to name-based checking if hass is not available
        return False
    
    # Look for person entities that match this user
    all_states = hass.states.async_all()
    for state in all_states:
        if state.entity_id.startswith('person.'):
            # Check if this person entity belongs to this user
            if hasattr(state, 'attributes') and 'user_id' in state.attributes:
                if state.attributes['user_id'] == user_id:
                    # User has a person entity, so they're a real user
                    return False
    
    # No person entity found for this user, so they're likely a built-in HA user
    return True


def _check_service_access_with_reason(
    domain: str,
    service: str,
    service_data: Optional[Dict[str, Any]],
    user_id: Optional[str],
    access_config: Dict[str, Any],
    hass: HomeAssistant = None
) -> tuple[bool, str]:
    """Check if a user has access to a specific service call with detailed reason."""
    
    # If no user_id, allow access (system calls)
    if not user_id or user_id == "null" or user_id is None:
        return True, "system call (no user_id)"
    
    # Get user configuration
    users = access_config.get("users", {})
    user_config = users.get(user_id)
    
    # If user not in config, apply default restrictions
    if not user_config:
        _LOGGER.warning(f"User {user_id} not in config, checking default restrictions")
        # Check default restrictions
        default_restrictions = access_config.get("default_restrictions", {})
        _LOGGER.warning(f"Default restrictions: {default_restrictions}")
        if default_restrictions:
            # Check domain-level default restrictions
            default_domains = default_restrictions.get("domains", {})
            _LOGGER.warning(f"Checking domain {domain} against default domains: {default_domains}")
            if domain in default_domains:
                domain_config = default_domains[domain]
                _LOGGER.warning(f"Found domain {domain} config: {domain_config}")
                # Check service restrictions
                default_services = domain_config.get("services", [])
                if not default_services:  # Empty services list = block all services
                    _LOGGER.warning(f"Domain {domain} blocks all services")
                    return False, f"domain {domain} blocked by default"
                elif service in default_services:  # Service is in blocked list = block it
                    return False, f"service {domain}.{service} blocked by default"
            
            # Check entity-level default restrictions
            if service_data and "entity_id" in service_data:
                entity_id = service_data["entity_id"]
                if isinstance(entity_id, list):
                    for eid in entity_id:
                        default_entities = default_restrictions.get("entities", {})
                        if eid in default_entities:
                            entity_config = default_entities[eid]
                            # Check service restrictions
                            default_entity_services = entity_config.get("services", [])
                            if not default_entity_services:  # Empty services list = block all services
                                return False, f"entity {eid} blocked by default"
                            elif service in default_entity_services:  # Service is in blocked list = block it
                                return False, f"entity {eid} service {service} blocked by default"
                else:
                    default_entities = default_restrictions.get("entities", {})
                    if entity_id in default_entities:
                        entity_config = default_entities[entity_id]
                        # Check service restrictions
                        default_entity_services = entity_config.get("services", [])
                        if not default_entity_services:  # Empty services list = block all services
                            return False, f"entity {entity_id} blocked by default"
                        elif service in default_entity_services:  # Specific services listed = block only those
                            return False, f"entity {entity_id} service {service} blocked by default"
        
        return True, f"no default restrictions"
    
    # Get user's role
    user_role = user_config.get("role", "unknown")
    
    # Get role configuration
    roles = access_config.get("roles", {})
    role_config = roles.get(user_role, {})
    
    # Evaluate template if present and switch to fallback role if template evaluates to false
    if role_config and hass:
        template_str = role_config.get("template")
        fallback_role = role_config.get("fallbackRole")
        
        if template_str and fallback_role:
            try:
                # Create a Template object and render it
                template = Template(template_str, hass)
                
                # Get current user's person entity for template context
                user_person_entity = None
                try:
                    # Look for person entities associated with this user
                    for state in hass.states.async_all():
                        if state.domain == "person" and state.attributes.get("user_id") == user_id:
                            user_person_entity = state.entity_id
                            break
                except Exception as e:
                    _LOGGER.debug(f"Could not find person entity for user {user_id}: {e}")
                
                # Create template context with user variable
                template_context = {}
                if user_person_entity:
                    template_context['current_user_str'] = user_person_entity
                
                result = template.async_render(template_context, parse_result=False)
                
                # Convert result to boolean
                template_result = bool(result) if result not in [None, "", "False", "false", "0"] else False
                
                _LOGGER.debug(f"Template for role {user_role} evaluated to: {template_result} (raw: {result})")
                
                # If template evaluates to false, switch to fallback role
                if not template_result:
                    _LOGGER.info(f"Template for role {user_role} evaluated to false, switching to fallback role: {fallback_role}")
                    user_role = fallback_role
                    role_config = roles.get(user_role, {})
                    
                    if not role_config:
                        _LOGGER.warning(f"Fallback role {fallback_role} not found in configuration")
                        return True, f"fallback role {fallback_role} not found"
            except Exception as e:
                _LOGGER.error(f"Error evaluating template for role {user_role}: {e}")
                _LOGGER.debug(f"Template evaluation error details: {e}", exc_info=True)
                # On error, switch to fallback role for security
                if fallback_role:
                    _LOGGER.warning(f"Template evaluation failed for role {user_role}, switching to fallback role: {fallback_role}")
                    user_role = fallback_role
                    role_config = roles.get(user_role, {})
                    
                    if not role_config:
                        _LOGGER.warning(f"Fallback role {fallback_role} not found in configuration")
                        return True, f"fallback role {fallback_role} not found"
                else:
                    _LOGGER.error(f"No fallback role defined for role {user_role}, continuing with original role")
    
    if not role_config:
        return True, f"no role configuration for {user_role}"
    
    # Check if role is admin
    is_admin_role = role_config.get("admin", False)
    if is_admin_role:
        return True, f"admin role {user_role} has full access"
    
    # Check if role has deny_all enabled
    deny_all = role_config.get("deny_all", False)
    
    # For non-admin roles, merge default restrictions with role-specific restrictions
    default_restrictions = access_config.get("default_restrictions", {})
    permissions = role_config.get("permissions", {})
    
    # Check entity-level restrictions FIRST (highest priority)
    if service_data and "entity_id" in service_data:
        entity_id = service_data["entity_id"]
        if isinstance(entity_id, list):
            for eid in entity_id:
                # Check default entity restrictions
                default_entities = default_restrictions.get("entities", {})
                if eid in default_entities:
                    default_entity_config = default_entities[eid]
                    default_entity_services = default_entity_config.get("services", [])
                    default_entity_allow = default_entity_config.get("allow", False)
                    
                    if default_entity_allow:
                        # Default allow rule: check if service is in allowed services
                        if not default_entity_services or service in default_entity_services:
                            return True, f"entity {eid} service {service} allowed by default"
                        else:
                            return False, f"entity {eid} service {service} not in default allow list"
                    else:
                        # Default block rule
                        if not default_entity_services:  # Default blocks all services
                            # Check if role allows this entity
                            role_entities = permissions.get("entities", {})
                            if eid not in role_entities:
                                return False, f"entity {eid} blocked by default restrictions"
                            role_entity_config = role_entities[eid]
                            role_entity_services = role_entity_config.get("services", [])
                            role_entity_allow = role_entity_config.get("allow", False)
                            
                            if role_entity_allow:
                                # Role allow rule: check if service is in allowed services
                                if not role_entity_services or service in role_entity_services:
                                    return True, f"entity {eid} service {service} allowed by role {user_role}"
                                else:
                                    return False, f"entity {eid} service {service} not in role allow list"
                            else:
                                # Role block rule
                                if not role_entity_services:  # Role also blocks all services
                                    return False, f"entity {eid} blocked by role {user_role}"
                                elif service not in role_entity_services:  # Service not in role's allowed list
                                    return False, f"entity {eid} service {service} not allowed by role {user_role}"
                        elif service in default_entity_services:  # Default blocks specific service
                            # Check if role allows this service
                            role_entities = permissions.get("entities", {})
                            if eid not in role_entities:
                                return False, f"entity {eid} service {service} blocked by default restrictions"
                            role_entity_config = role_entities[eid]
                            role_entity_services = role_entity_config.get("services", [])
                            role_entity_allow = role_entity_config.get("allow", False)
                            
                            if role_entity_allow:
                                # Role allow rule: check if service is in allowed services
                                if not role_entity_services or service in role_entity_services:
                                    return True, f"entity {eid} service {service} allowed by role {user_role}"
                                else:
                                    return False, f"entity {eid} service {service} not in role allow list"
                            else:
                                # Role block rule
                                if service in role_entity_services:  # Role also blocks this service
                                    return False, f"entity {eid} service {service} blocked by role {user_role}"
                
                # Check role-specific entity restrictions (always check, even if no default restrictions)
                role_entities = permissions.get("entities", {})
                if eid in role_entities:
                    role_entity_config = role_entities[eid]
                    role_entity_services = role_entity_config.get("services", [])
                    role_entity_allow = role_entity_config.get("allow", False)
                    
                    _LOGGER.warning(f"Found entity {eid} in role permissions: allow={role_entity_allow}, services={role_entity_services}")
                    
                    if role_entity_allow:
                        # Role allow rule: check if service is in allowed services
                        if not role_entity_services or service in role_entity_services:
                            return True, f"entity {eid} service {service} allowed by role {user_role}"
                        else:
                            return False, f"entity {eid} service {service} not in role allow list"
                    else:
                        # Role block rule
                        if not role_entity_services:  # Role blocks all services for this entity
                            return False, f"entity {eid} blocked by role {user_role}"
                        elif service in role_entity_services:  # Role blocks specific service
                            return False, f"entity {eid} service {service} blocked by role {user_role}"
        else:
            # Same logic for single entity
            default_entities = default_restrictions.get("entities", {})
            if entity_id in default_entities:
                default_entity_config = default_entities[entity_id]
                default_entity_services = default_entity_config.get("services", [])
                default_entity_allow = default_entity_config.get("allow", False)
                
                if default_entity_allow:
                    # Default allow rule: check if service is in allowed services
                    if not default_entity_services or service in default_entity_services:
                        return True, f"entity {entity_id} service {service} allowed by default"
                    else:
                        return False, f"entity {entity_id} service {service} not in default allow list"
                else:
                    # Default block rule
                    if not default_entity_services:  # Default blocks all services
                        role_entities = permissions.get("entities", {})
                        if entity_id not in role_entities:
                            return False, f"entity {entity_id} blocked by default restrictions"
                        role_entity_config = role_entities[entity_id]
                        role_entity_services = role_entity_config.get("services", [])
                        role_entity_allow = role_entity_config.get("allow", False)
                        
                        if role_entity_allow:
                            # Role allow rule: check if service is in allowed services
                            if not role_entity_services or service in role_entity_services:
                                return True, f"entity {entity_id} service {service} allowed by role {user_role}"
                            else:
                                return False, f"entity {entity_id} service {service} not in role allow list"
                        else:
                            # Role block rule
                            if not role_entity_services:  # Role also blocks all services
                                return False, f"entity {entity_id} blocked by role {user_role}"
                            elif service not in role_entity_services:  # Service not in role's allowed list
                                return False, f"entity {entity_id} service {service} not allowed by role {user_role}"
                    elif service in default_entity_services:  # Default blocks specific service
                        role_entities = permissions.get("entities", {})
                        if entity_id not in role_entities:
                            return False, f"entity {entity_id} service {service} blocked by default restrictions"
                        role_entity_config = role_entities[entity_id]
                        role_entity_services = role_entity_config.get("services", [])
                        role_entity_allow = role_entity_config.get("allow", False)
                        
                        if role_entity_allow:
                            # Role allow rule: check if service is in allowed services
                            if not role_entity_services or service in role_entity_services:
                                return True, f"entity {entity_id} service {service} allowed by role {user_role}"
                            else:
                                return False, f"entity {entity_id} service {service} not in role allow list"
                        else:
                            # Role block rule
                            if service in role_entity_services:  # Role also blocks this service
                                return False, f"entity {entity_id} service {service} blocked by role {user_role}"
            
            # Check role-specific entity restrictions (always check, even if no default restrictions)
            role_entities = permissions.get("entities", {})
            if entity_id in role_entities:
                role_entity_config = role_entities[entity_id]
                role_entity_services = role_entity_config.get("services", [])
                role_entity_allow = role_entity_config.get("allow", False)
                
                _LOGGER.warning(f"Found single entity {entity_id} in role permissions: allow={role_entity_allow}, services={role_entity_services}")
                
                if role_entity_allow:
                    # Role allow rule: check if service is in allowed services
                    if not role_entity_services or service in role_entity_services:
                        return True, f"entity {entity_id} service {service} allowed by role {user_role}"
                    else:
                        return False, f"entity {entity_id} service {service} not in role allow list"
                else:
                    # Role block rule
                    if not role_entity_services:  # Role blocks all services for this entity
                        return False, f"entity {entity_id} blocked by role {user_role}"
                    elif service in role_entity_services:  # Role blocks specific service
                        return False, f"entity {entity_id} service {service} blocked by role {user_role}"

    # Check domain-level restrictions (lower priority - only if no entity rules matched)
    default_domains = default_restrictions.get("domains", {})
    role_domains = permissions.get("domains", {})
    
    # Check if domain is restricted in defaults
    if domain in default_domains:
        default_config = default_domains[domain]
        default_services = default_config.get("services", [])
        default_allow = default_config.get("allow", False)
        
        if default_allow:
            # Default allow rule: check if service is in allowed services
            if not default_services or service in default_services:
                return True, f"domain {domain} service {service} allowed by default"
            else:
                return False, f"domain {domain} service {service} not in default allow list"
        else:
            # Default block rule
            if not default_services:  # Default blocks all services
                # Check if role allows this domain
                if domain not in role_domains:
                    return False, f"domain {domain} blocked by default restrictions"
                role_config = role_domains[domain]
                role_services = role_config.get("services", [])
                role_allow = role_config.get("allow", False)
                
                if role_allow:
                    # Role allow rule: check if service is in allowed services
                    if not role_services or service in role_services:
                        return True, f"domain {domain} service {service} allowed by role {user_role}"
                    else:
                        return False, f"domain {domain} service {service} not in role allow list"
                else:
                    # Role block rule
                    if not role_services:  # Role also blocks all services
                        return False, f"domain {domain} blocked by role {user_role}"
                    elif service not in role_services:  # Service not in role's allowed list
                        return False, f"service {domain}.{service} not allowed by role {user_role}"
            elif service in default_services:  # Default blocks specific service
                # Check if role allows this service
                if domain not in role_domains:
                    return False, f"service {domain}.{service} blocked by default restrictions"
                role_config = role_domains[domain]
                role_services = role_config.get("services", [])
                role_allow = role_config.get("allow", False)
                
                if role_allow:
                    # Role allow rule: check if service is in allowed services
                    if not role_services or service in role_services:
                        return True, f"domain {domain} service {service} allowed by role {user_role}"
                    else:
                        return False, f"domain {domain} service {service} not in role allow list"
                else:
                    # Role block rule
                    if service in role_services:  # Role also blocks this service
                        return False, f"service {domain}.{service} blocked by role {user_role}"
    
    # Check role-specific domain restrictions
    if domain in role_domains:
        role_config = role_domains[domain]
        role_services = role_config.get("services", [])
        role_allow = role_config.get("allow", False)
        
        _LOGGER.warning(f"Found domain {domain} in role permissions: allow={role_allow}, services={role_services}")
        
        if role_allow:
            # Role allow rule: check if service is in allowed services
            if not role_services or service in role_services:
                return True, f"domain {domain} service {service} allowed by role {user_role}"
            else:
                return False, f"domain {domain} service {service} not in role allow list"
        else:
            # Role block rule
            if not role_services:  # Role blocks all services for this domain
                return False, f"domain {domain} blocked by role {user_role}"
            elif service in role_services:  # Role blocks specific service
                return False, f"service {domain}.{service} blocked by role {user_role}"
    
    # If deny_all is enabled and no allow rules matched, deny access
    # Exception: Always allow system_log.write and browser_mod.notification even with deny_all enabled
    # Also check if there are entity-level allow rules that should override deny_all
    if deny_all and not ((domain == "system_log" and service == "write") or (domain == "browser_mod" and service == "notification")):
        # Check if this service call has entity-level allow permissions that should override deny_all
        entity_ids = []
        
        # Check for entity_id in service_data
        if service_data and "entity_id" in service_data:
            entity_id = service_data["entity_id"]
            if isinstance(entity_id, str):
                entity_ids = [entity_id]
            else:
                entity_ids = entity_id if isinstance(entity_id, list) else []
        
        # For script/automation calls, also check if domain.service matches an entity permission
        if domain in ["script", "automation"]:
            entity_name = f"{domain}.{service}"
            entity_ids.append(entity_name)
        
        # Check role entity permissions for allow rules
        role_entities = permissions.get("entities", {})
        for eid in entity_ids:
            if eid in role_entities:
                entity_config = role_entities[eid]
                entity_allow = entity_config.get("allow", False)
                if entity_allow:
                    entity_services = entity_config.get("services", [])
                    if not entity_services or service in entity_services:
                        return True, f"entity {eid} service {service} allowed by role entity permissions (overrides deny_all)"
        
        return False, f"access denied by deny_all setting for role {user_role}"
    
    return True, f"access granted"


def _check_service_access(
    domain: str,
    service: str,
    service_data: Optional[Dict[str, Any]],
    user_id: Optional[str],
    access_config: Dict[str, Any],
    hass: HomeAssistant = None
) -> bool:
    """Check if a user has access to a specific service call."""
    result, _ = _check_service_access_with_reason(domain, service, service_data, user_id, access_config, hass)
    return result


def _check_entity_access_with_reason(entity_id: str, service: str, user_config: Dict[str, Any]) -> tuple[bool, str]:
    """Check if user has access to a specific entity service with detailed reason."""
    if not user_config:
        return True, f"no user config"
    
    restrictions = user_config.get("restrictions", {})
    entities = restrictions.get("entities", {})
    
    if entity_id in entities:
        entity_config = entities[entity_id]
        
        # Check if this is an allow rule
        if entity_config.get("allow", False):
            # Allow rule: check if service is in allowed services
            services = entity_config.get("services", [])
            if not services or service in services:
                return True, f"entity {entity_id} service {service} allowed"
            else:
                return False, f"entity {entity_id} service {service} not in allow list"
        
        # Block rule: if entity is hidden, hide all services
        if entity_config.get("hide", False):
            return False, f"entity {entity_id} blocked"
        # Check specific service restrictions
        services = entity_config.get("services", [])
        if service in services:
            return False, f"entity {entity_id} service {service} blocked"
    
    return True, f"entity {entity_id} allowed"


def _check_entity_access(entity_id: str, service: str, user_config: Dict[str, Any]) -> bool:
    """Check if user has access to a specific entity service."""
    result, _ = _check_entity_access_with_reason(entity_id, service, user_config)
    return result


def _check_domain_access_with_reason(domain: str, service: str, user_config: Dict[str, Any]) -> tuple[bool, str]:
    """Check if user has access to a domain service with detailed reason."""
    if not user_config:
        return True, f"no user config"
    
    restrictions = user_config.get("restrictions", {})
    domains = restrictions.get("domains", {})
    
    if domain in domains:
        domain_config = domains[domain]
        
        # Check if this is an allow rule
        if domain_config.get("allow", False):
            # Allow rule: check if service is in allowed services
            services = domain_config.get("services", [])
            if not services or service in services:
                return True, f"domain {domain} service {service} allowed"
            else:
                return False, f"domain {domain} service {service} not in allow list"
        
        # Block rule: if domain is hidden, hide all services
        if domain_config.get("hide", False):
            return False, f"domain {domain} blocked"
        # Check specific service restrictions
        services = domain_config.get("services", [])
        if service in services:
            return False, f"domain {domain} service {service} blocked"
    
    return True, f"domain {domain} allowed"


def _check_domain_access(domain: str, service: str, user_config: Dict[str, Any]) -> bool:
    """Check if user has access to a domain service."""
    result, _ = _check_domain_access_with_reason(domain, service, user_config)
    return result




def _check_restriction_access_with_reason(
    domain: str,
    service: str,
    service_data: Optional[Dict[str, Any]],
    user_config: Dict[str, Any]
) -> tuple[bool, str]:
    """Check if service is in user's restrictions with detailed reason."""
    if not user_config:
        return False, f"no user config"
    
    restrictions = user_config.get("restrictions", {})
    domains = restrictions.get("domains", {})
    
    if domain in domains:
        domain_config = domains[domain]
        services = domain_config.get("services", [])
        # Return True if service is in restrictions list (should be denied)
        if service in services:
            return True, f"service {domain}.{service} restricted"
    
    return False, f"service {domain}.{service} allowed"


def _check_restriction_access(
    domain: str,
    service: str,
    service_data: Optional[Dict[str, Any]],
    user_config: Dict[str, Any]
) -> bool:
    """Check if service is in user's restrictions."""
    result, _ = _check_restriction_access_with_reason(domain, service, service_data, user_config)
    return result


def get_user_config(hass: HomeAssistant, user_id: str) -> Optional[Dict[str, Any]]:
    """Get the configuration for a specific user."""
    if DOMAIN not in hass.data:
        return None
    
    access_config = hass.data[DOMAIN].get("access_config", {})
    users = access_config.get("users", {})
    return users.get(user_id)


async def reload_access_config(hass: HomeAssistant) -> bool:
    """Reload the access control configuration from YAML file."""
    try:
        access_config = await _load_access_control_config(hass)
        hass.data[DOMAIN]["access_config"] = access_config
        _LOGGER.info("Access control configuration reloaded successfully")
        return True
    except Exception as e:
        _LOGGER.error(f"Failed to reload access control configuration: {e}")
        return False


async def _save_access_control_config(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Save access control configuration to YAML file."""
    config_path = os.path.join(hass.config.config_dir, "custom_components", "rbac", "access_control.yaml")
    
    def _save_file():
        try:
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2, sort_keys=False)
            return True
        except Exception as e:
            _LOGGER.error(f"Error saving access control configuration: {e}")
            return False
    
    # Run file I/O in executor to avoid blocking the event loop
    success = await hass.async_add_executor_job(_save_file)
    if success:
        _LOGGER.info(f"Saved access control configuration to {config_path}")
    return success


def _log_denial_to_file(hass: HomeAssistant, user_id: str, user_name: str, user_role: str, domain: str, service: str, reason: str):
    """Log access denial to deny_list.log file."""
    try:
        # Get the log file path
        log_path = os.path.join(hass.config.config_dir, "custom_components", "rbac", "deny_list.log")
        
        # Create timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format log entry
        log_entry = f"[{timestamp}] DENIED - User: {user_name} ({user_id}) | Role: {user_role} | Service: {domain}.{service} | Reason: {reason}\n"
        
        # Append to log file
        with open(log_path, 'a', encoding='utf-8') as log_file:
            log_file.write(log_entry)
        
        _LOGGER.debug(f"Logged denial to deny_list.log: {user_name} -> {domain}.{service}")
        
    except Exception as e:
        _LOGGER.error(f"Failed to log denial to file: {e}")


def _get_deny_log_contents(hass: HomeAssistant) -> str:
    """Get the contents of the deny_list.log file."""
    try:
        log_path = os.path.join(hass.config.config_dir, "custom_components", "rbac", "deny_list.log")
        
        if not os.path.exists(log_path):
            return "No deny log file found. Denials will be logged here when they occur."
        
        with open(log_path, 'r', encoding='utf-8') as log_file:
            contents = log_file.read()
        
        if not contents.strip():
            return "Deny log file is empty. No access denials have been logged yet."
        
        return contents
        
    except Exception as e:
        _LOGGER.error(f"Failed to read deny log file: {e}")
        return f"Error reading deny log file: {e}"


def _clear_deny_log(hass: HomeAssistant) -> bool:
    """Clear the contents of the deny_list.log file."""
    try:
        log_path = os.path.join(hass.config.config_dir, "custom_components", "rbac", "deny_list.log")
        
        # Create an empty file or truncate existing file
        with open(log_path, 'w', encoding='utf-8') as log_file:
            log_file.write("")
        
        _LOGGER.info("Deny log file cleared successfully")
        return True
        
    except Exception as e:
        _LOGGER.error(f"Failed to clear deny log file: {e}")
        return False


async def _register_sidebar_panel(hass: HomeAssistant):
    """Register RBAC configuration panel in the sidebar."""
    
    # Check if sidebar panel should be shown based on config entry options
    should_show_panel = True
    
    # Look for RBAC config entries
    for entry in hass.config_entries.async_entries(DOMAIN):
        # Check the options for show_sidebar_panel setting
        should_show_panel = entry.options.get("show_sidebar_panel", True)
        break  # Use the first (and likely only) RBAC entry
    
    if not should_show_panel:
        _LOGGER.info("RBAC sidebar panel disabled via config entry options")
        return
    
    async def _do_panel_registration():
        """Perform the actual panel registration."""
        try:
            from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel
            
            # First try to remove any existing panel to avoid conflicts
            try:
                await async_remove_panel(hass, "rbac-config")
            except Exception:
                pass  # Panel might not exist, which is fine
            
            # Now register the panel
            async_register_built_in_panel(
                hass,
                component_name="iframe",
                sidebar_title="RBAC Config",
                sidebar_icon="mdi:shield-account",
                frontend_url_path="rbac-config",
                config={
                    "url": "/api/rbac/static/config.html",
                    "title": "RBAC Configuration"
                },
                require_admin=True
            )
            _LOGGER.info("Successfully registered RBAC sidebar panel")
            return True
            
        except Exception as e:
            _LOGGER.debug(f"Panel registration attempt failed: {e}")
            return False
    
    # Try immediate registration first
    if await _do_panel_registration():
        return
    
    # If immediate registration fails, listen for the frontend_ready event
    async def _on_frontend_ready(event):
        """Handle frontend ready event."""
        if await _do_panel_registration():
            return
        
        # If still failing, try one more time with a small delay
        import asyncio
        await asyncio.sleep(2)
        
        if not await _do_panel_registration():
            _LOGGER.warning("Could not register RBAC sidebar panel. Users will need to access the config page manually at /api/rbac/static/config.html")
    
    # Listen for the frontend ready event
    try:
        hass.bus.async_listen_once("frontend_ready", _on_frontend_ready)
        _LOGGER.info("RBAC panel registration scheduled for when frontend is ready")
    except Exception as e:
        _LOGGER.warning(f"Could not schedule RBAC panel registration: {e}. Users will need to access the config page manually at /api/rbac/static/config.html")


def _is_top_level_user(hass: HomeAssistant, user_id: str) -> bool:
    """Check if user has top-level access (admin or super_admin role)."""
    if DOMAIN not in hass.data:
        return False
    
    access_config = hass.data[DOMAIN].get("access_config", {})
    users = access_config.get("users", {})
    user_config = users.get(user_id)
    
    if not user_config:
        # User not in config, check if they have admin privileges in HA
        try:
            user = hass.auth.async_get_user(user_id)
            if user and user.is_admin:
                return True
        except Exception:
            pass
        return False
    
    role = user_config.get("role", "")
    return role in ["admin", "super_admin"]


async def add_user_access(hass: HomeAssistant, user_id: str, role: str) -> bool:
    """Add a user to the access control configuration."""
    if DOMAIN not in hass.data:
        return False
    
    access_config = hass.data[DOMAIN].get("access_config", {})
    if "users" not in access_config:
        access_config["users"] = {}
    
    access_config["users"][user_id] = {
        "role": role
    }
    
    # Save to file
    if await _save_access_control_config(hass, access_config):
        hass.data[DOMAIN]["access_config"] = access_config
        _LOGGER.info(f"Added user '{user_id}' with role '{role}'")
        return True
    
    return False


async def remove_user_access(hass: HomeAssistant, user_id: str) -> bool:
    """Remove a user from the access control configuration."""
    if DOMAIN not in hass.data:
        return False
    
    access_config = hass.data[DOMAIN].get("access_config", {})
    users = access_config.get("users", {})
    
    if user_id in users:
        del users[user_id]
        
        # Save to file
        if _save_access_control_config(hass, access_config):
            hass.data[DOMAIN]["access_config"] = access_config
            _LOGGER.info(f"Removed user '{user_id}' from access control")
            return True
    
    return False


async def update_user_role(hass: HomeAssistant, user_id: str, role: str) -> bool:
    """Update a user's role in the access control configuration."""
    if DOMAIN not in hass.data:
        return False
    
    access_config = hass.data[DOMAIN].get("access_config", {})
    users = access_config.get("users", {})
    
    if user_id in users:
        users[user_id]["role"] = role
        
        # Save to file
        if _save_access_control_config(hass, access_config):
            hass.data[DOMAIN]["access_config"] = access_config
            _LOGGER.info(f"Updated user '{user_id}' role to '{role}'")
            return True
    
    return False


async def add_user_restriction(hass: HomeAssistant, user_id: str, domain: str, services: list) -> bool:
    """Add domain restrictions for a user."""
    if DOMAIN not in hass.data:
        return False
    
    access_config = hass.data[DOMAIN].get("access_config", {})
    users = access_config.get("users", {})
    
    if user_id not in users:
        return False
    
    user_config = users[user_id]
    if "restrictions" not in user_config:
        user_config["restrictions"] = {}
    if "domains" not in user_config["restrictions"]:
        user_config["restrictions"]["domains"] = {}
    
    user_config["restrictions"]["domains"][domain] = {
        "services": services
    }
    
    # Save to file
    if await _save_access_control_config(hass, access_config):
        hass.data[DOMAIN]["access_config"] = access_config
        _LOGGER.info(f"Added domain restriction for user '{user_id}': {domain}.{services}")
        return True
    
    return False


async def remove_user_restriction(hass: HomeAssistant, user_id: str, domain: str) -> bool:
    """Remove domain restrictions for a user."""
    if DOMAIN not in hass.data:
        return False
    
    access_config = hass.data[DOMAIN].get("access_config", {})
    users = access_config.get("users", {})
    
    if user_id not in users:
        return False
    
    user_config = users[user_id]
    restrictions = user_config.get("restrictions", {})
    domains = restrictions.get("domains", {})
    
    if domain in domains:
        del domains[domain]
        
        # Save to file
        if await _save_access_control_config(hass, access_config):
            hass.data[DOMAIN]["access_config"] = access_config
            _LOGGER.info(f"Removed domain restriction for user '{user_id}': {domain}")
            return True
    
    return False


