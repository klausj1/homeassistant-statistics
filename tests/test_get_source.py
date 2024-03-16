"""Unit tests for _get_source function."""

from homeassistant.exceptions import HomeAssistantError
from custom_components.import_statistics import _get_source

def test_get_source_recorder():
    """
    Test the _get_source function with a statistic_id containing a dot.
    """
    statistic_id = "sensor.temperature"
    source = _get_source(statistic_id)
    assert source == "recorder"

def test_get_source_other_source():
    """
    Test the _get_source function with a statistic_id containing a colon.
    """
    statistic_id = "custom_component:temperature"
    source = _get_source(statistic_id)
    assert source == "custom_component"

def test_get_source_invalid_statistic_id():
    """
    Test the _get_source function with an invalid statistic_id.
    """
    statistic_id = ":temperature"
    try:
        _get_source(statistic_id)
        assert False, "Expected an exception to be raised for invalid statistic_id"
    except HomeAssistantError as e:
        assert str(e) == f"invalid statistic_id. (must not start with ':'): {statistic_id}"

def test_get_source_invalid_statistic_id_no_separator():
    """
    Test the _get_source function with an invalid statistic_id that does not contain a dot or colon.
    """
    statistic_id = "temperature"
    try:
        _get_source(statistic_id)
        assert False, "Expected an exception to be raised for invalid statistic_id"
    except HomeAssistantError as e:
        assert str(e) == f"invalid statistic_id (must contain either '.' or ':'): {statistic_id}"
