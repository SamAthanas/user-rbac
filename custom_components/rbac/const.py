"""Constants for the RBAC integration."""

DOMAIN = "rbac"

# Configuration keys
CONF_USERS = "users"
CONF_RESTRICTIONS = "restrictions"

# Role hierarchy (higher number = more permissions)
ROLE_HIERARCHY = {
    "guest": 0,
    "user": 1,
    "admin": 2,
    "super_admin": 3
}

# Default roles
DEFAULT_ROLES = ["guest", "user", "admin", "super_admin"]

# Service domains that can be restricted
RESTRICTABLE_DOMAINS = [
    "light",
    "switch",
    "homeassistant",
    "system_log",
    "logger",
    "input_boolean",
    "input_number",
    "input_select",
    "input_text",
    "scene",
    "script",
    "automation",
    "group",
    "person",
    "zone",
    "sun",
    "weather",
    "calendar",
    "camera",
    "media_player",
    "climate",
    "cover",
    "fan",
    "lock",
    "vacuum",
    "water_heater",
    "alarm_control_panel",
    "notify",
]

# Common services that are often restricted
COMMON_SERVICES = {
    "light": ["turn_on", "turn_off", "toggle"],
    "switch": ["turn_on", "turn_off", "toggle"],
    "homeassistant": ["restart", "stop", "reload_config_entry"],
    "system_log": ["clear", "write"],
    "logger": ["set_level"],
    "input_boolean": ["turn_on", "turn_off", "toggle"],
    "input_number": ["set_value", "increment", "decrement"],
    "input_select": ["select_option", "select_next", "select_previous"],
    "input_text": ["set_value"],
    "scene": ["turn_on"],
    "script": ["turn_on", "turn_off", "toggle"],
    "automation": ["trigger", "toggle", "turn_on", "turn_off"],
    "group": ["set", "reload"],
    "person": ["reload"],
    "zone": ["reload"],
    "sun": ["reload"],
    "weather": ["reload"],
    "calendar": ["create_event", "delete_event"],
    "camera": ["snapshot", "record"],
    "media_player": [
        "volume_set", "volume_mute", "volume_up", "volume_down",
        "media_play", "media_pause", "media_stop", "media_next_track",
        "media_previous_track", "play_media", "select_source"
    ],
    "climate": [
        "set_temperature", "set_hvac_mode", "set_fan_mode",
        "set_swing_mode", "set_preset_mode"
    ],
    "cover": ["open", "close", "stop", "set_position", "set_tilt_position"],
    "fan": ["turn_on", "turn_off", "set_speed", "oscillate", "set_direction"],
    "lock": ["lock", "unlock"],
    "vacuum": [
        "start", "pause", "stop", "return_to_base", "clean_spot",
        "locate", "set_fan_speed", "send_command"
    ],
    "water_heater": ["set_temperature", "set_operation_mode"],
    "alarm_control_panel": [
        "alarm_arm_away", "alarm_arm_home", "alarm_arm_night",
        "alarm_arm_vacation", "alarm_disarm", "alarm_trigger"
    ],
    "notify": ["persistent_notification"]
}
