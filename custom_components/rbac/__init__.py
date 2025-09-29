"""RBAC Middleware for Home Assistant."""
import logging
import os
from typing import Any, Dict, Optional

import yaml

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.exceptions import HomeAssistantError
from homeassistant import config_entries

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rbac"


async def _load_access_control_config(hass: HomeAssistant) -> Dict[str, Any]:
    """Load access control configuration from YAML file."""
    config_path = os.path.join(hass.config.config_dir, "custom_components", "rbac", "access_control.yaml")
    
    def _load_file():
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            _LOGGER.warning(f"Access control configuration not found at {config_path}, using default allow-all")
            return {"default_access": "allow", "users": {}}
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
    
    user_count = len(access_config.get("users", {}))
    _LOGGER.info(f"RBAC Middleware initialized successfully with {user_count} configured users")
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up the RBAC middleware component from a config entry."""
    _LOGGER.info("Setting up RBAC Middleware from config entry")
    
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
    
    user_count = len(access_config.get("users", {}))
    _LOGGER.info(f"RBAC Middleware initialized successfully with {user_count} configured users")
    
    return True


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
                # Get user information
                user = None
                user_id = None
                
                if context and hasattr(context, 'user_id') and context.user_id:
                    user = await self._hass.auth.async_get_user(context.user_id)
                    user_id = context.user_id
                
                # Log the service call attempt
                user_name = user.name if user else "Unknown"
                _LOGGER.debug(f"Service call: {domain}.{service} by {user_name} (user_id: {user_id})")
                
                # Get access config
                access_config = self._hass.data[DOMAIN]["access_config"]
                
                # Check access permissions with detailed logging
                access_result, reason = _check_service_access_with_reason(domain, service, service_data, user_id, access_config)
                
                if not access_result:
                    _LOGGER.warning(
                        f"Access denied: {user_name} (user_id: {user_id}) attempted {domain}.{service} - {reason}"
                    )
                    
                    # Create persistent notification
                    try:
                        from homeassistant.components import persistent_notification
                        await persistent_notification.async_create(
                            self._hass,
                            f"Access denied: {user_name} attempted to call {domain}.{service} - {reason}",
                            title="RBAC Access Denied",
                            notification_id=f"rbac_denied_{domain}_{service}"
                        )
                    except Exception as e:
                        _LOGGER.error(f"Failed to create notification: {e}")
                    
                    # Raise exception to properly handle the denial
                    raise HomeAssistantError(
                        f"Access denied: {user_name} cannot call {domain}.{service} - {reason}"
                    )
                
                # Service is allowed, proceed with original call
                _LOGGER.warning(f"Service call allowed: {domain}.{service} by {user_name} - {reason}")
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
                default_services = default_domains[domain].get("services", [])
                if service in default_services:
                    return False, f"user {user_id} not in RBAC config but service {domain}.{service} is in default restrictions"
            
            # Check entity-level default restrictions
            if service_data and "entity_id" in service_data:
                entity_id = service_data["entity_id"]
                if isinstance(entity_id, list):
                    for eid in entity_id:
                        default_entities = default_restrictions.get("entities", {})
                        if eid in default_entities:
                            default_entity_services = default_entities[eid].get("services", [])
                            if service in default_entity_services:
                                return False, f"user {user_id} not in RBAC config but entity {eid} service {service} is in default restrictions"
                else:
                    default_entities = default_restrictions.get("entities", {})
                    if entity_id in default_entities:
                        default_entity_services = default_entities[entity_id].get("services", [])
                        if service in default_entity_services:
                            return False, f"user {user_id} not in RBAC config but entity {entity_id} service {service} is in default restrictions"
        
        return True, f"user {user_id} not in RBAC config (no default restrictions apply)"
    
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
    
    return True, f"user {user_id} ({user_role}) has access to {domain}.{service}"


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
    restrictions = user_config.get("restrictions", {})
    entities = restrictions.get("entities", {})
    
    if entity_id in entities:
        entity_config = entities[entity_id]
        services = entity_config.get("services", [])
        # If service is in restrictions list, deny access
        if service in services:
            return False, f"entity {entity_id} service {service} is restricted"
    
    return True, f"entity {entity_id} service {service} is allowed"


def _check_entity_access(entity_id: str, service: str, user_config: Dict[str, Any]) -> bool:
    """Check if user has access to a specific entity service."""
    result, _ = _check_entity_access_with_reason(entity_id, service, user_config)
    return result


def _check_domain_access_with_reason(domain: str, service: str, user_config: Dict[str, Any]) -> tuple[bool, str]:
    """Check if user has access to a domain service with detailed reason."""
    restrictions = user_config.get("restrictions", {})
    domains = restrictions.get("domains", {})
    
    if domain in domains:
        domain_config = domains[domain]
        services = domain_config.get("services", [])
        # If service is in restrictions list, deny access
        if service in services:
            return False, f"domain {domain} service {service} is restricted"
    
    return True, f"domain {domain} service {service} is allowed"


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
    restrictions = user_config.get("restrictions", {})
    domains = restrictions.get("domains", {})
    
    if domain in domains:
        domain_config = domains[domain]
        services = domain_config.get("services", [])
        # Return True if service is in restrictions list (should be denied)
        if service in services:
            return True, f"domain {domain} service {service} is in restrictions list"
    
    return False, f"domain {domain} service {service} is not restricted"


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
        if _save_access_control_config(hass, access_config):
            hass.data[DOMAIN]["access_config"] = access_config
            _LOGGER.info(f"Removed domain restriction for user '{user_id}': {domain}")
            return True
    
    return False
