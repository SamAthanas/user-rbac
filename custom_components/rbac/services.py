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
    _is_builtin_ha_user,
    add_user_access,
    remove_user_access,
    update_user_role,
    add_user_restriction,
    remove_user_restriction,
    _save_access_control_config
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

# New service schemas for device management
UPDATE_USER_DOMAIN_RESTRICTIONS_SCHEMA = vol.Schema({
    vol.Required("person"): cv.string,
    vol.Optional("domains"): vol.Any(dict, None),
})

UPDATE_USER_ENTITY_RESTRICTIONS_SCHEMA = vol.Schema({
    vol.Required("person"): cv.string,
    vol.Optional("entities"): vol.Any(dict, None),
})

UPDATE_USER_SERVICE_RESTRICTIONS_SCHEMA = vol.Schema({
    vol.Required("person"): cv.string,
    vol.Required("domain"): cv.string,
    vol.Optional("services"): vol.Any(dict, None),
})

GET_AVAILABLE_DOMAINS_SCHEMA = vol.Schema({})

GET_AVAILABLE_ENTITIES_SCHEMA = vol.Schema({})

GET_AVAILABLE_SERVICES_SCHEMA = vol.Schema({
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
    
    async def handle_update_user_domain_restrictions(call: ServiceCall) -> None:
        """Handle the update_user_domain_restrictions service call."""
        person_entity_id = call.data["person"]
        domains = call.data.get("domains", {})
        
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
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to update domain restrictions for user {user_id}")
            await hass.components.persistent_notification.async_create(
                f"Access denied: Only admin users can update domain restrictions",
                title="RBAC Access Denied"
            )
            return
        
        # Update access control configuration
        if DOMAIN not in hass.data:
            await hass.components.persistent_notification.async_create(
                "RBAC not initialized",
                title="RBAC Error"
            )
            return
        
        access_config = hass.data[DOMAIN]["access_config"]
        users = access_config.get("users", {})
        
        if user_id not in users:
            await hass.components.persistent_notification.async_create(
                f"User '{user_id}' not found in configuration",
                title="RBAC Error"
            )
            return
        
        user_config = users[user_id]
        if "restrictions" not in user_config:
            user_config["restrictions"] = {}
        
        user_config["restrictions"]["domains"] = domains
        
        # Save configuration
        success = await _save_access_control_config(hass, access_config)
        
        if success:
            hass.data[DOMAIN]["access_config"] = access_config
            _LOGGER.info(f"Updated domain restrictions for user '{user_id}': {domains}")
            message = f"Successfully updated domain restrictions for user '{user_id}'"
        else:
            _LOGGER.error(f"Failed to update domain restrictions for user '{user_id}'")
            message = f"Failed to update domain restrictions for user '{user_id}'"
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC Domain Restrictions"
        )
    
    async def handle_update_user_entity_restrictions(call: ServiceCall) -> None:
        """Handle the update_user_entity_restrictions service call."""
        person_entity_id = call.data["person"]
        entities = call.data.get("entities", {})
        
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
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to update entity restrictions for user {user_id}")
            await hass.components.persistent_notification.async_create(
                f"Access denied: Only admin users can update entity restrictions",
                title="RBAC Access Denied"
            )
            return
        
        # Update access control configuration
        if DOMAIN not in hass.data:
            await hass.components.persistent_notification.async_create(
                "RBAC not initialized",
                title="RBAC Error"
            )
            return
        
        access_config = hass.data[DOMAIN]["access_config"]
        users = access_config.get("users", {})
        
        if user_id not in users:
            await hass.components.persistent_notification.async_create(
                f"User '{user_id}' not found in configuration",
                title="RBAC Error"
            )
            return
        
        user_config = users[user_id]
        if "restrictions" not in user_config:
            user_config["restrictions"] = {}
        
        user_config["restrictions"]["entities"] = entities
        
        # Save configuration
        success = await _save_access_control_config(hass, access_config)
        
        if success:
            hass.data[DOMAIN]["access_config"] = access_config
            _LOGGER.info(f"Updated entity restrictions for user '{user_id}': {entities}")
            message = f"Successfully updated entity restrictions for user '{user_id}'"
        else:
            _LOGGER.error(f"Failed to update entity restrictions for user '{user_id}'")
            message = f"Failed to update entity restrictions for user '{user_id}'"
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC Entity Restrictions"
        )
    
    async def handle_update_user_service_restrictions(call: ServiceCall) -> None:
        """Handle the update_user_service_restrictions service call."""
        person_entity_id = call.data["person"]
        domain = call.data["domain"]
        services = call.data.get("services", {})
        
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
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to update service restrictions for user {user_id}")
            await hass.components.persistent_notification.async_create(
                f"Access denied: Only admin users can update service restrictions",
                title="RBAC Access Denied"
            )
            return
        
        # Update access control configuration
        if DOMAIN not in hass.data:
            await hass.components.persistent_notification.async_create(
                "RBAC not initialized",
                title="RBAC Error"
            )
            return
        
        access_config = hass.data[DOMAIN]["access_config"]
        users = access_config.get("users", {})
        
        if user_id not in users:
            await hass.components.persistent_notification.async_create(
                f"User '{user_id}' not found in configuration",
                title="RBAC Error"
            )
            return
        
        user_config = users[user_id]
        if "restrictions" not in user_config:
            user_config["restrictions"] = {}
        if "domains" not in user_config["restrictions"]:
            user_config["restrictions"]["domains"] = {}
        
        user_config["restrictions"]["domains"][domain] = services
        
        # Save configuration
        success = await _save_access_control_config(hass, access_config)
        
        if success:
            hass.data[DOMAIN]["access_config"] = access_config
            _LOGGER.info(f"Updated service restrictions for user '{user_id}' domain '{domain}': {services}")
            message = f"Successfully updated service restrictions for user '{user_id}' domain '{domain}'"
        else:
            _LOGGER.error(f"Failed to update service restrictions for user '{user_id}' domain '{domain}'")
            message = f"Failed to update service restrictions for user '{user_id}' domain '{domain}'"
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC Service Restrictions"
        )
    
    async def handle_get_available_domains(call: ServiceCall) -> None:
        """Handle the get_available_domains service call."""
        # Check if caller has top-level access
        caller_id = call.context.user_id if call.context else None
        if not caller_id or not _is_top_level_user(hass, caller_id):
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to get available domains")
            await hass.components.persistent_notification.async_create(
                f"Access denied: Only admin users can get available domains",
                title="RBAC Access Denied"
            )
            return
        
        # Get all domains from states
        all_states = hass.states.async_all()
        domains = set()
        
        for state in all_states:
            domain = state.entity_id.split('.')[0]
            domains.add(domain)
        
        domains_list = sorted(list(domains))
        
        _LOGGER.info(f"Available domains: {domains_list}")
        message = f"Available domains ({len(domains_list)}):\n" + "\n".join(domains_list)
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC Available Domains"
        )
    
    async def handle_get_available_entities(call: ServiceCall) -> None:
        """Handle the get_available_entities service call."""
        # Check if caller has top-level access
        caller_id = call.context.user_id if call.context else None
        if not caller_id or not _is_top_level_user(hass, caller_id):
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to get available entities")
            await hass.components.persistent_notification.async_create(
                f"Access denied: Only admin users can get available entities",
                title="RBAC Access Denied"
            )
            return
        
        # Get all entities from states
        all_states = hass.states.async_all()
        entities = [state.entity_id for state in all_states]
        
        entities_list = sorted(entities)
        
        _LOGGER.info(f"Available entities: {len(entities_list)} total")
        message = f"Available entities ({len(entities_list)}):\n" + "\n".join(entities_list[:50])  # Limit to first 50
        if len(entities_list) > 50:
            message += f"\n... and {len(entities_list) - 50} more"
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC Available Entities"
        )
    
    async def handle_get_available_services(call: ServiceCall) -> None:
        """Handle the get_available_services service call."""
        domain = call.data["domain"]
        
        # Check if caller has top-level access
        caller_id = call.context.user_id if call.context else None
        if not caller_id or not _is_top_level_user(hass, caller_id):
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to get available services for domain {domain}")
            await hass.components.persistent_notification.async_create(
                f"Access denied: Only admin users can get available services",
                title="RBAC Access Denied"
            )
            return
        
        # Get services for the domain
        try:
            services = hass.services.services_for_domain(domain)
            services_list = sorted(list(services.keys()))
            
            _LOGGER.info(f"Available services for domain '{domain}': {services_list}")
            message = f"Available services for domain '{domain}' ({len(services_list)}):\n" + "\n".join(services_list)
        except Exception as e:
            _LOGGER.error(f"Error getting services for domain '{domain}': {e}")
            message = f"Error getting services for domain '{domain}': {e}"
        
        await hass.components.persistent_notification.async_create(
            message,
            title="RBAC Available Services"
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
    
    # New device management services
    hass.services.async_register(
        DOMAIN, "update_user_domain_restrictions", handle_update_user_domain_restrictions, schema=UPDATE_USER_DOMAIN_RESTRICTIONS_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "update_user_entity_restrictions", handle_update_user_entity_restrictions, schema=UPDATE_USER_ENTITY_RESTRICTIONS_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "update_user_service_restrictions", handle_update_user_service_restrictions, schema=UPDATE_USER_SERVICE_RESTRICTIONS_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "get_available_domains", handle_get_available_domains, schema=GET_AVAILABLE_DOMAINS_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "get_available_entities", handle_get_available_entities, schema=GET_AVAILABLE_ENTITIES_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "get_available_services", handle_get_available_services, schema=GET_AVAILABLE_SERVICES_SCHEMA
    )
    
    _LOGGER.info("RBAC services registered successfully")

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
import json
import logging

_LOGGER = logging.getLogger(__name__)


def _is_admin_user(hass: HomeAssistant, user_id: str) -> bool:
    """Check if a user is an admin or if there are no admins configured."""
    try:
        access_config = hass.data.get(DOMAIN, {}).get("access_config", {})
        users = access_config.get("users", {})
        
        # Check if there are any admins configured
        has_admins = any(role == "admin" for role in users.values())
        
        # If no admins are configured, allow access to anyone
        if not has_admins:
            return True
        
        # If admins exist, check if current user is admin
        user_role = users.get(user_id, "unknown")
        return user_role == "admin"
        
    except Exception as e:
        _LOGGER.error(f"Error checking admin status: {e}")
        return False


class RBACConfigView(HomeAssistantView):
    """Handle RBAC configuration API requests."""

    url = "/api/rbac/config"
    name = "api:rbac:config"
    requires_auth = True

    async def get(self, request):
        """Get current RBAC configuration."""
        hass = request.app["hass"]
        user = request["hass_user"]
        
        try:
            # Check admin permissions
            if not _is_admin_user(hass, user.id):
                return self.json({
                    "error": "Admin access required",
                    "message": "Only administrators can access RBAC configuration",
                    "redirect_url": "/"
                }, status_code=403)
            
            # Load configuration directly from the YAML file
            from . import _load_access_control_config
            access_config = await _load_access_control_config(hass)
            
            # Return the configuration as-is for role-based management
            return self.json(access_config)
        except Exception as e:
            _LOGGER.error(f"Error getting RBAC config: {e}")
            return self.json({"error": str(e)}, status_code=500)

    async def post(self, request):
        """Update RBAC configuration."""
        hass = request.app["hass"]
        user = request["hass_user"]
        
        # Check admin permissions
        if not _is_admin_user(hass, user.id):
            return self.json({
                "error": "Admin access required",
                "message": "Only administrators can modify RBAC configuration",
                "redirect_url": "/"
            }, status_code=403)
        
        try:
            data = await request.json()
            action = data.get("action")
            
            if not action:
                return self.json({"error": "Missing action"}, status_code=400)
            
            # Load current configuration from YAML file
            from . import _load_access_control_config, _save_access_control_config
            access_config = await _load_access_control_config(hass)
            
            if action == "update_role":
                role_name = data.get("roleName")
                role_config = data.get("roleConfig")
                
                if not role_name or not role_config:
                    return self.json({"error": "Missing roleName or roleConfig"}, status_code=400)
                
                # Update or create role
                if "roles" not in access_config:
                    access_config["roles"] = {}
                access_config["roles"][role_name] = role_config
                
            elif action == "delete_role":
                role_name = data.get("roleName")
                
                if not role_name:
                    return self.json({"error": "Missing roleName"}, status_code=400)
                
                # Delete role
                if "roles" in access_config and role_name in access_config["roles"]:
                    del access_config["roles"][role_name]
                    
                # Remove role from users
                if "users" in access_config:
                    for user_id, user_config in access_config["users"].items():
                        if user_config.get("role") == role_name:
                            user_config["role"] = "user"  # Default role
                            
            elif action == "assign_user_role":
                user_id = data.get("userId")
                role_name = data.get("roleName")
                
                if not user_id or not role_name:
                    return self.json({"error": "Missing userId or roleName"}, status_code=400)
                
                # Assign role to user
                if "users" not in access_config:
                    access_config["users"] = {}
                if user_id not in access_config["users"]:
                    access_config["users"][user_id] = {}
                access_config["users"][user_id]["role"] = role_name
                
            elif action == "update_default_restrictions":
                restrictions = data.get("restrictions")
                
                if not restrictions:
                    return self.json({"error": "Missing restrictions"}, status_code=400)
                
                # Update default restrictions
                access_config["default_restrictions"] = restrictions
                
            # Save configuration back to YAML file
            success = await _save_access_control_config(hass, access_config)
            
            if success:
                # Update the in-memory config as well
                hass.data[DOMAIN]["access_config"] = access_config
                return self.json({"success": True})
            else:
                return self.json({"error": "Failed to save configuration"}, status_code=500)
                
        except Exception as e:
            _LOGGER.error(f"Error updating RBAC config: {e}")
            return self.json({"error": str(e)}, status_code=500)


class RBACUsersView(HomeAssistantView):
    """Handle RBAC users API requests."""

    url = "/api/rbac/users"
    name = "api:rbac:users"
    requires_auth = True

    async def get(self, request):
        """Get all users with their profile pictures."""
        hass = request.app["hass"]
        user = request["hass_user"]
        
        # Check admin permissions
        if not _is_admin_user(hass, user.id):
            return self.json({
                "error": "Admin access required",
                "message": "Only administrators can access user information",
                "redirect_url": "/"
            }, status_code=403)
        
        try:
            users = []
            for user_id in hass.auth._store._users:
                try:
                    user = await hass.auth.async_get_user(user_id)
                    if user:
                        # Skip built-in Home Assistant users (those without person entities)
                        if _is_builtin_ha_user(user_id, hass):
                            _LOGGER.debug(f"Skipping built-in HA user: {user_id} ({user.name})")
                            continue
                        
                        # Try to find the person entity for this user
                        entity_picture = None
                        person_entity_id = None
                        
                        # Look for person entities that match this user
                        all_states = hass.states.async_all()
                        for state in all_states:
                            if state.entity_id.startswith('person.'):
                                # Check if this person entity belongs to this user
                                if hasattr(state, 'attributes') and 'user_id' in state.attributes:
                                    if state.attributes['user_id'] == user_id:
                                        person_entity_id = state.entity_id
                                        # Get the entity_picture from the person entity
                                        if 'entity_picture' in state.attributes:
                                            entity_picture = state.attributes['entity_picture']
                                        break
                        
                        user_data = {
                            "id": user.id,
                            "name": user.name or f"User {user.id[:8]}",
                            "entity_picture": entity_picture,
                            "person_entity_id": person_entity_id
                        }
                        
                        users.append(user_data)
                        
                except Exception as e:
                    _LOGGER.debug(f"Could not get user {user_id}: {e}")
            
            return self.json(users)
        except Exception as e:
            _LOGGER.error(f"Error getting users: {e}")
            return self.json({"error": str(e)}, status_code=500)


class RBACDomainsView(HomeAssistantView):
    """Handle RBAC domains API requests."""

    url = "/api/rbac/domains"
    name = "api:rbac:domains"
    requires_auth = True

    async def get(self, request):
        """Get all available domains."""
        hass = request.app["hass"]
        user = request["hass_user"]
        
        # Check admin permissions
        if not _is_admin_user(hass, user.id):
            return self.json({
                "error": "Admin access required",
                "message": "Only administrators can access domain information",
                "redirect_url": "/"
            }, status_code=403)
        
        try:
            domains = set()
            
            # Get domains from entities
            all_states = hass.states.async_all()
            for state in all_states:
                domain = state.entity_id.split('.')[0]
                domains.add(domain)
            
            # Get domains from services (including domains that have no entities)
            for domain in hass.services.async_services().keys():
                domains.add(domain)
            
            return self.json(sorted(list(domains)))
        except Exception as e:
            _LOGGER.error(f"Error getting domains: {e}")
            return self.json({"error": str(e)}, status_code=500)


class RBACEntitiesView(HomeAssistantView):
    """Handle RBAC entities API requests."""

    url = "/api/rbac/entities"
    name = "api:rbac:entities"
    requires_auth = True

    async def get(self, request):
        """Get all available entities."""
        hass = request.app["hass"]
        user = request["hass_user"]
        
        # Check admin permissions
        if not _is_admin_user(hass, user.id):
            return self.json({
                "error": "Admin access required",
                "message": "Only administrators can access entity information",
                "redirect_url": "/"
            }, status_code=403)
        
        try:
            all_states = hass.states.async_all()
            entities = [state.entity_id for state in all_states]
            
            return self.json(sorted(entities))
        except Exception as e:
            _LOGGER.error(f"Error getting entities: {e}")
            return self.json({"error": str(e)}, status_code=500)


class RBACServicesView(HomeAssistantView):
    """Handle RBAC services API requests."""

    url = "/api/rbac/services"
    name = "api:rbac:services"
    requires_auth = True

    async def get(self, request):
        """Get all available services organized by domain and entity."""
        hass = request.app["hass"]
        user = request["hass_user"]
        
        # Check admin permissions
        if not _is_admin_user(hass, user.id):
            return self.json({
                "error": "Admin access required",
                "message": "Only administrators can access service information",
                "redirect_url": "/"
            }, status_code=403)
        
        try:
            services_by_domain = {}
            services_by_entity = {}
            
            # Get services by domain
            for domain, service_dict in hass.services.async_services().items():
                services_by_domain[domain] = list(service_dict.keys())
            
            # Get services by entity (for entities that have specific services)
            all_states = hass.states.async_all()
            for state in all_states:
                entity_id = state.entity_id
                domain = entity_id.split('.')[0]
                
                # Get services for this specific entity
                entity_services = []
                if domain in hass.services.async_services():
                    entity_services = list(hass.services.async_services()[domain].keys())
                
                if entity_services:
                    services_by_entity[entity_id] = entity_services
            
            return self.json({
                "domains": services_by_domain,
                "entities": services_by_entity
            })
        except Exception as e:
            _LOGGER.error(f"Error getting services: {e}")
            return self.json({"error": str(e)}, status_code=500)


class RBACCurrentUserView(HomeAssistantView):
    """View to get current user information."""
    
    url = "/api/rbac/current-user"
    name = "api:rbac:current-user"
    requires_auth = True
    
    async def get(self, request):
        """Get current user information."""
        try:
            hass = request.app["hass"]
            user = request["hass_user"]
            
            # Get user's role from access control config
            access_config = hass.data.get(DOMAIN, {}).get("access_config", {})
            users = access_config.get("users", {})
            user_role = users.get(user.id, "unknown")
            
            # Get entity_picture from person entity (same logic as users API)
            entity_picture = None
            person_entity_id = None
            
            # Look for person entities associated with this user
            for state in hass.states.async_all():
                if state.domain == "person" and state.attributes.get("user_id") == user.id:
                    person_entity_id = state.entity_id
                    # Get the entity_picture from the person entity
                    if 'entity_picture' in state.attributes:
                        entity_picture = state.attributes['entity_picture']
                    break
            
            return self.json({
                "id": user.id,
                "name": user.name,
                "role": user_role,
                "is_admin": user.is_admin,
                "is_owner": user.is_owner,
                "entity_picture": entity_picture,
                "person_entity_id": person_entity_id
            })
        except Exception as e:
            _LOGGER.error(f"Error getting current user: {e}")
            return self.json({"error": str(e)}, status_code=500)
