# Architecture Description: Home Assistant Statistics Import/Export Integration

## Overview

The `import_statistics` integration is a **service-based** Home Assistant custom component that provides bidirectional data flow for long-term statistics. Unlike typical integrations, it has no entities, platforms, or background coordinators - it operates purely through service calls.

**Key Characteristics:**

- **Service-Only Integration**: No entities, sensors, or continuous background tasks
- **Bidirectional Data Flow**: Import from files → Home Assistant, Export from Home Assistant → files
- **Dual Statistic Types**: Internal (recorder) and External (custom) statistics
- **Delta Processing**: Complex conversion system for delta-based statistics
- **File Format Support**: CSV, TSV, and JSON formats

---

## Package Structure

```
../../custom_components/import_statistics/
├── __init__.py                    # Integration entry point and service registration
├── manifest.json                  # Integration metadata and dependencies
├── config_flow.py                 # UI configuration flow (minimal)
├── const.py                       # Constants and attribute definitions
├── services.yaml                  # Service specifications for UI
├── helpers.py                     # Core validation, conversion, and utilities
├── import_service.py              # Main import service handler
├── export_service.py              # Main export service handler
├── import_service_helper.py       # Import data preparation and parsing
├── export_service_helper.py       # Export data formatting and file writing
├── import_service_delta_helper.py # Delta conversion algorithms
├── delta_database_access.py       # Database reference operations for deltas
├── export_database_access.py      # Database time range queries for exports
└── translations/                  # Localization files
    ├── en.json                    # English translations
    └── icons.json                 # Service icons
```

---

## Component Description

### [`__init__.py`](../../../../custom_components/import_statistics/__init__.py)

Integration entry point that registers three Home Assistant services: `import_from_file` (CSV/TSV import), `import_from_json` (JSON import), and `export_statistics` (export to file). Uses synchronous `setup()` to register async service handlers.

**Key Functions:**

- `setup(hass, config)`: Main entry point called by Home Assistant
- `async_setup_entry(hass, entry)`: Config entry setup (currently empty)

---

### [`import_service.py`](../../../../custom_components/import_statistics/import_service.py)

Orchestrates the import flow for both file and JSON sources. Detects delta processing needs via marker tuple, coordinates async database reference lookups, and dispatches to appropriate converters. Validates entity existence for internal statistics and optionally fetches units from entity attributes before calling Home Assistant's recorder API.

---

### [`import_service_helper.py`](../../../../custom_components/import_statistics/import_service_helper.py)

Handles data loading and DataFrame processing for imports. Loads CSV/TSV files with configurable delimiters and decimal separators, or constructs DataFrames from JSON input. Core processing validates columns and either extracts statistics directly (non-delta path) or returns a delta marker tuple with timestamp ranges for async database lookup (delta path).

---

### [`import_service_delta_helper.py`](../../../../custom_components/import_statistics/import_service_delta_helper.py)

Pure calculation functions for converting delta values to absolute sum/state values. Supports two conversion strategies: forward accumulation (reference before import range) and backward subtraction (reference at or after import range). All calculations are synchronous with pre-fetched database references.

---

### [`delta_database_access.py`](../../../../custom_components/import_statistics/delta_database_access.py)

Async database query functions for fetching delta conversion reference values. Implements two-pass lookup strategy: first attempts to find references before the oldest import timestamp, then falls back to references at or after the newest timestamp. Validates references are at least 1 hour away from import range.

---

### [`export_service.py`](../../../../custom_components/import_statistics/export_service.py)

Export service handler that fetches statistics from Home Assistant's recorder API, validates file paths and delimiters, and dispatches to appropriate formatters based on file extension (JSON vs CSV/TSV). Handles timezone conversion from UTC storage to user's local timezone for display.

**Key Features:**

- **Optional Entities Parameter**: When entities field is omitted or empty, exports all statistics in the database
- **Flexible Time Range**: Optional start_time/end_time with auto-detection from database
- **File Splitting**: `split_by` option to separate sensors and counters into different files
- **Performance Optimized**: Efficient database queries with proper async handling

---

### [`export_service_helper.py`](../../../../custom_components/import_statistics/export_service_helper.py)

Data formatting and file writing for exports. Detects statistic types (sensors vs counters), sorts records chronologically, formats timestamps and numeric values, and calculates delta columns for counters. Supports both CSV/TSV (with configurable delimiters) and JSON output formats.

---

### [`helpers.py`](../../../../custom_components/import_statistics/helpers.py)

Pure validation and conversion functions with no Home Assistant dependencies (except error handling). Provides the core validation pipeline including:

- Statistic ID format validation and source detection (recorder vs external)
- DataFrame column structure validation
- Row-level data extraction and validation for mean/min/max, sum/state, and delta statistics
- Constraint validation (min ≤ mean ≤ max, full hour timestamps)
- Unit source selection logic (TABLE vs ENTITY)
- File path security validation
- Timezone-aware datetime formatting
- Centralized error handling via `handle_error()`

---

### [`const.py`](../../../../custom_components/import_statistics/const.py)

Constants and configuration defaults including domain name, service parameter names, and datetime formats.

---

### [`config_flow.py`](../../../../custom_components/import_statistics/config_flow.py)

Minimal configuration flow using empty config schema.

---

## Module Dependencies

This section describes the internal module dependencies within the integration and the external dependencies to a running Home Assistant. The architecture follows a layered approach where pure validation functions (`helpers.py`) have minimal dependencies, while service handlers coordinate between Home Assistant APIs and business logic.

```mermaid
graph TB
    subgraph "Service Layer"
        init[__init__.py<br/>Service Registration]
        import_svc[import_service.py<br/>Import Orchestration]
        export_svc[export_service.py<br/>Export Orchestration]
    end

    subgraph "Data Processing"
        import_helper[import_service_helper.py<br/>Data Loading & Parsing]
        export_helper[export_service_helper.py<br/>Data Formatting & Splitting]
        delta_helper[import_service_delta_helper.py<br/>Delta Conversion]
        delta_db[delta_database_access.py<br/>DB Reference Queries]
        export_db[export_database_access.py<br/>Time Range Queries]
    end

    subgraph "Core Utilities"
        helpers[helpers.py<br/>Validation & Utils]
        const[const.py<br/>Constants]
    end

    subgraph "Home Assistant"
        ha_core[HA Core APIs]
        recorder[Recorder Database]
    end

    init --> import_svc
    init --> export_svc
    init --> ha_core

    import_svc --> import_helper
    import_svc --> delta_helper
    import_svc --> delta_db
    import_svc --> helpers
    import_svc --> ha_core

    export_svc --> export_helper
    export_svc --> helpers
    export_svc --> ha_core
    export_svc --> export_db

    import_helper --> helpers
    export_helper --> helpers
    delta_helper --> helpers
    delta_db --> helpers
    delta_db --> recorder

    helpers --> const

    style init fill:#e1f5ff
    style import_svc fill:#e1f5ff
    style export_svc fill:#e1f5ff
    style helpers fill:#fff4e1
    style const fill:#fff4e1
```

---

## Key Architectural Patterns

### 1. Dual-Mode Statistics System

Two mutually exclusive types with different validation and source rules:

| Aspect      | Internal (recorder)           | External (custom)                 |
| ----------- | ----------------------------- | --------------------------------- |
| Format      | `sensor.name` (dot separator) | `domain:name` (colon separator)   |
| Source      | Existing HA entity            | New synthetic entity              |
| Unit Source | Flexible (entity or CSV)      | Must be from CSV (TABLE)          |
| Validation  | Entity must exist in HA       | Domain cannot be "recorder"       |
| HA API      | `async_import_statistics()`   | `async_add_external_statistics()` |

### 2. Validation Pipeline

Distributed across multiple stages rather than centralized:

1. **Pre-processing**: File path security, delimiter normalization
2. **Column-level**: `are_columns_valid()` checks structure and column requirements
3. **Row-level**: Individual extraction functions validate values (silent failure on error)
4. **Constraint-level**: Relationship validation (min ≤ mean ≤ max, timestamp full hour)

### 3. Delta Processing Architecture

Three-stage async pipeline with reference lookups:

```
CSV with delta column
  ↓
[Stage 1] prepare_data_to_import() [sync via executor]
  - Detect delta column
  - Extract statistic_ids with oldest/newest timestamps
  - Return marker tuple
  ↓
[Stage 2] get_oldest_statistics_before() [async]
  - Query database for older references (1+ hour before)
  - Query database for newer references (1+ hour after) if older is missing
  - Return pre-fetched references
  ↓
[Stage 3] convert_delta_dataframe_with_references() [sync via executor]
  - Pure calculation: no HA dependency
  - Detect older reference vs newer reference from reference timestamp
  - Convert deltas to absolute values via accumulation or subtraction
  - Build metadata and statistics list
```

### 4. Async/Sync Hybrid Pattern

- Service handlers are async (required by HA)
- Data preparation (CSV/JSON parsing) runs sync via executor (avoids blocking)
- Database queries run async (native async support in HA)
- Pure calculations run sync via executor (testable independently)

### 5. Error Handling

Centralized via `handle_error()`:

- Always logs warning
- Always raises HomeAssistantError
- Ensures consistent error behavior across all functions

Silent failures occur only at row-level during extraction:

- `get_delta_stat()` returns empty dict on validation failure
- Invalid rows are skipped (not imported)
- Logged as debug or warning, continues processing

### 6. Timezone Conversion (Bidirectional)

**Import**: User's timezone → UTC

- User provides timestamps in local timezone
- Parsed with `zoneinfo.ZoneInfo(timezone_id)`
- Converted to UTC for internal storage: `.astimezone(dt.UTC)`

**Export**: UTC → User's timezone

- Recorder stores all times in UTC
- Converted to user's timezone for display: `.astimezone(tz)`
- Formatted using user's datetime format preference

### 7. File Path Security

Defense-in-depth for export filenames:

1. Reject absolute paths (start with `/`)
2. Reject `..` directory traversal sequences
3. Resolve final path using `Path.resolve()`
4. Verify within config_dir using `Path.relative_to()`

---

## Data Flow Diagrams

### Import Data Flow (with Delta Processing)

```mermaid
sequenceDiagram
    participant User
    participant HA as Home Assistant
    participant Import as import_service
    participant Helper as import_service_helper
    participant DeltaDB as delta_database_access
    participant DeltaCalc as import_service_delta_helper
    participant Recorder as HA Recorder API

    User->>HA: Call import_from_file<br/>(with delta column)
    HA->>Import: handle_import_from_file_impl()

    Note over Import: Async service handler
    Import->>Helper: prepare_data_to_import()<br/>[via executor]
    Note over Helper: Read CSV/TSV file<br/>Detect delta column<br/>Extract timestamp ranges
    Helper-->>Import: Delta marker tuple<br/>(statistic_ids, timestamps)

    Note over Import: Delta processing needed
    Import->>DeltaDB: get_oldest_statistics_before()<br/>[async]
    DeltaDB->>Recorder: Query refs 1+ hour before
    Recorder-->>DeltaDB: Reference records

    alt No older references found
        DeltaDB->>Recorder: Query refs at/after newest
        Recorder-->>DeltaDB: Newer reference records
    end

    DeltaDB-->>Import: {statistic_id: {start, sum, state}}

    Import->>DeltaCalc: convert_delta_dataframe()<br/>[via executor]
    Note over DeltaCalc: Determine reference type<br/>Forward/backward accumulation<br/>Convert deltas to absolute values
    DeltaCalc-->>Import: Statistics dict with sum/state

    Import->>Import: check_all_entities_exists()

    opt unit_from_entity == True
        Import->>Recorder: Get entity attributes
        Recorder-->>Import: unit_of_measurement
    end

    Import->>Recorder: async_import_statistics()<br/>or async_add_external_statistics()
    Recorder-->>Import: Success

    Import-->>HA: Complete
    HA-->>User: Success response
```

### Export Data Flow

```mermaid
sequenceDiagram
    participant User
    participant HA as Home Assistant
    participant Export as export_service
    participant Recorder as Recorder API
    participant Formatter as export_service_helper
    participant FileIO as File System
    participant Validation as helpers

    User->>HA: Call export_statistics
    HA->>Export: handle_export_statistics_impl()

    Export->>Validation: validate_filename()<br/>[security check]
    Validation-->>Export: Safe file path

    Export->>Validation: validate_delimiter()
    Validation-->>Export: Normalized delimiter

    Note over Export: Async database query
    Export->>Recorder: get_statistics_from_recorder()
    Note over Recorder: Parse timestamps in user TZ<br/>Convert to UTC<br/>Query database<br/>Fetch metadata (units)
    Recorder-->>Export: (statistics_dict, units_dict)

    alt Filename ends with .json
        Export->>Formatter: prepare_export_json()<br/>[via executor]
        Note over Formatter: Build entity objects<br/>Format timestamps/values<br/>Calculate deltas for counters
        Formatter-->>Export: JSON list

        Export->>Formatter: write_export_json()<br/>[via executor]
        Formatter->>FileIO: Write JSON file
        FileIO-->>Formatter: Success
    else CSV/TSV (default)
        Export->>Formatter: prepare_export_data()<br/>[via executor]
        Note over Formatter: Detect statistic types<br/>Format timestamps/values<br/>Calculate deltas<br/>Build column list
        Formatter-->>Export: (columns, rows)

        Export->>Formatter: write_export_file()<br/>[via executor]
        Formatter->>FileIO: Write CSV/TSV file
        FileIO-->>Formatter: Success
    end

    Export-->>HA: Complete
    HA-->>User: Success response
```

---

## Class Structure

```mermaid
classDiagram
    class ImportService {
        +handle_import_from_file_impl()
        +handle_import_from_json_impl()
        -_process_delta_references()
    }

    class ExportService {
        +handle_export_statistics_impl()
        +get_statistics_from_recorder()
    }

    class ImportServiceHelper {
        +prepare_data_to_import()
        +prepare_json_data_to_import()
        -_validate_and_detect_delta()
    }

    class ExportServiceHelper {
        +prepare_export_data()
        +prepare_export_json()
        +write_export_file()
        +write_export_json()
        +split_statistics_by_type()
    }

    class ExportDatabaseAccess {
        +get_global_statistics_time_range()
        -_get_min_max_start_ts()
        -_get_min_max_start_ts_short_term()
    }

    class DeltaDatabaseAccess {
        +get_oldest_statistics_before()
        +get_newest_statistics_after()
        -_get_reference_stats()
    }

    class DeltaHelper {
        +convert_deltas_with_older_reference()
        +convert_deltas_with_newer_reference()
        +handle_dataframe_delta()
    }

    class Helpers {
        +handle_error()
        +are_columns_valid()
        +get_source()
        +validate_filename()
        +get_mean_stat()
        +get_sum_stat()
        +get_delta_stat()
    }

    class UnitFrom {
        <<enumeration>>
        TABLE
        ENTITY
    }

    class DeltaReferenceType {
        <<enumeration>>
        OLDER_REFERENCE
        NEWER_REFERENCE
    }

    ImportService --> ImportServiceHelper
    ImportService --> DeltaDatabaseAccess
    ImportService --> DeltaHelper
    ImportService --> Helpers

    ExportService --> ExportServiceHelper
    ExportService --> ExportDatabaseAccess
    ExportService --> Helpers

    ImportServiceHelper --> Helpers
    ExportServiceHelper --> Helpers
    DeltaDatabaseAccess --> Helpers
    DeltaHelper --> Helpers

    DeltaHelper ..> UnitFrom : uses
    DeltaHelper ..> DeltaReferenceType : uses
```

---

## Data Structures

### Statistics Dictionary Structure

```python
{
    "sensor.temperature": (
        {
            "source": "recorder",
            "statistic_id": "sensor.temperature",
            "mean_type": StatisticMeanType.ARITHMETIC,
            "has_sum": False,
            "unit_of_measurement": "°C",
            "name": None,
            "unit_class": None,
        },
        [
            {
                "start": datetime(...),  # timezone-aware
                "min": 15.2,
                "max": 22.5,
                "mean": 18.7,
            },
            # ... more records
        ]
    ),
    "power:total": (
        {
            "source": "power",
            "statistic_id": "power:total",
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
            "unit_of_measurement": "kWh",
            "name": None,
            "unit_class": None,
        },
        [
            {
                "start": datetime(...),  # timezone-aware
                "sum": 1234.56,
                "state": 1234.56,
            },
            # ... more records
        ]
    ),
}
```

### References Dictionary (for Delta Import)

```python
{
    "sensor.energy": {
        "start": datetime(...),  # datetime of reference record
        "sum": 5432.1,          # sum value at reference time
        "state": 5432.1,        # state value at reference time
    },
    "power:total": None,  # No reference found (error case)
}
```

### Delta Marker Tuple

```python
(
    "_DELTA_PROCESSING_NEEDED",  # Marker string
    df,                          # DataFrame with delta column
    {                            # references_needed dict
        "sensor.energy": (oldest_dt_utc, newest_dt_utc),
        "power:total": (oldest_dt_utc, newest_dt_utc),
    },
    "Europe/Vienna",             # timezone_identifier
    "%d.%m.%Y %H:%M",           # datetime_format
    UnitFrom.TABLE,             # unit_from_where
)
```

---

## Implementation and Debugging Guide

### Where to Implement New Features

#### New Import Formats

- **Location**: `import_service_helper.py`
- **Pattern**: Add new preparation function similar to `prepare_json_data_to_import()`
- **Integration**: Call from `import_service.py` handlers

#### New Export Formats

- **Location**: `export_service_helper.py`
- **Pattern**: Add new formatting function similar to `prepare_export_json()`
- **Integration**: Call from `export_service.py`

#### New Validation Rules

- **Location**: `helpers.py`
- **Pattern**: Add validation function and call from `are_columns_valid()`
- **Integration**: Used throughout for consistent validation

#### New Services

- **Location**: `__init__.py` (registration), `services.yaml` (specification)
- **Pattern**: Add service handler in `setup()` function
- **Integration**: Follow async service handler pattern

### Where to Debug Issues

#### Service Call Problems

- **Entry Point**: `__init__.py` service registration
- **Parameter Issues**: `services.yaml` specifications
- **Handler Problems**: `import_service.py` or `export_service.py`

#### Data Validation Errors

- **Location**: `helpers.py` validation functions
- **Common Issues**: Column validation, statistic ID format, timestamp format
- **Debug Strategy**: Check `are_columns_valid()` and `get_source()` results

#### File Processing Problems

- **Import Issues**: `import_service_helper.py` parsing functions
- **Export Issues**: `export_service_helper.py` formatting functions
- **File Access**: Check `validate_filename()` for export security

#### Database Problems

- **Import Issues**: `import_service.py` database insertion
- **Export Issues**: `export_service.py` database querying
- **Delta Issues**: `delta_database_access.py` reference fetching

#### Delta Conversion Problems

- **Algorithm Issues**: `import_service_delta_helper.py` conversion functions
- **Reference Issues**: `delta_database_access.py` reference queries
- **Detection Issues**: `import_service_helper.py` delta detection

---

## Testing Strategy

The architecture supports multiple test levels:

1. **Unit Tests** (`tests/unit_tests/`):
   - Test pure functions in `helpers.py`, `import_service_delta_helper.py`
   - No Home Assistant mocks required
   - Fast execution

2. **Integration Tests with Mocks** (`tests/integration_tests_mock/`):
   - Test service handlers with mocked Home Assistant
   - Uses `pytest-homeassistant-custom-component`
   - Tests delta detection and conversion flow

3. **Integration Tests with Real HA** (`tests/integration_tests/`):
   - Tests against running Home Assistant instance
   - Requires HA_TOKEN_DEV environment variable
   - Validates full import/export workflow with actual database
   - Database should be clean before tests (use `scripts/clean_config`)

---

## Usage Examples

### Export All Statistics with Auto-Detected Range

```yaml
action: import_statistics.export_statistics
data:
  filename: all_statistics.tsv
  # All parameters optional - exports everything
  # entities: omitted (exports all)
  # start_time: omitted (auto-detect earliest)
  # end_time: omitted (auto-detect latest)
  split_by: both  # Separate sensors and counters
```

### Export Specific Entities with Time Range

```yaml
action: import_statistics.export_statistics
data:
  filename: exported_statistics.tsv
  entities:
    - sensor.temperature
    - sensor.energy_consumption
    - sensor:ext_value
  start_time: "2025-12-22 12:00:00"
  end_time: "2025-12-25 12:00:00"
  timezone_identifier: Europe/Vienna
  delimiter: \t
  decimal: false
```

---

## Performance Characteristics

- **Large Dataset Handling**: Exports of 450,000+ statistics complete in 30-60 seconds on Raspberry Pi hardware
- **Memory Efficiency**: Streaming data processing prevents memory exhaustion
- **Database Optimization**: Single queries for metadata and statistics minimize database load
- **Async Processing**: Non-blocking I/O operations maintain Home Assistant responsiveness

---

## External System Integration

### Home Assistant APIs Used

- **Recorder Statistics**: `statistics_during_period`, `async_import_statistics`, `get_metadata`, `list_statistic_ids`
- **Database Access**: Direct recorder database access for delta references and time range queries
- **Entity Validation**: `valid_entity_id`, `valid_statistic_id`
- **Error Handling**: `HomeAssistantError` exception hierarchy

### File System Access

- **Import**: Read from config directory (user-provided files)
- **Export**: Write to config directory with security validation
- **Security**: Path traversal protection in `validate_filename()`

### Dependencies

- **pandas**: Data manipulation and CSV/TSV parsing
- **zoneinfo**: Timezone handling (Python 3.12+)
- **Home Assistant Core**: Recorder component and statistics API

---

## Known Limitations & Design Decisions

1. **No Transaction Rollback**: Partial imports succeed if some rows validate
2. **Row-Level Silent Failures**: Invalid rows skipped, not reported individually
3. **Data Format Asymmetry**: Export allows mixed sensor/counter data, import requires separation
4. **Timezone Validation**: Must be valid zoneinfo timezone identifier
5. **Full-Hour Timestamps**: All timestamps must be at exact hour boundary (minutes=0, seconds=0)
