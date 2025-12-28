# Export Statistics - Design Proposal

## Overview

This document proposes a design for the export functionality that mirrors the import architecture while adhering to the specified constraints: using the recorder API (not direct database access), separating HA-dependent from HA-independent logic, and supporting both counter (state/sum) and sensor (mean/max/min) statistics types.

## Architecture Principles

Based on the import logic analysis, the architecture follows these patterns:

1. **HA-Dependent Layer**: Methods that require the `hass` object (service registration, file writing to config dir, entity lookups)
2. **HA-Independent Layer**: Pure data transformation functions that can be tested without Home Assistant (validation, formatting, data structure building)
3. **Recorder API Usage**: Leverage recorder's `get_statistics()` API for all database reads
4. **Separation of Concerns**: Handle entities and statistic_ids separately based on their source

---

## Service Definition

### Service: `export_statistics`

**Location**: `custom_components/import_statistics/services.yaml`

```yaml
export_statistics:
  description: "Export statistics to a file or JSON format"
  fields:
    filename:
      required: true
      example: "exported_statistics.tsv"
      description: "Filename relative to config directory (e.g., 'exported.tsv')"
      selector:
        text:

    entities:
      required: true
      example: ["sensor.temperature", "sensor.energy_consumption"]
      description: "List of statistic IDs or entity IDs to export (supports both internal and external)"
      selector:
        object:

    start_time:
      required: true
      example: "2025-12-22 12:00:00"
      description: "Datetime string in the format %Y-%m-%d %H:%M:%s (must be full hour, e.g. 2025-12-22 12:00:00)"
      selector:
        datetime:

    end_time:
      required: true
      example: "2025-12-25 12:00:00"
      description: "Datetime string in the format %Y-%m-%d %H:%M:%s (must be full hour, e.g. 2025-12-25 12:00:00)"
      selector:
        datetime:

    timezone_identifier:
      required: false
      default: "UTC"
      example: "Europe/Vienna"
      description: "Timezone for timestamp output formatting"
      selector:
        text:

    delimiter:
      required: false
      default: "\t"
      example: "\t"
      description: "Column delimiter for export file"
      selector:
        select:
          custom_value: true
          options:
            - '\t'
            - ";"
            - ","
            - "|"

    decimal:
      required: false
      default: false
      example: false
      description: "Use comma (true) or dot (false) as decimal separator"
      selector:
        boolean:

    datetime_format:
      required: false
      default: "%d.%m.%Y %H:%M"
      example: "%d.%m.%Y %H:%M"
      description: "Output datetime format string"
      selector:
        select:
          custom_value: true
          options:
            - "%d.%m.%Y %H:%M"
            - "%Y.%m.%d %H:%M"
            - "%Y-%m-%d %H:%M"
            - "%m/%d/%Y %H:%M"
            - "%d/%m/%Y %H:%M"
```

---

## Constants

**Location**: `custom_components/import_statistics/const.py` (additions)

```python
ATTR_EXPORT_TYPE = "export_type"  # "tsv", "csv", or "json"

# Export-specific constants
EXPORT_TYPE_TSV = "tsv"
EXPORT_TYPE_CSV = "csv"
EXPORT_TYPE_JSON = "json"
```

---

## Data Flow & Architecture

### 1. Service Handler (HA-Dependent)
**File**: `custom_components/import_statistics/__init__.py`

```python
def handle_export_statistics(call: ServiceCall) -> None:
    """
    Handle the export statistics service call.

    This is the only method that needs the hass object. It orchestrates:
    - Input validation
    - Entity/statistic_id resolution
    - HA API calls via recorder
    - File writing
    """
    filename = call.data.get(ATTR_FILENAME)
    entities_input = call.data.get(ATTR_ENTITIES)
    start_time_str = call.data.get(ATTR_START_TIME)
    end_time_str = call.data.get(ATTR_END_TIME)

    # Extract other parameters (with defaults matching services.yaml)
    timezone_identifier = call.data.get(ATTR_TIMEZONE_IDENTIFIER, "UTC")
    delimiter = call.data.get(ATTR_DELIMITER, "\t")
    decimal = call.data.get(ATTR_DECIMAL, False)
    datetime_format = call.data.get(ATTR_DATETIME_FORMAT, DATETIME_DEFAULT_FORMAT)

    _LOGGER.info("Service handle_export_statistics called")
    _LOGGER.info("Exporting entities: %s", entities_input)
    _LOGGER.info("Time range: %s to %s", start_time_str, end_time_str)
    _LOGGER.info("Output file: %s", filename)

    # Get statistics from recorder API
    statistics_dict = get_statistics_from_recorder(hass, entities_input, start_time_str, end_time_str)

    # Prepare data for export (HA-independent)
    columns, rows = prepare_data.prepare_export_data(
        statistics_dict,
        timezone_identifier,
        datetime_format,
        delimiter,
        decimal
    )

    # Write to file (HA-independent)
    file_path = f"{hass.config.config_dir}/{filename}"
    prepare_data.write_export_file(file_path, columns, rows, delimiter)

    hass.states.set("import_statistics.export_statistics", "OK")
    _LOGGER.info("Export completed successfully")
```

---

### 2. Recorder API Wrapper (HA-Dependent)
**File**: `custom_components/import_statistics/__init__.py`

```python
def get_statistics_from_recorder(
    hass: HomeAssistant,
    entities_input: list[str],
    start_time_str: str,
    end_time_str: str
) -> dict:
    """
    Fetch statistics from Home Assistant recorder API.

    Uses the recorder API to avoid direct database access.

    Returns:
        dict: {
            "statistic_id": {
                "metadata": {...},
                "statistics": [{"start": datetime, "mean": ..., ...}]
            },
            ...
        }

    Raises:
        HomeAssistantError: If time formats are invalid or no data found
    """
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.statistics import statistics_during_period

    _LOGGER.info("Fetching statistics from recorder API")

    # Parse datetime strings (format: "2025-12-01 12:00:00")
    try:
        start_dt = dt.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        end_dt = dt.datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        helpers.handle_error(f"Invalid datetime format. Expected 'YYYY-MM-DD HH:MM:SS': {e}")

    # Normalize to full hours
    if start_dt.minute != 0 or start_dt.second != 0:
        helpers.handle_error("start_time must be a full hour (minutes and seconds must be 0)")
    if end_dt.minute != 0 or end_dt.second != 0:
        helpers.handle_error("end_time must be a full hour (minutes and seconds must be 0)")

    # Convert string entity/statistic IDs to statistic_ids for recorder API
    statistic_ids = []
    for entity in entities_input:
        # Both "sensor.temperature" and "sensor:external_temp" formats supported
        # The get_source() helper validates the format
        source = helpers.get_source(entity)
        if source == "recorder":
            # It's an entity ID, keep as-is
            statistic_ids.append(entity)
        else:
            # It's an external statistic_id
            statistic_ids.append(entity)

    # Use recorder API to get statistics
    recorder_instance = get_instance(hass)
    if recorder_instance is None:
        helpers.handle_error("Recorder component is not running")

    # statistics_during_period returns data as:
    # {"statistic_id": [{"start": datetime, "end": datetime, "mean": ..., ...}]}
    statistics_dict = statistics_during_period(
        hass,
        start_dt,
        end_dt,
        statistic_ids,
        "hour",  # period
        None,    # units
        "not_missing"  # types
    )

    _LOGGER.debug("Statistics fetched: %s", statistics_dict)
    return statistics_dict
```

---

### 3. Data Preparation (HA-Independent)
**File**: `custom_components/import_statistics/prepare_data.py` (new functions)

```python
def prepare_export_data(
    statistics_dict: dict,
    timezone_identifier: str,
    datetime_format: str,
    delimiter: str,
    decimal_comma: bool
) -> tuple:
    """
    Prepare statistics data for export (TSV/CSV format).

    Args:
        statistics_dict: Raw data from recorder API
        timezone_identifier: Timezone for timestamp output
        datetime_format: Format string for timestamps
        delimiter: Column separator
        decimal_comma: Use comma (True) or dot (False) for decimals

    Returns:
        tuple: (columns list, data rows list)
            columns: ["statistic_id", "unit", "start", "mean", "min", "max", "sum", "state"]
            data: List of row tuples

    Raises:
        HomeAssistantError: If timezone is invalid or data is malformed
    """
    _LOGGER.info("Preparing export data")

    if timezone_identifier not in pytz.all_timezones:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    timezone = zoneinfo.ZoneInfo(timezone_identifier)

    # Analyze what types of statistics we have (sensors vs counters)
    has_sensors = False  # mean/min/max
    has_counters = False  # sum/state

    all_columns = ["statistic_id", "unit", "start"]
    rows = []

    for statistic_id, data in statistics_dict.items():
        if not data or "statistics" not in data:
            _LOGGER.warning("No statistics data for %s", statistic_id)
            continue

        statistics_list = data["statistics"]
        if not statistics_list:
            _LOGGER.warning("Empty statistics list for %s", statistic_id)
            continue

        # Determine type from first non-empty record
        stat_type = _detect_statistic_type(statistics_list)

        if stat_type == "sensor":
            has_sensors = True
        elif stat_type == "counter":
            has_counters = True

        # Get unit
        unit = data.get("unit_of_measurement", "")

        for stat_record in statistics_list:
            row_dict = {
                "statistic_id": statistic_id,
                "unit": unit,
                "start": _format_datetime(stat_record["start"], timezone, datetime_format),
            }

            # Add sensor columns (empty for counters)
            if "mean" in stat_record:
                row_dict["mean"] = _format_decimal(stat_record["mean"], decimal_comma)
                if "min" not in all_columns:
                    all_columns.extend(["min", "max", "mean"])

            # Add counter columns (empty for sensors)
            if "sum" in stat_record:
                row_dict["sum"] = _format_decimal(stat_record["sum"], decimal_comma)
                if "sum" not in all_columns:
                    all_columns.append("sum")

            if "state" in stat_record:
                row_dict["state"] = _format_decimal(stat_record["state"], decimal_comma)
                if "state" not in all_columns:
                    all_columns.append("state")

            rows.append(row_dict)

    # Validate if sensors and counters are mixed
    if has_sensors and has_counters:
        _LOGGER.info(
            "Export contains both sensor (mean/min/max) and counter (sum/state) statistics. "
            "Sensor columns will be empty for counters and vice versa."
        )

    # Build column list: always include statistic_id, unit, start
    # Then conditionally add sensor or counter columns
    column_order = ["statistic_id", "unit", "start"]
    if has_sensors:
        column_order.extend(["min", "max", "mean"])
    if has_counters:
        column_order.extend(["sum", "state"])

    # Convert row dicts to tuples in column order, filling empty cells
    data_rows = []
    for row_dict in rows:
        row_tuple = tuple(
            row_dict.get(col, "")
            for col in column_order
        )
        data_rows.append(row_tuple)

    _LOGGER.debug("Export data prepared with columns: %s", column_order)
    return column_order, data_rows


def _detect_statistic_type(statistics_list: list) -> str:
    """
    Detect if statistics are sensor (mean/min/max) or counter (sum/state) type.

    Args:
        statistics_list: List of statistic records from recorder

    Returns:
        str: "sensor", "counter", or "unknown"
    """
    for stat_record in statistics_list:
        if "mean" in stat_record or "min" in stat_record or "max" in stat_record:
            return "sensor"
        if "sum" in stat_record or "state" in stat_record:
            return "counter"

    return "unknown"


def _format_datetime(dt_obj: datetime.datetime, timezone: zoneinfo.ZoneInfo, format_str: str) -> str:
    """
    Format a datetime object to string in specified timezone and format.

    Args:
        dt_obj: Datetime object (may be UTC or already localized)
        timezone: Target timezone
        format_str: Format string

    Returns:
        str: Formatted datetime string
    """
    if dt_obj.tzinfo is None:
        # Assume UTC if naive
        dt_obj = dt_obj.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))

    # Convert to target timezone
    local_dt = dt_obj.astimezone(timezone)

    return local_dt.strftime(format_str)


def _format_decimal(value: float | int | None, use_comma: bool) -> str:
    """
    Format a numeric value with specified decimal separator.

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


def prepare_export_json(
    statistics_dict: dict,
    timezone_identifier: str,
    datetime_format: str
) -> list:
    """
    Prepare statistics data for JSON export.

    Returns:
        list: List of entity objects in JSON format
            [
                {
                    "id": "sensor.temperature",
                    "unit": "°C",
                    "values": [
                        {
                            "datetime": "2023-01-01T00:00:00",
                            "mean": 20.5,
                            "min": 20.0,
                            "max": 21.0
                        },
                        ...
                    ]
                },
                ...
            ]
    """
    _LOGGER.info("Preparing JSON export data")

    if timezone_identifier not in pytz.all_timezones:
        helpers.handle_error(f"Invalid timezone_identifier: {timezone_identifier}")

    timezone = zoneinfo.ZoneInfo(timezone_identifier)

    export_entities = []

    for statistic_id, data in statistics_dict.items():
        if not data or "statistics" not in data:
            continue

        statistics_list = data["statistics"]
        if not statistics_list:
            continue

        entity_obj = {
            "id": statistic_id,
            "unit": data.get("unit_of_measurement", ""),
            "values": []
        }

        for stat_record in statistics_list:
            value_obj = {
                "datetime": _format_datetime(stat_record["start"], timezone, datetime_format)
            }

            # Add all available fields
            if "mean" in stat_record:
                value_obj["mean"] = stat_record["mean"]
            if "min" in stat_record:
                value_obj["min"] = stat_record["min"]
            if "max" in stat_record:
                value_obj["max"] = stat_record["max"]
            if "sum" in stat_record:
                value_obj["sum"] = stat_record["sum"]
            if "state" in stat_record:
                value_obj["state"] = stat_record["state"]

            entity_obj["values"].append(value_obj)

        export_entities.append(entity_obj)

    return export_entities
```

---

### 4. File Writing (HA-Independent)
**File**: `custom_components/import_statistics/prepare_data.py`

```python
def write_export_file(file_path: str, columns: list, rows: list, delimiter: str) -> None:
    """
    Write export data to a TSV/CSV file.

    Args:
        file_path: Absolute path to output file
        columns: List of column headers
        rows: List of row tuples
        delimiter: Column delimiter

    Raises:
        HomeAssistantError: If file cannot be written
    """
    _LOGGER.info("Writing export file: %s", file_path)

    try:
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=delimiter)
            writer.writerow(columns)
            writer.writerows(rows)

        _LOGGER.info("Export file written successfully: %s", file_path)
    except IOError as e:
        helpers.handle_error(f"Failed to write export file {file_path}: {e}")


def write_export_json(file_path: str, json_data: list) -> None:
    """
    Write export data to a JSON file.

    Args:
        file_path: Absolute path to output file
        json_data: Data to export

    Raises:
        HomeAssistantError: If file cannot be written
    """
    _LOGGER.info("Writing JSON export file: %s", file_path)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)

        _LOGGER.info("JSON export file written successfully: %s", file_path)
    except IOError as e:
        helpers.handle_error(f"Failed to write JSON export file {file_path}: {e}")
```

---

## Type Distinction Strategy

### Counters vs Sensors

The design distinguishes between entity types at multiple levels:

#### 1. **Data Detection**
- Sensor statistics: contain `mean`, `min`, `max` columns
- Counter statistics: contain `sum` and optionally `state` columns
- Never mixed in same entity's history

#### 2. **Column Handling**
When exporting mixed entity types:
- Always include base columns: `statistic_id`, `unit`, `start`
- Sensor entities → populate `min`, `max`, `mean`; leave `sum`, `state` empty
- Counter entities → populate `sum`, `state`; leave `min`, `max`, `mean` empty

#### 3. **Output Validation**
Log info if mixed types detected, but allow export (mirrors import flexibility)

---

## Error Handling

The architecture maintains the import pattern:

1. **Validation Errors**: Raised immediately via `helpers.handle_error()`
   - Invalid timezone
   - Invalid datetime formats
   - No data found for requested range
   - File write permissions

2. **Logging Pattern**:
   - INFO: Service start, entity count, file location, completion
   - DEBUG: Column structure, record counts, data samples
   - WARNING: Missing data, type mismatches

3. **User Feedback**:
   - Home Assistant state update: `import_statistics.export_statistics` → "OK" or error message
   - Exceptions propagate to service call handler

---

## Testing Structure

### Unit Tests (HA-Independent)
**Location**: `tests/test_prepare_export_data.py`

```python
def test_prepare_export_data_sensors() -> None:
    """Test export of sensor statistics (mean/min/max)"""

def test_prepare_export_data_counters() -> None:
    """Test export of counter statistics (sum/state)"""

def test_prepare_export_data_mixed_types() -> None:
    """Test export with both sensor and counter entities"""

def test_format_datetime() -> None:
    """Test timezone-aware datetime formatting"""

def test_format_decimal_dot() -> None:
    """Test decimal formatting with dot separator"""

def test_format_decimal_comma() -> None:
    """Test decimal formatting with comma separator"""

def test_detect_statistic_type() -> None:
    """Test automatic statistic type detection"""
```

### Integration Tests
- Mock recorder API responses
- Verify file output structure
- Validate timestamp and decimal formatting

---

## Implementation Steps (Recommended Order)

1. **Add Constants** (`const.py`)
   - Export-related attribute names

2. **Add Helper Functions** (`helpers.py`)
   - Any additional validation needed beyond import

3. **Add Data Preparation** (`prepare_data.py`)
   - `prepare_export_data()`
   - `prepare_export_json()`
   - Formatting utilities

4. **Add Service Handler** (`__init__.py`)
   - `get_statistics_from_recorder()`
   - `handle_export_statistics()`
   - `write_export_file()` / `write_export_json()`

5. **Update Service Definition** (`services.yaml`)
   - Add complete `export_statistics` schema

6. **Add Tests** (`tests/test_*.py`)
   - Data preparation tests
   - Integration tests

7. **Update Documentation** (`README.md`)
   - Service usage examples
   - Output file format examples
   - Entity ID vs statistic_id explanation

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Use recorder API | No direct DB access, supports all HA backends |
| ISO 8601 input dates | Standard format, unambiguous across timezones |
| Full-hour enforcement | Matches HA statistics granularity (hourly) |
| HA-dependent/independent split | Mirrors import, enables testing without HA |
| Mixed type support | Flexibility; most real-world exports are heterogeneous |
| Empty cell approach | Clear indicator which entity is counter vs sensor |
| Timezone-aware formatting | Matches import, supports multiple timezone outputs |
| Decimal separator choice | Matches import's localization flexibility |

---

## Example Usage

### Export as TSV
```yaml
service: import_statistics.export_statistics
data:
  filename: "my_export.tsv"
  entities:
    - sensor.temperature
    - sensor.energy_total
    - sensor:external_metric
  start_time: "2024-01-01 00:00:00"
  end_time: "2024-01-31 23:00:00"
  timezone_identifier: "Europe/Vienna"
  delimiter: "\t"
  decimal: false
  datetime_format: "%d.%m.%Y %H:%M"
```

### Export as CSV
```yaml
service: import_statistics.export_statistics
data:
  filename: "my_export.csv"
  entities: ["sensor.temperature", "sensor:external_metric"]
  start_time: "2024-01-01 00:00:00"
  end_time: "2024-01-31 23:00:00"
  delimiter: ","
  decimal: true
```

---

## Constraints Addressed

✅ **No Direct Database Access**: Uses recorder API (`statistics_during_period()`)

✅ **HA-Independent Methods**: Data preparation functions are pure; only service handler touches `hass` object

✅ **Type Distinction**: Counters (sum/state) separated from sensors (mean/min/max) at detection, preparation, and output levels

✅ **Type Mixing**: Supported via empty column pattern; no validation error for mixed exports

✅ **Logging & Error Patterns**: Mirrors import (validation errors immediate, debug logging detailed)

