# Accessing Home Assistant Timezone from Docker Container

## Question
Can I access the Home Assistant frontend timezone setting from inside the Docker container where HA is running?

## Answer: YES! ✅

Home Assistant provides the timezone setting through the `hass` object, which is accessible from custom components running inside the Docker container.

---

## How to Access the Timezone

### Method 1: Using `hass.config.time_zone` (Recommended)

The timezone configured in Home Assistant's frontend is available via:

```python
from homeassistant.core import HomeAssistant

def get_ha_timezone(hass: HomeAssistant) -> str:
    """Get the Home Assistant configured timezone."""
    return hass.config.time_zone
```

This returns the IANA timezone identifier (e.g., `"Europe/Berlin"`, `"America/New_York"`, `"UTC"`).

### Example Integration in Your Code

Here's how you can modify your custom component to use HA's timezone instead of requiring users to specify it:

```python
from homeassistant.core import HomeAssistant, ServiceCall
import zoneinfo

async def handle_import_from_file_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle import_from_file service implementation."""

    # Get timezone from Home Assistant configuration
    timezone_identifier = hass.config.time_zone

    # Or allow override from service call with HA timezone as default
    timezone_identifier = call.data.get("timezone_identifier", hass.config.time_zone)

    # Use it with zoneinfo
    timezone = zoneinfo.ZoneInfo(timezone_identifier)

    # ... rest of your code
```

---

## Current State in Your Codebase

### How Timezone is Currently Handled

Your custom component currently **requires** users to specify the timezone in every service call:

**File: [`custom_components/import_statistics/import_service_helper.py`](custom_components/import_statistics/import_service_helper.py:164)**
```python
timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER)

if timezone_identifier not in pytz.all_timezones:
    helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")
```

**File: [`custom_components/import_statistics/export_service.py`](custom_components/import_statistics/export_service.py:146)**
```python
timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER, "Europe/Vienna")
```

### Issues with Current Approach

1. **User Burden**: Users must manually specify timezone in every service call
2. **Inconsistency**: Export has a hardcoded default (`"Europe/Vienna"`), import has no default
3. **Redundancy**: Users already configured timezone in HA frontend
4. **Error-Prone**: Users might specify wrong timezone or forget to include it

---

## Recommended Improvements

### 1. Use HA Timezone as Default

Modify [`handle_arguments()`](custom_components/import_statistics/import_service_helper.py:141) to use HA's timezone as default:

```python
def handle_arguments(hass: HomeAssistant, call: ServiceCall) -> tuple:
    """Handle the arguments for importing statistics from a file."""

    # Use HA's configured timezone as default, allow override
    timezone_identifier = call.data.get(
        ATTR_TIMEZONE_IDENTIFIER,
        hass.config.time_zone  # ✅ Use HA timezone as default
    )

    if timezone_identifier not in pytz.all_timezones:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    # ... rest of function
```

### 2. Update Service Signatures

You'll need to pass `hass` to functions that currently don't receive it:

**Before:**
```python
def prepare_data_to_import(file_path: str, call: ServiceCall) -> tuple:
    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(call)
```

**After:**
```python
def prepare_data_to_import(hass: HomeAssistant, file_path: str, call: ServiceCall) -> tuple:
    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(hass, call)
```

### 3. Update Service Calls

**File: [`custom_components/import_statistics/import_service.py`](custom_components/import_statistics/import_service.py:254)**

**Before:**
```python
df, timezone_id, datetime_format, unit_from_entity, is_delta = await hass.async_add_executor_job(
    lambda: prepare_data_to_import(file_path, call)
)
```

**After:**
```python
df, timezone_id, datetime_format, unit_from_entity, is_delta = await hass.async_add_executor_job(
    lambda: prepare_data_to_import(hass, file_path, call)
)
```

### 4. Update Services YAML

Make timezone optional in [`services.yaml`](custom_components/import_statistics/services.yaml):

```yaml
import_from_file:
  description: Import statistics from a CSV/TSV file
  fields:
    timezone_identifier:
      description: >
        Timezone identifier (IANA format, e.g., 'Europe/Berlin').
        If not specified, uses Home Assistant's configured timezone.
      example: "Europe/Berlin"
      required: false  # ✅ Make it optional
      selector:
        text:
```

---

## Docker Container Considerations

### System Timezone vs HA Timezone

**Important distinction:**

1. **Container System Timezone**: The timezone of the Docker container's OS (usually UTC)
2. **Home Assistant Timezone**: The timezone configured in HA's frontend (stored in `hass.config.time_zone`)

Your [`get_timezone.py`](get_timezone.py) script reads the **container's system timezone**, which is typically UTC in Docker containers. This is **different** from the user's configured HA timezone.

### Why Use `hass.config.time_zone` Instead of System Timezone

```python
# ❌ DON'T: Read container system timezone
import datetime as dt
system_tz = dt.datetime.now().astimezone().tzinfo  # Returns UTC in Docker

# ✅ DO: Use Home Assistant's configured timezone
def get_timezone(hass: HomeAssistant) -> str:
    return hass.config.time_zone  # Returns user's actual timezone
```

### Container Timezone Files

Inside the Docker container, you'll find:
- `/etc/timezone` - Usually contains `"Etc/UTC"`
- `/etc/localtime` - Symlink to `/usr/share/zoneinfo/Etc/UTC`

These reflect the **container's** timezone, not the user's HA timezone.

---

## Complete Example: Timezone-Aware Service

Here's a complete example showing best practices:

```python
from homeassistant.core import HomeAssistant, ServiceCall
import zoneinfo
import datetime as dt

async def handle_import_from_file_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle import with timezone awareness."""

    # Get timezone from HA config (with optional override)
    timezone_identifier = call.data.get("timezone_identifier", hass.config.time_zone)

    # Validate timezone
    try:
        timezone = zoneinfo.ZoneInfo(timezone_identifier)
    except zoneinfo.ZoneInfoNotFoundError:
        raise HomeAssistantError(f"Invalid timezone: {timezone_identifier}")

    # Log for debugging
    _LOGGER.info(
        "Using timezone: %s (HA default: %s)",
        timezone_identifier,
        hass.config.time_zone
    )

    # Parse user-provided timestamp in their timezone
    user_timestamp = "18.01.2026 14:30"
    dt_obj = dt.datetime.strptime(user_timestamp, "%d.%m.%Y %H:%M")
    dt_obj = dt_obj.replace(tzinfo=timezone)

    # Convert to UTC for storage
    dt_utc = dt_obj.astimezone(dt.UTC)

    # ... rest of import logic
```

---

## Testing Timezone Access

You can test timezone access using the Home Assistant MCP server:

```python
# Get HA version (confirms connection)
await mcp.get_version()

# The timezone is part of hass.config, accessible in custom components
# It's set in Configuration -> General -> Time Zone in the frontend
```

---

## Summary

### ✅ What You Can Do

1. **Access HA timezone**: Use `hass.config.time_zone` in any custom component
2. **Use as default**: Make timezone parameter optional, defaulting to HA's setting
3. **Allow override**: Let users override if they need a different timezone
4. **Simplify UX**: Remove burden of specifying timezone in every service call

### ❌ What to Avoid

1. **Don't read system timezone**: Container timezone is usually UTC, not user's timezone
2. **Don't hardcode defaults**: `"Europe/Vienna"` is arbitrary and wrong for most users
3. **Don't require timezone**: Users already configured it in HA

### 🎯 Recommended Changes

1. Add `hass` parameter to [`handle_arguments()`](custom_components/import_statistics/import_service_helper.py:141)
2. Use `hass.config.time_zone` as default for `timezone_identifier`
3. Update all callers to pass `hass` object
4. Make `timezone_identifier` optional in [`services.yaml`](custom_components/import_statistics/services.yaml)
5. Update documentation to explain the default behavior

---

## Additional Resources

- **Home Assistant Config Object**: [Core Documentation](https://developers.home-assistant.io/docs/dev_101_hass/)
- **Python zoneinfo**: [Python 3.12 Documentation](https://docs.python.org/3/library/zoneinfo.html)
- **IANA Timezone Database**: [Wikipedia](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

---

## Architecture Diagram

```mermaid
graph TD
    A[User Configures Timezone in HA Frontend] -->|Stored in| B[hass.config.time_zone]
    B -->|Accessed by| C[Custom Component]
    C -->|Uses| D[zoneinfo.ZoneInfo]
    D -->|Converts| E[User Timestamps to UTC]
    E -->|Stored in| F[Recorder Database]

    G[Docker Container System TZ] -.->|Usually UTC| H[/etc/timezone]
    H -.->|Don't use this| C

    style B fill:#90EE90
    style C fill:#87CEEB
    style G fill:#FFB6C1
    style H fill:#FFB6C1
```

The green path shows the correct approach (using HA's configured timezone), while the red path shows what to avoid (using container's system timezone).
