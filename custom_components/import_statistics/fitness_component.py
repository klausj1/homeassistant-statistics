"""Fitness component creation for the import_statistics integration."""

import logging
from typing import Any, Dict, List

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from custom_components.import_statistics.const import DOMAIN
from custom_components.import_statistics.helpers import _LOGGER, handle_error

_LOGGER = logging.getLogger(__name__)


class FitnessSensorEntity(SensorEntity):
    """Representation of a Fitness Sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        component_name: str,
        entity_config: Dict[str, Any],
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the fitness sensor."""
        self._hass = hass
        self._component_name = component_name
        self._entity_name = entity_config["name"]
        self._friendly_name = entity_config["friendly_name"]
        self._unit_of_measurement = entity_config.get("unit_of_measurement")
        self._device_class = entity_config.get("device_class")
        self._state_class = entity_config.get("state_class")
        self._icon = entity_config.get("icon")
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{component_name}_{self._entity_name}"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._friendly_name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._attr_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self._device_info

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self) -> str | None:
        """Return the device class."""
        return self._device_class

    @property
    def state_class(self) -> str | None:
        """Return the state class."""
        return self._state_class

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return self._icon

    @property
    def should_poll(self) -> bool:
        """Return False as we don't need polling."""
        return False

    @property
    def entity_id(self) -> str:
        """Return the entity ID."""
        return f"sensor.{self._component_name}_{self._entity_name}"


def create_fitness_component_entities(hass: HomeAssistant, call: ServiceCall) -> None:
    """
    Create a fitness component with its entities.

    Args:
    ----
        hass: Home Assistant instance
        call: Service call containing the component configuration

    Raises:
    ------
        HomeAssistantError: If component creation fails

    """
    _LOGGER.info("Creating fitness component entities")
    
    component_name = call.data.get("component_name")
    vendor = call.data.get("vendor")
    device_info = call.data.get("device_info", {})
    entities = call.data.get("entities", [])

    # Validate required parameters
    if not component_name:
        handle_error("component_name is required")
    if not vendor:
        handle_error("vendor is required")
    if not entities:
        handle_error("at least one entity must be specified")

    # Validate component name
    if not component_name.replace("_", "").isalnum():
        handle_error(f"Invalid component_name: {component_name}. Only alphanumeric characters and underscores are allowed")

    # Validate entities
    for entity in entities:
        if "name" not in entity:
            handle_error("entity name is required")
        if "friendly_name" not in entity:
            handle_error("entity friendly_name is required")
        if not entity["name"].replace("_", "").isalnum():
            handle_error(f"Invalid entity name: {entity['name']}. Only alphanumeric characters and underscores are allowed")

    # Create device info
    device_config = DeviceInfo(
        name=vendor,
        identifiers={(DOMAIN, component_name)},
        manufacturer=device_info.get("manufacturer", vendor),
        model=device_info.get("model"),
        sw_version=device_info.get("sw_version"),
        hw_version=device_info.get("hw_version"),
        entry_type=DeviceEntryType.SERVICE,
    )

    # Create sensor entities
    created_entities = []
    for entity_config in entities:
        try:
            sensor = FitnessSensorEntity(hass, component_name, entity_config, device_config)
            
            # Register the entity with Home Assistant
            entity_id = sensor.entity_id
            _LOGGER.info(f"Creating entity: {entity_id}")
            
            # Set the initial state
            attributes = {
                "friendly_name": sensor.name,
                "unique_id": sensor.unique_id,
                "device_class": sensor.device_class,
                "state_class": sensor.state_class,
                "unit_of_measurement": sensor.native_unit_of_measurement,
                "icon": sensor.icon,
            }
            
            # Add device info to attributes for reference
            if sensor.device_info:
                attributes["device_info"] = {
                    "name": sensor.device_info.get("name"),
                    "identifiers": list(sensor.device_info.get("identifiers", [])),
                    "manufacturer": sensor.device_info.get("manufacturer"),
                    "model": sensor.device_info.get("model"),
                    "sw_version": sensor.device_info.get("sw_version"),
                    "hw_version": sensor.device_info.get("hw_version"),
                }
            
            hass.states.async_set(
                entity_id=entity_id,
                new_state=None,
                attributes=attributes,
            )
            
            created_entities.append(entity_id)
            _LOGGER.info(f"Successfully created entity: {entity_id}")
            
        except Exception as exc:
            _LOGGER.error(f"Failed to create entity {entity_config.get('name', 'unknown')}: {exc}")
            handle_error(f"Failed to create entity {entity_config.get('name', 'unknown')}: {exc}")

    _LOGGER.info(f"Successfully created {len(created_entities)} entities for fitness component: {component_name}")
    
    # Set a state to indicate successful component creation
    hass.states.async_set(
        f"import_statistics.{component_name}_component_created",
        True,
        attributes={
            "component_name": component_name,
            "vendor": vendor,
            "entities_created": created_entities,
            "entity_count": len(created_entities),
        },
    )