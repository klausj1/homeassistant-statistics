"""Helper functions for delta conversion in import service."""

import datetime
import zoneinfo

import pandas as pd
from homeassistant.components.recorder.models import StatisticMeanType

from custom_components.import_statistics import helpers
from custom_components.import_statistics.helpers import _LOGGER, UnitFrom, format_decimal


def convert_deltas_case_1(delta_rows: list[dict], sum_oldest: float, state_oldest: float) -> list[dict]:
    """
    Convert delta rows to absolute sum/state values.

    Uses Case 1 reference (older database record) to accumulate deltas.

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


def convert_deltas_case_2(
    delta_rows: list[dict],
    sum_reference: float,
    state_reference: float,
) -> list[dict]:
    """
    Convert delta rows to absolute sum/state values using younger reference data.

    Case 2: Works backward from younger data using subtraction.

    Args:
    ----
        delta_rows: List of dicts with 'start' (datetime) and 'delta' (float) keys
        sum_reference: Reference sum value from younger database record
        state_reference: Reference state value from younger database record

    Returns:
    -------
        list[dict]: Converted rows with 'start', 'sum', and 'state' keys in ascending order

    Raises:
    ------
        HomeAssistantError: If rows are not sorted by timestamp

    """
    _LOGGER.debug("Converting %d delta rows to absolute values (Case 2 - younger reference)", len(delta_rows))
    _LOGGER.debug("Starting from sum=%s, state=%s (working backward)", sum_reference, state_reference)

    if not delta_rows:
        return []

    # Validate rows are sorted by start timestamp (ascending)
    sorted_rows = sorted(delta_rows, key=lambda r: r["start"])
    if sorted_rows != delta_rows:
        helpers.handle_error("Delta rows must be sorted by start timestamp in ascending order")

    # Work backward from youngest to oldest: subtract deltas instead of adding
    # We process in reverse order, starting from the reference (youngest)
    # and moving backward to the oldest
    converted_rows = []

    # Process rows in reverse order (youngest to oldest)
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

    # Reverse result to ascending order (oldest to youngest)
    converted_rows.reverse()

    _LOGGER.debug(
        "Case 2 conversion complete: final oldest sum=%s, state=%s",
        converted_rows[0]["sum"] if converted_rows else None,
        converted_rows[0]["state"] if converted_rows else None,
    )
    return converted_rows


def convert_delta_dataframe_with_references(  # noqa: PLR0913
    df: pd.DataFrame,
    references: dict,
    timezone_identifier: str,
    datetime_format: str,
    unit_from_where: UnitFrom,
    case_2_conversion_enabled: bool = True,  # noqa: FBT001, FBT002
) -> dict:
    """
    Convert DataFrame with delta column using pre-fetched reference data.

    Pure calculation function - no HA dependency (all references pre-fetched).
    Supports both Case 1 (older reference) and Case 2 (younger reference) conversion.

    Args:
    ----
        df: DataFrame with delta column
        references: {statistic_id: {start, sum, state} or None}
        timezone_identifier: User's timezone
        datetime_format: Datetime format string
        unit_from_where: UnitFrom.ENTITY or UnitFrom.TABLE
        case_2_conversion_enabled: Enable Case 2 (younger reference) conversion (default True)

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

        reference = references[statistic_id]
        if reference is None:
            helpers.handle_error(f"Failed to find database reference for: {statistic_id} (no records at least 1 hour before/after import start)")

        sum_ref = reference.get("sum", 0)
        state_ref = reference.get("state", 0)
        ref_start = reference.get("start")

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

        # Detect which case to use based on reference timestamp
        # Case 1: reference is at least 1 hour before first delta (oldest statistic)
        # Case 2: reference is at least 1 hour after last delta (youngest statistic)
        first_delta_time = delta_rows[0]["start"]
        last_delta_time = delta_rows[-1]["start"]
        min_ref_distance = datetime.timedelta(hours=1)

        # If reference timestamp is available, validate 1-hour distance and detect case
        if ref_start is not None:
            time_before_first = first_delta_time - ref_start
            time_after_last = ref_start - last_delta_time

            if ref_start < first_delta_time and time_before_first >= min_ref_distance:
                # Case 1: Older reference (at least 1 hour before) - accumulate deltas forward
                _LOGGER.debug("Using Case 1 conversion (older reference) for %s", statistic_id)
                converted = convert_deltas_case_1(delta_rows, sum_ref, state_ref)
            elif case_2_conversion_enabled and ref_start > last_delta_time and time_after_last >= min_ref_distance:
                # Case 2: Younger reference (at least 1 hour after) - subtract deltas backward
                _LOGGER.debug("Using Case 2 conversion (younger reference) for %s", statistic_id)
                converted = convert_deltas_case_2(delta_rows, sum_ref, state_ref)
            else:
                # Reference is not 1 hour away (between first and last deltas or within 1 hour)
                error_msg = (
                    f"Invalid reference for {statistic_id}: reference timestamp {ref_start} must be "
                    f"at least 1 hour before (Case 1) or after (Case 2) the import data range "
                    f"({first_delta_time} to {last_delta_time})"
                )
                helpers.handle_error(error_msg)
        else:
            # Reference timestamp is unavailable (None) - skip distance validation
            # Default to Case 1 when timestamp is unavailable
            _LOGGER.debug("Using Case 1 conversion (older reference, timestamp unavailable) for %s", statistic_id)
            converted = convert_deltas_case_1(delta_rows, sum_ref, state_ref)

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
