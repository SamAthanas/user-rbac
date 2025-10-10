"""Services for the RBAC integration."""
import logging
import os
import mimetypes
from typing import Any, Dict

import voluptuous as vol
import yaml

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util.json import JsonObjectType
from homeassistant.components.http import HomeAssistantView
from aiohttp import web

from . import (
    DOMAIN, 
    get_user_config, 
    reload_access_config,
    _is_top_level_user,
    _is_builtin_ha_user,
    add_user_access,
    remove_user_access,
    update_user_role,
    remove_user_restriction,
    _save_access_control_config
)

_LOGGER = logging.getLogger(__name__)

def _get_available_roles(hass: HomeAssistant) -> list:
    """Get available roles from access control configuration."""
    if DOMAIN not in hass.data:
        return ["guest", "user", "admin", "super_admin"]  # Default roles
    
    access_config = hass.data[DOMAIN].get("access_config", {})
    roles = list(access_config.get("roles", {}).keys())
    
    # If no roles defined, use default roles
    if not roles:
        roles = ["guest", "user", "admin", "super_admin"]
    
    return roles

def _validate_role(hass: HomeAssistant, role: str) -> bool:
    """Validate if a role is available in the access control configuration."""
    available_roles = _get_available_roles(hass)
    return role in available_roles

# Service schemas
GET_USER_CONFIG_SCHEMA = vol.Schema({
    vol.Required("person"): cv.string,
})

RELOAD_CONFIG_SCHEMA = vol.Schema({})

LIST_USERS_SCHEMA = vol.Schema({})

# User management schemas (restricted to top-level users)
ADD_USER_SCHEMA = vol.Schema({
    vol.Required("person"): cv.string,
    vol.Required("role"): cv.string,
})

GET_AVAILABLE_ROLES_SCHEMA = vol.Schema({})


def _create_guest_dashboard(hass: HomeAssistant, guest_id: str) -> bool:
    """Create dashboard directory and empty dashboard.yml for a guest user."""
    try:
        www_path = os.path.join(hass.config.config_dir, "custom_components", "rbac", "www")
        dashboards_path = os.path.join(www_path, "dashboards")
        guest_dashboard_path = os.path.join(dashboards_path, guest_id)
        
        # Create guest dashboard directory
        os.makedirs(guest_dashboard_path, exist_ok=True)
        
        # Create empty dashboard.yml file
        dashboard_yml_path = os.path.join(guest_dashboard_path, "dashboard.yml")
        if not os.path.exists(dashboard_yml_path):
            empty_dashboard = {"cards": []}
            with open(dashboard_yml_path, 'w', encoding='utf-8') as f:
                yaml.dump(empty_dashboard, f, default_flow_style=False, indent=2)
            
            _LOGGER.info(f"Created empty dashboard for guest user: {guest_id}")
            return True
        
        return True
    except Exception as e:
        _LOGGER.error(f"Error creating dashboard for guest user {guest_id}: {e}")
        return False


def _remove_guest_dashboard(hass: HomeAssistant, guest_id: str) -> bool:
    """Remove dashboard directory and files for a guest user."""
    try:
        www_path = os.path.join(hass.config.config_dir, "custom_components", "rbac", "www")
        dashboards_path = os.path.join(www_path, "dashboards")
        guest_dashboard_path = os.path.join(dashboards_path, guest_id)
        
        # Remove guest dashboard directory and all contents
        if os.path.exists(guest_dashboard_path):
            import shutil
            shutil.rmtree(guest_dashboard_path)
            _LOGGER.info(f"Removed dashboard for guest user: {guest_id}")
            return True
        
        return True
    except Exception as e:
        _LOGGER.error(f"Error removing dashboard for guest user {guest_id}: {e}")
        return False


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the RBAC services."""
    
    async def handle_get_user_config(call: ServiceCall) -> ServiceResponse:
        """Handle the get_user_config service call."""
        person_entity_id = call.data.get("person", "")
        
        # Extract user_id from person entity
        try:
            person_state = hass.states.get(person_entity_id)
            if not person_state:
                raise HomeAssistantError(f"Person entity {person_entity_id} not found")
            
            user_id = person_state.attributes.get("user_id")
            if not user_id:
                raise HomeAssistantError(f"No user_id found for person {person_entity_id}")
        except Exception as e:
            _LOGGER.error(f"Error extracting user_id from person {person_entity_id}: {e}")
            raise HomeAssistantError(f"Error extracting user_id from person {person_entity_id}: {e}")
        
        user_config = get_user_config(hass, user_id)
        
        if user_config:
            _LOGGER.info(f"User '{user_id}' configuration: {user_config}")
            response_data: JsonObjectType = {
                "success": True,
                "user_id": user_id,
                "config": user_config,
                "message": f"User '{user_id}' configuration retrieved successfully"
            }
        else:
            _LOGGER.info(f"User '{user_id}' not found in configuration (has full access)")
            response_data: JsonObjectType = {
                "success": True,
                "user_id": user_id,
                "config": None,
                "message": f"User '{user_id}' not found in configuration (has full access)"
            }
        
        # Fire event with the data
        hass.bus.async_fire("rbac_service_response", {
            "service": "get_user_config",
            "data": response_data
        })
        
        return response_data

    async def handle_reload_config(call: ServiceCall) -> Dict[str, Any]:
        """Handle the reload_config service call."""
        # Check if caller has top-level access
        caller_id = call.context.user_id if call.context else None
        if not caller_id or not _is_top_level_user(hass, caller_id):
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to reload config")
            return {
                "success": False,
                "message": "Access denied: Only admin users can reload configuration"
            }
        
        success = await reload_access_config(hass)
        
        if success:
            _LOGGER.info("Access control configuration reloaded successfully")
            return {
                "success": True,
                "message": "Access control configuration reloaded successfully"
            }
        else:
            _LOGGER.error("Failed to reload access control configuration")
            return {
                "success": False,
                "message": "Failed to reload access control configuration"
            }

    async def handle_list_users(call: ServiceCall) -> ServiceResponse:
        """Handle the list_users service call."""
        if DOMAIN not in hass.data:
            users = {}
        else:
            access_config = hass.data[DOMAIN].get("access_config", {})
            users = access_config.get("users", {})
        
        _LOGGER.info(f"Configured users: {list(users.keys())}")
        
        # Format user data for return
        user_list = []
        if users:
            for user_id, user_config in users.items():
                role = user_config.get("role", "unknown")
                access = user_config.get("access", "allow")
                user_list.append({
                    "user_id": user_id,
                    "role": role,
                    "access": access
                })
        
        response_data: JsonObjectType = {
            "success": True,
            "users": user_list,
            "count": len(user_list),
            "message": f"Found {len(user_list)} configured users" if user_list else "No users configured (all users have full access)"
        }
        
        # Fire event with the data
        hass.bus.async_fire("rbac_service_response", {
            "service": "list_users",
            "data": response_data
        })
        
        return response_data

    async def handle_add_user(call: ServiceCall) -> Dict[str, Any]:
        """Handle the add_user service call."""
        person_entity_id = call.data.get("person", "")
        role = call.data.get("role", "")
        
        # Validate role
        if not role:
            raise HomeAssistantError("Role is required")
        
        if not _validate_role(hass, role):
            available_roles = _get_available_roles(hass)
            raise HomeAssistantError(f"Invalid role '{role}'. Available roles: {', '.join(available_roles)}")
        
        # Extract user_id from person entity
        try:
            person_state = hass.states.get(person_entity_id)
            if not person_state:
                _LOGGER.error(f"Person entity {person_entity_id} not found")
                return {
                    "success": False,
                    "message": f"Person entity {person_entity_id} not found"
                }
            
            user_id = person_state.attributes.get("user_id")
            if not user_id:
                _LOGGER.error(f"No user_id found for person {person_entity_id}")
                return {
                    "success": False,
                    "message": f"No user_id found for person {person_entity_id}"
                }
        except Exception as e:
            _LOGGER.error(f"Error extracting user_id from person {person_entity_id}: {e}")
            return {
                "success": False,
                "message": f"Error extracting user_id from person {person_entity_id}: {e}"
            }
        
        # Check if caller has top-level access
        caller_id = call.context.user_id if call.context else None
        if not caller_id or not _is_top_level_user(hass, caller_id):
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to add user {user_id}")
            return {
                "success": False,
                "message": "Access denied: Only admin users can add users"
            }
        
        # Check if user is a built-in HA user
        if _is_builtin_ha_user(user_id):
            _LOGGER.warning(f"Cannot add built-in Home Assistant user: {user_id}")
            return {
                "success": False,
                "message": f"Cannot add built-in Home Assistant user: {user_id}"
            }
        
        success = await add_user_access(hass, user_id, role)
        
        if success:
            _LOGGER.info(f"Added user '{user_id}' with role '{role}'")
            return {
                "success": True,
                "user_id": user_id,
                "role": role,
                "message": f"Successfully added user '{user_id}' with role '{role}'"
            }
        else:
            _LOGGER.error(f"Failed to add user '{user_id}'")
            return {
                "success": False,
                "message": f"Failed to add user '{user_id}'"
            }

    async def handle_get_available_roles(call: ServiceCall) -> ServiceResponse:
        """Handle the get_available_roles service call."""
        # Check if caller has top-level access
        caller_id = call.context.user_id if call.context else None
        if not caller_id or not _is_top_level_user(hass, caller_id):
            _LOGGER.warning(f"Access denied: User {caller_id} attempted to get available roles")
            raise HomeAssistantError("Access denied: Only top-level users can get available roles")
        
        try:
            # Get roles from access_config
            roles = _get_available_roles(hass)
            
            _LOGGER.info(f"Available roles: {roles}")
            
            response_data: JsonObjectType = {
                "success": True,
                "roles": roles,
                "count": len(roles),
                "message": f"Found {len(roles)} available roles"
            }
            
            # Fire event with the data
            hass.bus.async_fire("rbac_service_response", {
                "service": "get_available_roles",
                "data": response_data
            })
            
            return response_data
            
        except Exception as e:
            _LOGGER.error(f"Error getting available roles: {e}")
            raise HomeAssistantError(f"Error getting available roles: {e}")
    
    # Register services
    hass.services.async_register(
        DOMAIN, "get_user_config", handle_get_user_config, schema=GET_USER_CONFIG_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    
    hass.services.async_register(
        DOMAIN, "reload_config", handle_reload_config, schema=RELOAD_CONFIG_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "list_users", handle_list_users, schema=LIST_USERS_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    
    # User management services (restricted to top-level users)
    hass.services.async_register(
        DOMAIN, "add_user", handle_add_user, schema=ADD_USER_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "get_available_roles", handle_get_available_roles, schema=GET_AVAILABLE_ROLES_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    
    _LOGGER.info("RBAC services registered successfully")


from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
import json
import logging

_LOGGER = logging.getLogger(__name__)


async def _is_admin_user(hass: HomeAssistant, user_id: str, user_obj=None) -> bool:
    """Check if a user is an admin (either HA native admin or RBAC admin role)."""
    try:
        # First check if user is a Home Assistant native admin
        try:
            # If we have the user object directly, use it
            if user_obj and hasattr(user_obj, 'is_admin'):
                _LOGGER.debug(f"User object type: {type(user_obj)}, is_admin: {user_obj.is_admin}")
                if user_obj.is_admin:
                    _LOGGER.warning(f"User {user_id} is Home Assistant native admin")
                    return True
            else:
                # Try different methods to get the user
                user = None
                if hasattr(hass.auth, 'async_get_user'):
                    user = await hass.auth.async_get_user(user_id)
                elif hasattr(hass.auth, 'get_user'):
                    user = hass.auth.get_user(user_id)
                elif hasattr(hass.auth, '_store') and hasattr(hass.auth._store, 'async_get_user'):
                    user = await hass.auth._store.async_get_user(user_id)
                
                if user and hasattr(user, 'is_admin') and user.is_admin:
                    _LOGGER.warning(f"User {user_id} is Home Assistant native admin")
                    return True
                elif user:
                    _LOGGER.debug(f"User {user_id} found but not admin: {type(user)}")
        except Exception as e:
            _LOGGER.warning(f"Could not check HA native admin status for user {user_id}: {e}")
        
        # Then check RBAC admin role
        access_config = hass.data.get(DOMAIN, {}).get("access_config", {})
        users = access_config.get("users", {})
        
        # Check if current user has admin role
        user_config = users.get(user_id)
        if not user_config:
            _LOGGER.warning(f"User {user_id} not found in RBAC configuration")
            return False
        
        user_role = user_config.get("role", "unknown")
        if user_role == "unknown":
            _LOGGER.warning(f"User {user_id} has no role assigned")
            return False
        
        # Get role configuration and check admin flag
        roles = access_config.get("roles", {})
        role_config = roles.get(user_role, {})
        is_rbac_admin = role_config.get("admin", False)
        
        if is_rbac_admin:
            _LOGGER.warning(f"User {user_id} has RBAC admin role: {user_role}")
        
        return is_rbac_admin
        
    except Exception as e:
        _LOGGER.error(f"Error checking admin status: {e}")
        return False


def _update_rejection_sensors(hass: HomeAssistant, user_id: str, service: str):
    """Update the last rejection sensors when access is denied."""
    try:
        from datetime import datetime
        
        # Get current time
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get user name from person entity
        user_name = "Unknown"
        try:
            # First try to get the person entity for this user
            for state in hass.states.async_all():
                if state.domain == "person" and state.attributes.get("user_id") == user_id:
                    # Use the friendly name from the person entity
                    user_name = state.attributes.get("friendly_name") or state.name
                    break
            
            # Fallback to user name if no person entity found
            if user_name == "Unknown":
                user = hass.auth.async_get_user(user_id)
                if user:
                    user_name = user.name or f"User {user_id[:8]}"
        except:
            pass
        
        # Update sensors
        hass.states.async_set(
            f"sensor.{DOMAIN}_last_rejection",
            now,
            {
                "friendly_name": "RBAC Last Rejection",
                "icon": "mdi:clock-alert"
            }
        )
        
        hass.states.async_set(
            f"sensor.{DOMAIN}_last_user_rejected",
            user_name,
            {
                "friendly_name": "RBAC Last User Rejected",
                "icon": "mdi:account-alert"
            }
        )
        
        # Update access config in memory
        access_config = hass.data.get(DOMAIN, {}).get("access_config", {})
        access_config["last_rejection"] = now
        access_config["last_user_rejected"] = user_name
        hass.data[DOMAIN]["access_config"] = access_config
        
        # Save to YAML file for persistence
        try:
            from . import _save_access_control_config
            # Use asyncio to run the async function
            import asyncio
            loop = hass.loop
            if loop.is_running():
                # Schedule the save operation
                asyncio.create_task(_save_access_control_config(hass, access_config))
            else:
                # Run directly if no event loop is running
                loop.run_until_complete(_save_access_control_config(hass, access_config))
        except Exception as save_error:
            _LOGGER.error(f"Error saving rejection data to YAML: {save_error}")
        
    except Exception as e:
        _LOGGER.error(f"Error updating rejection sensors: {e}")


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
            if not await _is_admin_user(hass, user.id, user):
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
        if not await _is_admin_user(hass, user.id):
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
                
                _LOGGER.info(f"Updating role: {role_name} with config: {role_config}")
                
                if not role_name or not role_config:
                    return self.json({"error": "Missing roleName or roleConfig"}, status_code=400)
                
                # Validate role name format
                import re
                if not re.match(r'^[a-z0-9_]+$', role_name):
                    return self.json({"error": "Role name must contain only lowercase letters, numbers, and underscores"}, status_code=400)
                
                # Update or create role
                if "roles" not in access_config:
                    access_config["roles"] = {}
                access_config["roles"][role_name] = role_config
                _LOGGER.info(f"Role {role_name} saved successfully")
                
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
                
            elif action == "add_guest_user":
                guest_name = data.get("guestName")
                guest_id = data.get("guestId")
                
                if not guest_name or not guest_id:
                    return self.json({"error": "Missing guestName or guestId"}, status_code=400)
                
                # Validate guest ID format (GUID)
                import re
                if not re.match(r'^[a-f0-9-]{36}$', guest_id):
                    return self.json({"error": "Guest ID must be a valid GUID format"}, status_code=400)
                
                # Add guest user to configuration
                if "users" not in access_config:
                    access_config["users"] = {}
                
                # Check if guest ID already exists
                if guest_id in access_config["users"]:
                    return self.json({"error": "Guest ID already exists"}, status_code=400)
                
                # Add guest user with default role
                access_config["users"][guest_id] = {
                    "role": "guest",
                    "name": guest_name,
                    "is_guest": True,
                    "enabled": True
                }
                _create_guest_dashboard(hass, guest_id)
                
                _LOGGER.info(f"Added guest user: {guest_name} with ID: {guest_id}")
                
            elif action == "remove_guest_user":
                guest_id = data.get("guestId")
                
                if not guest_id:
                    return self.json({"error": "Missing guestId"}, status_code=400)
                
                # Check if guest user exists
                if "users" not in access_config or guest_id not in access_config["users"]:
                    return self.json({"error": "Guest user not found"}, status_code=404)
                
                guest_config = access_config["users"][guest_id]
                if not guest_config.get("is_guest", False):
                    return self.json({"error": "User is not a guest user"}, status_code=400)

                del access_config["users"][guest_id]

                _remove_guest_dashboard(hass, guest_id)
                
                _LOGGER.info(f"Removed guest user with ID: {guest_id}")
                
            elif action == "toggle_guest_user":
                guest_id = data.get("guestId")
                enabled = data.get("enabled")
                
                if not guest_id:
                    return self.json({"error": "Missing guestId"}, status_code=400)
                
                if enabled is None:
                    return self.json({"error": "Missing enabled status"}, status_code=400)
                
                # Check if guest user exists
                if "users" not in access_config or guest_id not in access_config["users"]:
                    return self.json({"error": "Guest user not found"}, status_code=404)
                
                # Check if it's actually a guest user
                guest_config = access_config["users"][guest_id]
                if not guest_config.get("is_guest", False):
                    return self.json({"error": "User is not a guest user"}, status_code=400)
                
                # Update guest user enabled status
                access_config["users"][guest_id]["enabled"] = enabled
                
                action_text = "enabled" if enabled else "disabled"
                _LOGGER.info(f"Guest user {guest_id} {action_text}")
                
            elif action == "update_default_restrictions":
                restrictions = data.get("restrictions")
                
                if not restrictions:
                    return self.json({"error": "Missing restrictions"}, status_code=400)
                
                # Update default restrictions
                access_config["default_restrictions"] = restrictions
                
            elif action == "update_settings":
                # Update enabled, show_notifications, send_event, frontend_blocking_enabled, log_deny_list settings
                if "enabled" in data:
                    access_config["enabled"] = data["enabled"]
                if "show_notifications" in data:
                    access_config["show_notifications"] = data["show_notifications"]
                if "send_event" in data:
                    access_config["send_event"] = data["send_event"]
                if "frontend_blocking_enabled" in data:
                    access_config["frontend_blocking_enabled"] = data["frontend_blocking_enabled"]
                if "log_deny_list" in data:
                    access_config["log_deny_list"] = data["log_deny_list"]
                if "allow_chained_actions" in data:
                    access_config["allow_chained_actions"] = data["allow_chained_actions"]
                
            # Preserve runtime fields that shouldn't be saved to YAML
            config_to_save = access_config.copy()
            runtime_fields = ["last_rejection", "last_user_rejected"]
            for field in runtime_fields:
                if field in config_to_save:
                    del config_to_save[field]
            
            # Save configuration back to YAML file
            success = await _save_access_control_config(hass, config_to_save)
            
            if success:
                # Update the in-memory config as well (keep runtime fields)
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
        if not await _is_admin_user(hass, user.id):
            return self.json({
                "error": "Admin access required",
                "message": "Only administrators can access user information",
                "redirect_url": "/"
            }, status_code=403)
        
        try:
            users = []
            
            # Add regular Home Assistant users
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
            
            # Add guest users from access control configuration
            if DOMAIN in hass.data:
                access_config = hass.data[DOMAIN].get("access_config", {})
                guest_users = access_config.get("users", {})
                
                for guest_id, guest_config in guest_users.items():
                    if guest_config.get("is_guest", False):
                        user_data = {
                            "id": guest_id,
                            "name": guest_config.get("name", f"Guest {guest_id[:8]}"),
                            "entity_picture": None,
                            "person_entity_id": None,
                            "isGuest": True,
                            "enabled": guest_config.get("enabled", True)  # Default to enabled if not specified
                        }
                        users.append(user_data)
            
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
        if not await _is_admin_user(hass, user.id):
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
        if not await _is_admin_user(hass, user.id):
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
        if not await _is_admin_user(hass, user.id):
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


class RBACSensorsView(HomeAssistantView):
    """View to get RBAC sensor states."""
    
    url = "/api/rbac/sensors"
    name = "api:rbac:sensors"
    requires_auth = True
    
    async def get(self, request):
        """Get RBAC sensor states."""
        try:
            hass = request.app["hass"]
            
            # Get sensor states
            sensors = {
                "last_rejection": hass.states.get(f"sensor.{DOMAIN}_last_rejection"),
                "last_user_rejected": hass.states.get(f"sensor.{DOMAIN}_last_user_rejected"),
                "enabled": hass.states.get(f"sensor.{DOMAIN}_enabled"),
                "show_notifications": hass.states.get(f"sensor.{DOMAIN}_show_notifications"),
                "send_events": hass.states.get(f"sensor.{DOMAIN}_send_events"),
            }
            
            # Convert to simple dict
            result = {}
            for key, sensor in sensors.items():
                if sensor:
                    result[key] = {
                        "state": sensor.state,
                        "attributes": dict(sensor.attributes)
                    }
                else:
                    result[key] = None
            
            return self.json(result)
        except Exception as e:
            _LOGGER.error(f"Error getting RBAC sensors: {e}")
            return self.json({"error": str(e)}, status_code=500)


class RBACDenyLogView(HomeAssistantView):
    """View to get deny log contents."""
    
    url = "/api/rbac/deny-log"
    name = "api:rbac:deny-log"
    requires_auth = True
    
    async def get(self, request):
        """Get deny log file contents."""
        try:
            hass = request.app["hass"]
            user = request["hass_user"]
            
            # Check admin permissions
            if not await _is_admin_user(hass, user.id):
                return self.json({
                    "error": "Admin access required",
                    "message": "Only administrators can access deny logs",
                    "redirect_url": "/"
                }, status_code=403)
            
            # Get deny log contents
            from . import _get_deny_log_contents
            log_contents = _get_deny_log_contents(hass)
            
            return self.json({
                "success": True,
                "contents": log_contents
            })
            
        except Exception as e:
            _LOGGER.error(f"Error getting deny log: {e}")
            return self.json({
                "success": False,
                "error": str(e)
            }, status_code=500)
    
    async def delete(self, request):
        """Clear deny log file contents."""
        try:
            hass = request.app["hass"]
            user = request["hass_user"]
            
            # Check admin permissions
            if not await _is_admin_user(hass, user.id):
                return self.json({
                    "error": "Admin access required",
                    "message": "Only administrators can clear deny logs",
                    "redirect_url": "/"
                }, status_code=403)
            
            # Clear deny log file
            from . import _clear_deny_log
            success = _clear_deny_log(hass)
            
            if success:
                _LOGGER.info(f"Deny log cleared by user {user.name} ({user.id})")
                return self.json({
                    "success": True,
                    "message": "Deny log cleared successfully"
                })
            else:
                return self.json({
                    "success": False,
                    "error": "Failed to clear deny log"
                }, status_code=500)
            
        except Exception as e:
            _LOGGER.error(f"Error clearing deny log: {e}")
            return self.json({
                "success": False,
                "error": str(e)
            }, status_code=500)


class RBACTemplateEvaluateView(HomeAssistantView):
    """View to evaluate a template."""
    
    url = "/api/rbac/evaluate-template"
    name = "api:rbac:evaluate-template"
    requires_auth = True
    
    async def post(self, request):
        """Evaluate a template."""
        try:
            hass = request.app["hass"]
            user = request["hass_user"]
            
            # Get template from request
            data = await request.json()
            template_str = data.get("template")
            
            if not template_str:
                return self.json({"error": "No template provided"}, status_code=400)
            
            # Import Template
            from homeassistant.helpers.template import Template
            
            # Create and render template with user context
            template = Template(template_str, hass)
            
            # Get current user's person entity for template context
            user_person_entity = None
            try:
                # Look for person entities associated with this user
                for state in hass.states.async_all():
                    if state.domain == "person" and state.attributes.get("user_id") == user.id:
                        user_person_entity = state.entity_id
                        break
            except Exception as e:
                _LOGGER.debug(f"Could not find person entity for user {user.id}: {e}")
            
            # Create template context with user variable
            template_context = {}
            if user_person_entity:
                template_context['current_user_str'] = user_person_entity
            
            result = template.async_render(template_context, parse_result=False)
            
            # Convert result to boolean
            template_result = bool(result) if result not in [None, "", "False", "false", "0"] else False
            
            return self.json({
                "success": True,
                "result": template_result,
                "raw_result": str(result),
                "evaluated_value": result  # The actual evaluated value from the template
            })
            
        except Exception as e:
            _LOGGER.error(f"Error evaluating template: {e}")
            return self.json({
                "success": False,
                "error": str(e)
            }, status_code=200)  # Return 200 so frontend can handle error gracefully


class RBACFrontendBlockingView(HomeAssistantView):
    """View to get frontend blocking configuration for current user."""
    
    url = "/api/rbac/frontend-blocking"
    name = "api:rbac:frontend-blocking"
    requires_auth = True
    
    async def get(self, request):
        """Get frontend blocking configuration for current user."""
        try:
            hass = request.app["hass"]
            user = request["hass_user"]
            
            # Get access control configuration
            access_config = hass.data.get(DOMAIN, {}).get("access_config", {})
            
            rbac_enabled = access_config.get("enabled", True)
            frontend_blocking_enabled = access_config.get("frontend_blocking_enabled", True)
            
            if not rbac_enabled or not frontend_blocking_enabled:
                return self.json({
                    "enabled": False,
                    "domains": [],
                    "entities": [],
                    "services": []
                })
            
            # Get user configuration
            users = access_config.get("users", {})
            user_config = users.get(user.id)
            
            if not user_config:
                # User not in config, return empty blocking (full access)
                return self.json({
                    "enabled": True,
                    "domains": [],
                    "entities": [],
                    "services": []
                })
            
            # Get user role
            user_role = user_config.get("role", "user")
            roles = access_config.get("roles", {})
            role_config = roles.get(user_role, {})
            
            # Check if user has admin role (bypasses restrictions)
            if role_config.get("admin", False):
                return self.json({
                    "enabled": True,
                    "domains": [],
                    "entities": [],
                    "services": []
                })
            
            # Check if role has deny_all enabled
            deny_all = role_config.get("deny_all", False)
            if deny_all:
                # In deny_all mode, we need to get all available domains/entities
                # and only allow those explicitly marked with allow: true
                hass = request.app["hass"]
                
                # Get all available domains and entities
                all_available_domains = set()
                all_available_entities = set()
                
                # Get domains from all states
                for state in hass.states.async_all():
                    domain = state.entity_id.split('.')[0]
                    all_available_domains.add(domain)
                    all_available_entities.add(state.entity_id)
                
                # Get domains from services
                for domain in hass.services.async_services():
                    all_available_domains.add(domain)
                
                # Get role permissions to find allowed items
                role_permissions = role_config.get("permissions", {})
                role_domains = role_permissions.get("domains", {})
                role_entities = role_permissions.get("entities", {})
                
                # Get user-specific restrictions
                user_restrictions = user_config.get("restrictions", {})
                user_domains = user_restrictions.get("domains", {})
                user_entities = user_restrictions.get("entities", {})
                
                # Build blocked and allowed lists - block everything except explicitly allowed
                blocked_domains = []
                blocked_entities = []
                blocked_services = []
                allowed_domains = []
                allowed_entities = []
                
                # Process domains - block all except those with allow: true
                for domain in all_available_domains:
                    domain_allowed = False
                    
                    # Check user-specific restrictions first
                    if domain in user_domains:
                        user_domain_config = user_domains[domain]
                        if isinstance(user_domain_config, dict):
                            domain_allowed = user_domain_config.get("allow", False)
                    
                    # Check role-specific permissions
                    if not domain_allowed and domain in role_domains:
                        role_domain_config = role_domains[domain]
                        if isinstance(role_domain_config, dict):
                            domain_allowed = role_domain_config.get("allow", False)
                    
                    if domain_allowed:
                        allowed_domains.append(domain)
                    else:
                        blocked_domains.append(domain)
                
                # Process entities - block all except those with allow: true
                for entity in all_available_entities:
                    entity_allowed = False
                    
                    # Check user-specific restrictions first
                    if entity in user_entities:
                        user_entity_config = user_entities[entity]
                        if isinstance(user_entity_config, dict):
                            entity_allowed = user_entity_config.get("allow", False)
                    
                    # Check role-specific permissions
                    if not entity_allowed and entity in role_entities:
                        role_entity_config = role_entities[entity]
                        if isinstance(role_entity_config, dict):
                            entity_allowed = role_entity_config.get("allow", False)
                    
                    if entity_allowed:
                        allowed_entities.append(entity)
                    else:
                        blocked_entities.append(entity)
                
                return self.json({
                    "enabled": True,
                    "domains": blocked_domains,
                    "entities": blocked_entities,
                    "services": blocked_services,
                    "allowed_domains": allowed_domains,
                    "allowed_entities": allowed_entities
                })
            
            # Get default restrictions
            default_restrictions = access_config.get("default_restrictions", {})
            default_domains = default_restrictions.get("domains", {})
            default_entities = default_restrictions.get("entities", {})
            
            # Get role-specific permissions
            role_permissions = role_config.get("permissions", {})
            role_domains = role_permissions.get("domains", {})
            role_entities = role_permissions.get("entities", {})
            
            # Get user-specific restrictions
            user_restrictions = user_config.get("restrictions", {})
            user_domains = user_restrictions.get("domains", {})
            user_entities = user_restrictions.get("entities", {})
            
            # Check if role allows by default (opposite of deny_all)
            role_allows_by_default = not role_config.get("deny_all", False)
            
            # Get all available domains and entities from Home Assistant
            all_available_domains = set()
            all_available_entities = set()
            
            # Get domains from all states
            for state in hass.states.async_all():
                domain = state.entity_id.split('.')[0]
                all_available_domains.add(domain)
                all_available_entities.add(state.entity_id)
            
            # Get domains from services
            for domain in hass.services.async_services():
                all_available_domains.add(domain)
            
            # Build blocked and allowed lists
            blocked_domains = []
            blocked_entities = []
            blocked_services = []
            allowed_domains = []
            allowed_entities = []
            
            # Process domains
            for domain in all_available_domains:
                domain_blocked = False
                domain_services = []
                domain_allowed = False
                
                # Check user-specific restrictions first (highest priority)
                if domain in user_domains:
                    user_domain_config = user_domains[domain]
                    if isinstance(user_domain_config, dict):
                        user_services = user_domain_config.get("services", [])
                        domain_allowed = user_domain_config.get("allow", False)
                        if domain_allowed:
                            # User explicitly allows this domain
                            allowed_domains.append(domain)
                            continue
                        if not user_services:  # Empty list means block all
                            domain_blocked = True
                        else:
                            domain_services = user_services
                    else:
                        domain_blocked = True  # Non-dict means block all
                
                # Check role-specific permissions (medium priority)
                elif domain in role_domains:
                    role_domain_config = role_domains[domain]
                    if isinstance(role_domain_config, dict):
                        role_services = role_domain_config.get("services", [])
                        domain_allowed = role_domain_config.get("allow", False)
                        if domain_allowed:
                            # Role explicitly allows this domain
                            allowed_domains.append(domain)
                            continue
                        if not role_services:  # Empty list means block all
                            domain_blocked = True
                        else:
                            domain_services = role_services
                    else:
                        domain_blocked = True  # Non-dict means block all
                
                # Check default restrictions (lowest priority)
                elif domain in default_domains:
                    default_domain_config = default_domains[domain]
                    if isinstance(default_domain_config, dict):
                        default_services = default_domain_config.get("services", [])
                        domain_allowed = default_domain_config.get("allow", False)
                        if domain_allowed:
                            # Default explicitly allows this domain
                            allowed_domains.append(domain)
                            continue
                        if not default_services:  # Empty list means block all
                            domain_blocked = True
                        else:
                            domain_services = default_services
                    else:
                        domain_blocked = True  # Non-dict means block all
                
                # If no explicit configuration found, apply role's default behavior
                else:
                    if not role_allows_by_default:
                        # Role denies by default, so block this domain
                        domain_blocked = True
                    # If role allows by default, don't block (domain_allowed remains False)
                
                if domain_blocked:
                    blocked_domains.append(domain)
                elif domain_services:
                    # Add specific services to blocked services list
                    for service in domain_services:
                        blocked_services.append(f"{domain}.{service}")
            
            # Process entities
            for entity in all_available_entities:
                entity_blocked = False
                entity_services = []
                entity_allowed = False
                
                # Check user-specific restrictions first (highest priority)
                if entity in user_entities:
                    user_entity_config = user_entities[entity]
                    if isinstance(user_entity_config, dict):
                        user_services = user_entity_config.get("services", [])
                        entity_allowed = user_entity_config.get("allow", False)
                        if entity_allowed:
                            # User explicitly allows this entity
                            allowed_entities.append(entity)
                            continue
                        if not user_services:  # Empty list means block all
                            entity_blocked = True
                        else:
                            entity_services = user_services
                    else:
                        entity_blocked = True  # Non-dict means block all
                
                # Check role-specific permissions (medium priority)
                elif entity in role_entities:
                    role_entity_config = role_entities[entity]
                    if isinstance(role_entity_config, dict):
                        role_services = role_entity_config.get("services", [])
                        entity_allowed = role_entity_config.get("allow", False)
                        if entity_allowed:
                            # Role explicitly allows this entity
                            allowed_entities.append(entity)
                            continue
                        if not role_services:  # Empty list means block all
                            entity_blocked = True
                        else:
                            entity_services = role_services
                    else:
                        entity_blocked = True  # Non-dict means block all
                
                # Check default restrictions (lowest priority)
                elif entity in default_entities:
                    default_entity_config = default_entities[entity]
                    if isinstance(default_entity_config, dict):
                        default_services = default_entity_config.get("services", [])
                        entity_allowed = default_entity_config.get("allow", False)
                        if entity_allowed:
                            # Default explicitly allows this entity
                            allowed_entities.append(entity)
                            continue
                        if not default_services:  # Empty list means block all
                            entity_blocked = True
                        else:
                            entity_services = default_services
                    else:
                        entity_blocked = True  # Non-dict means block all
                
                # If no explicit configuration found, apply role's default behavior
                else:
                    if not role_allows_by_default:
                        # Role denies by default, so block this entity
                        entity_blocked = True
                    # If role allows by default, don't block (entity_allowed remains False)
                
                if entity_blocked:
                    blocked_entities.append(entity)
                elif entity_services:
                    # Add specific services to blocked services list
                    for service in entity_services:
                        blocked_services.append(f"{entity}.{service}")
            
            return self.json({
                "enabled": True,
                "domains": blocked_domains,
                "entities": blocked_entities,
                "services": blocked_services,
                "allowed_domains": allowed_domains,
                "allowed_entities": allowed_entities
            })
            
        except Exception as e:
            _LOGGER.error(f"Error getting frontend blocking config: {e}")
            return self.json({"error": str(e)}, status_code=500)


class RBACYamlEditorView(HomeAssistantView):
    """View for YAML editor operations."""
    
    url = "/api/rbac/yaml-editor"
    name = "api:rbac:yaml-editor"
    requires_auth = True
    
    async def get(self, request):
        """Get the current access_control.yaml content."""
        try:
            hass = request.app["hass"]
            
            # Load configuration directly from the YAML file
            from . import _load_access_control_config
            access_config = await _load_access_control_config(hass)
            
            # Convert to YAML string
            yaml_content = yaml.dump(access_config, default_flow_style=False, indent=2, sort_keys=False)
            
            return self.json({"yaml_content": yaml_content})
            
        except Exception as e:
            _LOGGER.error(f"Error getting YAML content: {e}")
            return self.json({"error": str(e)}, status_code=500)
    
    async def post(self, request):
        """Update the access_control.yaml file with new content."""
        try:
            hass = request.app["hass"]
            data = await request.json()
            yaml_content = data.get("yaml_content", "")
            
            if not yaml_content.strip():
                return self.json({"error": "YAML content cannot be empty"}, status_code=400)
            
            # Validate YAML syntax
            try:
                parsed_config = yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                return self.json({"error": f"Invalid YAML syntax: {str(e)}"}, status_code=400)
            
            # Basic validation of the structure
            if not isinstance(parsed_config, dict):
                return self.json({"error": "YAML must contain a dictionary/object"}, status_code=400)
            
            # Validate required top-level keys
            required_keys = ["roles", "users"]
            for key in required_keys:
                if key not in parsed_config:
                    return self.json({"error": f"Missing required key: {key}"}, status_code=400)
            
            # Validate roles structure
            if not isinstance(parsed_config["roles"], dict):
                return self.json({"error": "roles must be a dictionary"}, status_code=400)
            
            # Validate users structure
            if not isinstance(parsed_config["users"], dict):
                return self.json({"error": "users must be a dictionary"}, status_code=400)
            
            # Validate role names (alphanumeric and underscores only)
            for role_name in parsed_config["roles"].keys():
                if not isinstance(role_name, str) or not role_name.replace("_", "").replace("-", "").isalnum():
                    return self.json({"error": f"Invalid role name '{role_name}': must contain only letters, numbers, underscores, and hyphens"}, status_code=400)
            
            # Save the configuration
            from . import _save_access_control_config
            success = await _save_access_control_config(hass, parsed_config)
            
            if success:
                # Update the in-memory configuration
                hass.data[DOMAIN]["access_config"] = parsed_config
                return self.json({"success": True, "message": "YAML configuration updated successfully"})
            else:
                return self.json({"error": "Failed to save YAML configuration"}, status_code=500)
                
        except Exception as e:
            _LOGGER.error(f"Error updating YAML content: {e}")
            return self.json({"error": str(e)}, status_code=500)


class RBACStaticView(HomeAssistantView):
    """View to serve static files for RBAC frontend."""
    
    url = "/api/rbac/static/{file_path:.+}"
    name = "api:rbac:static"
    requires_auth = False
    
    def __init__(self, hass: HomeAssistant):
        """Initialize the static view."""
        self.hass = hass
        self._www_path = os.path.join(hass.config.config_dir, "custom_components", "rbac", "www")
    
    async def get(self, request: web.Request, file_path: str) -> web.Response:
        """Serve static files."""
        try:
            # Security: prevent directory traversal
            if ".." in file_path or file_path.startswith("/"):
                return web.Response(status=403, text="Forbidden")
            
            # Construct full file path
            full_path = os.path.join(self._www_path, file_path)
            
            # Check if file exists
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                return web.Response(status=404, text="File not found")
            
            # Get MIME type
            mime_type, _ = mimetypes.guess_type(full_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            
            # Read file content
            with open(full_path, 'rb') as f:
                content = f.read()
            
            # Set appropriate headers
            headers = {
                "Content-Type": mime_type,
                "Cache-Control": "public, max-age=3600"  # Cache for 1 hour
            }
            
            # Special handling for JavaScript files
            if file_path.endswith('.js'):
                headers["Content-Type"] = "application/javascript"
            elif file_path.endswith('.css'):
                headers["Content-Type"] = "text/css"
            elif file_path.endswith('.html'):
                headers["Content-Type"] = "text/html"
            
            return web.Response(body=content, headers=headers)
            
        except Exception as e:
            _LOGGER.error(f"Error serving static file {file_path}: {e}")
            return web.Response(status=500, text="Internal server error")


async def async_setup_static_routes(hass: HomeAssistant) -> None:
    """Set up static file serving routes."""
    hass.http.register_view(RBACStaticView(hass))
    _LOGGER.info("RBAC static file serving routes registered")


class RBACHassInstanceView(HomeAssistantView):
    """View to provide Home Assistant instance data for dashboard."""
    
    url = "/api/rbac/hass-instance"
    name = "api:rbac:hass-instance"
    requires_auth = False
    
    def __init__(self, hass: HomeAssistant):
        """Initialize the hass instance view."""
        self.hass = hass
    
    async def get(self, request: web.Request) -> web.Response:
        """Provide Home Assistant instance data."""
        try:
            # Get states as object (entity_id -> state data)
            states = {}
            try:
                for entity_id in self.hass.states.async_entity_ids():
                    state = self.hass.states.get(entity_id)
                    if state:
                        states[entity_id] = {
                            "entity_id": state.entity_id,
                            "state": state.state,
                            "attributes": dict(state.attributes),
                            "last_changed": state.last_changed.isoformat(),
                            "last_updated": state.last_updated.isoformat(),
                            "context": {
                                "id": state.context.id,
                                "user_id": state.context.user_id,
                                "parent_id": state.context.parent_id
                            }
                        }
            except Exception as e:
                _LOGGER.warning(f"Error getting states: {e}")
            
            # Get services safely
            services = {}
            try:
                for domain, service_map in self.hass.services.async_services().items():
                    services[domain] = list(service_map.keys())
            except Exception as e:
                _LOGGER.warning(f"Error getting services: {e}")
            
            # Get themes safely
            themes = {}
            try:
                themes = {
                    "default_theme": getattr(self.hass.config, 'default_theme', 'default'),
                    "themes": {}
                }
                # Try to get theme data if available
                if hasattr(self.hass, 'themes') and self.hass.themes:
                    themes["themes"] = dict(self.hass.themes.themes) if hasattr(self.hass.themes, 'themes') else {}
            except Exception as e:
                _LOGGER.warning(f"Error getting themes: {e}")
            
            # Get configuration safely
            config = {}
            try:
                config = {
                    "location_name": getattr(self.hass.config, 'location_name', 'Home'),
                    "latitude": getattr(self.hass.config, 'latitude', 0),
                    "longitude": getattr(self.hass.config, 'longitude', 0),
                    "elevation": getattr(self.hass.config, 'elevation', 0),
                    "unit_system": {
                        "length": getattr(self.hass.config, 'unit_system', {}).get('length', 'mi'),
                        "mass": getattr(self.hass.config, 'unit_system', {}).get('mass', 'lb'),
                        "temperature": getattr(self.hass.config, 'unit_system', {}).get('temperature', '°F'),
                        "volume": getattr(self.hass.config, 'unit_system', {}).get('volume', 'gal')
                    },
                    "time_zone": str(getattr(self.hass.config, 'time_zone', 'UTC')),
                    "components": list(getattr(self.hass.config, 'components', set())),
                    "version": getattr(self.hass.config, 'version', 'unknown')
                }
            except Exception as e:
                _LOGGER.warning(f"Error getting config: {e}")
            
            return self.json({
                "states": states,
                "services": services,
                "config": config,
                "themes": themes,
                "callService": True
            })
            
        except Exception as e:
            _LOGGER.error(f"Error getting hass instance: {e}")
            return self.json({"error": str(e)}, status_code=500)


class RBACMockAPIView(HomeAssistantView):
    """View to provide mock Home Assistant API endpoints for custom cards."""
    
    url = "/api/rbac/mock-api/{endpoint:.*}"
    name = "api:rbac:mock-api"
    requires_auth = False
    
    def __init__(self, hass: HomeAssistant):
        """Initialize the mock API view."""
        self.hass = hass
    
    async def get(self, request: web.Request) -> web.Response:
        """Handle mock API requests."""
        try:
            endpoint = request.match_info['endpoint']
            
            if endpoint == 'areas':
                # Return areas data
                areas = {}
                try:
                    if hasattr(self.hass, 'areas') and self.hass.areas:
                        areas = dict(self.hass.areas.areas) if hasattr(self.hass.areas, 'areas') else {}
                except Exception as e:
                    _LOGGER.warning(f"Error getting areas: {e}")
                
                return self.json(areas)
            
            elif endpoint.startswith('scenes/'):
                # Return scenes for a specific area
                area_id = endpoint.split('/')[1]
                
                scenes = []
                try:
                    for entity_id in self.hass.states.async_entity_ids():
                        if entity_id.startswith('scene.'):
                            state = self.hass.states.get(entity_id)
                            if state and state.attributes:
                                # Check if this scene belongs to the requested area
                                scene_area_id = state.attributes.get('area_id')
                                if not scene_area_id:
                                    # Fallback: extract area from friendly_name
                                    friendly_name = state.attributes.get('friendly_name', '')
                                    if friendly_name:
                                        area_name = friendly_name.split(' ')[0]
                                        # Find matching area
                                        for aid, area_data in (self.hass.areas.areas if hasattr(self.hass, 'areas') and self.hass.areas else {}).items():
                                            if area_data.get('name') == area_name:
                                                scene_area_id = aid
                                                break
                                
                                if scene_area_id == area_id:
                                    scenes.append({
                                        "entity_id": entity_id,
                                        "name": state.attributes.get('friendly_name', entity_id),
                                        "state": state.state
                                    })
                except Exception as e:
                    _LOGGER.warning(f"Error getting scenes: {e}")
                
                return self.json(scenes)
            
            else:
                return self.json({"error": f"Unknown endpoint: {endpoint}"}, status_code=404)
                
        except Exception as e:
            _LOGGER.error(f"Error in mock API: {e}")
            return self.json({"error": str(e)}, status_code=500)


class RBACServiceCallView(HomeAssistantView):
    """View to handle service calls for dashboard."""
    
    url = "/api/rbac/service-call"
    name = "api:rbac:service-call"
    requires_auth = False
    
    def __init__(self, hass: HomeAssistant):
        """Initialize the service call view."""
        self.hass = hass
    
    async def post(self, request: web.Request) -> web.Response:
        """Handle service calls."""
        try:
            data = await request.json()
            
            # Extract service call parameters
            domain = data.get('domain')
            service = data.get('service')
            service_data = data.get('service_data', {})
            target = data.get('target')
            
            if not domain or not service:
                return self.json({"error": "Missing domain or service"}, status_code=400)
            
            # Handle target parameter for services that need it
            if target:
                _LOGGER.info(f"Service call: {domain}.{service} with target: {target} and data: {service_data}")
                await self.hass.services.async_call(domain, service, service_data, target=target)
            else:
                # Standard service call
                _LOGGER.info(f"Service call: {domain}.{service} with data: {service_data}")
                await self.hass.services.async_call(domain, service, service_data)
            
            return self.json({"success": True, "message": f"Service {domain}.{service} called successfully"})
            
        except Exception as e:
            _LOGGER.error(f"Error calling service: {e}")
            return self.json({"error": str(e)}, status_code=500)


class RBACDashboardView(HomeAssistantView):
    """View to serve guest dashboard."""
    
    url = "/api/rbac/dashboard/{user_id}"
    name = "api:rbac:dashboard"
    requires_auth = False
    
    def __init__(self, hass: HomeAssistant):
        """Initialize the dashboard view."""
        self.hass = hass
        self._www_path = os.path.join(hass.config.config_dir, "custom_components", "rbac", "www")
        self._dashboards_path = os.path.join(self._www_path, "dashboards")
    
    async def get(self, request: web.Request, user_id: str) -> web.Response:
        """Serve dashboard page or dashboard data."""
        try:
            # Security: prevent directory traversal
            if ".." in user_id or "/" in user_id:
                return web.Response(status=403, text="Forbidden")
            
            # Check if requesting dashboard.html or dashboard data
            if request.query.get('format') == 'html':
                # Serve the dashboard.html page
                dashboard_html_path = os.path.join(self._www_path, "dashboard.html")
                
                if not os.path.exists(dashboard_html_path):
                    return web.Response(status=404, text="Dashboard page not found")
                
                with open(dashboard_html_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                return web.Response(
                    text=content,
                    content_type="text/html",
                    headers={"Cache-Control": "no-cache"}
                )
            else:
                # Serve dashboard data (YAML)
                dashboard_yml_path = os.path.join(self._dashboards_path, user_id, "dashboard.yml")
                
                if not os.path.exists(dashboard_yml_path):
                    # Return empty dashboard if file doesn't exist
                    dashboard_data = {"cards": []}
                else:
                    with open(dashboard_yml_path, 'r', encoding='utf-8') as f:
                        dashboard_data = yaml.safe_load(f) or {"cards": []}
                
                return self.json(dashboard_data)
                
        except Exception as e:
            _LOGGER.error(f"Error serving dashboard for user {user_id}: {e}")
            return self.json({"error": str(e)}, status_code=500)
