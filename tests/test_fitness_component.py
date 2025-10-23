"""Unit tests for fitness component functions."""

import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import fitness_component


@pytest.mark.asyncio
async def test_create_fitness_component_entities_success(hass) -> None:
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
    await fitness_component.create_fitness_component_entities(hass, call)
    
    # Check that the component creation state is set
    state = hass.states.get("import_statistics.my_fitness_tracker_component_created")
    assert state is not None
    assert state.state == "True"
    assert state.attributes["component_name"] == "my_fitness_tracker"
    assert state.attributes["vendor"] == "Generic Fitness Tracker"
    assert len(state.attributes["entities_created"]) == 2
    assert state.attributes["entity_count"] == 2


@pytest.mark.asyncio
async def test_create_fitness_component_entities_missing_component_name(hass) -> None:
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
        await fitness_component.create_fitness_component_entities(hass, call)


@pytest.mark.asyncio
async def test_create_fitness_component_entities_missing_vendor(hass) -> None:
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
        await fitness_component.create_fitness_component_entities(hass, call)


@pytest.mark.asyncio
async def test_create_fitness_component_entities_missing_entities(hass) -> None:
    """Test error when entities list is empty."""
    test_data = {
        "component_name": "my_fitness_tracker",
        "vendor": "Generic Fitness Tracker",
        "entities": [],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    with pytest.raises(HomeAssistantError, match="at least one entity must be specified"):
        await fitness_component.create_fitness_component_entities(hass, call)


@pytest.mark.asyncio
async def test_create_fitness_component_entities_invalid_component_name(hass) -> None:
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
        await fitness_component.create_fitness_component_entities(hass, call)


@pytest.mark.asyncio
async def test_create_fitness_component_entities_missing_entity_name(hass) -> None:
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
        await fitness_component.create_fitness_component_entities(hass, call)


@pytest.mark.asyncio
async def test_create_fitness_component_entities_missing_entity_friendly_name(hass) -> None:
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
        await fitness_component.create_fitness_component_entities(hass, call)


@pytest.mark.asyncio
async def test_create_fitness_component_entities_invalid_entity_name(hass) -> None:
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
        await fitness_component.create_fitness_component_entities(hass, call)


@pytest.mark.asyncio
async def test_create_fitness_component_entities_minimal_config(hass) -> None:
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
    await fitness_component.create_fitness_component_entities(hass, call)
    
    # Check that the component creation state is set
    state = hass.states.get("import_statistics.minimal_tracker_component_created")
    assert state is not None
    assert state.state == "True"
    assert state.attributes["component_name"] == "minimal_tracker"
    assert state.attributes["vendor"] == "Minimal Tracker"
    assert len(state.attributes["entities_created"]) == 1
    assert state.attributes["entity_count"] == 1


@pytest.mark.asyncio
async def test_create_fitness_component_entities_with_device_info(hass) -> None:
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
    await fitness_component.create_fitness_component_entities(hass, call)
    
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


@pytest.mark.asyncio
async def test_create_fitness_component_entities_optional_attributes_not_set(hass) -> None:
    """Test that optional attributes are not set when they are None."""
    test_data = {
        "component_name": "optional_tracker",
        "vendor": "Optional Tracker",
        "entities": [
            {
                "name": "steps",
                "friendly_name": "Steps",
                # Note: unit_of_measurement and device_class are intentionally omitted
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    # This should not raise an exception
    await fitness_component.create_fitness_component_entities(hass, call)
    
    # Check that the entity was created
    state = hass.states.get("sensor.optional_tracker_steps")
    assert state is not None
    
    # Verify that optional attributes are not present in the state attributes
    assert "unit_of_measurement" not in state.attributes
    assert "device_class" not in state.attributes
    assert "state_class" not in state.attributes
    assert "icon" not in state.attributes
    
    # Verify required attributes are still present
    assert "friendly_name" in state.attributes
    assert "unique_id" in state.attributes


@pytest.mark.asyncio
async def test_create_fitness_component_entities_mixed_attributes(hass) -> None:
    """Test entities with mixed optional attributes."""
    test_data = {
        "component_name": "mixed_tracker",
        "vendor": "Mixed Tracker",
        "entities": [
            {
                "name": "steps",
                "friendly_name": "Steps",
                "unit_of_measurement": "steps",
                # device_class omitted
                "state_class": "total_increasing",
                # icon omitted
            },
            {
                "name": "heart_rate",
                "friendly_name": "Heart Rate",
                # unit_of_measurement omitted
                "device_class": "heart_rate",
                # state_class omitted
                "icon": "mdi:heart-pulse",
            },
        ],
    }
    
    call = ServiceCall("import_statistics", "create_fitness_component", test_data, test_data)
    
    # This should not raise an exception
    await fitness_component.create_fitness_component_entities(hass, call)
    
    # Check first entity
    steps_state = hass.states.get("sensor.mixed_tracker_steps")
    assert steps_state is not None
    assert "unit_of_measurement" in steps_state.attributes
    assert steps_state.attributes["unit_of_measurement"] == "steps"
    assert "device_class" not in steps_state.attributes
    assert "state_class" in steps_state.attributes
    assert steps_state.attributes["state_class"] == "total_increasing"
    assert "icon" not in steps_state.attributes
    
    # Check second entity
    heart_state = hass.states.get("sensor.mixed_tracker_heart_rate")
    assert heart_state is not None
    assert "unit_of_measurement" not in heart_state.attributes
    assert "device_class" in heart_state.attributes
    assert heart_state.attributes["device_class"] == "heart_rate"
    assert "state_class" not in heart_state.attributes
    assert "icon" in heart_state.attributes
    assert heart_state.attributes["icon"] == "mdi:heart-pulse"


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