"""Unit tests for get_source function."""

from homeassistant.exceptions import HomeAssistantError
from custom_components.import_statistics.helpers import get_source

def test_get_source_recorder():
    """Test the get_source function with a statistic_id containing a dot."""
    statistic_id = "sensor.temperature"
    source = get_source(statistic_id)
    assert source == "recorder"

def test_get_source_other_source():
    """Test the get_source function with a statistic_id containing a colon."""
    statistic_id = "custom_component:temperature"
    source = get_source(statistic_id)
    assert source == "custom_component"

def test_get_source_invalid_statistic_id():
    """Test the get_source function with an invalid statistic_id."""
    statistic_id = ":temperature"
    try:
        get_source(statistic_id)
        assert False, "Expected an exception to be raised for invalid statistic_id"
    except HomeAssistantError as e:
        assert str(e) == f"Statistic_id {statistic_id} is invalid. Use either an existing entity ID (containing a '.'), or a statistic id (containing a ':')"

def test_get_source_invalid_statistic_id_no_separator():
    """Test the get_source function with an invalid statistic_id that does not contain a dot or colon."""
    statistic_id = "temperature"
    try:
        get_source(statistic_id)
        assert False, "Expected an exception to be raised for invalid statistic_id"
    except HomeAssistantError as e:
        assert str(e) == f"Statistic_id {statistic_id} is invalid. Use either an existing entity ID (containing a '.'), or a statistic id (containing a ':')"

def test_get_source_invalid_external_statistic_id_wrong_domain():
    """Test the get_source function with an invalid statistic_id that does not contain a dot or colon."""
    statistic_id = "recorder:temperature"
    try:
        get_source(statistic_id)
        assert False, "Expected an exception to be raised for invalid statistic_id"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid statistic_id {statistic_id}. DOMAIN 'recorder' is not allowed."

def test_get_source_invalid_statistic_id_wrong_domain():
    """Test the get_source function with an invalid statistic_id that does not contain a dot or colon."""
    statistic_id = "recorder.temperature"
    try:
        get_source(statistic_id)
        assert False, "Expected an exception to be raised for invalid statistic_id"
    except HomeAssistantError as e:
        assert str(e) == f"Invalid statistic_id {statistic_id}. DOMAIN 'recorder' is not allowed."
