"""Helpers for the import_statistics integration."""

import datetime as dt
import datetime as dt_module
import logging
import zoneinfo
from enum import Enum
from pathlib import Path

import pandas as pd
from homeassistant.components.recorder.statistics import valid_statistic_id
from homeassistant.core import valid_entity_id
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.const import DATETIME_DEFAULT_FORMAT, UPLOAD_ALLOWED_EXTENSIONS, UPLOAD_MAX_SIZE

_LOGGER = logging.getLogger(__name__)


class DeltaReferenceType(Enum):
    """Type of reference used for delta conversion."""

    OLDER_REFERENCE = "older"  # Reference is 1+ hour before oldest import
    NEWER_REFERENCE = "newer"  # Reference is at or after newest import


def get_source(statistic_id: str) -> str:
    """
    Get the source of a statistic based on the given statistic_id.

    Args:
    ----
        statistic_id (str): The ID of the statistic.

    Returns:
    -------
        str: The source of the statistic.

    Raises:
    ------
        ValueError: If the statistic_id is invalid.

    """
    if valid_entity_id(statistic_id):
        source = statistic_id.split(".", maxsplit=1)[0]
        if source == "recorder":
            handle_error(f"Invalid statistic_id {statistic_id}. DOMAIN 'recorder' is not allowed.")
        source = "recorder"
    elif valid_statistic_id(statistic_id):
        source = statistic_id.split(":", maxsplit=1)[0]
        if len(source) == 0:
            handle_error(f"Implementation error, this must not happen. Invalid statistic_id. (must not start with ':'): {statistic_id}")
        if source == "recorder":
            handle_error(f"Invalid statistic_id {statistic_id}. DOMAIN 'recorder' is not allowed.")
    else:
        handle_error(f"Statistic_id {statistic_id} is invalid. Use either an existing entity ID (containing a '.'), or a statistic id (containing a ':')")

    return source


def is_not_in_future(newest_timestamp: dt.datetime) -> bool:
    """
    Check if the newest timestamp is not too recent (in the future from HA perspective).

    Home Assistant requires statistics to be at least 1 hour old.
    The newest allowed time is: current time - 65 minutes, truncated to the full hour.

    Args:
    ----
        newest_timestamp (dt.datetime): The newest timestamp in the import data (with timezone).

    Returns:
    -------
        bool: True if the timestamp is valid (not too recent).

    Raises:
    ------
        HomeAssistantError: If the timestamp is too recent (in the future).

    """
    now = dt.datetime.now(dt.UTC)
    # Subtract 65 minutes and truncate to full hour
    max_allowed = (now - dt.timedelta(minutes=65)).replace(minute=0, second=0, microsecond=0)

    # Convert newest_timestamp to UTC for comparison
    newest_utc = newest_timestamp.astimezone(dt.UTC)

    if newest_utc > max_allowed:
        # Display max_allowed in the same timezone as the input timestamp
        max_allowed_local = max_allowed.astimezone(newest_timestamp.tzinfo)
        msg = (
            f"Timestamp {newest_timestamp} is too recent. "
            f"The newest allowed timestamp is {max_allowed_local} (current time minus 65 minutes, truncated to full hour)."
        )
        handle_error(msg)

    return True


def are_columns_valid(df: pd.DataFrame) -> bool:
    """
    Check if the given DataFrame columns meet the required criteria.

    Args:
    ----
        df: dataFrame.

    Returns:
    -------
        bool: True if the columns meet the required criteria, False otherwise.

    """
    columns = df.columns

    # Check required columns: statistic_id, start, and unit (always required)
    # Determine if this is delta or non-delta data first
    has_delta = "delta" in columns

    if not ("statistic_id" in columns and "start" in columns and "unit" in columns):
        found_columns_num = len(columns)
        # embrace each column name with quotes for clarity
        found_columns_quoted = [f"'{col}'" for col in columns]
        found_columns_str = ", ".join(sorted(found_columns_quoted))
        error_str = "The file must contain the columns 'statistic_id', 'start' and 'unit'"
        error_str += f" (check delimiter). Number of found columns: {found_columns_num}. Found columns: {found_columns_str}"
        handle_error(error_str)

    # Check for value column requirements and incompatible combinations
    has_mean_min_max = "mean" in columns or "min" in columns or "max" in columns
    has_sum_state = "sum" in columns or "state" in columns

    if has_delta:
        # Delta cannot coexist with sum, state, mean, min, or max - check each individually to match test expectations
        if "sum" in columns or "state" in columns or has_mean_min_max:
            handle_error("Delta column cannot be used with 'sum', 'state', 'mean', 'min', or 'max' columns")
    # Non-delta: cannot mix mean/min/max with sum/state
    elif has_mean_min_max and has_sum_state:
        handle_error("The file must not contain the columns 'sum/state' together with 'mean'/'min'/'max'")

    # Define allowed columns based on data type - unit is always allowed
    allowed_columns = {"statistic_id", "start", "unit", "delta"} if has_delta else {"statistic_id", "start", "unit", "mean", "min", "max", "sum", "state"}

    # Check for unknown columns
    unknown_columns = set(columns) - allowed_columns
    if unknown_columns:
        unknown_cols_str = ", ".join(sorted(unknown_columns))
        allowed_cols_str = ", ".join(sorted(allowed_columns))
        handle_error(f"Unknown columns in file: {unknown_cols_str}. Only these columns are allowed: {allowed_cols_str}")

    return True


def handle_error(error_string: str) -> None:
    """
    Handle an error by logging a warning and raising a HomeAssistantError.

    Args:
    ----
        error_string (str): The error message.

    Raises:
    ------
        HomeAssistantError: The raised exception containing the error message.

    """
    _LOGGER.warning(error_string)
    raise HomeAssistantError(error_string)


def get_unit_from_row(unit_from_row: str, statistic_id: str) -> str:
    """
    Get unit from the input row and validate it exists.

    Args:
    ----
        unit_from_row: The unit from the imported file
        statistic_id: The statistic id from the imported file

    Returns:
    -------
        str: unit from the row

    Raises:
    ------
        HomeAssistantError: If unit is missing or empty

    """
    if unit_from_row == "":
        handle_error(f"Unit does not exist in input file. Statistic ID: {statistic_id}.")
    return unit_from_row


def validate_delimiter(delimiter: str | None) -> str:
    r"""
    Validate and normalize a delimiter string.

    Converts None to tab character, converts literal \t to actual tab,
    and validates that the delimiter is exactly 1 character.

    Args:
    ----
        delimiter: The delimiter to validate (can be None, "\t", or a single character)

    Returns:
    -------
        str: The validated and normalized delimiter character

    Raises:
    ------
        HomeAssistantError: If the delimiter is invalid

    """
    if delimiter is None:
        # Default to tab character
        return "\t"
    if delimiter == "\\t":
        # Convert literal \t string to actual tab character
        return "\t"
    if not isinstance(delimiter, str) or len(delimiter) != 1:
        handle_error(f"Delimiter must be exactly 1 character or \\t, got: {delimiter!r}")
    return delimiter


def validate_file_encoding(file_path: str, expected_encoding: str = "utf-8") -> bool:
    """
    Validate that a file can be read with the expected encoding.

    Checks if the file contains valid UTF-8 (or other specified encoding) and
    detects common encoding issues that could cause problems with special characters
    like ° (degree) or ³ (superscript).

    Args:
    ----
        file_path: Path to the file to validate
        expected_encoding: Expected encoding (default: "utf-8")

    Returns:
    -------
        bool: True if the file is valid

    Raises:
    ------
        HomeAssistantError: If the file has encoding issues

    """
    try:
        with Path(file_path).open(encoding=expected_encoding, errors="strict") as f:
            # Read the entire file to detect any encoding errors
            content = f.read()

            # Check for common problematic characters that might indicate wrong encoding
            # These are replacement characters or mojibake patterns
            problematic_patterns = [
                "\ufffd",  # Unicode replacement character (�)
                "Â°",  # Common mojibake for ° when UTF-8 read as Latin-1
                "Â³",  # Common mojibake for ³ when UTF-8 read as Latin-1
            ]

            for pattern in problematic_patterns:
                if pattern in content:
                    handle_error(
                        f"File '{file_path}' contains invalid characters ('{pattern}'). "
                        f"This usually indicates the file was saved with incorrect encoding. "
                        f"Please ensure the file is saved as UTF-8 encoding. "
                        f"Common issues: degree symbol (°), superscript (³), or other special characters."
                    )

            _LOGGER.debug("File encoding validation passed for: %s", file_path)
            return True

    except UnicodeDecodeError as e:
        handle_error(
            f"File '{file_path}' has encoding errors and cannot be read as {expected_encoding}. "
            f"Error at position {e.start}: {e.reason}. "
            f"Please ensure the file is saved with UTF-8 encoding, especially if it contains "
            f"special characters like ° (degree), ³ (superscript), or other non-ASCII characters."
        )
    except OSError as e:
        handle_error(f"Cannot read file '{file_path}': {e}")

    return False


def validate_filename(filename: str, config_dir: str) -> str:
    """
    Validate and normalize a filename to prevent directory traversal attacks.

    Ensures that:
    - The filename is a string
    - No absolute paths
    - No .. directory traversal sequences
    - The resolved path stays within config_dir

    Args:
    ----
        filename: The filename relative to config directory
        config_dir: The config directory path

    Returns:
    -------
        str: The full validated file path

    Raises:
    ------
        HomeAssistantError: If the filename is invalid or attempts directory traversal

    """
    if not isinstance(filename, str):
        handle_error(f"Filename must be a string, got {type(filename).__name__}")

    if not filename:
        handle_error("Filename cannot be empty")

    # Reject absolute paths
    if filename.startswith("/"):
        handle_error(f"Filename cannot be an absolute path: {filename}")

    # Reject .. sequences
    if ".." in filename:
        handle_error(f"Filename cannot contain .. directory traversal: {filename}")

    # Construct and validate the full path
    config_path = Path(config_dir).resolve()
    file_path = (config_path / filename).resolve()

    # Ensure the resolved path is within the config directory
    try:
        file_path.relative_to(config_path)
    except ValueError:
        handle_error(f"Filename would resolve outside config directory: {filename}")

    return str(file_path)


def format_datetime(dt_obj: dt.datetime | float, timezone: zoneinfo.ZoneInfo, format_str: str) -> str:
    """
    Format a datetime object to string in specified timezone and format.

    Args:
         dt_obj: Datetime object (may be UTC or already localized) or Unix timestamp (float/int)
         timezone: Target timezone
         format_str: Format string

    Returns:
         str: Formatted datetime string

    """
    # Handle Unix timestamp (float or int) from recorder API
    if isinstance(dt_obj, (float, int)):
        dt_obj = dt_module.datetime.fromtimestamp(dt_obj, tz=dt.UTC)

    # At this point, dt_obj is guaranteed to be a datetime
    if not isinstance(dt_obj, dt.datetime):
        # This should never happen, but satisfies type checker
        msg = f"Expected datetime object, got {type(dt_obj)}"
        raise HomeAssistantError(msg)

    if dt_obj.tzinfo is None:
        # Assume UTC if naive
        dt_obj = dt_obj.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))

    # Convert to target timezone
    local_dt = dt_obj.astimezone(timezone)

    return local_dt.strftime(format_str)


def format_decimal(value: float | None, *, use_comma: bool = False) -> str:
    """
    Format a numeric value with specified decimal separator.

    Handles numeric values including min, max, mean, sum, state, and delta values.

    Args:
         value: Numeric value to format
         use_comma: Use comma (True) or dot (False) as decimal separator

    Returns:
         str: Formatted number string

    """
    if value is None:
        return ""

    formatted = f"{float(value):.10g}"  # Avoid scientific notation, remove trailing zeros

    if use_comma:
        formatted = formatted.replace(".", ",")

    return formatted


def validate_timestamps_vectorized(df: pd.DataFrame) -> None:
    """
    Validate all timestamps in DataFrame are full hours (vectorized).

    Args:
    ----
        df: DataFrame with 'start' column containing datetime objects with timezone

    Raises:
    ------
        HomeAssistantError: If any timestamp is not a full hour

    """
    # Check if any timestamp has non-zero minutes or seconds
    start_series: pd.Series[pd.Timestamp] = df["start"]  # type: ignore[assignment]
    invalid_times = (start_series.dt.minute != 0) | (start_series.dt.second != 0)

    if invalid_times.any():
        # Get first invalid timestamp for error message
        first_invalid_idx: int = invalid_times.idxmax()  # type: ignore[assignment]
        first_invalid = df.loc[first_invalid_idx, "start"]
        # Convert to human-readable row number (1-based + 1 for header = +2)
        human_row = first_invalid_idx + 2
        msg = f"Invalid timestamp at row {human_row}: {first_invalid}. The timestamp must be a full hour."
        raise HomeAssistantError(msg)


def validate_floats_vectorized(df: pd.DataFrame, columns: list[str]) -> None:
    """
    Validate all float values in specified columns (vectorized).

    Args:
    ----
        df: DataFrame to validate
        columns: List of column names to validate as floats

    Raises:
    ------
        HomeAssistantError: If any value is NaN or cannot be converted to float

    """
    for col in columns:
        if col not in df.columns:
            continue

        # Check for NaN values
        if df[col].isna().any():
            first_na_idx = int(df[col].isna().idxmax()) + 2
            msg = f"Invalid float value in column '{col}' at row {first_na_idx}: NaN/empty value not allowed. Check for missing or empty values in your data."
            raise HomeAssistantError(msg)

        # Try to convert to float (pandas should already have done this, but validate)
        try:
            # This will raise if any value cannot be converted
            pd.to_numeric(df[col], errors="raise")
        except (ValueError, TypeError) as exc:
            # Find first problematic value
            for idx, val in df[col].items():
                try:
                    float(val)
                except (ValueError, TypeError):
                    # Convert to human-readable row number (1-based + 1 for header = +2)
                    human_row: int = idx + 2  # type: ignore[assignment]
                    msg = f"Invalid float value in column '{col}' at row {human_row}: {val}. Check the decimal separator."
                    raise HomeAssistantError(msg) from exc


def validate_min_max_mean_vectorized(df: pd.DataFrame) -> None:
    """
    Validate min <= mean <= max constraint for all rows (vectorized).

    Args:
    ----
        df: DataFrame with 'min', 'max', and 'mean' columns

    Raises:
    ------
        HomeAssistantError: If constraint is violated for any row

    """
    # Vectorized check: min <= mean <= max
    invalid_mmm = ~((df["min"] <= df["mean"]) & (df["mean"] <= df["max"]))

    if invalid_mmm.any():
        # Get first invalid row for error message
        first_invalid_idx: int = invalid_mmm.idxmax()  # type: ignore[assignment]
        row = df.loc[first_invalid_idx]
        # Convert to human-readable row number (1-based + 1 for header = +2)
        human_row = first_invalid_idx + 2
        msg = f"Invalid values at row {human_row}: min: {row['min']}, max: {row['max']}, mean: {row['mean']}, mean must be between min and max."
        raise HomeAssistantError(msg)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe storage.

    Removes path separators, path traversal sequences, and special characters
    while preserving the file extension. Only allows alphanumeric characters,
    dots, hyphens, and underscores.

    Args:
    ----
        filename: Original filename to sanitize

    Returns:
    -------
        str: Sanitized filename safe for storage

    Raises:
    ------
        HomeAssistantError: If filename is empty, contains only invalid characters,
                           or results in an empty name after sanitization

    """
    if not filename or not filename.strip():
        handle_error("Filename cannot be empty")

    # Get the file extension first
    path = Path(filename)
    stem = path.stem
    suffix = path.suffix.lower()

    # Remove path separators and traversal sequences
    stem = stem.replace("/", "").replace("\\", "").replace("..", "")

    # Remove special characters, keep only alphanumeric, dash, underscore
    sanitized_stem = "".join(c for c in stem if c.isalnum() or c in "._-")

    # Remove leading/trailing dots and spaces
    sanitized_stem = sanitized_stem.strip(". ")

    if not sanitized_stem:
        handle_error(f"Filename '{filename}' contains only invalid characters")

    # Reconstruct with sanitized stem and original extension
    return f"{sanitized_stem}{suffix}"


def validate_upload_file(filename: str, file_size: int) -> None:
    """
    Validate an uploaded file's extension and size.

    Args:
    ----
        filename: Name of the uploaded file
        file_size: Size of the file in bytes

    Raises:
    ------
        HomeAssistantError: If file extension is not allowed or file size exceeds limit

    """
    # Check file extension
    file_ext = Path(filename).suffix.lower()
    if file_ext not in UPLOAD_ALLOWED_EXTENSIONS:
        allowed = ", ".join(UPLOAD_ALLOWED_EXTENSIONS)
        handle_error(f"File extension '{file_ext}' not allowed. Allowed extensions: {allowed}")

    # Check file size
    if file_size > UPLOAD_MAX_SIZE:
        max_mb = UPLOAD_MAX_SIZE / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        handle_error(f"File size {actual_mb:.2f} MB exceeds maximum allowed size of {max_mb:.0f} MB")
