# Refactored Delta Import Design

## Overview

This document describes the refactored delta import architecture that separates concerns and eliminates the `_DELTA_PROCESSING_NEEDED` hack by:

1. Removing Home Assistant dependencies from data preparation
2. Separating delta handling logic into dedicated methods
3. Creating a clear async/sync boundary for database queries
4. Making all delta conversion logic testable without Home Assistant

---

## Architecture Changes

### Current State vs. Refactored State

| Aspect | Current | Refactored |
|--------|---------|-----------|
| `prepare_data_to_import()` | Calls `handle_dataframe()`, returns stats or marker tuple | Returns `(df, timezone_id, datetime_format, unit_from_entity, is_delta)` |
| HA Dependency | In data preparation | Only in async service handlers |
| Delta Marker | `("_DELTA_PROCESSING_NEEDED", ...)` tuple hack | Boolean flag in return value || Reference Type Indicator | Case 1/Case 2 integers | `DeltaReferenceType` enum (OLDER_REFERENCE, YOUNGER_REFERENCE) || Database Query Orchestration | In `import_service.py` (async) | New `prepare_delta_handling()` method |
| Delta Conversion | In `import_service_delta_helper.py` | Renamed to `handle_dataframe_delta()` |
| Non-delta Processing | Via `handle_dataframe()` | New method `handle_dataframe_no_delta()` |

---

## New File Structure

### Modified: [`import_service_helper.py`](../custom_components/import_statistics/import_service_helper.py)

**Purpose**: Data loading and initial DataFrame processing (no HA dependencies).

**New Method Signature**:
```python
def prepare_data_to_import(file_path: str, call: ServiceCall) -> tuple[pd.DataFrame, str, str, UnitFrom, bool]:
    """
    Load and prepare data from CSV/TSV file for import.

    Returns:
        Tuple of (df, timezone_identifier, datetime_format, unit_from_entity, is_delta)

    Raises:
        HomeAssistantError: On validation errors
    """
    # Extract parameters from call
    # Read CSV file
    # Return (df, timezone_id, datetime_format, unit_from_where, is_delta_mode)
    # No call to handle_dataframe()
    # No HA dependency
```

**New Method Signature**:
```python
def prepare_json_data_to_import(call: ServiceCall) -> tuple[pd.DataFrame, str, str, UnitFrom, bool]:
    """
    Prepare data from JSON service call for import.

    Returns:
        Tuple of (df, timezone_identifier, datetime_format, unit_from_entity, is_delta)

    Raises:
        HomeAssistantError: On validation errors
    """
    # Extract entities from service call
    # Construct DataFrame
    # Return (df, timezone_id, datetime_format, unit_from_where, is_delta_mode)
    # No HA dependency
```

**Removed**:
- `handle_dataframe()` method (logic split into `handle_dataframe_no_delta()` and `handle_dataframe_delta()`)
- Marker tuple detection and construction
- References lookup from `prepare_data_to_import()`
- Return of `unit_from_entity` flag (now part of tuple)

**Existing Methods** (unchanged):
- `handle_arguments()`: Still extracts parameters from service call
- `validate_delimiter()`: Already in helpers

---

### New Method in [`import_service_helper.py`](../custom_components/import_statistics/import_service_helper.py)

**New Method Signature**:
```python
def handle_dataframe_no_delta(
    df: pd.DataFrame,
    timezone_identifier: str,
    datetime_format: str,
    unit_from_where: UnitFrom,
) -> dict[str, tuple[dict, list[dict]]]:
    """
    Process non-delta statistics from DataFrame.

    Args:
        df: DataFrame with statistic_id, start, and value columns
        timezone_identifier: IANA timezone string
        datetime_format: Format string for parsing timestamps
        unit_from_where: Source of unit values (TABLE or ENTITY)

    Returns:
        Dictionary mapping statistic_id to (metadata, statistics_list)

    Raises:
        HomeAssistantError: On validation errors
    """
    # Extract from current handle_dataframe() non-delta logic
    # Validate columns with are_columns_valid()
    # Iterate rows, extracting mean/sum statistics
    # Build metadata and statistics list per statistic_id
    # Returns stats dict
```

**Implementation Notes**:
- Contains the non-delta path logic from current `handle_dataframe()`
- No HA dependencies
- No delta column detection or handling
- Validates unit columns based on `unit_from_where`
- Calls `helpers.are_columns_valid()` to ensure non-delta specific column structure

---

### New Method in [`import_service_delta_helper.py`](../custom_components/import_statistics/import_service_delta_helper.py)

**Renamed Method**:
```python
def handle_dataframe_delta(
    df: pd.DataFrame,
    timezone_identifier: str,
    datetime_format: str,
    unit_from_where: UnitFrom,
    references: dict[str, dict],  # Maps statistic_id to reference data
) -> dict[str, tuple[dict, list[dict]]]:
    """
    Process delta statistics from DataFrame using pre-fetched references.

    This is the renamed version of convert_delta_dataframe_with_references().

    Args:
        df: DataFrame with delta column and statistic_id, start columns
        timezone_identifier: IANA timezone string
        datetime_format: Format string for parsing timestamps
        unit_from_where: Source of unit values (TABLE or ENTITY)
        references: Dict mapping statistic_id to reference data
                   Format: {
                       statistic_id: {
                           "reference": {"start": datetime, "sum": float, "state": float},
                           "ref_type": DeltaReferenceType.OLDER_REFERENCE or DeltaReferenceType.YOUNGER_REFERENCE
                       } or None
                   }

    Returns:
        Dictionary mapping statistic_id to (metadata, statistics_list)

    Raises:
        HomeAssistantError: On validation errors or missing references
    """
    # Renamed from convert_delta_dataframe_with_references()
    # Same logic, but references dict structure uses DeltaReferenceType enum
    # Calls helpers.are_columns_valid() to validate delta column structure
    # Groups by statistic_id
    # Calls convert_deltas_with_older_reference() or convert_deltas_with_younger_reference()
    # Builds metadata and returns stats dict
```

**Implementation Notes**:
- Renamed from `convert_delta_dataframe_with_references()`
- Pure calculation: no HA dependency
- All references are pre-fetched and passed in
- Returns same stats dict format as `handle_dataframe_no_delta()`
- Calls `helpers.are_columns_valid()` with special delta validation (delta column required, no min/max/mean/sum)

---

### New Method in [`import_service.py`](../custom_components/import_statistics/import_service.py)

**New Async Method**:
```python
async def prepare_delta_handling(
    hass: HomeAssistant,
    df: pd.DataFrame,
    timezone_identifier: str,
    datetime_format: str,
) -> dict[str, dict]:
    """
    Fetch and validate database references for delta import.

    This method orchestrates all database queries needed for delta processing,
    validates time range intersections, and returns structured reference data.

    Args:
        hass: Home Assistant instance
        df: DataFrame with delta column
        timezone_identifier: IANA timezone string
        datetime_format: Format string for parsing timestamps

    Returns:
        Dictionary mapping statistic_id to reference data:
        {
            statistic_id: {
                "reference": {"start": datetime, "sum": float, "state": float},
                "case": 1 or 2  # Which conversion case applies
            } or None if no valid reference found
        }

    Raises:
        HomeAssistantError: On validation errors or incompatible time ranges
    """
    # Step 1: Extract oldest/youngest timestamps from df per statistic_id
    #         (move logic from current handle_dataframe delta detection)

    # Step 2: For each statistic_id:
    #   a) Fetch t_youngest_db using get_last_statistics()
    #      ERROR: "Importing values younger than the youngest value in the database is not possible"
    #             if t_youngest_import < t_youngest_db
    #
    #   b) Fetch t_youngest_db_time_before_oldest_import
    #      ERROR: "imported timerange is completely newer than timerange in DB"
    #             if t_youngest_db <= t_oldest_import
    #
    #   c) If t_youngest_db_time_before_oldest_import is not found:
    #      - Fetch t_youngest_db_time_before_youngest_import
    #        ERROR: "imported timerange is completely older than timerange in DB"
    #               if not found
    #      - Fetch t_oldest_db_time_after_youngest_import
    #        ERROR: "imported timerange completely overlaps timerange in DB"
    #               if not found
    #
    # Step 3: Return structured reference data with DeltaReferenceType indicators

    # This method replaces the get_oldest_statistics_before() call in service handlers
```

**Implementation Notes**:
- All database queries are async
- Comprehensive error checking for time range compatibility
- Includes entity ID in error messages for clarity
- Returns structured data ready for `handle_dataframe_delta()` with `DeltaReferenceType` enum values
- Validates distance of references (1+ hour away for OLDER_REFERENCE, 0+ hours for YOUNGER_REFERENCE)

---

### Updated: [`import_service.py`](../custom_components/import_statistics/import_service.py)

**Updated Method Signature**:
```python
async def handle_import_from_file_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle import_from_file service implementation."""
    # Extract filename

    # Step 1: Prepare data (non-HA operation)
    df, timezone_id, datetime_format, unit_from_entity, is_delta = \
        await hass.async_add_executor_job(lambda: prepare_data_to_import(file_path, call))

    # Step 2: Handle based on delta flag
    if is_delta:
        # Delta path: fetch database references
        references = await prepare_delta_handling(hass, df, timezone_id, datetime_format)

        # Convert deltas with references
        stats = await hass.async_add_executor_job(
            lambda: handle_dataframe_delta(df, timezone_id, datetime_format, unit_from_entity, references)
        )
    else:
        # Non-delta path: direct processing
        stats = await hass.async_add_executor_job(
            lambda: handle_dataframe_no_delta(df, timezone_id, datetime_format, unit_from_entity)
        )

    # Step 3: Import to Home Assistant
    import_stats(hass, stats, unit_from_entity)
```

**Updated Method Signature**:
```python
async def handle_import_from_json_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle import_from_json service implementation."""
    # Extract JSON data

    # Step 1: Prepare data (non-HA operation)
    df, timezone_id, datetime_format, unit_from_entity, is_delta = \
        await hass.async_add_executor_job(lambda: prepare_json_data_to_import(call))

    # Step 2: Handle based on delta flag
    if is_delta:
        # Delta path: fetch database references
        references = await prepare_delta_handling(hass, df, timezone_id, datetime_format)

        # Convert deltas with references
        stats = await hass.async_add_executor_job(
            lambda: handle_dataframe_delta(df, timezone_id, datetime_format, unit_from_entity, references)
        )
    else:
        # Non-delta path: direct processing
        stats = await hass.async_add_executor_job(
            lambda: handle_dataframe_no_delta(df, timezone_id, datetime_format, unit_from_entity)
        )

    # Step 3: Import to Home Assistant
    import_stats(hass, stats, unit_from_entity)
```

**Removed**:
- Marker tuple detection and handling
- Direct call to `get_oldest_statistics_before()`
- Manual reference passing logic

---

### New/Modified: [`delta_import.py`](../custom_components/import_statistics/delta_import.py)

**Removed**:
- `get_oldest_statistics_before()`: Functionality moved into `prepare_delta_handling()`
- `get_youngest_statistic_after()`: Functionality merged into helper methods

**New/Helper Methods** (to support `prepare_delta_handling()`):
```python
async def _get_youngest_db_statistic(
    hass: HomeAssistant,
    statistic_id: str,
) -> dict | None:
    """
    Fetch the youngest statistic from database for given statistic_id.

    Returns:
        Dict with keys: start (datetime), sum (float), state (float)
        Or None if no statistics exist for this ID
    """
    # Uses get_last_statistics()
```

```python
async def _get_reference_before_timestamp(
    hass: HomeAssistant,
    statistic_id: str,
    timestamp: datetime,
    period_type: str = "hour",
) -> dict | None:
    """
    Fetch the youngest statistic before given timestamp.

    Args:
        hass: Home Assistant instance
        statistic_id: The statistic to query
        timestamp: Find records before this time
        period_type: "hour" (default) for hourly statistics

    Returns:
        Dict with keys: start (datetime), sum (float), state (float)
        Or None if no matching record exists
    """
    # Uses _get_reference_stats() or similar
```

```python
async def _get_reference_at_or_after_timestamp(
    hass: HomeAssistant,
    statistic_id: str,
    timestamp: datetime,
    period_type: str = "hour",
) -> dict | None:
    """
    Fetch the oldest statistic at or after given timestamp.

    Args:
        hass: Home Assistant instance
        statistic_id: The statistic to query
        timestamp: Find records at or after this time
        period_type: "hour" (default) for hourly statistics

    Returns:
        Dict with keys: start (datetime), sum (float), state (float)
        Or None if no matching record exists
    """
    # Low-level database query using statistics_at_time or get_statistics
```

**Implementation Notes**:
- Helper methods are extracted from current logic
- Remain private (`_*` prefix) and only used internally by `prepare_delta_handling()`

---

## Data Structures

### Delta Reference Type Enum

Definition in `helpers.py`:
```python
from enum import Enum

class DeltaReferenceType(Enum):
    """Type of reference used for delta conversion."""
    OLDER_REFERENCE = "older"    # Reference is 1+ hour before oldest import
    YOUNGER_REFERENCE = "younger" # Reference is at or after youngest import
```

### Return Value of Refactored Preparation Methods

```python
# prepare_data_to_import() and prepare_json_data_to_import()
return_value: tuple[
    pd.DataFrame,      # 0: Parsed DataFrame with all rows/columns from file
    str,               # 1: IANA timezone identifier (e.g., "Europe/Berlin")
    str,               # 2: Datetime format string (e.g., "%d.%m.%Y %H:%M")
    UnitFrom,          # 3: Unit source (TABLE or ENTITY)
    bool,              # 4: Is delta mode (presence of delta column)
]
```

### Reference Data Structure for `prepare_delta_handling()`

Input: None (extracted internally from DataFrame)

Output:
```python
references: dict[str, dict | None] = {
    "sensor.temperature": {
        "reference": {
            "start": datetime(...),  # Timezone-aware datetime
            "sum": 42.5,
            "state": 42.5,
        },
        "ref_type": DeltaReferenceType.OLDER_REFERENCE,  # or YOUNGER_REFERENCE
    },
    "sensor.power": None,  # No valid reference found
}
```

### Reference Data Structure for `handle_dataframe_delta()`

Same as output from `prepare_delta_handling()`:
```python
references: dict[str, dict | None] = {
    statistic_id: {
        "reference": {"start": datetime, "sum": float, "state": float},
        "ref_type": DeltaReferenceType.OLDER_REFERENCE or DeltaReferenceType.YOUNGER_REFERENCE,
    } or None
}
```

---

## Error Handling

### New Validation Errors in `prepare_delta_handling()`

All errors use `helpers.handle_error()` for consistency.

**By Scenario**:

1. **t_youngest_import < t_youngest_db**
   - Error: `"Entity '<entity_id>': Importing values younger than the youngest value in the database (<timestamp>) is not possible"`

2. **t_youngest_db <= t_oldest_import (no backward reference)**
   - Error: `"Entity '<entity_id>': imported timerange is completely newer than timerange in DB (database youngest: <timestamp>)"`

3. **No reference before oldest import AND no reference before youngest import**
   - Error: `"Entity '<entity_id>': imported timerange is completely older than timerange in DB (database oldest: <timestamp>)"`

4. **No reference before youngest import AND no reference at/after youngest import**
   - Error: `"Entity '<entity_id>': imported timerange completely overlaps timerange in DB (cannot find reference before or after import)"`

5. **Implementation Error (neither OLDER_REFERENCE nor YOUNGER_REFERENCE found after validation)**
   - Error: `"Internal error: Neither OLDER_REFERENCE nor YOUNGER_REFERENCE found for '<entity_id>' despite validation passing"`

**Error Message Format**:
- Always include `<entity_id>` in message
- Include relevant timestamp(s) where helpful
- Include database values (youngest/oldest) for context

---

## Method Dependencies & Call Graph

```
handle_import_from_file_impl() [async]
  ├─ prepare_data_to_import() [executor]
  │   ├─ helpers.get_source()
  │   ├─ helpers.are_columns_valid()
  │   └─ (detects delta column presence)
  │
  ├─ IF is_delta:
  │   ├─ prepare_delta_handling() [async]
  │   │   ├─ _extract_oldest_youngest_from_df()
  │   │   ├─ _get_youngest_db_statistic() [async]
  │   │   ├─ _get_reference_before_timestamp() [async]
  │   │   └─ _get_reference_at_or_after_timestamp() [async]
  │   │
  │   └─ handle_dataframe_delta() [executor]
  │       ├─ helpers.are_columns_valid() (with delta validation)
  │       ├─ helpers.get_delta_stat()
  │       ├─ convert_deltas_with_older_reference()
  │       └─ convert_deltas_with_younger_reference()
  │
  └─ IF NOT is_delta:
      └─ handle_dataframe_no_delta() [executor]
          ├─ helpers.are_columns_valid()
          ├─ helpers.get_mean_stat() OR helpers.get_sum_stat()
          └─ helpers.add_unit_to_dataframe()

  └─ import_stats() [sync]
      ├─ check_all_entities_exists()
      ├─ add_unit_for_all_entities()
      └─ async_import_statistics() or async_add_external_statistics()
```

---

## Methods Removed

The following methods are removed and replaced:

1. **`get_oldest_statistics_before()` in `delta_import.py`**
   - Functionality replaced by `prepare_delta_handling()` in `import_service.py`
   - All database orchestration is now in `prepare_delta_handling()`

2. **`get_youngest_statistic_after()` in `delta_import.py`**
   - Functionality merged into helper methods used by `prepare_delta_handling()`

3. **`handle_dataframe()` in `import_service_helper.py`**
   - Logic split into `handle_dataframe_no_delta()` and `handle_dataframe_delta()`
   - Marker tuple detection removed

4. **`convert_delta_dataframe_with_references()` in `import_service_delta_helper.py`**
   - Renamed to `handle_dataframe_delta()` with updated reference structure
   - Method names `convert_deltas_case_1()` and `convert_deltas_case_2()` renamed to `convert_deltas_with_older_reference()` and `convert_deltas_with_younger_reference()`

## Methods to Keep (Unchanged)

1. **`check_all_entities_exists()` in `import_service.py`** - Still needed
2. **`add_unit_for_all_entities()` in `import_service.py`** - Still needed
3. **`import_stats()` in `import_service.py`** - Still needed
4. **All helpers in `helpers.py`** - Core validation, still needed

---

## Testing Impact

### New Unit Tests Required

#### 1. **`test_prepare_delta_handling.py`** (new file)
Tests for the new `prepare_delta_handling()` method in `import_service.py`.

**Test Scenarios** (comprehensive):

**Success Scenarios**:
- ✓ OLDER_REFERENCE: Reference exists 1+ hour BEFORE oldest import
- ✓ YOUNGER_REFERENCE: Reference exists AT or AFTER youngest import
- ✓ Multiple entities: Mix of OLDER_REFERENCE and YOUNGER_REFERENCE
- ✓ Multiple entities: Some with references, some without (partial valid)

**Error Scenarios**:
- ✗ t_youngest_import < t_youngest_db: "Importing values younger..."
- ✗ t_youngest_db <= t_oldest_import (no OLDER_REFERENCE): "completely newer than timerange..."
- ✗ No reference before youngest import (no YOUNGER_REFERENCE): "completely older than timerange..."
- ✗ No reference before or after youngest import: "completely overlaps timerange..."
- ✗ OLDER_REFERENCE is less than 1 hour away: Should reject

**Edge Cases**:
- Empty DataFrame (no entities)
- Single entity with single timestamp
- Multiple entities with non-overlapping time ranges
- Database has no statistics for an entity

#### 2. **`test_handle_dataframe_delta.py`** (new file)
Tests for the new `handle_dataframe_delta()` method.

**Tests**:
- ✓ Calls `helpers.are_columns_valid()` with delta validation
- ✓ Handles reference data structure with `DeltaReferenceType` enum
- ✓ Correctly routes to `convert_deltas_with_older_reference()` for OLDER_REFERENCE
- ✓ Correctly routes to `convert_deltas_with_younger_reference()` for YOUNGER_REFERENCE
- ✓ Works with partial references (some entities have refs, some don't)
- ✓ Builds metadata and returns stats dict in correct format

#### 3. **`test_handle_dataframe_no_delta.py`** (new file)
Tests for the new `handle_dataframe_no_delta()` method.

**Tests**:
- ✓ Calls `helpers.are_columns_valid()` with non-delta validation
- ✓ Mean/min/max statistics extraction
- ✓ Sum/state statistics extraction
- ✓ Unit column handling (TABLE and ENTITY modes)
- ✓ Error handling for invalid columns
- ✓ Builds metadata and returns stats dict in correct format

#### 4. **`test_prepare_data_to_import.py`** (modify existing)
Tests for the refactored `prepare_data_to_import()` and `prepare_json_data_to_import()`.

**Test Aspects**:
- ✓ Returns tuple of (df, timezone_id, datetime_format, unit_from_where, is_delta)
- ✓ Correctly detects delta mode (is_delta=True if delta column present)
- ✓ Correctly detects non-delta mode (is_delta=False if no delta column)
- ✓ Returns DataFrame with all rows intact
- ✓ Validates basic column structure (existence and naming)

### Existing Tests That Need Updates

#### 1. **`test_import_service_helper.py`**
- Rename tests or update to call:
  - `handle_dataframe_no_delta()` for non-delta tests
  - `handle_dataframe_delta()` for delta tests (with reference data)
- Remove tests checking for marker tuple `_DELTA_PROCESSING_NEEDED`
- Add test verifying new return tuple structure

#### 2. **`test_import_service_delta_helper.py`**
- Rename method: `test_convert_delta_dataframe_with_references()` → `test_handle_dataframe_delta()`
- Update method names in test cases:
  - `convert_deltas_case_1()` → `convert_deltas_with_older_reference()`
  - `convert_deltas_case_2()` → `convert_deltas_with_younger_reference()`
- Update reference data structure in test inputs/assertions (use `DeltaReferenceType` enum)

#### 3. **`test_delta_import.py`**
- Remove tests for `get_oldest_statistics_before()` and `get_youngest_statistic_after()` (methods removed)
- Keep/update tests for low-level helpers if they remain public

#### 4. **Integration Test: `test_integration_delta_imports.py`**
- Should work unchanged (tests service behavior, not internal structure)
- Validate after refactoring to ensure end-to-end behavior is preserved

---

## Benefits of Refactoring

1. **Separation of Concerns**
   - Data preparation is HA-independent and testable in isolation
   - Database queries are explicitly async in dedicated method
   - Delta conversion is pure calculation without HA dependency

2. **Improved Testability**
   - `prepare_data_to_import()` and `prepare_json_data_to_import()` can be tested without mocking Home Assistant
   - `handle_dataframe_delta()` and `handle_dataframe_no_delta()` can be tested independently
   - `prepare_delta_handling()` can be thoroughly tested with all error scenarios

3. **Clearer Code Flow**
   - No marker tuple hack: boolean `is_delta` flag is explicit
   - Service handlers have simple if/else logic
   - Database query orchestration is in dedicated method

4. **Better Error Messages**
   - All database validation errors include entity ID
   - Error messages reference database state (youngest/oldest timestamps)
   - Consistent error handling via `helpers.handle_error()`

5. **Maintainability**
   - Each method has single responsibility
   - Async/sync boundary is clear
   - New developers can understand flow without tracing through marker tuple logic

---

## Backward Compatibility

- **Breaking Changes**: None for external users (integration service interface unchanged)
- **Internal Breaking Changes**:
  - `prepare_data_to_import()` return value changes (from dict or tuple to always tuple)
  - `handle_dataframe()` removed (functionality split)
  - `convert_delta_dataframe_with_references()` renamed to `handle_dataframe_delta()` (can keep alias)

---

## Summary of File Changes

| File | Changes |
|------|---------|
| `helpers.py` | Add `DeltaReferenceType` enum with OLDER_REFERENCE and YOUNGER_REFERENCE values |
| `import_service_helper.py` | Split `handle_dataframe()` → `handle_dataframe_no_delta()`, update `prepare_data_to_import()`/`prepare_json_data_to_import()` to return tuple |
| `import_service_delta_helper.py` | Rename `convert_delta_dataframe_with_references()` → `handle_dataframe_delta()`, rename `convert_deltas_case_1()` → `convert_deltas_with_older_reference()`, rename `convert_deltas_case_2()` → `convert_deltas_with_younger_reference()` |
| `import_service.py` | Add `prepare_delta_handling()` async method, update service handlers to use `is_delta` boolean flag |
| `delta_import.py` | Remove `get_oldest_statistics_before()` and `get_youngest_statistic_after()`, add private helper methods for `prepare_delta_handling()` |
| Tests | Create 4 new test files (`test_prepare_delta_handling.py`, `test_handle_dataframe_delta.py`, `test_handle_dataframe_no_delta.py`, update `test_prepare_data_to_import.py`), update 4 existing test files |

