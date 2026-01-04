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
| Delta Marker | `("_DELTA_PROCESSING_NEEDED", ...)` tuple hack | Boolean flag in return value |
| Database Query Orchestration | In `import_service.py` (async) | New `prepare_delta_handling()` method |
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
                           "case": 1 or 2  # Which conversion case to use
                       } or None
                   }

    Returns:
        Dictionary mapping statistic_id to (metadata, statistics_list)

    Raises:
        HomeAssistantError: On validation errors or missing references
    """
    # Renamed from convert_delta_dataframe_with_references()
    # Same logic, but references dict structure may be adjusted
    # Groups by statistic_id
    # Calls convert_deltas_case_1() or convert_deltas_case_2()
    # Builds metadata and returns stats dict
```

**Implementation Notes**:
- Renamed from `convert_delta_dataframe_with_references()`
- Pure calculation: no HA dependency
- All references are pre-fetched and passed in
- Returns same stats dict format as `handle_dataframe_no_delta()`

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
    # Step 3: Return structured reference data with case indicators

    # This method replaces the get_oldest_statistics_before() call in service handlers
```

**Implementation Notes**:
- All database queries are async
- Comprehensive error checking for time range compatibility
- Includes entity ID in error messages for clarity
- Returns structured data ready for `handle_dataframe_delta()`
- Validates distance of references (1+ hour away for t_oldest_db_time_after_youngest_import, equal also possible for t_youngest_db_time_before_youngest_import)

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

### Modified: [`delta_import.py`](../custom_components/import_statistics/delta_import.py)

**Deprecated Methods** (still exist for backward compatibility, but may be removed):
- `get_oldest_statistics_before()`: Functionality split into `prepare_delta_handling()`

**New Methods** (extracted from current `get_oldest_statistics_before()` and refactored):
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
- May remain private (`_*` prefix) if only used by `prepare_delta_handling()`
- Can be kept public for testing purposes

---

## Data Structures

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
        "case": 1,  # or 2 for Case 2 (younger reference)
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
        "case": 1 or 2,
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

5. **Implementation Error (neither case found after validation)**
   - Error: `"Internal error: Neither Case 1 nor Case 2 reference found for '<entity_id>' despite validation passing"`

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
  │       ├─ helpers.get_delta_stat()
  │       ├─ convert_deltas_case_1()
  │       └─ convert_deltas_case_2()
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

## Dependency Analysis: Methods No Longer Needed

### Methods to Deprecate/Remove

1. **`get_oldest_statistics_before()` in `delta_import.py`**
   - **Current Role**: Orchestrates all database queries for delta processing
   - **New Role**: Replaced by `prepare_delta_handling()` (better structure and validation)
   - **Status**: Can be deprecated after refactor completes
   - **Removal Impact**: Only used in current `import_service.py` handler; no tests call it directly

2. **`get_youngest_statistic_after()` in `delta_import.py`**
   - **Current Role**: Queries for Case 2 reference (younger than import range)
   - **New Role**: Logic moved into `_get_reference_at_or_after_timestamp()` (more general)
   - **Status**: Can be deprecated after refactor completes
   - **Removal Impact**: Only called by `get_oldest_statistics_before()`; refactor eliminates need

3. **Current `convert_delta_dataframe_with_references()` in `import_service_delta_helper.py`**
   - **Current Role**: Processes delta DataFrame with pre-fetched references
   - **New Role**: Renamed to `handle_dataframe_delta()` (no logic change)
   - **Status**: Keep both names during transition; `convert_delta_dataframe_with_references()` becomes wrapper calling `handle_dataframe_delta()`
   - **Removal Impact**: Tests call it directly; tests should migrate to `handle_dataframe_delta()`

4. **`handle_dataframe()` in `import_service_helper.py`**
   - **Current Role**: Detects delta vs non-delta, dispatches to appropriate logic
   - **New Role**: Split into `handle_dataframe_no_delta()` and `handle_dataframe_delta()` (separation of concerns)
   - **Status**: Can be removed entirely after refactor
   - **Removal Impact**: Tests call it; tests should call split methods directly

### Methods to Keep (Unchanged)

1. **`check_all_entities_exists()` in `import_service.py`** - Still needed
2. **`add_unit_for_all_entities()` in `import_service.py`** - Still needed
3. **`import_stats()` in `import_service.py`** - Still needed
4. **All helpers in `helpers.py`** - Core validation, still needed
5. **`convert_deltas_case_1()` and `convert_deltas_case_2()` in `import_service_delta_helper.py`** - Still needed (pure calculations)

---

## Testing Impact

### New Unit Tests Required

#### 1. **`test_prepare_delta_handling.py`** (new file)
Tests for the new `prepare_delta_handling()` method in `import_service.py`.

**Test Scenarios** (comprehensive):

**Success Scenarios**:
- ✓ Case 1: Reference exists 1+ hour BEFORE oldest import
- ✓ Case 2: Reference exists AFTER youngest import or at the same time
- ✓ Multiple entities: Mix of Case 1 and Case 2 references
- ✓ Multiple entities: Some with references, some without (partial valid)

**Error Scenarios**:
- ✗ t_youngest_import < t_youngest_db: "Importing values younger..."
- ✗ t_youngest_db <= t_oldest_import (no Case 1 ref): "completely newer than timerange..."
- ✗ No reference before youngest import (no Case 2 ref): "completely older than timerange..."
- ✗ No reference before or after youngest import: "completely overlaps timerange..."
- ✗ Reference is exactly 0 hours away (not 1+ hour): Should reject
- ✗ Reference is 59 minutes away (not 1+ hour): Should reject

**Edge Cases**:
- Empty DataFrame (no entities)
- Single entity with single timestamp
- Multiple entities with non-overlapping time ranges
- Database has no statistics for an entity

#### 2. **`test_handle_dataframe_delta.py`** (new file, or merge with existing)
Tests for the new `handle_dataframe_delta()` method (renamed from `convert_delta_dataframe_with_references`).

**Can Reuse Existing Tests**:
- Current tests for `convert_delta_dataframe_with_references()` should migrate to `handle_dataframe_delta()`
- Update method name and reference structure in assertions

**New Tests** (specific to refactoring):
- ✓ Handles new reference data structure with "case" indicator
- ✓ Correctly detects Case 1 vs Case 2 from reference timestamp
- ✓ Works with partial references (some entities have refs, some don't)

#### 3. **`test_handle_dataframe_no_delta.py`** (new file)
Tests for the new `handle_dataframe_no_delta()` method (extracted from current `handle_dataframe`).

**Can Reuse Existing Tests**:
- Current non-delta tests from `test_import_service_helper.py` should work unchanged
- Just ensure they call `handle_dataframe_no_delta()` instead of `handle_dataframe()`

**Tests to Migrate**:
- Mean/min/max statistics extraction
- Sum/state statistics extraction
- Unit column handling (TABLE and ENTITY modes)
- Column validation
- Error handling for invalid columns

#### 4. **`test_prepare_data_to_import.py`** (modify existing)
Tests for the refactored `prepare_data_to_import()` and `prepare_json_data_to_import()`.

**New Test Aspects**:
- ✓ Returns tuple of (df, timezone_id, datetime_format, unit_from_where, is_delta)
- ✓ Correctly detects delta mode (is_delta=True if delta column present)
- ✓ Correctly detects non-delta mode (is_delta=False if no delta column)
- ✓ No HA dependency (can be called without hass instance)
- ✓ Returns DataFrame with all rows intact (no filtering by `handle_dataframe()`)

**Tests to Remove**:
- Tests that expected marker tuple return (those tested `_DELTA_PROCESSING_NEEDED`)

### Existing Tests That Need Updates

#### 1. **`test_import_service_helper.py`**
- Update tests calling `handle_dataframe()` to call either:
  - `handle_dataframe_no_delta()` for non-delta tests
  - `handle_dataframe_delta()` for delta tests (with reference data)
- Remove tests checking for marker tuple `_DELTA_PROCESSING_NEEDED`
- Add test verifying new return tuple structure

#### 2. **`test_import_service_delta_helper.py`**
- `convert_delta_dataframe_with_references()` → Migrate to test `handle_dataframe_delta()`
- Keep all Case 1 and Case 2 conversion tests (logic unchanged)
- Update reference data structure in test inputs/assertions

#### 3. **`test_delta_import.py`**
- Tests for `get_oldest_statistics_before()` and `get_youngest_statistic_after()` may be deprecated
- Move logic testing to new `test_prepare_delta_handling.py`
- Keep any tests for low-level helpers (if they're kept public)

#### 4. **Integration Test: `test_integration_delta_imports.py`**
- **Status**: Should still work unchanged (tests service behavior, not internal structure)
- **Validation**: Run after refactoring to ensure end-to-end behavior is preserved

### Tests No Longer Needed

1. **Tests that check for marker tuple**
   - Any test that verified `stats[0] == "_DELTA_PROCESSING_NEEDED"`
   - Any test that expected 6-element tuple in specific order

2. **Tests that tested marker tuple extraction logic**
   - Logic moved to `is_delta` boolean in new tuple structure

---

## Migration Path

### Phase 1: Create New Infrastructure
1. Create `handle_dataframe_no_delta()` in `import_service_helper.py`
2. Create `handle_dataframe_delta()` (renamed from `convert_delta_dataframe_with_references()`)
3. Create `prepare_delta_handling()` in `import_service.py`
4. Create new test files for validation

### Phase 2: Refactor Service Handlers
1. Update `handle_import_from_file_impl()` to use new `prepare_data_to_import()` return tuple
2. Update `handle_import_from_json_impl()` similarly
3. Switch from marker tuple detection to `is_delta` boolean check
4. Call new `prepare_delta_handling()` method

### Phase 3: Update Preparation Methods
1. Refactor `prepare_data_to_import()` to return tuple
2. Refactor `prepare_json_data_to_import()` to return tuple
3. Remove marker tuple construction
4. Remove HA dependency (hass parameter can be removed if not needed)

### Phase 4: Deprecate Old Methods
1. Keep `get_oldest_statistics_before()` as deprecated wrapper (for backward compatibility)
2. Keep old `handle_dataframe()` as deprecated wrapper if tests still need it
3. Update CHANGELOG with deprecation notice

### Phase 5: Cleanup (Optional, later)
1. Remove deprecated methods after sufficient time period
2. Remove old test cases
3. Update documentation

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
| `import_service_helper.py` | Split `handle_dataframe()` into `handle_dataframe_no_delta()` + new return tuple from `prepare_data_to_import()` |
| `import_service_delta_helper.py` | Rename `convert_delta_dataframe_with_references()` to `handle_dataframe_delta()` |
| `import_service.py` | Add new `prepare_delta_handling()` method, update service handlers with boolean flag logic |
| `delta_import.py` | Add helper methods for `prepare_delta_handling()` (may extract from existing logic) |
| Tests | Create 4 new test files, update 4 existing test files |

