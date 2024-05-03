"""Unit tests for function add_unit_to_dataframe."""

from homeassistant.exceptions import HomeAssistantError
from custom_components.import_statistics.helpers import add_unit_to_dataframe

def test_internal_from_entity_with_unit():
    """Internal statistics, unit_from_entity is true, unit is contained in row."""
    source = "recorder"
    unit_from_entity = True
    statistic_id = "stat1.mean"
    unit_from_row = "unit1"

    result = add_unit_to_dataframe(source, unit_from_entity, unit_from_row, statistic_id)

    assert result == ""

def test_internal_from_entity_without_unit():
    """Internal statistics, unit_from_entity is true, unit is not contained in row."""
    source = "recorder"
    unit_from_entity = True
    statistic_id = "stat1.mean"
    unit_from_row = ""

    result = add_unit_to_dataframe(source, unit_from_entity, unit_from_row, statistic_id)

    assert result == ""

def test_internal_from_row_with_unit():
    """Internal statistics, unit_from_entity is false, unit is contained in row."""
    source = "recorder"
    unit_from_entity = False
    statistic_id = "stat1.mean"
    unit_from_row = "unit1"

    result = add_unit_to_dataframe(source, unit_from_entity, unit_from_row, statistic_id)

    assert result == "unit1"

def test_internal_from_row_without_unit():
    """Internal statistics, unit_from_entity is false, unit is not contained in row."""
    source = "recorder"
    unit_from_entity = False
    statistic_id = "stat1.mean"
    unit_from_row = ""

    try:
        _result = add_unit_to_dataframe(source, unit_from_entity, unit_from_row, statistic_id)
        assert False, "Expected an exception to be raised for missing unit"
    except HomeAssistantError as e:
        assert str(e) == f"Unit does not exist. Statistic ID: {statistic_id}."

def test_external_from_entity_with_unit():
    """External statistics, unit_from_entity is true, unit is contained in row."""
    source = "sensor"
    unit_from_entity = True
    statistic_id = "stat1:mean"
    unit_from_row = "unit1"

    try:
        _result = add_unit_to_dataframe(source, unit_from_entity, unit_from_row, statistic_id)
        assert False, "Expected an exception to be raised for missing unit"
    except HomeAssistantError as e:
        assert str(e) == f"Unit_from_entity set to TRUE is not allowed for external statistics (statistic_id with a ':'). Statistic ID: {statistic_id}."

def test_external_from_entity_without_unit():
    """External statistics, unit_from_entity is true, unit is not contained in row."""
    source = "sensor"
    unit_from_entity = True
    statistic_id = "stat1:mean"
    unit_from_row = ""

    try:
        _result = add_unit_to_dataframe(source, unit_from_entity, unit_from_row, statistic_id)
        assert False, "Expected an exception to be raised for missing unit"
    except HomeAssistantError as e:
        assert str(e) == f"Unit_from_entity set to TRUE is not allowed for external statistics (statistic_id with a ':'). Statistic ID: {statistic_id}."

def test_external_from_row_with_unit():
    """External statistics, unit_from_entity is false, unit is contained in row."""
    source = "sensor"
    unit_from_entity = False
    statistic_id = "stat1:mean"
    unit_from_row = "unit1"

    result = add_unit_to_dataframe(source, unit_from_entity, unit_from_row, statistic_id)

    assert result == "unit1"

def test_external_from_row_without_unit():
    """External statistics, unit_from_entity is false, unit is not contained in row."""
    source = "sensor"
    unit_from_entity = False
    statistic_id = "stat1:mean"
    unit_from_row = ""

    try:
        _result = add_unit_to_dataframe(source, unit_from_entity, unit_from_row, statistic_id)
        assert False, "Expected an exception to be raised for missing unit"
    except HomeAssistantError as e:
        assert str(e) == f"Unit does not exist. Statistic ID: {statistic_id}."
