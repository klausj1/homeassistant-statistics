# Fitness Data Service Proposal for Home Assistant Statistics Integration

## Overview

This proposal outlines a new service for the Home Assistant Statistics integration that will allow users to create persistent Home Assistant components and entities for storing fitness data from various fitness trackers. This service will complement the existing `import_from_json` service, which will continue to be used for importing historical data.

## Service Name

`create_fitness_component`

## Purpose

To create a Home Assistant component with configurable entities for tracking fitness metrics such as:
- Sleep duration
- Step count
- Heart rate
- Blood oxygen levels
- Other customizable fitness metrics

## Key Features

1. **Generic Vendor Support**: Completely generic to allow any vendor name with custom configurations
2. **Configurable Entities**: Support for creating a variable set of entities based on user needs
3. **Persistent Components**: Creates actual Home Assistant entities (sensors) that persist in the system
4. **Flexible Configuration**: Allows customization of entity properties like unit, type, and other attributes
5. **Separation of Concerns**: Component creation is separate from data import, allowing for one-time setup followed by ongoing data updates

## Service Interface

The service will be called with the following parameters:

```yaml
service: import_statistics.create_fitness_component
data:
  component_name: "my_fitness_tracker"
  vendor: "Generic Fitness Tracker"
  device_info:
    model: "FT-1000"
    manufacturer: "Fitness Corp"
    sw_version: "1.0.0"
    hw_version: "2.0"
  entities:
    - name: "daily_steps"
      friendly_name: "Daily Steps"
      state_class: "total_increasing"
      icon: "mdi:foot-print"
    - name: "heart_rate"
      friendly_name: "Heart Rate"
      state_class: "measurement"
      icon: "mdi:heart-pulse"
    - name: "sleep_duration"
      friendly_name: "Sleep Duration"
      unit_of_measurement: "h"
      device_class: "duration"
      state_class: "total"
      icon: "mdi:sleep"
    - name: "blood_oxygen"
      friendly_name: "Blood Oxygen"
      state_class: "measurement"
      icon: "mdi:heart-pulse"
```

## Implementation Details

### 1. Service Registration

The service will be registered in `__init__.py` similar to the existing services:

```python
def handle_create_fitness_component(call: ServiceCall) -> None:
    """Handle the fitness component creation service call."""
    _LOGGER.info("Service handle_create_fitness_component called")
    create_fitness_component_entities(hass, call)

hass.services.register(DOMAIN, "create_fitness_component", handle_create_fitness_component)
```

### 2. Component Creation Logic

A new module `fitness_component.py` will handle the creation of the component and its entities:

```python
def create_fitness_component_entities(hass: HomeAssistant, call: ServiceCall) -> None:
    """Create a fitness component with its entities."""
    component_name = call.data.get("component_name")
    vendor = call.data.get("vendor")
    device_info = call.data.get("device_info", {})
    entities = call.data.get("entities", [])
    
    # Create component registry entry
    # Create sensor entities with specified configurations
    # Register entities with Home Assistant
```

### 3. Entity Configuration

Each entity will support the following configurable properties:
- `name`: Internal entity name (required)
- `friendly_name`: Display name in UI (required)
- `unit_of_measurement`: Unit for the sensor (optional)
- `device_class`: Type of sensor for HA to understand the data (optional)
- `state_class`: How to treat the state value (measurement, total, total_increasing) (optional)
- `icon`: Icon to display in UI (optional)
- Any additional custom attributes

### 4. Data Flow

1. User calls `create_fitness_component` service with desired configuration
2. Service creates component registry entry and sensor entities
3. Entities are now available in Home Assistant and can receive updates
4. User can then use the existing `import_from_json` service to import historical data for these entities
5. Future data updates can be sent to these entities through normal Home Assistant mechanisms

### 5. Integration with Existing Services

The new service will work seamlessly with the existing `import_from_json` service:

```yaml
# First, create the component
service: import_statistics.create_fitness_component
data:
  component_name: "my_fitness_tracker"
  vendor: "Generic Fitness Tracker"
  entities:
    - name: "daily_steps"
      friendly_name: "Daily Steps"
      unit_of_measurement: "steps"
      device_class: "step"
      state_class: "total_increasing"

# Then, import data using the existing service
service: import_statistics.import_from_json
data:
  timezone_identifier: Europe/Vienna
  entities:
    - id: "sensor.my_fitness_tracker_daily_steps"
      unit: "steps"
      values:
        - state: 8500
          sum: 8500
          datetime: "2024-09-13 00:00"
```

## Benefits

1. **Flexibility**: Users can create fitness tracking components for any vendor or custom setup
2. **Persistence**: Entities persist in Home Assistant and can be used in automations, dashboards, etc.
3. **Reusability**: One-time setup followed by ongoing data updates
4. **Integration**: Works seamlessly with existing data import services
5. **Customization**: Each entity can be configured with appropriate units, icons, and classes

## Technical Considerations

1. **Entity IDs**: Will follow the pattern `sensor.{component_name}_{entity_name}`
2. **Unique IDs**: Will be generated to ensure entities can be tracked across restarts
3. **Device Registry**: Components will be registered in the device registry for better organization
4. **Error Handling**: Proper validation and error messages for invalid configurations
5. **Cleanup**: Consideration for how to handle component deletion if needed

## Files to be Created/Modified

1. `custom_components/import_statistics/__init__.py` - Add service registration
2. `custom_components/import_statistics/fitness_component.py` - New module for component creation
3. `custom_components/import_statistics/services.yaml` - Add service definition
4. `custom_components/import_statistics/const.py` - Add new constants
5. Tests for the new functionality

## Example Use Cases

1. **Gadgetbridge Integration**: Create entities for a Gadgetbridge-synced fitness tracker
2. **Custom Fitness App**: Create entities for a custom fitness application
3. **Multiple Devices**: Create separate components for different fitness trackers
4. **Specialized Metrics**: Create entities for specialized fitness metrics not covered by standard sensors

## Conclusion

This proposal outlines a flexible and powerful way to extend the Home Assistant Statistics integration to support fitness data from any source. By separating component creation from data import, users can set up their fitness tracking infrastructure once and then use the existing robust data import mechanisms to populate it with historical and ongoing data.