"""User-scoped state and entity registry filtering for RBAC."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

import voluptuous as vol
from homeassistant.auth.permissions import AbstractPermissions
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

RBAC_MIDDLEWARE_DEVICE_IDENTIFIERS = frozenset({(DOMAIN, "rbac_middleware")})
MIN_HA_VERSION = (2024, 1, 0)


@dataclass(frozen=True)
class EntityVisibilityConfig:
    """Precomputed visibility for a user/role."""

    apply_filter: bool = False
    deny_all: bool = False
    blocked_entities: frozenset[str] = frozenset()
    blocked_domains: frozenset[str] = frozenset()
    allowed_entities: frozenset[str] = frozenset()
    allowed_domains: frozenset[str] = frozenset()

    def is_visible(self, entity_id: str) -> bool:
        """Return True if entity state/registry entry should be visible."""
        if not self.apply_filter:
            return True
        if entity_id in self.allowed_entities:
            return True
        domain = entity_id.split(".", 1)[0]
        if domain in self.allowed_domains:
            return True
        if self.deny_all:
            return False
        if entity_id in self.blocked_entities:
            return False
        if domain in self.blocked_domains:
            return False
        return True


@dataclass(frozen=True)
class _VisibilityComputeResult(EntityVisibilityConfig):
    """Internal visibility result that may include blocked services."""

    blocked_services: frozenset[str] = frozenset()


def _parse_ha_version(version: str) -> tuple[int, ...]:
    """Parse HA version string into comparable tuple."""
    parts: list[int] = []
    for segment in version.split(".")[:3]:
        digits = "".join(ch for ch in segment if ch.isdigit())
        if digits:
            parts.append(int(digits))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def validate_ha_version() -> bool:
    """Return True if the running HA version meets the minimum requirement."""
    current = _parse_ha_version(HA_VERSION)
    if current < MIN_HA_VERSION:
        _LOGGER.error(
            "RBAC state filter requires Home Assistant %s+ (running %s)",
            ".".join(str(p) for p in MIN_HA_VERSION),
            HA_VERSION,
        )
        return False
    return True


def _validate_permissions_patch() -> bool:
    """Verify User.permissions can be patched safely."""
    import homeassistant.auth.models as auth_models
    from functools import cached_property as std_cached_property

    descriptor = auth_models.User.permissions
    if not hasattr(descriptor, "func"):
        _LOGGER.error(
            "RBAC state filter: User.permissions has no func attribute; "
            "incompatible Home Assistant auth model"
        )
        return False

    try:
        test_descriptor = std_cached_property(lambda self: None)
        test_descriptor.__set_name__(auth_models.User, "_rbac_patch_test")
    except Exception as err:  # noqa: BLE001
        _LOGGER.error(
            "RBAC state filter: cached_property __set_name__ test failed: %s", err
        )
        return False

    return True


def clear_visibility_cache(hass: HomeAssistant) -> None:
    """Clear cached visibility configs after config or registry changes."""
    if DOMAIN in hass.data:
        hass.data[DOMAIN].pop("visibility_cache", None)


def should_apply_state_filter(hass: HomeAssistant, user_id: str) -> bool:
    """Return True when RBAC should filter state/entity API responses."""
    if DOMAIN not in hass.data:
        return False

    access_config = hass.data[DOMAIN].get("access_config", {})
    if not access_config.get("enabled", True):
        return False

    state_filter_enabled = access_config.get(
        "state_api_filter_enabled",
        access_config.get("frontend_blocking_enabled", True),
    )
    if not state_filter_enabled:
        return False

    user_config = access_config.get("users", {}).get(user_id)
    if not user_config:
        return False

    role_name = user_config.get("role", "user")
    role_config = access_config.get("roles", {}).get(role_name, {})
    if role_config.get("admin", False):
        return False

    return True


def _visibility_cache_key(hass: HomeAssistant, user_id: str) -> str | None:
    """Build a role + user-override cache key."""
    access_config = hass.data.get(DOMAIN, {}).get("access_config", {})
    user_config = access_config.get("users", {}).get(user_id)
    if not user_config:
        return None

    role_name = user_config.get("role", "user")
    restrictions = user_config.get("restrictions", {})
    override_hash = hashlib.md5(
        json.dumps(restrictions, sort_keys=True, default=str).encode(),
        usedforsecurity=False,
    ).hexdigest()[:8]
    return f"{role_name}:{override_hash}"


def get_visibility_config(hass: HomeAssistant, user_id: str) -> EntityVisibilityConfig:
    """Return cached visibility config for a user."""
    cache_key = _visibility_cache_key(hass, user_id)
    if cache_key is None:
        return _VisibilityComputeResult(apply_filter=False)

    cache = hass.data.setdefault(DOMAIN, {}).setdefault("visibility_cache", {})
    if cache_key not in cache:
        cache[cache_key] = _compute_visibility_config(
            hass, user_id, include_services=True
        )
    return cache[cache_key]


def is_entity_visible_for_user(
    hass: HomeAssistant, user_id: str, entity_id: str
) -> bool:
    """Return True if entity should appear in state/entity APIs for this user."""
    if not should_apply_state_filter(hass, user_id):
        return True
    if _is_rbac_internal_entity(hass, entity_id):
        return False
    return get_visibility_config(hass, user_id).is_visible(entity_id)


def get_frontend_blocking_response(
    hass: HomeAssistant, user_id: str
) -> dict[str, Any]:
    """Build frontend blocking API payload (used by RBACFrontendBlockingView)."""
    access_config = hass.data.get(DOMAIN, {}).get("access_config", {})
    rbac_enabled = access_config.get("enabled", True)
    frontend_blocking_enabled = access_config.get("frontend_blocking_enabled", True)

    if not rbac_enabled or not frontend_blocking_enabled:
        return {"enabled": False, "domains": [], "entities": [], "services": []}

    user_config = access_config.get("users", {}).get(user_id)
    if not user_config:
        return {"enabled": True, "domains": [], "entities": [], "services": []}

    role_name = user_config.get("role", "user")
    role_config = access_config.get("roles", {}).get(role_name, {})
    if role_config.get("admin", False):
        return {"enabled": True, "domains": [], "entities": [], "services": []}

    visibility_result = get_visibility_config(hass, user_id)
    if not visibility_result.apply_filter:
        return {"enabled": True, "domains": [], "entities": [], "services": []}

    blocked_services = (
        visibility_result.blocked_services
        if isinstance(visibility_result, _VisibilityComputeResult)
        else frozenset()
    )

    response: dict[str, Any] = {
        "enabled": True,
        "deny_all": visibility_result.deny_all,
        "domains": sorted(visibility_result.blocked_domains),
        "entities": sorted(visibility_result.blocked_entities),
        "services": sorted(blocked_services),
    }
    if visibility_result.allowed_domains:
        response["allowed_domains"] = sorted(visibility_result.allowed_domains)
    if visibility_result.allowed_entities:
        response["allowed_entities"] = sorted(visibility_result.allowed_entities)
    return response


def _collect_allow_lists_from_config(
    role_domains: dict[str, Any],
    role_entities: dict[str, Any],
    user_domains: dict[str, Any],
    user_entities: dict[str, Any],
) -> tuple[set[str], set[str]]:
    """Collect explicitly allowed domains/entities from YAML (O(config size))."""
    allowed_domains: set[str] = set()
    allowed_entities: set[str] = set()

    for domains, entities in (
        (role_domains, role_entities),
        (user_domains, user_entities),
    ):
        for domain, domain_config in domains.items():
            if isinstance(domain_config, dict) and domain_config.get("allow", False):
                allowed_domains.add(domain)
        for entity, entity_config in entities.items():
            if isinstance(entity_config, dict) and entity_config.get("allow", False):
                allowed_entities.add(entity)

    return allowed_domains, allowed_entities


def _compute_deny_all_visibility(
    role_domains: dict[str, Any],
    role_entities: dict[str, Any],
    user_domains: dict[str, Any],
    user_entities: dict[str, Any],
) -> _VisibilityComputeResult:
    """Build allow-list-only visibility for deny_all roles."""
    allowed_domains, allowed_entities = _collect_allow_lists_from_config(
        role_domains, role_entities, user_domains, user_entities
    )
    return _VisibilityComputeResult(
        apply_filter=True,
        deny_all=True,
        allowed_domains=frozenset(allowed_domains),
        allowed_entities=frozenset(allowed_entities),
    )


def _compute_visibility_config(
    hass: HomeAssistant,
    user_id: str,
    *,
    include_services: bool = False,
) -> _VisibilityComputeResult:
    """Compute blocked/allowed entity sets from RBAC YAML."""
    access_config = hass.data.get(DOMAIN, {}).get("access_config", {})
    if not should_apply_state_filter(hass, user_id):
        return _VisibilityComputeResult(apply_filter=False)

    user_config = access_config["users"][user_id]
    role_name = user_config.get("role", "user")
    role_config = access_config.get("roles", {}).get(role_name, {})
    deny_all = role_config.get("deny_all", False)

    role_permissions = role_config.get("permissions", {})
    role_domains = role_permissions.get("domains", {})
    role_entities = role_permissions.get("entities", {})
    user_restrictions = user_config.get("restrictions", {})
    user_domains = user_restrictions.get("domains", {})
    user_entities = user_restrictions.get("entities", {})

    if deny_all:
        return _compute_deny_all_visibility(
            role_domains, role_entities, user_domains, user_entities
        )

    all_available_domains: set[str] = set()
    all_available_entities: set[str] = set()
    for state in hass.states.async_all():
        domain = state.entity_id.split(".", 1)[0]
        all_available_domains.add(domain)
        all_available_entities.add(state.entity_id)
    for domain in hass.services.async_services():
        all_available_domains.add(domain)

    blocked_domains: set[str] = set()
    blocked_entities: set[str] = set()
    blocked_services: set[str] = set()
    allowed_domains: set[str] = set()
    allowed_entities: set[str] = set()

    default_restrictions = access_config.get("default_restrictions", {})
    default_domains = default_restrictions.get("domains", {})
    default_entities = default_restrictions.get("entities", {})

    for domain in all_available_domains:
        domain_blocked = False
        domain_services: list[str] = []
        domain_allowed = False

        if domain in user_domains:
            user_domain_config = user_domains[domain]
            if isinstance(user_domain_config, dict):
                user_services = user_domain_config.get("services", [])
                domain_allowed = user_domain_config.get("allow", False)
                if domain_allowed:
                    allowed_domains.add(domain)
                    continue
                if not user_services:
                    domain_blocked = True
                else:
                    domain_services = user_services
            else:
                domain_blocked = True
        elif domain in role_domains:
            role_domain_config = role_domains[domain]
            if isinstance(role_domain_config, dict):
                role_services = role_domain_config.get("services", [])
                domain_allowed = role_domain_config.get("allow", False)
                if domain_allowed:
                    allowed_domains.add(domain)
                    continue
                if not role_services:
                    domain_blocked = True
                else:
                    domain_services = role_services
            else:
                domain_blocked = True
        elif domain in default_domains:
            default_domain_config = default_domains[domain]
            if isinstance(default_domain_config, dict):
                default_services = default_domain_config.get("services", [])
                domain_allowed = default_domain_config.get("allow", False)
                if domain_allowed:
                    allowed_domains.add(domain)
                    continue
                if not default_services:
                    domain_blocked = True
                else:
                    domain_services = default_services
            else:
                domain_blocked = True

        if domain_blocked:
            blocked_domains.add(domain)
        elif include_services and domain_services:
            blocked_services.update(f"{domain}.{service}" for service in domain_services)

    for entity in all_available_entities:
        entity_blocked = False
        entity_services: list[str] = []
        entity_allowed = False

        if entity in user_entities:
            user_entity_config = user_entities[entity]
            if isinstance(user_entity_config, dict):
                user_services = user_entity_config.get("services", [])
                entity_allowed = user_entity_config.get("allow", False)
                if entity_allowed:
                    allowed_entities.add(entity)
                    continue
                if not user_services:
                    entity_blocked = True
                else:
                    entity_services = user_services
            else:
                entity_blocked = True
        elif entity in role_entities:
            role_entity_config = role_entities[entity]
            if isinstance(role_entity_config, dict):
                role_services = role_entity_config.get("services", [])
                entity_allowed = role_entity_config.get("allow", False)
                if entity_allowed:
                    allowed_entities.add(entity)
                    continue
                if not role_services:
                    entity_blocked = True
                else:
                    entity_services = role_services
            else:
                entity_blocked = True
        elif entity in default_entities:
            default_entity_config = default_entities[entity]
            if isinstance(default_entity_config, dict):
                default_services = default_entity_config.get("services", [])
                entity_allowed = default_entity_config.get("allow", False)
                if entity_allowed:
                    allowed_entities.add(entity)
                    continue
                if not default_services:
                    entity_blocked = True
                else:
                    entity_services = default_services
            else:
                entity_blocked = True

        if entity_blocked:
            blocked_entities.add(entity)
        elif include_services and entity_services:
            blocked_services.update(f"{entity}.{service}" for service in entity_services)

    return _VisibilityComputeResult(
        apply_filter=True,
        deny_all=False,
        blocked_domains=frozenset(blocked_domains),
        blocked_entities=frozenset(blocked_entities),
        allowed_domains=frozenset(allowed_domains),
        allowed_entities=frozenset(allowed_entities),
        blocked_services=frozenset(blocked_services),
    )


def _is_rbac_integration_device(device_entry: dr.DeviceEntry | None) -> bool:
    """Return True for the RBAC Middleware integration device."""
    if device_entry is None:
        return False
    return any(
        identifier in RBAC_MIDDLEWARE_DEVICE_IDENTIFIERS
        for identifier in device_entry.identifiers
    )


def _is_rbac_internal_entity(hass: HomeAssistant, entity_id: str) -> bool:
    """Return True for RBAC integration entities that should stay hidden."""
    return entity_id.startswith(
        ("sensor.rbac_middleware_", "update.rbac_", "switch.rbac_middleware_")
    )


def _user_has_full_entity_access(user) -> bool:
    """Return True when HA grants unrestricted entity read access."""
    return user.is_admin or user.permissions.access_all_entities(POLICY_READ)


def _visible_area_ids(hass: HomeAssistant, entity_perm) -> set[str]:
    """Return area IDs that contain at least one visible entity."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    visible_areas: set[str] = set()

    for entry in entity_registry.entities.values():
        if not entity_perm(entry.entity_id, POLICY_READ):
            continue
        if entry.area_id:
            visible_areas.add(entry.area_id)
        if entry.device_id:
            device = device_registry.devices.get(entry.device_id)
            if device and device.area_id:
                visible_areas.add(device.area_id)

    return visible_areas


def _visible_device_ids(hass: HomeAssistant, entity_perm) -> set[str]:
    """Return device IDs that have at least one visible entity."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    visible_devices: set[str] = set()

    for entry in entity_registry.entities.values():
        if not entry.device_id or not entity_perm(entry.entity_id, POLICY_READ):
            continue
        device_entry = device_registry.devices.get(entry.device_id)
        if _is_rbac_integration_device(device_entry):
            continue
        visible_devices.add(entry.device_id)

    return visible_devices


class RBACPermissionsWrapper(AbstractPermissions):
    """Wrap HA permissions to apply RBAC entity visibility on POLICY_READ."""

    def __init__(
        self,
        hass: HomeAssistant,
        user_id: str,
        wrapped: AbstractPermissions,
    ) -> None:
        self._hass = hass
        self._user_id = user_id
        self._wrapped = wrapped
        self._apply_read_filter: bool | None = None

    def _read_filter_active(self) -> bool:
        if self._apply_read_filter is None:
            self._apply_read_filter = should_apply_state_filter(self._hass, self._user_id)
        return self._apply_read_filter

    def access_all_entities(self, key: str) -> bool:
        if key == POLICY_READ and self._read_filter_active():
            return False
        return self._wrapped.access_all_entities(key)

    def check_entity(self, entity_id: str, key: str) -> bool:
        if key == POLICY_READ and self._read_filter_active():
            if not is_entity_visible_for_user(self._hass, self._user_id, entity_id):
                return False
        return self._wrapped.check_entity(entity_id, key)

    def _entity_func(self):
        return self._wrapped._entity_func()


@callback
def _on_entity_registry_updated(hass: HomeAssistant, event: Event) -> None:
    """Invalidate visibility cache when entities are added/removed/updated."""
    clear_visibility_cache(hass)


def setup_state_api_filter(hass: HomeAssistant) -> None:
    """Install permission wrapper and filtered registry websocket handlers."""
    if hass.data.get(DOMAIN, {}).get("state_api_filter_installed"):
        return

    access_config = hass.data.get(DOMAIN, {}).get("access_config", {})
    state_filter_enabled = access_config.get(
        "state_api_filter_enabled",
        access_config.get("frontend_blocking_enabled", True),
    )
    if not state_filter_enabled:
        _LOGGER.warning("RBAC state/entity API filtering disabled in access_control.yaml")
        return

    if not validate_ha_version() or not _validate_permissions_patch():
        _LOGGER.error(
            "RBAC state/entity API filtering disabled due to compatibility check failure"
        )
        return

    _patch_user_permissions(hass)
    _register_filtered_registry_handlers(hass)
    hass.bus.async_listen(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        lambda event: _on_entity_registry_updated(hass, event),
    )
    hass.data.setdefault(DOMAIN, {})["state_api_filter_installed"] = True
    _LOGGER.warning(
        "RBAC state/entity API filtering enabled (HA %s, cache keyed by role)",
        HA_VERSION,
    )


def _patch_user_permissions(hass: HomeAssistant) -> None:
    if hass.data.get(DOMAIN, {}).get("permissions_patched"):
        return

    import homeassistant.auth.models as auth_models
    from functools import cached_property as std_cached_property

    original_func = auth_models.User.permissions.func

    def permissions_impl(self) -> AbstractPermissions:
        base = original_func(self)
        return RBACPermissionsWrapper(hass, self.id, base)

    descriptor = std_cached_property(permissions_impl)
    descriptor.__set_name__(auth_models.User, "permissions")
    auth_models.User.permissions = descriptor
    hass.data.setdefault(DOMAIN, {})["permissions_patched"] = True
    _LOGGER.debug("Patched User.permissions with RBAC wrapper")


def _register_filtered_registry_handlers(hass: HomeAssistant) -> None:
    _register_filtered_entity_registry_handler(hass)
    _register_filtered_area_registry_handler(hass)
    _register_filtered_device_registry_handler(hass)


def _register_filtered_entity_registry_handler(hass: HomeAssistant) -> None:
    entity_categories_json = json.dumps(er.ENTITY_CATEGORY_INDEX_TO_VALUE)

    @websocket_api.websocket_command(
        {vol.Required("type"): "config/entity_registry/list_for_display"}
    )
    @callback
    def websocket_list_entities_for_display_rbac(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        registry = er.async_get(hass)
        user = connection.user

        if _user_has_full_entity_access(user):
            entries = [
                entry.display_json_repr
                for entry in registry.entities.values()
                if entry.disabled_by is None and entry.display_json_repr is not None
            ]
        else:
            entity_perm = user.permissions.check_entity
            entries = [
                entry.display_json_repr
                for entry in registry.entities.values()
                if entry.disabled_by is None
                and entry.display_json_repr is not None
                and entity_perm(entry.entity_id, POLICY_READ)
            ]

        msg_json_prefix = (
            f'{{"id":{msg["id"]},"type":"{websocket_api.TYPE_RESULT}","success":true,'
            f'"result":{{"entity_categories":{entity_categories_json},"entities":['
        ).encode()
        inner = b",".join(entries)
        connection.send_message(b"".join((msg_json_prefix, inner, b"]}}")))

    websocket_api.async_register_command(hass, websocket_list_entities_for_display_rbac)
    _LOGGER.debug("Registered RBAC-filtered entity registry list_for_display handler")


def _register_filtered_area_registry_handler(hass: HomeAssistant) -> None:
    @websocket_api.websocket_command(
        {vol.Required("type"): "config/area_registry/list"}
    )
    @callback
    def websocket_list_areas_rbac(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        registry = ar.async_get(hass)
        user = connection.user

        if _user_has_full_entity_access(user):
            areas = [entry.json_fragment for entry in registry.async_list_areas()]
        else:
            visible_areas = _visible_area_ids(hass, user.permissions.check_entity)
            areas = [
                entry.json_fragment
                for entry in registry.async_list_areas()
                if entry.id in visible_areas
            ]

        connection.send_result(msg["id"], areas)

    websocket_api.async_register_command(hass, websocket_list_areas_rbac)
    _LOGGER.debug("Registered RBAC-filtered area registry list handler")


def _register_filtered_device_registry_handler(hass: HomeAssistant) -> None:
    @websocket_api.websocket_command(
        {vol.Required("type"): "config/device_registry/list"}
    )
    @callback
    def websocket_list_devices_rbac(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        registry = dr.async_get(hass)
        user = connection.user

        if _user_has_full_entity_access(user):
            devices = [
                entry.json_repr
                for entry in registry.devices.values()
                if entry.json_repr is not None
            ]
        else:
            visible_devices = _visible_device_ids(hass, user.permissions.check_entity)
            devices = [
                entry.json_repr
                for entry in registry.devices.values()
                if entry.json_repr is not None and entry.id in visible_devices
            ]

        msg_json_prefix = (
            f'{{"id":{msg["id"]},"type": "{websocket_api.TYPE_RESULT}",'
            f'"success":true,"result": ['
        ).encode()
        inner = b",".join(devices)
        connection.send_message(b"".join((msg_json_prefix, inner, b"]}")))

    websocket_api.async_register_command(hass, websocket_list_devices_rbac)
    _LOGGER.debug("Registered RBAC-filtered device registry list handler")
