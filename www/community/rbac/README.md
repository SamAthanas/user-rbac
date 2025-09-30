# RBAC Frontend JavaScript

This JavaScript file provides debugging and monitoring for the RBAC (Role-Based Access Control) middleware by intercepting WebSocket messages.

## Installation

### Option 1: Using the deploy script (recommended)
1. Run the frontend-only deploy script: `./scripts/deploy-frontend.sh`
2. Add the following to your Home Assistant `configuration.yaml`:

```yaml
frontend:
  extra_module_url:
    - /local/community/rbac/rbac.js
```

### Option 2: Manual installation
1. Copy the `rbac.js` file to your Home Assistant `www/community/rbac/` directory
2. Add the following to your Home Assistant `configuration.yaml`:

```yaml
frontend:
  extra_module_url:
    - /local/community/rbac/rbac.js
```

## How it works

The JavaScript file:
- Intercepts WebSocket messages sent from the frontend
- Provides debugging logs for WebSocket message types
- Works with Home Assistant's built-in user context system
- The backend uses Home Assistant's WebSocket connection user context for RBAC filtering

## Configuration

The frontend JavaScript provides debugging logs for WebSocket messages. No configuration is needed as it works with Home Assistant's built-in user context system.

## Benefits

- **Uses built-in context**: Leverages Home Assistant's native WebSocket user context
- **More reliable**: No custom user context injection needed
- **Better performance**: Backend filtering using native Home Assistant APIs
- **Cleaner implementation**: Simpler code with fewer edge cases

## Debugging

The JavaScript file logs to the browser console:
- `RBAC frontend script loaded`
- `RBAC: Patched WebSocket sendMessage`
- `RBAC: Patched WebSocket sendMessagePromise`
- `RBAC: WebSocket [message_type] by user: [user_id]`

Check the browser console (F12 → Console) to see the WebSocket message monitoring in action.
