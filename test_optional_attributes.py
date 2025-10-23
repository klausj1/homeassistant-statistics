#!/usr/bin/env python3
"""Test script to verify that optional attributes are not set when they are None."""

import asyncio
from unittest.mock import Mock
from homeassistant.core import HomeAssistant, ServiceCall

# Import the module we're testing
from custom_components.import_statistics import fitness_component


async def test_optional_attributes():
    """Test that optional attributes are not included when None."""
    # Create a mock Home Assistant instance
    hass = Mock(spec=HomeAssistant)
    hass.states = Mock()
    
    # Track what states are set
    set_states = {}
    
    def async_set(entity_id, new_state, attributes=None):
        set_states[entity_id] = {
            "state": new_state,
            "attributes": attributes or {}
        }
    
    hass.states.async_set = async_set
    
    # Test data with minimal entity configuration (no optional attributes)
    test_data = {
        "component_name": "test_tracker",
        "vendor": "Test Vendor",
        "entities": [
            {
                "name": "steps",
                "friendly_name": "Steps",
                # No unit_of_measurement, device_class, state_class, or icon
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    # Call the function
    await fitness_component.create_fitness_component_entities(hass, call)
    
    # Check the created entity
    entity_id = "sensor.test_tracker_steps"
    assert entity_id in set_states, f"Entity {entity_id} was not created"
    
    attributes = set_states[entity_id]["attributes"]
    
    # Verify that optional attributes are NOT present
    assert "unit_of_measurement" not in attributes, "unit_of_measurement should not be set when None"
    assert "device_class" not in attributes, "device_class should not be set when None"
    assert "state_class" not in attributes, "state_class should not be set when None"
    assert "icon" not in attributes, "icon should not be set when None"
    
    # Verify that required attributes ARE present
    assert "friendly_name" in attributes, "friendly_name should be set"
    assert attributes["friendly_name"] == "Steps"
    assert "unique_id" in attributes, "unique_id should be set"
    
    print("✓ Test passed: Optional attributes are not set when None")
    
    # Test with mixed attributes
    test_data_mixed = {
        "component_name": "mixed_tracker",
        "vendor": "Mixed Vendor",
        "entities": [
            {
                "name": "heart_rate",
                "friendly_name": "Heart Rate",
                "unit_of_measurement": "bpm",
                # device_class omitted
                "state_class": "measurement",
                # icon omitted
            },
        ],
    }
    
    call_mixed = ServiceCall("import_statistics", "create_fitness_component", test_data_mixed, test_data_mixed)
    
    # Clear previous states
    set_states.clear()
    
    # Call the function
    await fitness_component.create_fitness_component_entities(hass, call_mixed)
    
    # Check the created entity
    entity_id_mixed = "sensor.mixed_tracker_heart_rate"
    assert entity_id_mixed in set_states, f"Entity {entity_id_mixed} was not created"
    
    attributes_mixed = set_states[entity_id_mixed]["attributes"]
    
    # Verify that only specified optional attributes are present
    assert "unit_of_measurement" in attributes_mixed, "unit_of_measurement should be set when provided"
    assert attributes_mixed["unit_of_measurement"] == "bpm"
    assert "device_class" not in attributes_mixed, "device_class should not be set when omitted"
    assert "state_class" in attributes_mixed, "state_class should be set when provided"
    assert attributes_mixed["state_class"] == "measurement"
    assert "icon" not in attributes_mixed, "icon should not be set when omitted"
    
    print("✓ Test passed: Mixed attributes work correctly")
    
    print("\nAll tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(test_optional_attributes())