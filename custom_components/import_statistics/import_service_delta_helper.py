"""Helper functions for import service in delta case. No hass object needed"""

import zoneinfo

import pandas as pd
from homeassistant.components.recorder.models import StatisticMeanType

from custom_components.import_statistics import helpers
from custom_components.import_statistics.helpers import _LOGGER, DeltaReferenceType, UnitFrom, format_decimal


def convert_deltas_with_older_reference(delta_rows: list[dict], sum_oldest: float, state_oldest: float) -> list[dict]:
    """
    Convert delta rows to absolute sum/state values.

    Uses older database record reference to accumulate deltas forward in time.

    Args:
    ----
        delta_rows: List of dicts with 'start' (datetime) and 'delta' (float) keys
        sum_oldest: Reference sum value from database
        state_oldest: Reference state value from database

    Returns:
    -------
        list[dict]: Converted rows with 'start', 'sum', and 'state' keys

    Raises:
    ------
        HomeAssistantError: If rows are not sorted by timestamp

    """
    _LOGGER.debug("Converting %d delta rows to absolute values", len(delta_rows))
    _LOGGER.debug("Starting from sum=%s, state=%s", sum_oldest, state_oldest)

    if not delta_rows:
        return []

    # Validate rows are sorted by start timestamp
    sorted_rows = sorted(delta_rows, key=lambda r: r["start"])
    if sorted_rows != delta_rows:
        helpers.handle_error("Delta rows must be sorted by start timestamp in ascending order")

    # Initialize accumulators
    current_sum = sum_oldest
    current_state = state_oldest
    converted_rows = []

    # Accumulate deltas
    for delta_row in delta_rows:
        current_sum += delta_row["delta"]
        current_state += delta_row["delta"]

        converted_rows.append(
            {
                "start": delta_row["start"],
                "sum": current_sum,
                "state": current_state,
            }
        )

        _LOGGER.debug(
            "Delta: %s, Accumulated: sum=%s, state=%s",
            delta_row["delta"],
            current_sum,
            current_state,
        )

    _LOGGER.debug("Conversion complete: final sum=%s, state=%s", current_sum, current_state)
    return converted_rows


def convert_deltas_with_newer_reference(
    delta_rows: list[dict],
    sum_reference: float,
    state_reference: float,
) -> list[dict]:
    """
    Convert delta rows to absolute sum/state values using newer reference data.

    Works backward in time from newer reference record using subtraction.

    Args:
    ----
        delta_rows: List of dicts with 'start' (datetime) and 'delta' (float) keys
        sum_reference: Reference sum value from newer database record
        state_reference: Reference state value from newer database record

    Returns:
    -------
        list[dict]: Converted rows with 'start', 'sum', and 'state' keys in ascending order

    Raises:
    ------
        HomeAssistantError: If rows are not sorted by timestamp

    """
    _LOGGER.debug("Converting %d delta rows to absolute values (newer reference)", len(delta_rows))
    _LOGGER.debug("Starting from sum=%s, state=%s (working backward)", sum_reference, state_reference)

    if not delta_rows:
        return []

    # Validate rows are sorted by start timestamp (ascending)
    sorted_rows = sorted(delta_rows, key=lambda r: r["start"])
    if sorted_rows != delta_rows:
        helpers.handle_error("Delta rows must be sorted by start timestamp in ascending order")

    # Work backward from newest to oldest: subtract deltas instead of adding
    # We process in reverse order, starting from the reference (newest)
    # and moving backward to the oldest
    converted_rows = []

    # Process rows in reverse order (newest to oldest)
    for delta_row in reversed(delta_rows):
        sum_reference -= delta_row["delta"]
        state_reference -= delta_row["delta"]

        converted_rows.append(
            {
                "start": delta_row["start"],
                "sum": sum_reference,
                "state": state_reference,
            }
        )

        _LOGGER.debug(
            "Delta: %s, Calculated backward: sum=%s, state=%s",
            delta_row["delta"],
            sum_reference,
            state_reference,
        )

    # Reverse result to ascending order (oldest to newest)
    converted_rows.reverse()

    _LOGGER.debug(
        "Younger reference conversion complete: final oldest sum=%s, state=%s",
        converted_rows[0]["sum"] if converted_rows else None,
        converted_rows[0]["state"] if converted_rows else None,
    )
    return converted_rows


def handle_dataframe_delta(
    df: pd.DataFrame,
    timezone_identifier: str,
    datetime_format: str,
    unit_from_where: UnitFrom,
    references: dict,
) -> dict:
    """
    Process delta statistics from DataFrame using pre-fetched references.

    Pure calculation function - no HA dependency (all references pre-fetched).
    Supports both OLDER_REFERENCE and NEWER_REFERENCE conversion.

    Args:
    ----
        df: DataFrame with delta column
        timezone_identifier: User's timezone
        datetime_format: Datetime format string
        unit_from_where: UnitFrom.ENTITY or UnitFrom.TABLE
        references: Dict mapping statistic_id to reference data:
                   {
                       statistic_id: {
                           "reference": {"start": datetime, "sum": float, "state": float},
                           "ref_type": DeltaReferenceType.OLDER_REFERENCE or DeltaReferenceType.NEWER_REFERENCE
                       } or None
                   }

    Returns:
    -------
        dict: {statistic_id: (metadata, statistics_list), ...}

    Raises:
    ------
        HomeAssistantError: On validation or missing reference

    """
    _LOGGER.info("Converting delta dataframe with references")

    # Group rows by statistic_id
    stats = {}
    timezone = zoneinfo.ZoneInfo(timezone_identifier)

    for statistic_id in df["statistic_id"].unique():
        group = df[df["statistic_id"] == statistic_id]

        # Validate reference exists
        if statistic_id not in references:
            helpers.handle_error(f"No reference found for statistic_id: {statistic_id}")

        ref_data = references[statistic_id]
        if ref_data is None:
            helpers.handle_error(f"Failed to find database reference for: {statistic_id} (no records at least 1 hour before/after import start)")

        reference = ref_data.get("reference")
        ref_type = ref_data.get("ref_type")

        if reference is None or ref_type is None:
            helpers.handle_error(f"Invalid reference data structure for {statistic_id}")

        sum_ref = reference.get("sum", 0)
        state_ref = reference.get("state", 0)

        # Extract delta rows using get_delta_stat
        delta_rows = []
        for _index, row in group.iterrows():
            delta_stat = helpers.get_delta_stat(row, timezone, datetime_format)
            if delta_stat:  # Silent failure - skip invalid rows
                delta_rows.append(delta_stat)

        if not delta_rows:
            _LOGGER.warning("No valid delta rows found for statistic_id: %s", statistic_id)
            continue

        # Get source and unit
        source = helpers.get_source(statistic_id)
        unit = helpers.add_unit_to_dataframe(source, unit_from_where, group.iloc[0].get("unit", ""), statistic_id)

        # Route to appropriate conversion method based on reference type
        if ref_type == DeltaReferenceType.OLDER_REFERENCE:
            _LOGGER.debug("Using OLDER_REFERENCE conversion for %s", statistic_id)
            converted = convert_deltas_with_older_reference(delta_rows, sum_ref, state_ref)
        elif ref_type == DeltaReferenceType.NEWER_REFERENCE:
            _LOGGER.debug("Using NEWER_REFERENCE conversion for %s", statistic_id)
            converted = convert_deltas_with_newer_reference(delta_rows, sum_ref, state_ref)
        else:
            helpers.handle_error(f"Internal error: Unknown reference type {ref_type} for {statistic_id}")

        # Build metadata
        metadata = {
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
            "source": source,
            "statistic_id": statistic_id,
            "name": None,
            "unit_class": None,
            "unit_of_measurement": unit,
        }

        stats[statistic_id] = (metadata, converted)

        _LOGGER.debug(
            "Converted %d delta rows for %s (unit: %s)",
            len(converted),
            statistic_id,
            unit,
        )

    _LOGGER.info("Delta dataframe conversion complete: %d statistics", len(stats))
    return stats


def get_delta_from_stats(rows: list[dict], *, decimal_comma: bool = False) -> list[dict]:
    """
    Calculate delta values from a list of records sorted by statistic_id and start.

    For each statistic_id, calculates delta as the difference between consecutive sum/state values.
    The first record of each statistic_id has an empty delta (no previous value).

    Args:
          rows: List of row dicts with statistic_id, start, sum, and/or state fields
          decimal_comma: Use comma (True) or dot (False) as decimal separator for output

    Returns:
          list[dict]: Rows with delta column added (formatted as string)

    """
    if not rows:
        return []

    # Sort rows by statistic_id first, then by start timestamp (sorted as string works if format is consistent)
    # Start is in datetime format like "26.01.2024 12:00" - sort as string works if format is consistent
    sorted_rows = sorted(rows, key=lambda r: (r["statistic_id"], r["start"]))

    result = []
    previous_sum_by_id = {}

    for row_dict in sorted_rows:
        statistic_id = row_dict["statistic_id"]
        new_row = dict(row_dict)

        # Get previous sum for this statistic_id
        prev_sum = previous_sum_by_id.get(statistic_id)

        # Calculate delta if we have sum/state values and a previous value
        if prev_sum is not None and "sum" in row_dict:
            # sum is already a string (formatted), need to extract numeric value
            sum_str = row_dict["sum"]
            if sum_str:  # Only if sum is not empty
                try:
                    # Convert back to float for calculation
                    decimal_sep = "," if decimal_comma else "."
                    sum_value = float(sum_str.replace(decimal_sep, "."))
                    delta_value = sum_value - prev_sum
                    new_row["delta"] = format_decimal(delta_value, use_comma=decimal_comma)
                except (ValueError, AttributeError):
                    new_row["delta"] = ""
            else:
                new_row["delta"] = ""
        else:
            # First record for this statistic_id has empty delta
            new_row["delta"] = ""

        # Update previous sum for next iteration
        if row_dict.get("sum"):
            try:
                decimal_sep = "," if decimal_comma else "."
                previous_sum_by_id[statistic_id] = float(row_dict["sum"].replace(decimal_sep, "."))
            except (ValueError, AttributeError):
                pass

        result.append(new_row)

    # Sort result by statistic_id and start to ensure consistent output order
    return sorted(result, key=lambda r: (r["statistic_id"], r["start"]))
