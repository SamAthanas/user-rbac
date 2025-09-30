"""RBAC Middleware for Home Assistant."""
import logging
import os
from typing import Any, Dict, Optional

import yaml

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import Platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rbac"


class RBACConfigURLSensor(SensorEntity):
    """Sensor for RBAC configuration URL."""
    
    def __init__(self, base_url: str = ""):
        """Initialize the sensor."""
        self._attr_name = "RBAC Configuration URL"
        self._attr_unique_id = f"{DOMAIN}_config_url"
        self._attr_icon = "mdi:web"
        self._attr_device_class = "url"
        self._attr_native_value = f"{base_url}/local/community/rbac/config.html" if base_url else "/local/community/rbac/config.html"


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
    
    # Create RBAC device with config URL entity
    await _setup_rbac_device(hass)
    
    user_count = len(access_config.get("users", {}))
    _LOGGER.info(f"RBAC Middleware initialized successfully with {user_count} configured users")
    # Register API endpoints
    from .services import RBACConfigView, RBACUsersView, RBACDomainsView, RBACEntitiesView, RBACServicesView, RBACCurrentUserView
    
    hass.http.register_view(RBACConfigView())
    hass.http.register_view(RBACUsersView())
    hass.http.register_view(RBACDomainsView())
    hass.http.register_view(RBACEntitiesView())
    hass.http.register_view(RBACServicesView())
    hass.http.register_view(RBACCurrentUserView())
    
    _LOGGER.info("Registered RBAC API endpoints")    
    return True


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up the RBAC middleware component from a config entry."""
    _LOGGER.info("Setting up RBAC Middleware from config entry")
    
    # Just call the main setup function
    return await async_setup(hass, {})




async def _setup_rbac_device(hass: HomeAssistant):
    """Set up RBAC config URL entity."""
    _LOGGER.info("Setting up RBAC config URL entity...")
    
    # Get the base URL from Home Assistant
    base_url = hass.config.external_url or hass.config.internal_url
    if not base_url:
        base_url = f"http://{hass.config.api.host}:{hass.config.api.port}"
    
    config_url = f"{base_url}/local/community/rbac/config.html"
    
    # Create standalone entity (no device needed)
    hass.states.async_set(
        f"sensor.{DOMAIN}_config_url",
        config_url,
        {
            "friendly_name": "RBAC Configuration URL",
            "icon": "mdi:web",
            "device_class": "url"
        }
    )
    
    _LOGGER.info(f"Created RBAC config URL entity: sensor.{DOMAIN}_config_url with URL: {config_url}")


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
                # Skip RBAC enforcement for certain domains that are needed for API functionality
                excluded_domains = ['http', 'auth', 'system_log', 'persistent_notification']
                if domain in excluded_domains:
                    _LOGGER.debug(f"Skipping RBAC enforcement for {domain}.{service} (excluded domain)")
                    return await self._original.async_call(domain, service, service_data, blocking, context, **kwargs)
                
                # Get user information
                user = None
                user_id = None
                
                if context and hasattr(context, 'user_id') and context.user_id:
                        user = await self._hass.auth.async_get_user(context.user_id)
                        user_id = context.user_id
                        
                        # Store user context for UI calls
                        if DOMAIN in self._hass.data:
                            self._hass.data[DOMAIN]["last_service_user"] = user_id
                            _LOGGER.debug(f"Stored user context for UI calls: {user_id}")
                
                # Skip RBAC enforcement for Home Assistant built-in users
                if user_id and _is_builtin_ha_user(user_id, self._hass):
                    _LOGGER.debug(f"Skipping RBAC enforcement for built-in HA user: {user_id} ({user.name if user else 'Unknown'})")
                    return await self._original.async_call(domain, service, service_data, blocking, context, **kwargs)
                
                # Log the service call attempt
                user_name = user.name if user else "Unknown"
                _LOGGER.debug(f"Service call: {domain}.{service} by {user_name} (user_id: {user_id})")
                
                # Get access config
                access_config = self._hass.data[DOMAIN]["access_config"]
                
                # Check if service call blocking is enabled
                block_service_calls = options.get("block_service_calls", True)
                
                if block_service_calls:
                    # Check access permissions with detailed logging
                    access_result, reason = _check_service_access_with_reason(domain, service, service_data, user_id, access_config)
                    
                    if not access_result:
                        _LOGGER.warning(
                            f"Access denied: {user_name} cannot call {domain}.{service} - {reason}"
                        )
                        
                        # Create persistent notification if enabled
                        if access_config.get("show_notifications", True):
                            try:
                                # Use the service call approach which is more reliable
                                # Call the original service registry to avoid recursion
                                await self._original.async_call(
                                    "persistent_notification",
                                    "create",
                                    {
                                        "message": f"Access denied: {user_name} cannot call {domain}.{service}",
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
                        
                        # Raise exception to properly handle the denial
                        raise HomeAssistantError(
                            f"Access denied: {user_name} cannot call {domain}.{service} - {reason}"
                        )
                
                # Service is allowed, proceed with original call
                if block_service_calls:
                    _LOGGER.debug(f"Service call allowed: {domain}.{service} by {user_name}")
                else:
                    _LOGGER.debug(f"Service call allowed (blocking disabled): {domain}.{service} by {user_name}")
                return await self._original.async_call(domain, service, service_data, blocking, context, **kwargs)
                
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
    
    # Patch service registry to filter restricted services
    _patch_service_list(hass)
    
    # Patch search functionality to filter restricted entities
    _patch_search(hass)
    
    # Store options in hass.data for access by other functions
    hass.data[DOMAIN]["options"] = {}




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
                        
                        # Filter out restricted entities
                        hide_blocked_entities = options.get("hide_blocked_entities", False)
                        
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
    access_config: Dict[str, Any]
) -> tuple[bool, str]:
    """Check if a user has access to a specific service call with detailed reason."""
    
    # If no user_id, allow access (system calls)
    if not user_id:
        return True, "system call (no user_id)"
    
    # Get user configuration
    users = access_config.get("users", {})
    user_config = users.get(user_id)
    
    # If user not in config, apply default restrictions
    if not user_config:
        # Check default restrictions
        default_restrictions = access_config.get("default_restrictions", {})
        if default_restrictions:
            # Check domain-level default restrictions
            default_domains = default_restrictions.get("domains", {})
            if domain in default_domains:
                domain_config = default_domains[domain]
                # If domain is hidden, hide all services
                if domain_config.get("hide", False):
                    return False, f"domain {domain} blocked by default"
                # Check specific service restrictions
                default_services = domain_config.get("services", [])
                if service in default_services:
                    return False, f"service {domain}.{service} blocked by default"
            
            # Check entity-level default restrictions
            if service_data and "entity_id" in service_data:
                entity_id = service_data["entity_id"]
                if isinstance(entity_id, list):
                    for eid in entity_id:
                        default_entities = default_restrictions.get("entities", {})
                        if eid in default_entities:
                            entity_config = default_entities[eid]
                            # If entity is hidden, hide all services
                            if entity_config.get("hide", False):
                                return False, f"entity {eid} blocked by default"
                            # Check specific service restrictions
                            default_entity_services = entity_config.get("services", [])
                            if service in default_entity_services:
                                return False, f"entity {eid} service {service} blocked by default"
                else:
                    default_entities = default_restrictions.get("entities", {})
                    if entity_id in default_entities:
                        entity_config = default_entities[entity_id]
                        # If entity is hidden, hide all services
                        if entity_config.get("hide", False):
                            return False, f"entity {entity_id} blocked by default"
                        # Check specific service restrictions
                        default_entity_services = entity_config.get("services", [])
                        if service in default_entity_services:
                            return False, f"entity {entity_id} service {service} blocked by default"
        
        return True, f"no default restrictions"
    
    # Get user's role
    user_role = user_config.get("role", "unknown")
    
    # Check entity-level restrictions first
    if service_data and "entity_id" in service_data:
        entity_id = service_data["entity_id"]
        if isinstance(entity_id, list):
            # Check all entities in the list
            for eid in entity_id:
                entity_result, entity_reason = _check_entity_access_with_reason(eid, service, user_config)
                if not entity_result:
                    return False, f"entity restriction: {entity_reason}"
        else:
            entity_result, entity_reason = _check_entity_access_with_reason(entity_id, service, user_config)
            if not entity_result:
                return False, f"entity restriction: {entity_reason}"
    
    # Check domain-level restrictions
    domain_result, domain_reason = _check_domain_access_with_reason(domain, service, user_config)
    if not domain_result:
        return False, f"domain restriction: {domain_reason}"
    
    # All users use allow model with restrictions (allow by default, deny specific services)
    restriction_result, restriction_reason = _check_restriction_access_with_reason(domain, service, service_data, user_config)
    if restriction_result:
        return False, f"service restriction: {restriction_reason}"
    
    return True, f"access granted"


def _check_service_access(
    domain: str,
    service: str,
    service_data: Optional[Dict[str, Any]],
    user_id: Optional[str],
    access_config: Dict[str, Any]
) -> bool:
    """Check if a user has access to a specific service call."""
    result, _ = _check_service_access_with_reason(domain, service, service_data, user_id, access_config)
    return result


def _check_entity_access_with_reason(entity_id: str, service: str, user_config: Dict[str, Any]) -> tuple[bool, str]:
    """Check if user has access to a specific entity service with detailed reason."""
    if not user_config:
        return True, f"no user config"
    
    restrictions = user_config.get("restrictions", {})
    entities = restrictions.get("entities", {})
    
    if entity_id in entities:
        entity_config = entities[entity_id]
        # If entity is hidden, hide all services
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
        # If domain is hidden, hide all services
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


