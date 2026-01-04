"""Import statistics functionality."""

from typing import Any

from homeassistant.components.recorder.statistics import async_add_external_statistics, async_import_statistics
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.import_statistics import prepare_data
from custom_components.import_statistics.const import ATTR_FILENAME, DATETIME_DEFAULT_FORMAT
from custom_components.import_statistics.delta_import import get_oldest_statistics_before
from custom_components.import_statistics.helpers import _LOGGER, UnitFrom


# Minimum tuple length for delta processing marker
_DELTA_MARKER_TUPLE_LENGTH = 6


async def handle_import_from_file_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle import_from_file service implementation."""
    _LOGGER.info("Service handle_import_from_file called")
    file_path = f"{hass.config.config_dir}/{call.data.get(ATTR_FILENAME)}"

    hass.states.async_set("import_statistics.import_from_file", file_path)

    _LOGGER.info("Peparing data for import")
    stats, unit_from_entity = await hass.async_add_executor_job(lambda: prepare_data.prepare_data_to_import(file_path, call, hass=hass))

    # Handle delta processing marker (async operation required)
    if isinstance(stats, tuple) and len(stats) >= _DELTA_MARKER_TUPLE_LENGTH and stats[0] == "_DELTA_PROCESSING_NEEDED":
        _LOGGER.info("Delta processing detected, fetching references from database")
        _marker, df, references_needed, timezone_identifier, datetime_format, unit_from_where = stats[:_DELTA_MARKER_TUPLE_LENGTH]

        # Fetch references from database asynchronously
        references = await get_oldest_statistics_before(hass, references_needed)
        _LOGGER.debug("References fetched: %s", references)

        # Convert delta dataframe with references (run in executor)
        stats = await hass.async_add_executor_job(
            lambda: prepare_data.convert_delta_dataframe_with_references(df, references, timezone_identifier, datetime_format, unit_from_where)
        )

    import_stats(hass, stats, unit_from_entity)


async def handle_import_from_json_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle import_from_json service implementation."""
    _LOGGER.info("Service handle_import_from_json called")
    stats, unit_from_entity = await hass.async_add_executor_job(lambda: prepare_data.prepare_json_data_to_import(call, hass=hass))

    # Handle delta processing marker (async operation required)
    if isinstance(stats, tuple) and len(stats) >= _DELTA_MARKER_TUPLE_LENGTH and stats[0] == "_DELTA_PROCESSING_NEEDED":
        _LOGGER.info("Delta processing detected, fetching references from database")
        _marker, df, references_needed, timezone_identifier, datetime_format, unit_from_where = stats[:_DELTA_MARKER_TUPLE_LENGTH]

        # Fetch references from database asynchronously
        references = await get_oldest_statistics_before(hass, references_needed)

        # Convert delta dataframe with references (run in executor)
        stats = await hass.async_add_executor_job(
            lambda: prepare_data.convert_delta_dataframe_with_references(df, references, timezone_identifier, datetime_format, unit_from_where)
        )

    import_stats(hass, stats, unit_from_entity)


def import_stats(hass: HomeAssistant, stats: dict, unit_from_entity: UnitFrom) -> None:
    """Import statistics into Home Assistant."""
    _LOGGER.info("Checking if all entities exist")
    check_all_entities_exists(hass, stats)

    if unit_from_entity:
        _LOGGER.info("Adding units from entities")
        add_unit_for_all_entities(hass, stats)

    _LOGGER.info("Calling hass import methods")
    for stat in stats.values():
        metadata = stat[0]
        statistics = stat[1]
        _LOGGER.debug("Calling async_import_statistics / async_add_external_statistics with:")
        _LOGGER.debug("Metadata:")
        _LOGGER.debug(metadata)
        _LOGGER.debug("Statistics:")
        _LOGGER.debug(statistics)

        if metadata["source"] == "recorder":
            if check_entity_exists(hass, metadata["statistic_id"]):
                async_import_statistics(hass, metadata, statistics)
        else:
            async_add_external_statistics(hass, metadata, statistics)

    _LOGGER.info("Finished importing data")


def check_all_entities_exists(hass: HomeAssistant, stats: dict) -> None:
    """
    Check all entities in stats if they exist.

    Args:
    ----
        hass: home assistant
        stats: dictionary with all statistic data

    Returns:
    -------
        n/a

    Raises:
    ------
        n/a

    """
    for stat in stats.values():
        metadata = stat[0]

        if metadata["source"] == "recorder":
            check_entity_exists(hass, metadata["statistic_id"])


def check_entity_exists(hass: HomeAssistant, entity_id: Any) -> bool:
    """
    Check if a specific entity exists.

    Args:
    ----
        hass: home assistant
        entity_id: id to check for existence

    Returns:
    -------
        bool: True if entity exists, otherwise exception is thrown

    Raises:
    ------
        HomeAssistantError: If entity does not exist

    """
    from custom_components.import_statistics import helpers

    entity_exists = hass.states.get(entity_id) is not None

    if not entity_exists:
        helpers.handle_error(f"Entity does not exist: '{entity_id}'")
        return False

    return True


def add_unit_for_all_entities(hass: HomeAssistant, stats: dict) -> None:
    """
    Add units for all rows to be imported.

    Args:
    ----
        hass: home assistant
        stats: dictionary with all statistic data

    Returns:
    -------
        n/a

    Raises:
    ------
        n/a

    """
    for stat in stats.values():
        metadata = stat[0]

        if metadata["source"] == "recorder":
            add_unit_for_entity(hass, metadata)


def add_unit_for_entity(hass: HomeAssistant, metadata: dict) -> None:
    """
    Add units for one rows to be imported.

    Args:
    ----
        hass: home assistant
        entity_id: id to check for existence
        metadata: metadata of row to be imported

    Returns:
    -------
        n/a

    Raises:
    ------
        HomeAssistantError: If entity does not exist

    """
    entity_id = metadata["statistic_id"]
    entity = hass.states.get(entity_id)

    if entity is None:
        from custom_components.import_statistics import helpers

        helpers.handle_error(f"Entity does not exist: '{entity_id}'")
    elif metadata.get("unit_of_measurement", "") == "":
        uom = None
        if hasattr(entity, "attributes") and isinstance(entity.attributes, dict):
            uom = entity.attributes.get("unit_of_measurement")
        if uom:
            metadata["unit_of_measurement"] = uom
            _LOGGER.debug(
                "Adding unit '%s' for entity_id: %s",
                metadata["unit_of_measurement"],
                entity_id,
            )
