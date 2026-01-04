"""Unit tests for get_source function."""

import re

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import get_source


def test_get_source_recorder() -> None:
    """Test the get_source function with a statistic_id containing a dot."""
    statistic_id = "sensor.temperature"
    source = get_source(statistic_id)
    assert source == "recorder"


def test_get_source_other_source() -> None:
    """Test the get_source function with a statistic_id containing a colon."""
    statistic_id = "custom_component:temperature"
    source = get_source(statistic_id)
    assert source == "custom_component"


def test_get_source_invalid_statistic_id() -> None:
    """Test the get_source function with an invalid statistic_id."""
    statistic_id = ":temperature"

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Statistic_id {statistic_id} is invalid. Use either an existing entity ID (containing a '.'), or a statistic id (containing a ':')"),
    ):
        get_source(statistic_id)


def test_get_source_invalid_statistic_id_no_separator() -> None:
    """Test the get_source function with an invalid statistic_id that does not contain a dot or colon."""
    statistic_id = "temperature"
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Statistic_id {statistic_id} is invalid. Use either an existing entity ID (containing a '.'), or a statistic id (containing a ':')"),
    ):
        get_source(statistic_id)


def test_get_source_invalid_external_statistic_id_wrong_domain() -> None:
    """Test the get_source function with an invalid statistic_id that does not contain a dot or colon."""
    statistic_id = "recorder:temperature"
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Invalid statistic_id {statistic_id}. DOMAIN 'recorder' is not allowed."),
    ):
        get_source(statistic_id)


def test_get_source_invalid_statistic_id_wrong_domain() -> None:
    """Test the get_source function with an invalid statistic_id that does not contain a dot or colon."""
    statistic_id = "recorder.temperature"
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Invalid statistic_id {statistic_id}. DOMAIN 'recorder' is not allowed."),
    ):
        get_source(statistic_id)
