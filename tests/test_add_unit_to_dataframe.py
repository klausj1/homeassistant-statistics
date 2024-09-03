"""Unit tests for function add_unit_to_dataframe."""

import re

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import UnitFrom, add_unit_to_dataframe


def test_internal_from_entity_with_unit() -> None:
    """Internal statistics, unit_from_where = UnitFrom.ENTITY, unit is contained in row."""
    source = "recorder"
    unit_from_where = UnitFrom.ENTITY
    statistic_id = "stat1.mean"
    unit_from_row = "unit1"

    result = add_unit_to_dataframe(source, unit_from_where, unit_from_row, statistic_id)

    assert result == ""


def test_internal_from_entity_without_unit() -> None:
    """Internal statistics, unit_from_where = UnitFrom.ENTITY, unit is not contained in row."""
    source = "recorder"
    unit_from_where = UnitFrom.ENTITY
    statistic_id = "stat1.mean"
    unit_from_row = ""

    result = add_unit_to_dataframe(source, unit_from_where, unit_from_row, statistic_id)

    assert result == ""


def test_internal_from_row_with_unit() -> None:
    """Internal statistics, _where = UnitFrom.TABLE, unit is contained in row."""
    source = "recorder"
    unit_from_where = UnitFrom.TABLE
    statistic_id = "stat1.mean"
    unit_from_row = "unit1"

    result = add_unit_to_dataframe(source, unit_from_where, unit_from_row, statistic_id)

    assert result == "unit1"


def test_internal_from_row_without_unit() -> None:
    """Internal statistics, _where = UnitFrom.TABLE, unit is not contained in row."""
    source = "recorder"
    unit_from_where = UnitFrom.TABLE
    statistic_id = "stat1.mean"
    unit_from_row = ""

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Unit does not exist. Statistic ID: {statistic_id}."),
    ):
        # Call the function
        add_unit_to_dataframe(source, unit_from_where, unit_from_row, statistic_id)


def test_external_from_entity_with_unit() -> None:
    """External statistics, unit_from_where = UnitFrom.ENTITY, unit is contained in row."""
    source = "sensor"
    unit_from_where = UnitFrom.ENTITY
    statistic_id = "stat1:mean"
    unit_from_row = "unit1"

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Unit_from_entity set to TRUE is not allowed for external statistics (statistic_id with a ':'). Statistic ID: {statistic_id}."),
    ):
        add_unit_to_dataframe(source, unit_from_where, unit_from_row, statistic_id)


def test_external_from_entity_without_unit() -> None:
    """External statistics, unit_from_where = UnitFrom.ENTITY, unit is not contained in row."""
    source = "sensor"
    unit_from_where = UnitFrom.ENTITY
    statistic_id = "stat1:mean"
    unit_from_row = ""

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Unit_from_entity set to TRUE is not allowed for external statistics (statistic_id with a ':'). Statistic ID: {statistic_id}."),
    ):
        add_unit_to_dataframe(source, unit_from_where, unit_from_row, statistic_id)


def test_external_from_row_with_unit() -> None:
    """External statistics, _where = UnitFrom.TABLE, unit is contained in row."""
    source = "sensor"
    unit_from_where = UnitFrom.TABLE
    statistic_id = "stat1:mean"
    unit_from_row = "unit1"

    result = add_unit_to_dataframe(source, unit_from_where, unit_from_row, statistic_id)

    assert result == "unit1"


def test_external_from_row_without_unit() -> None:
    """External statistics, unit_from_where = UnitFrom.TABLE, unit is not contained in row."""
    source = "sensor"
    unit_from_where = UnitFrom.TABLE
    statistic_id = "stat1:mean"
    unit_from_row = ""

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Unit does not exist. Statistic ID: {statistic_id}."),
    ):
        add_unit_to_dataframe(source, unit_from_where, unit_from_row, statistic_id)
