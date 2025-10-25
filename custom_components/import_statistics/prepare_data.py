"""Main methods for the import_statistics integration."""

import zoneinfo
from pathlib import Path

import pandas as pd
import pytz
from homeassistant.core import ServiceCall

from custom_components.import_statistics import helpers
from custom_components.import_statistics.const import (
    ATTR_DATETIME_FORMAT,
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_TIMEZONE_IDENTIFIER,
    ATTR_UNIT_FROM_ENTITY,
    DATETIME_DEFAULT_FORMAT,
)
from custom_components.import_statistics.helpers import _LOGGER, UnitFrom


def prepare_data_to_import(file_path: str, call: ServiceCall) -> tuple:
    """
    Prepare data to import statistics from a file.

    Args:
    ----
        file_path: Path to the file with the data to be imported.
        call: The call data containing the necessary information.

    Returns:
    -------
        A dictionary containing the imported statistics.

    Raises:
    ------
        FileNotFoundError: If the specified file does not exist.
        ValueError: If there is an implementation error.

    """
    decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity = handle_arguments(call)

    _LOGGER.info("Importing statistics from file: %s", file_path)
    if not Path(file_path).exists():
        helpers.handle_error(f"path {file_path} does not exist.")

    my_df = pd.read_csv(file_path, sep=delimiter, decimal=decimal, engine="python")

    stats = handle_dataframe(my_df, timezone_identifier, datetime_format, unit_from_entity)
    return stats, unit_from_entity


def prepare_json_entities(call: ServiceCall) -> tuple:
    """Prepare json entities for import."""
    timezone_identifier = call.data.get("timezone_identifier")

    if timezone_identifier not in pytz.all_timezones:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    timezone = zoneinfo.ZoneInfo(timezone_identifier)
    entities = call.data.get("entities", [])

    return timezone, entities


def prepare_json_data_to_import(call: ServiceCall) -> tuple:
    """Parse json data to import statistics from."""
    _, timezone_identifier, _, datetime_format, unit_from_entity = handle_arguments(call)

    valid_columns = ["state", "sum", "min", "max", "mean"]
    columns = ["statistic_id", "unit", "start"]
    data = []

    input_entities = call.data.get("entities", [])

    for entity in input_entities:
        statistic_id, values, unit = (entity["id"], entity["values"], entity["unit"])
        _LOGGER.info(f"Parsing entity with id: {statistic_id} with {len(values)} values")
        for value in values:
            value_dict = {
                "statistic_id": statistic_id,
                "unit": unit,
                "start": value["datetime"],
            }
            for valid_column in valid_columns:
                if valid_column in value:
                    if valid_column not in columns:
                        columns.append(valid_column)
                    value_dict[valid_column] = value[valid_column]

            data.append(tuple([value_dict[column] for column in columns]))

    my_df = pd.DataFrame(data, columns=columns)
    stats = handle_dataframe(my_df, timezone_identifier, datetime_format, unit_from_entity)
    return stats, unit_from_entity


def handle_arguments(call: ServiceCall) -> tuple:
    """
    Handle the arguments for importing statistics from a file.

    Args:
    ----
        call (ServiceCall): The service call object containing additional data.

    Returns:
    -------
        tuple: A tuple containing the decimal separator, timezone identifier, and delimiter.

    Raises:
    ------
        ValueError: If the timezone identifier is invalid.

    """
    decimal = "," if call.data.get(ATTR_DECIMAL, True) else "."

    datetime_format = call.data.get(ATTR_DATETIME_FORMAT) if ATTR_DATETIME_FORMAT in call.data else DATETIME_DEFAULT_FORMAT

    unit_from_entity = UnitFrom.ENTITY if call.data.get(ATTR_UNIT_FROM_ENTITY) is True else UnitFrom.TABLE

    timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER)

    if timezone_identifier not in pytz.all_timezones:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    delimiter = call.data.get(ATTR_DELIMITER)
    _LOGGER.debug("Timezone_identifier: %s", timezone_identifier)
    _LOGGER.debug("Delimiter: %s", delimiter)
    _LOGGER.debug("Decimal separator: %s", decimal)
    _LOGGER.debug("Datetime format: %s", datetime_format)
    _LOGGER.debug("Unit from entity: %s", unit_from_entity)

    return decimal, timezone_identifier, delimiter, datetime_format, unit_from_entity


def handle_dataframe(
    df: pd.DataFrame,
    timezone_identifier: str,
    datetime_format: str,
    unit_from_where: UnitFrom,
) -> dict:
    """
    Process a dataframe and extract statistics based on the specified columns and timezone.

    Args:
    ----
        df (pandas.DataFrame): The input dataframe containing the statistics data.
        columns (list): The list of columns to extract from the dataframe.
        timezone_identifier (str): The timezone identifier to convert the timestamps.
        datetime_format (str): The format of the provided datetimes, e.g. "%d.%m.%Y %H:%M"
        unit_from_where: ENTITY if the unit is taken from the entity, TABLE if taken from input file.

    Returns:
    -------
        dict: A dictionary containing the extracted statistics, organized by statistic_id.

    Raises:
    ------
        ImplementationError: If both 'mean' and 'sum' columns are present in the columns list.

    """
    columns = df.columns
    _LOGGER.debug("Columns:")
    _LOGGER.debug(columns)
    if not helpers.are_columns_valid(df, unit_from_where):
        helpers.handle_error(
            "Implementation error. helpers.are_columns_valid returned false, this should never happen, because helpers.are_columns_valid throws an exception!"
        )
    stats = {}
    timezone = zoneinfo.ZoneInfo(timezone_identifier)
    has_mean = "mean" in columns
    has_sum = "sum" in columns
    for _index, row in df.iterrows():
        statistic_id = row["statistic_id"]
        if statistic_id not in stats:  # New statistic id found
            source = helpers.get_source(statistic_id)
            metadata = {
                "has_mean": has_mean,
                "has_sum": has_sum,
                "source": source,
                "statistic_id": statistic_id,
                "name": None,
                "unit_of_measurement": helpers.add_unit_to_dataframe(source, unit_from_where, row.get("unit", ""), statistic_id),
            }
            stats[statistic_id] = (metadata, [])

        if has_mean:
            new_stat = helpers.get_mean_stat(row, timezone, datetime_format)
        if has_sum:
            new_stat = helpers.get_sum_stat(row, timezone, datetime_format)
        stats[statistic_id][1].append(new_stat)
    return stats
