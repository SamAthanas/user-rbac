# Home Assistant RBAC Middleware

A flexible Role-Based Access Control (RBAC) middleware component for Home Assistant that intercepts service calls and enforces access control based on YAML configuration.

## Features

- **Service Call Interception**: Automatically intercepts all Home Assistant service calls
- **YAML-Based Configuration**: Define access control rules in a YAML file
- **Domain and Entity Level Control**: Restrict access at both domain and entity levels
- **Flexible Access Models**: Support for both allowlist and restriction-based access
- **Dynamic Configuration**: Reload configuration without restarting Home Assistant
- **Comprehensive Logging**: Detailed logging of access attempts and denials
- **Persistent Notifications**: User-friendly notifications for access denials
- **Service Management**: Built-in services to manage and inspect configuration

## Installation

1. Copy the `rbac` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Add the component to your `configuration.yaml`
4. Configure access control in `access_control.yaml`

## Configuration

### Basic Configuration

Add the following to your `configuration.yaml`:

```yaml
rbac:
```

### Access Control Configuration

The component uses a YAML file located at `custom_components/rbac/access_control.yaml` to define access control rules.

#### YAML Structure

```yaml
version: "1.0"
description: "RBAC Access Control Configuration"
default_access: "allow"

users:
  user-id-1:
    role: "admin"
    access: "allow"
    restrictions:
      domains:
        homeassistant:
          access: "deny"
          services:
            - "restart"
            - "stop"
      entities:
        light.bedroom_light:
          access: "deny"
          services:
            - "turn_off"
```

#### Access Control Models

**1. Allowlist Model (access: "deny")**
- User is denied by default
- Only explicitly allowed services/entities are permitted

**2. Restriction Model (access: "allow")**
- User is allowed by default
- Only explicitly restricted services/entities are denied

#### Configuration Levels

**Domain Level**: Control access to entire service domains
```yaml
domains:
  light:
    access: "deny"
    services:
      - "turn_off"
      - "toggle"
```

**Entity Level**: Control access to specific entities
```yaml
entities:
  light.bedroom_light:
    access: "deny"
    services:
      - "turn_off"
```

## Services

The component provides several services to manage and inspect the configuration:

### rbac.get_user_config
Get the access control configuration for a specific user.

```yaml
service: rbac.get_user_config
data:
  user_id: "user-123"
```

### rbac.reload_config
Reload the access control configuration from the YAML file.

```yaml
service: rbac.reload_config
```

### rbac.list_users
List all configured users and their roles.

```yaml
service: rbac.list_users
```

## Usage Examples

### Basic Access Control Configuration

```yaml
version: "1.0"
default_access: "allow"

users:
  owner-user-id:
    role: "admin"
    access: "allow"
    restrictions:
      domains:
        homeassistant:
          access: "deny"
          services:
            - "restart"
            - "stop"

  guest-user-id:
    role: "guest"
    access: "deny"
    allowlist:
      domains:
        light:
          access: "allow"
          services:
            - "turn_on"
      entities:
        light.living_room:
          access: "allow"
          services:
            - "turn_on"
            - "turn_off"
```

### Configuration Management

```yaml
automation:
  - alias: "Reload RBAC Config"
    trigger:
      - platform: event
        event_type: rbac_config_changed
    action:
      - service: rbac.reload_config

script:
  check_user_access:
    sequence:
      - service: rbac.get_user_config
        data:
          user_id: "user-123"
      - service: rbac.list_users
```

## Logging

The component provides comprehensive logging:

- **INFO**: Component initialization and configuration loading
- **DEBUG**: All service call attempts (allowed and denied)
- **WARNING**: Access denials with user and service details
- **ERROR**: Component errors and configuration issues

Enable debug logging to see all service call attempts:

```yaml
logger:
  logs:
    custom_components.rbac: debug
```

## Security Considerations

1. **User ID Mapping**: Ensure user IDs in your YAML configuration match actual Home Assistant user IDs
2. **Default Access**: Users not in the configuration have full access by default
3. **Service Patching**: The component patches the core service call method - ensure this doesn't conflict with other components
4. **Persistent Notifications**: Access denials create persistent notifications that users can see
5. **YAML Configuration**: Keep the access control YAML file secure and backed up

## Troubleshooting

### Component Not Loading
- Check that the folder structure is correct: `custom_components/rbac/`
- Verify all required files are present
- Check Home Assistant logs for import errors
- Ensure `access_control.yaml` is valid YAML

### Access Control Not Working
- Verify the YAML configuration is valid
- Check that user IDs exist in Home Assistant
- Use the `rbac.get_user_config` service to inspect user configuration
- Review component logs for access decisions

### Configuration Issues
- Use `rbac.reload_config` service to reload configuration without restart
- Check YAML syntax with a validator
- Ensure proper file permissions on the YAML configuration

## Development

The component is structured as follows:

- `__init__.py`: Main component logic and service call interception
- `config_flow.py`: Configuration flow for UI setup
- `const.py`: Constants and default configurations
- `services.py`: Service definitions and handlers
- `services.yaml`: Service schemas
- `manifest.json`: Component metadata
- `access_control.yaml`: Access control configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.
