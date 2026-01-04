"""Unit tests for add_unit_for_entity function."""

from unittest.mock import MagicMock, patch

from homeassistant.core import State

from custom_components.import_statistics import add_unit_for_entity


def test_add_unit_for_entity_no_unit_of_measurement() -> None:
    """
    Test add_unit_for_entity when entity_id does not have a unit_of_measurement.

    This test verifies that when the entity doesn't have a unit_of_measurement
    attribute, no unit is added to the metadata.
    """
    # Create mock hass object without spec to allow arbitrary attributes
    hass = MagicMock()

    # Create a mock entity state without unit_of_measurement
    entity_state = State(
        entity_id="sensor.test_entity",
        state="100",
        attributes={},  # No unit_of_measurement attribute
    )

    # Setup hass.states.get to return the entity state
    hass.states.get.return_value = entity_state

    # Create metadata with empty unit_of_measurement
    metadata = {
        "statistic_id": "sensor.test_entity",
        "unit_of_measurement": "",
        "source": "recorder",
    }

    # Call the function - suppress KeyError as the entity lacks the attribute
    # with contextlib.suppress(KeyError):
    add_unit_for_entity(hass, metadata)

    # Verify hass.states.get was called with the correct entity_id
    hass.states.get.assert_called_once_with("sensor.test_entity")

def test_add_unit_for_entity_with_unit_of_measurement() -> None:
    """
    Test add_unit_for_entity when entity_id has a unit_of_measurement.

    This test verifies that when the entity has a unit_of_measurement attribute,
    it is correctly added to the metadata.
    """
    # Create mock hass object without spec to allow arbitrary attributes
    hass = MagicMock()

    # Create a mock entity state with unit_of_measurement
    entity_state = State(
        entity_id="sensor.test_entity",
        state="100",
        attributes={"unit_of_measurement": "kWh"},
    )

    # Setup hass.states.get to return the entity state
    hass.states.get.return_value = entity_state

    # Create metadata with empty unit_of_measurement
    metadata = {
        "statistic_id": "sensor.test_entity",
        "unit_of_measurement": "",
        "source": "recorder",
    }

    # Call the function
    with patch("custom_components.import_statistics._LOGGER"):
        add_unit_for_entity(hass, metadata)

    # Verify the unit was added to metadata
    assert metadata["unit_of_measurement"] == "kWh"

    # Verify hass.states.get was called with the correct entity_id
    hass.states.get.assert_called_once_with("sensor.test_entity")


def test_add_unit_for_entity_entity_does_not_exist() -> None:
    """
    Test add_unit_for_entity when entity_id does not exist.

    This test verifies that when the entity doesn't exist, an error is handled.
    """
    # Create mock hass object without spec to allow arbitrary attributes
    hass = MagicMock()

    # Setup hass.states.get to return None (entity doesn't exist)
    hass.states.get.return_value = None

    # Create metadata with empty unit_of_measurement
    metadata = {
        "statistic_id": "sensor.non_existent",
        "unit_of_measurement": "",
        "source": "recorder",
    }

    # Call the function and expect handle_error to be called
    with patch("custom_components.import_statistics.helpers.handle_error") as mock_error:
        add_unit_for_entity(hass, metadata)
        mock_error.assert_called_once_with("Entity does not exist: 'sensor.non_existent'")

    # Verify hass.states.get was called with the correct entity_id
    hass.states.get.assert_called_once_with("sensor.non_existent")
