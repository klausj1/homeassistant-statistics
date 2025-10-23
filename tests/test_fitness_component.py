"""Unit tests for fitness component functions."""

import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import fitness_component


def test_create_fitness_component_entities_success(hass) -> None:
    """Test successful creation of fitness component entities."""
    test_data = {
        "component_name": "my_fitness_tracker",
        "vendor": "Generic Fitness Tracker",
        "device_info": {
            "model": "FT-1000",
            "manufacturer": "Fitness Corp",
            "sw_version": "1.0.0",
            "hw_version": "2.0",
        },
        "entities": [
            {
                "name": "daily_steps",
                "friendly_name": "Daily Steps",
                "state_class": "total_increasing",
                "icon": "mdi:foot-print",
            },
            {
                "name": "heart_rate",
                "friendly_name": "Heart Rate",
                "state_class": "measurement",
                "icon": "mdi:heart-pulse",
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    # This should not raise an exception
    fitness_component.create_fitness_component_entities(hass, call)
    
    # Check that the component creation state is set
    state = hass.states.get("import_statistics.my_fitness_tracker_component_created")
    assert state is not None
    assert state.state == "True"
    assert state.attributes["component_name"] == "my_fitness_tracker"
    assert state.attributes["vendor"] == "Generic Fitness Tracker"
    assert len(state.attributes["entities_created"]) == 2
    assert state.attributes["entity_count"] == 2


def test_create_fitness_component_entities_missing_component_name(hass) -> None:
    """Test error when component_name is missing."""
    test_data = {
        "vendor": "Generic Fitness Tracker",
        "entities": [
            {
                "name": "daily_steps",
                "friendly_name": "Daily Steps",
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    with pytest.raises(HomeAssistantError, match="component_name is required"):
        fitness_component.create_fitness_component_entities(hass, call)


def test_create_fitness_component_entities_missing_vendor(hass) -> None:
    """Test error when vendor is missing."""
    test_data = {
        "component_name": "my_fitness_tracker",
        "entities": [
            {
                "name": "daily_steps",
                "friendly_name": "Daily Steps",
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    with pytest.raises(HomeAssistantError, match="vendor is required"):
        fitness_component.create_fitness_component_entities(hass, call)


def test_create_fitness_component_entities_missing_entities(hass) -> None:
    """Test error when entities list is empty."""
    test_data = {
        "component_name": "my_fitness_tracker",
        "vendor": "Generic Fitness Tracker",
        "entities": [],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    with pytest.raises(HomeAssistantError, match="at least one entity must be specified"):
        fitness_component.create_fitness_component_entities(hass, call)


def test_create_fitness_component_entities_invalid_component_name(hass) -> None:
    """Test error when component_name contains invalid characters."""
    test_data = {
        "component_name": "my-fitness-tracker",  # Contains hyphen which is invalid
        "vendor": "Generic Fitness Tracker",
        "entities": [
            {
                "name": "daily_steps",
                "friendly_name": "Daily Steps",
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    with pytest.raises(HomeAssistantError, match="Invalid component_name"):
        fitness_component.create_fitness_component_entities(hass, call)


def test_create_fitness_component_entities_missing_entity_name(hass) -> None:
    """Test error when entity name is missing."""
    test_data = {
        "component_name": "my_fitness_tracker",
        "vendor": "Generic Fitness Tracker",
        "entities": [
            {
                "friendly_name": "Daily Steps",
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    with pytest.raises(HomeAssistantError, match="entity name is required"):
        fitness_component.create_fitness_component_entities(hass, call)


def test_create_fitness_component_entities_missing_entity_friendly_name(hass) -> None:
    """Test error when entity friendly_name is missing."""
    test_data = {
        "component_name": "my_fitness_tracker",
        "vendor": "Generic Fitness Tracker",
        "entities": [
            {
                "name": "daily_steps",
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    with pytest.raises(HomeAssistantError, match="entity friendly_name is required"):
        fitness_component.create_fitness_component_entities(hass, call)


def test_create_fitness_component_entities_invalid_entity_name(hass) -> None:
    """Test error when entity name contains invalid characters."""
    test_data = {
        "component_name": "my_fitness_tracker",
        "vendor": "Generic Fitness Tracker",
        "entities": [
            {
                "name": "daily-steps",  # Contains hyphen which is invalid
                "friendly_name": "Daily Steps",
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    with pytest.raises(HomeAssistantError, match="Invalid entity name"):
        fitness_component.create_fitness_component_entities(hass, call)


def test_create_fitness_component_entities_minimal_config(hass) -> None:
    """Test creation with minimal configuration."""
    test_data = {
        "component_name": "minimal_tracker",
        "vendor": "Minimal Tracker",
        "entities": [
            {
                "name": "steps",
                "friendly_name": "Steps",
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    # This should not raise an exception
    fitness_component.create_fitness_component_entities(hass, call)
    
    # Check that the component creation state is set
    state = hass.states.get("import_statistics.minimal_tracker_component_created")
    assert state is not None
    assert state.state == "True"
    assert state.attributes["component_name"] == "minimal_tracker"
    assert state.attributes["vendor"] == "Minimal Tracker"
    assert len(state.attributes["entities_created"]) == 1
    assert state.attributes["entity_count"] == 1


def test_create_fitness_component_entities_with_device_info(hass) -> None:
    """Test creation with device info."""
    test_data = {
        "component_name": "device_tracker",
        "vendor": "Device Vendor",
        "device_info": {
            "model": "DT-2000",
            "manufacturer": "Device Corp",
            "sw_version": "2.1.0",
            "hw_version": "3.0",
        },
        "entities": [
            {
                "name": "battery",
                "friendly_name": "Battery Level",
                "unit_of_measurement": "%",
                "device_class": "battery",
                "state_class": "measurement",
                "icon": "mdi:battery",
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    # This should not raise an exception
    fitness_component.create_fitness_component_entities(hass, call)
    
    # Check that the component creation state is set
    state = hass.states.get("import_statistics.device_tracker_component_created")
    assert state is not None
    assert state.state == "True"
    assert state.attributes["component_name"] == "device_tracker"
    assert state.attributes["vendor"] == "Device Vendor"
    assert len(state.attributes["entities_created"]) == 1
    assert state.attributes["entity_count"] == 1


def test_fitness_sensor_entity_properties(hass) -> None:
    """Test FitnessSensorEntity properties."""
    component_name = "test_tracker"
    entity_config = {
        "name": "test_entity",
        "friendly_name": "Test Entity",
        "unit_of_measurement": "steps",
        "device_class": "step",
        "state_class": "total_increasing",
        "icon": "mdi:foot-print",
    }
    device_info = {
        "name": "Test Device",
        "identifiers": {("import_statistics", component_name)},
    }
    
    sensor = fitness_component.FitnessSensorEntity(hass, component_name, entity_config, device_info)
    
    assert sensor.name == "Test Entity"
    assert sensor.unique_id == "import_statistics_test_tracker_test_entity"
    assert sensor.entity_id == "sensor.test_tracker_test_entity"
    assert sensor.native_unit_of_measurement == "steps"
    assert sensor.device_class == "step"
    assert sensor.state_class == "total_increasing"
    assert sensor.icon == "mdi:foot-print"
    assert sensor.should_poll is False
    assert sensor.device_info == device_info


def test_fitness_sensor_entity_minimal_config(hass) -> None:
    """Test FitnessSensorEntity with minimal configuration."""
    component_name = "minimal_tracker"
    entity_config = {
        "name": "minimal_entity",
        "friendly_name": "Minimal Entity",
    }
    device_info = {
        "name": "Minimal Device",
        "identifiers": {("import_statistics", component_name)},
    }
    
    sensor = fitness_component.FitnessSensorEntity(hass, component_name, entity_config, device_info)
    
    assert sensor.name == "Minimal Entity"
    assert sensor.unique_id == "import_statistics_minimal_tracker_minimal_entity"
    assert sensor.entity_id == "sensor.minimal_tracker_minimal_entity"
    assert sensor.native_unit_of_measurement is None
    assert sensor.device_class is None
    assert sensor.state_class is None
    assert sensor.icon is None
    assert sensor.should_poll is False
    assert sensor.device_info == device_info