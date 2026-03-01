"""
Helper functions for import service in delta case.

No hass object needed.
"""

import datetime as dt

import pandas as pd
from homeassistant.components.recorder.models import StatisticMeanType

from custom_components.import_statistics import helpers
from custom_components.import_statistics.helpers import _LOGGER, DeltaReferenceType


def convert_deltas_with_older_reference(delta_rows: list[dict], sum_oldest: float | None, state_oldest: float | None) -> list[dict]:
    """
    Convert delta rows to absolute sum/state values.

    Uses older database record reference to accumulate deltas forward in time.

    Args:
    ----
        delta_rows: List of dicts with 'start' (datetime) and 'delta' (float) keys
        sum_oldest: Reference sum value from database (None treated as 0)
        state_oldest: Reference state value from database (None treated as 0)

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

    # Initialize accumulators (treat None as 0)
    current_sum = sum_oldest if sum_oldest is not None else 0
    current_state = state_oldest if state_oldest is not None else 0
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
            "Delta: %s, Accumulated: sum=%s, state=%s, start=%s",
            delta_row["delta"],
            current_sum,
            current_state,
            delta_row["start"],
        )

    _LOGGER.debug("Conversion complete: final sum=%s, state=%s", current_sum, current_state)
    return converted_rows


def convert_deltas_with_newer_reference(
    delta_rows: list[dict],
    sum_reference: float | None,
    state_reference: float | None,
    reference_time: dt.datetime,
) -> list[dict]:
    """
    Convert delta rows to absolute sum/state values using newer reference data.

    Works backward in time from newer reference record using subtraction.

    Args:
    ----
        delta_rows: List of dicts with 'start' (datetime) and 'delta' (float) keys
        sum_reference: Reference sum value from newer database record (None treated as 0)
        state_reference: Reference state value from newer database record (None treated as 0)
        reference_time: The timestamp of the reference record

    Returns:
    -------
        list[dict]: Converted rows with 'start', 'sum', and 'state' keys in ascending order

    Raises:
    ------
        HomeAssistantError: If rows are not sorted by timestamp

    """
    _LOGGER.debug("Converting %d delta rows to absolute values (newer reference)", len(delta_rows))
    _LOGGER.debug("Starting from sum=%s, state=%s (working backward) at %s", sum_reference, state_reference, reference_time)

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
    reversed_rows = list(reversed(delta_rows))

    # Treat None as 0 for reference values
    sum_reference = sum_reference if sum_reference is not None else 0
    state_reference = state_reference if state_reference is not None else 0

    # Save the original reference values for the connection record
    original_sum_reference = sum_reference
    original_state_reference = state_reference

    # Process rows in reverse order (newest to oldest)
    for i, delta_row in enumerate(reversed_rows):
        sum_reference -= delta_row["delta"]
        state_reference -= delta_row["delta"]

        # Write calculated values to the next older item (next in reversed iteration)
        start_time = reversed_rows[i + 1]["start"] if i + 1 < len(reversed_rows) else delta_row["start"] - dt.timedelta(hours=1)
        converted_rows.append(
            {
                "start": start_time,
                "sum": sum_reference,
                "state": state_reference,
            }
        )
        _LOGGER.debug(
            "Delta: %s, Calculated backward: sum=%s, state=%s, start=%s",
            delta_row["delta"],
            sum_reference,
            state_reference,
            start_time,
        )

    # Reverse result to ascending order (oldest to newest)
    converted_rows.reverse()

    # Add the connection record at the newest import time with the original reference values
    # This bridges the imported data to the existing database records
    # Must be added AFTER reversing so it's at the end (newest time)
    newest_import_time = delta_rows[-1]["start"]
    converted_rows.append(
        {
            "start": newest_import_time,
            "sum": original_sum_reference,
            "state": original_state_reference,
        }
    )
    _LOGGER.debug(
        "Added connection record: sum=%s, state=%s, start=%s",
        original_sum_reference,
        original_state_reference,
        newest_import_time,
    )

    _LOGGER.debug(
        "Newer reference conversion complete: final oldest sum=%s, state=%s",
        converted_rows[0]["sum"] if converted_rows else None,
        converted_rows[0]["state"] if converted_rows else None,
    )
    return converted_rows


def handle_dataframe_delta(df: pd.DataFrame, references: dict) -> dict:
    """
    Process delta statistics from DataFrame using pre-fetched references.

    Pure calculation function - no HA dependency (all references pre-fetched).
    Supports both OLDER_REFERENCE and NEWER_REFERENCE conversion.

    Args:
    ----
        df: DataFrame with delta column
        timezone_identifier: User's timezone
        datetime_format: Datetime format string
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

    # Vectorized validation: validate all delta values at once (if timestamps are already datetime objects)
    # Note: Timestamps are validated per-group below since they may not be parsed yet in unit tests
    if pd.api.types.is_datetime64_any_dtype(df["start"]):
        helpers.validate_timestamps_vectorized(df)

    helpers.validate_floats_vectorized(df, ["delta"])

    # Group rows by statistic_id
    stats = {}

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

        sum_ref = reference.get("sum") or 0
        state_ref = reference.get("state") or 0

        # Build delta_rows using itertuples (faster than iterrows)
        delta_rows = []
        for row in group.itertuples(index=False, name=None):
            row_dict = dict(zip(group.columns, row, strict=True))
            delta_rows.append(
                {
                    "start": row_dict["start"],
                    "delta": float(row_dict["delta"]),
                }
            )

        if not delta_rows:
            _LOGGER.warning("No valid delta rows found for statistic_id: %s", statistic_id)
            continue

        # Sort delta_rows by start timestamp to ensure chronological order
        # Try to fix#https://github.com/klausj1/homeassistant-statistics/issues/173
        delta_rows.sort(key=lambda r: r["start"])

        # Get source and unit
        source = helpers.get_source(statistic_id)
        unit = helpers.get_unit_from_row(group.iloc[0].get("unit", ""), statistic_id)

        # Route to appropriate conversion method based on reference type
        if ref_type == DeltaReferenceType.OLDER_REFERENCE:
            _LOGGER.debug("Using OLDER_REFERENCE conversion for %s", statistic_id)
            converted = convert_deltas_with_older_reference(delta_rows, sum_ref, state_ref)
        elif ref_type == DeltaReferenceType.NEWER_REFERENCE:
            _LOGGER.debug("Using NEWER_REFERENCE conversion for %s", statistic_id)
            reference_time = reference.get("start")
            converted = convert_deltas_with_newer_reference(delta_rows, sum_ref, state_ref, reference_time)
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
