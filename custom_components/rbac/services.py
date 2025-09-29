"""Services for the RBAC integration."""
import logging
import os
from typing import Any, Dict

import voluptuous as vol
import yaml

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from . import (
    DOMAIN, 
    get_user_config, 
    reload_access_config,
    _is_top_level_user,
    add_user_access,
    remove_user_access,
    update_user_role,
    add_user_restriction,
    remove_user_restriction
)

_LOGGER = logging.getLogger(__name__)

# Service schemas
GET_USER_CONFIG_SCHEMA = vol.Schema({
    vol.Required("user_id"): cv.string,
})

RELOAD_CONFIG_SCHEMA = vol.Schema({})

LIST_USERS_SCHEMA = vol.Schema({})

# User management schemas (restricted to top-level users)
ADD_USER_SCHEMA = vol.Schema({
    vol.Required("person"): cv.string,
    vol.Required("role"): vol.In(["guest", "user", "admin", "super_admin"]),
})

REMOVE_USER_SCHEMA = vol.Schema({
    vol.Required("person"): cv.string,
})

UPDATE_USER_ROLE_SCHEMA = vol.Schema({
    vol.Required("person"): cv.string,
    vol.Required("role"): vol.In(["guest", "user", "admin", "super_admin"]),
})

ADD_USER_RESTRICTION_SCHEMA = vol.Schema({
    vol.Required("person"): cv.string,
    vol.Required("domain"): cv.string,
    vol.Required("services"): vol.Any(cv.ensure_list, cv.string),
})

REMOVE_USER_RESTRICTION_SCHEMA = vol.Schema({
    vol.Required("person"): cv.string,
    vol.Required("domain"): cv.string,
})


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the RBAC services."""
    
    async def handle_get_user_config(call: ServiceCall) -> None:
        """Handle the get_user_config service call."""
        user_id = call.data["user_id"]
        user_config = get_user_config(hass, user_id)
        
        if user_config:
            _LOGGER.info(f"User '{user_id}' configuration: {user_config}")
            message = f"User '{user_id}' configuration:\n{yaml.dump(user_config, default_flow_style=False, indent=2)}"
        else:
            _LOGGER.info(f"User '{user_id}' not found in configuration (has full access)")
            message = f"User '{user_id}' not found in configuration (has full access)"
        
        # Create notification
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC User Configuration"
        )
    
    async def handle_reload_config(call: ServiceCall) -> None:
        """Handle the reload_config service call."""
        success = await reload_access_config(hass)
        
        if success:
            _LOGGER.info("Access control configuration reloaded successfully")
            message = "Access control configuration reloaded successfully"
        else:
            _LOGGER.error("Failed to reload access control configuration")
            message = "Failed to reload access control configuration"
        
        # Create notification
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC Configuration Reload"
        )
    
    async def handle_list_users(call: ServiceCall) -> None:
        """Handle the list_users service call."""
        if DOMAIN not in hass.data:
            users = {}
        else:
            access_config = hass.data[DOMAIN].get("access_config", {})
            users = access_config.get("users", {})
        
        _LOGGER.info(f"Configured users: {list(users.keys())}")
        
        # Create notification
        if users:
            message = "Configured users:\n"
            for user_id, user_config in users.items():
                role = user_config.get("role", "unknown")
                access = user_config.get("access", "allow")
                message += f"  {user_id}: role={role}, access={access}\n"
        else:
            message = "No users configured (all users have full access)"
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC Users"
        )
    
    async def handle_add_user(call: ServiceCall) -> None:
        """Handle the add_user service call."""
        person_entity_id = call.data["person"]
        role = call.data["role"]
        
        # Extract user_id from person entity
        try:
            person_state = hass.states.get(person_entity_id)
            if not person_state:
                _LOGGER.error(f"Person entity {person_entity_id} not found")
                await hass.components.persistent_notification.async_create(
                    f"Person entity {person_entity_id} not found",
                    title="RBAC Error"
                )
                return
            
            user_id = person_state.attributes.get("user_id")
            if not user_id:
                _LOGGER.error(f"No user_id found for person {person_entity_id}")
                await hass.components.persistent_notification.async_create(
                    f"No user_id found for person {person_entity_id}",
                    title="RBAC Error"
                )
                return
        except Exception as e:
            _LOGGER.error(f"Error extracting user_id from person {person_entity_id}: {e}")
            await hass.components.persistent_notification.async_create(
                f"Error extracting user_id from person {person_entity_id}: {e}",
                title="RBAC Error"
            )
            return
        
        # Check if caller has top-level access
        caller_id = call.context.user_id if call.context else None
        if not caller_id or not _is_top_level_user(hass, caller_id):
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to add user {user_id}")
            await hass.components.persistent_notification.async_create(
                f"Access denied: Only admin users can add users",
                title="RBAC Access Denied"
            )
            return
        
        success = await add_user_access(hass, user_id, role)
        
        if success:
            _LOGGER.info(f"Added user '{user_id}' with role '{role}'")
            message = f"Successfully added user '{user_id}' with role '{role}'"
        else:
            _LOGGER.error(f"Failed to add user '{user_id}'")
            message = f"Failed to add user '{user_id}'"
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC User Management"
        )
    
    async def handle_remove_user(call: ServiceCall) -> None:
        """Handle the remove_user service call."""
        person_entity_id = call.data["person"]
        
        # Extract user_id from person entity
        try:
            person_state = hass.states.get(person_entity_id)
            if not person_state:
                _LOGGER.error(f"Person entity {person_entity_id} not found")
                await hass.components.persistent_notification.async_create(
                    f"Person entity {person_entity_id} not found",
                    title="RBAC Error"
                )
                return
            
            user_id = person_state.attributes.get("user_id")
            if not user_id:
                _LOGGER.error(f"No user_id found for person {person_entity_id}")
                await hass.components.persistent_notification.async_create(
                    f"No user_id found for person {person_entity_id}",
                    title="RBAC Error"
                )
                return
        except Exception as e:
            _LOGGER.error(f"Error extracting user_id from person {person_entity_id}: {e}")
            await hass.components.persistent_notification.async_create(
                f"Error extracting user_id from person {person_entity_id}: {e}",
                title="RBAC Error"
            )
            return
        
        # Check if caller has top-level access
        caller_id = call.context.user_id if call.context else None
        if not caller_id or not _is_top_level_user(hass, caller_id):
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to remove user {user_id}")
            await hass.components.persistent_notification.async_create(
                f"Access denied: Only admin users can remove users",
                title="RBAC Access Denied"
            )
            return
        
        success = await remove_user_access(hass, user_id)
        
        if success:
            _LOGGER.info(f"Removed user '{user_id}' from access control")
            message = f"Successfully removed user '{user_id}' from access control"
        else:
            _LOGGER.error(f"Failed to remove user '{user_id}' or user not found")
            message = f"Failed to remove user '{user_id}' or user not found"
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC User Management"
        )
    
    async def handle_update_user_role(call: ServiceCall) -> None:
        """Handle the update_user_role service call."""
        person_entity_id = call.data["person"]
        role = call.data["role"]
        
        # Extract user_id from person entity
        try:
            person_state = hass.states.get(person_entity_id)
            if not person_state:
                _LOGGER.error(f"Person entity {person_entity_id} not found")
                await hass.components.persistent_notification.async_create(
                    f"Person entity {person_entity_id} not found",
                    title="RBAC Error"
                )
                return
            
            user_id = person_state.attributes.get("user_id")
            if not user_id:
                _LOGGER.error(f"No user_id found for person {person_entity_id}")
                await hass.components.persistent_notification.async_create(
                    f"No user_id found for person {person_entity_id}",
                    title="RBAC Error"
                )
                return
        except Exception as e:
            _LOGGER.error(f"Error extracting user_id from person {person_entity_id}: {e}")
            await hass.components.persistent_notification.async_create(
                f"Error extracting user_id from person {person_entity_id}: {e}",
                title="RBAC Error"
            )
            return
        
        # Check if caller has top-level access
        caller_id = call.context.user_id if call.context else None
        if not caller_id or not _is_top_level_user(hass, caller_id):
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to update user {user_id}")
            await hass.components.persistent_notification.async_create(
                f"Access denied: Only admin users can update user roles",
                title="RBAC Access Denied"
            )
            return
        
        success = await update_user_role(hass, user_id, role)
        
        if success:
            _LOGGER.info(f"Updated user '{user_id}' role to '{role}'")
            message = f"Successfully updated user '{user_id}' role to '{role}'"
        else:
            _LOGGER.error(f"Failed to update user '{user_id}' role or user not found")
            message = f"Failed to update user '{user_id}' role or user not found"
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC User Management"
        )
    
    async def handle_add_user_restriction(call: ServiceCall) -> None:
        """Handle the add_user_restriction service call."""
        person_entity_id = call.data["person"]
        domain = call.data["domain"]
        services = call.data["services"]
        
        # Extract user_id from person entity
        try:
            person_state = hass.states.get(person_entity_id)
            if not person_state:
                _LOGGER.error(f"Person entity {person_entity_id} not found")
                await hass.components.persistent_notification.async_create(
                    f"Person entity {person_entity_id} not found",
                    title="RBAC Error"
                )
                return
            
            user_id = person_state.attributes.get("user_id")
            if not user_id:
                _LOGGER.error(f"No user_id found for person {person_entity_id}")
                await hass.components.persistent_notification.async_create(
                    f"No user_id found for person {person_entity_id}",
                    title="RBAC Error"
                )
                return
        except Exception as e:
            _LOGGER.error(f"Error extracting user_id from person {person_entity_id}: {e}")
            await hass.components.persistent_notification.async_create(
                f"Error extracting user_id from person {person_entity_id}: {e}",
                title="RBAC Error"
            )
            return
        
        # Convert single service to list if needed
        if isinstance(services, str):
            services = [services]
        
        # Check if caller has top-level access
        caller_id = call.context.user_id if call.context else None
        if not caller_id or not _is_top_level_user(hass, caller_id):
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to add restriction for user {user_id}")
            await hass.components.persistent_notification.async_create(
                f"Access denied: Only admin users can add user restrictions",
                title="RBAC Access Denied"
            )
            return
        
        success = await add_user_restriction(hass, user_id, domain, services)
        
        if success:
            _LOGGER.info(f"Added restriction for user '{user_id}': {domain}.{services}")
            message = f"Successfully added restriction for user '{user_id}': {domain}.{services}"
        else:
            _LOGGER.error(f"Failed to add restriction for user '{user_id}' or user not found")
            message = f"Failed to add restriction for user '{user_id}' or user not found"
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC User Management"
        )
    
    async def handle_remove_user_restriction(call: ServiceCall) -> None:
        """Handle the remove_user_restriction service call."""
        person_entity_id = call.data["person"]
        domain = call.data["domain"]
        
        # Extract user_id from person entity
        try:
            person_state = hass.states.get(person_entity_id)
            if not person_state:
                _LOGGER.error(f"Person entity {person_entity_id} not found")
                await hass.components.persistent_notification.async_create(
                    f"Person entity {person_entity_id} not found",
                    title="RBAC Error"
                )
                return
            
            user_id = person_state.attributes.get("user_id")
            if not user_id:
                _LOGGER.error(f"No user_id found for person {person_entity_id}")
                await hass.components.persistent_notification.async_create(
                    f"No user_id found for person {person_entity_id}",
                    title="RBAC Error"
                )
                return
        except Exception as e:
            _LOGGER.error(f"Error extracting user_id from person {person_entity_id}: {e}")
            await hass.components.persistent_notification.async_create(
                f"Error extracting user_id from person {person_entity_id}: {e}",
                title="RBAC Error"
            )
            return
        
        # Check if caller has top-level access
        caller_id = call.context.user_id if call.context else None
        if not caller_id or not _is_top_level_user(hass, caller_id):
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to remove restriction for user {user_id}")
            await hass.components.persistent_notification.async_create(
                f"Access denied: Only admin users can remove user restrictions",
                title="RBAC Access Denied"
            )
            return
        
        success = await remove_user_restriction(hass, user_id, domain)
        
        if success:
            _LOGGER.info(f"Removed restriction for user '{user_id}': {domain}")
            message = f"Successfully removed restriction for user '{user_id}': {domain}"
        else:
            _LOGGER.error(f"Failed to remove restriction for user '{user_id}' or restriction not found")
            message = f"Failed to remove restriction for user '{user_id}' or restriction not found"
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC User Management"
        )
    
    # Register services
    hass.services.async_register(
        DOMAIN, "get_user_config", handle_get_user_config, schema=GET_USER_CONFIG_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "reload_config", handle_reload_config, schema=RELOAD_CONFIG_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "list_users", handle_list_users, schema=LIST_USERS_SCHEMA
    )
    
    # User management services (restricted to top-level users)
    hass.services.async_register(
        DOMAIN, "add_user", handle_add_user, schema=ADD_USER_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "remove_user", handle_remove_user, schema=REMOVE_USER_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "update_user_role", handle_update_user_role, schema=UPDATE_USER_ROLE_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "add_user_restriction", handle_add_user_restriction, schema=ADD_USER_RESTRICTION_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "remove_user_restriction", handle_remove_user_restriction, schema=REMOVE_USER_RESTRICTION_SCHEMA
    )
    
    _LOGGER.info("RBAC services registered successfully")
