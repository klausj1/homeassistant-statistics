# Delta Column Support - Implementation Plan (Phase 1)

## Phase 1: Support Case 1 (Older Database Reference)

### Overview
Phase 1 implements Case 1 only: "if a value in the HA long term statistics database exists, which is at least 1 hour older than tImportOldest". This is the primary use case where users import historical delta data for counters that already have a long history.

**Architecture**: Strict separation of concerns with single batch query optimization:
- HA-independent calculation layer in `prepare_data.py` (fully testable without mocks)
- HA-dependent batch query layer in `__init__.py` (single efficient database query)
- Enhanced column validation in `helpers.py` (supports delta detection)

**Success Criteria**: 
- Unit tests: 100% pass (calculation logic without HA mocks)
- Integration tests: 100% pass (batch query with mocked recorder)
- Manual testing: User confirms spike-free data alignment

---

## Implementation Breakdown

### 1. Core Helper Functions (helpers.py)

#### Task 1.1: Add `get_delta_stat()` function
**File**: [`custom_components/import_statistics/helpers.py`](custom_components/import_statistics/helpers.py)
**Dependencies**: None (existing helpers)
**Testing**: `tests/test_get_delta_stat.py`

```
Function: get_delta_stat(row: pd.Series, timezone: zoneinfo.ZoneInfo, datetime_format: str) -> dict
- Validate timestamp is full hour using existing is_full_hour()
- Validate delta is valid float using existing is_valid_float()
- Return dict with 'start' (datetime with timezone) and 'delta' (float)
- Return empty dict {} on validation failure (silent failure pattern)
```

**Test Cases**:
- Valid delta row (positive, negative, zero values)
- Invalid timestamp (not full hour)
- Invalid delta (non-numeric)
- Missing delta column
- Decimal separator handling (comma vs dot)

---

#### Task 1.2: Add enhanced `are_columns_valid()` function
**File**: [`custom_components/import_statistics/helpers.py`](custom_components/import_statistics/helpers.py)
**Dependencies**: `handle_error()`, `get_source()`
**Testing**: Modify `tests/test_are_columns_valid.py`

```
Function: are_columns_valid(df: pd.DataFrame, unit_from_where: UnitFrom) -> bool
- At start: detect if 'delta' column exists in df.columns
- If delta exists:
  a. Check that delta column is present
  b. Ensure sum column does NOT exist (raise error if found)
  c. Ensure state column does NOT exist (raise error if found)
  d. Ensure mean/min/max columns do NOT exist (raise error if any found)
  e. Validate unit column per existing rules (or unit_from_entity behavior)
  f. Return True if all validations pass
- If delta does not exist:
  a. Use existing validation logic unchanged
  b. Return result
- Raises HomeAssistantError on validation failure
```

**Test Cases**:
- All existing test cases should still pass (100% backward compatibility)
- New test: valid delta-only CSV (with unit column)
- New test: valid delta-only CSV (without unit, unit_from_entity=True)
- New test: error - delta + sum columns
- New test: error - delta + mean columns
- New test: error - delta + state columns

---

### 2. HA-Dependent Batch Query Function (__init__.py)

#### Task 2.1: Add `get_oldest_statistics_before()` function
**File**: [`custom_components/import_statistics/__init__.py`](custom_components/import_statistics/__init__.py)
**Dependencies**: Recorder API - See [`docs/ai_task_01_recorder_api_updated.md`](docs/ai_task_01_recorder_api_updated.md)
**Testing**: `tests/test_get_oldest_statistics_before.py`

**API Used**: `_statistics_at_time()` and `get_metadata()` from recorder

```
Function: get_oldest_statistics_before(
    hass: HomeAssistant,
    references_needed: dict  # {statistic_id: before_timestamp}
) -> dict  # {statistic_id: {start, sum, state} or None}

Algorithm:
1. Extract all unique statistic_ids from references_needed keys
2. For each statistic_id:
   a. Call get_metadata(statistic_id) to get metadata_id
   b. Collect all metadata_ids in a set
3. Call _statistics_at_time() ONCE with all metadata_ids
   - Queries recorder for last known statistics before each timestamp
   - Returns records where start < timestamp
4. Parse result and match back to statistic_ids:
   a. For each statistic_id, extract the record from batch result
   b. Validate record exists and is at least 1 hour before target timestamp
   c. If valid: include in results, else: set to None
5. Return dict: {statistic_id: {start, sum, state} or None}
6. Log debug: query details, count of found vs missing references
```

**Test Cases** (with mocked recorder and _statistics_at_time):
- Single statistic - record exactly 1 hour before target → return it
- Single statistic - record exactly 2 hours before target → return it
- Single statistic - no record available → return None
- Single statistic - record less than 1 hour before → return None
- Multiple statistics - all have records → return all
- Multiple statistics - some missing → return partial dict
- Metadata lookup failure → raise HomeAssistantError
- Database query failure → raise HomeAssistantError

---

### 3. HA-Independent Calculation Logic (prepare_data.py)

#### Task 3.1: Add `convert_deltas_case_1()` function
**File**: [`custom_components/import_statistics/prepare_data.py`](custom_components/import_statistics/prepare_data.py)
**Dependencies**: None (pure calculation)
**Testing**: `tests/test_convert_deltas_case_1.py`

```
Function: convert_deltas_case_1(
    delta_rows: list[dict],  # [{start: datetime, delta: float}, ...]
    sum_oldest: float,       # Reference sum value
    state_oldest: float      # Reference state value
) -> list[dict]

Algorithm:
1. Validate delta_rows is sorted by start timestamp (ascending)
   - If not sorted: raise HomeAssistantError
2. Initialize accumulators: current_sum = sum_oldest, current_state = state_oldest
3. For each delta_row in delta_rows (in order):
   a. current_sum += delta_row['delta']
   b. current_state += delta_row['delta']
   c. Append {start: delta_row['start'], sum: current_sum, state: current_state}
4. Return list of converted rows in ascending time order
5. Log debug: conversion progress (starting values, final values, row count)

- Validate all deltas are numeric (should already be validated by get_delta_stat)
```

**Test Cases**:
- Single delta row
- Multiple delta rows (ascending order)
- Unsorted rows → raise error
- Positive deltas only
- Negative deltas only (decreasing sum/state)
- Zero delta
- Large delta values
- Mixed positive/negative deltas
- Verify accumulation order correctness

---

#### Task 3.2: Add `convert_delta_dataframe_with_references()` function
**File**: [`custom_components/import_statistics/prepare_data.py`](custom_components/import_statistics/prepare_data.py)
**Dependencies**: `convert_deltas_case_1()`, `get_delta_stat()`, existing helpers
**Testing**: `tests/test_convert_delta_dataframe_with_references.py`

```
Function: convert_delta_dataframe_with_references(
    df: pd.DataFrame,                                    # Input with delta column
    references: dict,                                    # {statistic_id: {start, sum, state} or None}
    timezone_identifier: str,
    datetime_format: str,
    unit_from_where: UnitFrom
) -> dict  # {statistic_id: (metadata, statistics_list), ...}

Algorithm:
1. Validate column structure:
   a. Check delta column exists (should already be done)
   b. Ensure sum column does NOT exist
   c. Ensure state column does NOT exist
   d. Ensure mean/min/max columns do NOT exist
   e. Raise HomeAssistantError if validation fails
2. Group rows by statistic_id
3. For each statistic_id group:
   a. Get reference record from references dict
   b. Validate reference is not None:
      - If None: raise HomeAssistantError with statistic_id
   c. Extract sum_oldest and state_oldest from reference record
   d. Extract delta rows using get_delta_stat() for each row:
      - Filter out empty dicts (silent failure rows)
      - Collect valid rows
   e. Get source using get_source(statistic_id)
   f. Get unit using add_unit_to_dataframe() (existing function)
   g. Call convert_deltas_case_1() to accumulate deltas
   h. Build metadata dict:
      {
        "mean_type": StatisticMeanType.NONE,
        "has_sum": True,
        "source": source,
        "statistic_id": statistic_id,
        "name": None,
        "unit_class": None,
        "unit_of_measurement": unit
      }
   i. Append to stats dict: stats[statistic_id] = (metadata, converted_statistics_list)
4. Return stats dict
5. Log info: processing delta dataframe, count of statistics
6. Log debug: per-statistic conversion details

- No HA access: all references pre-fetched
- Pure calculation: fully testable without mocks
```

**Test Cases**:
- Single statistic with multiple deltas
- Multiple statistics in one dataframe
- Mixed internal and external statistics
- Invalid delta value (silent failure) - filtered out
- Unit from table
- Unit from entity
- Reference validation failure (None) → raise error
- Column validation failure → raise error

---

#### Task 3.3: Modify `handle_dataframe()` function signature and logic
**File**: [`custom_components/import_statistics/prepare_data.py`](custom_components/import_statistics/prepare_data.py)
**Dependencies**: `convert_delta_dataframe_with_references()`, `get_oldest_statistics_before()` from `__init__.py`
**Testing**: Modify `tests/test_handle_dataframe.py`

```
Async Function: handle_dataframe(
    df: pd.DataFrame,
    timezone_identifier: str,
    datetime_format: str,
    unit_from_where: UnitFrom,
    hass: HomeAssistant | None = None  # New parameter
) -> dict

Algorithm:
1. Check if 'delta' column exists in df.columns
2. If delta exists:
   a. Validate hass is not None:
      - If None: raise HomeAssistantError "hass required for delta processing"
   b. Extract all unique statistic_ids from df
   c. For each statistic_id, find oldest delta timestamp:
      - Get min(df[df['statistic_id'] == id]['start'])
   d. Build references_needed dict: {statistic_id: oldest_timestamp}
   e. Call get_oldest_statistics_before(hass, references_needed) (await)
   f. Call convert_delta_dataframe_with_references(df, references, ...) (pure function)
   g. Return result
3. If delta does not exist:
   a. Use existing logic unchanged (non-delta path)
   b. Return result

- Maintains 100% backward compatibility
- hass parameter optional but required if delta detected
- All existing tests pass without modification
- New path only taken when delta column detected
```

**Test Cases**:
- All existing test_handle_dataframe.py tests should pass unchanged
- New test: delta column detected - calls batch query and conversion
- New test: delta column with hass=None → raise error
- New test: verify references_needed dict construction
- New test: verify conversion result structure

---

#### Task 3.4: Modify `prepare_data_to_import()` function signature
**File**: [`custom_components/import_statistics/prepare_data.py`](custom_components/import_statistics/prepare_data.py)
**Dependencies**: Modified `handle_dataframe()`
**Testing**: Existing `tests/test_prepare_data_to_import.py` (no changes needed)

```
Async Function: prepare_data_to_import(
    file_path: str,
    call: ServiceCall,
    hass: HomeAssistant | None = None  # New optional parameter
) -> tuple(dict, UnitFrom)

- Add hass parameter with default None
- Pass hass through to handle_dataframe() call
- All existing logic unchanged
```

**Test Cases**:
- All existing tests should pass
- New test: with hass parameter
- New test: without hass parameter (backward compatibility)

---

#### Task 3.5: Modify `prepare_json_data_to_import()` function signature
**File**: [`custom_components/import_statistics/prepare_data.py`](custom_components/import_statistics/prepare_data.py)
**Dependencies**: Modified `handle_dataframe()`
**Testing**: Existing tests (no changes needed)

```
Async Function: prepare_json_data_to_import(
    call: ServiceCall,
    hass: HomeAssistant | None = None  # New optional parameter
) -> tuple(dict, UnitFrom)

- Add hass parameter with default None
- Pass hass through to handle_dataframe() call
- All existing logic unchanged
- Note: JSON import with delta is Phase 2
```

---

### 4. Service Handler Updates (__init__.py)

#### Task 4.1: Modify `handle_import_from_file()` service handler
**File**: [`custom_components/import_statistics/__init__.py`](custom_components/import_statistics/__init__.py)
**Dependencies**: Modified `prepare_data_to_import()`
**Testing**: Existing service tests (integration tests)

```
Async Function: handle_import_from_file(call: ServiceCall) -> None
- Change from sync to async
- Get file_path parameter from call
- Get hass from closure context (already available)
- Call prepare_data_to_import(file_path, call, hass) (await, with hass param)
- Call import_stats() with results (unchanged)
- All existing logic unchanged
```

**Test Cases**:
- All existing tests should pass
- New test: service call with delta file

---

#### Task 4.2: Modify `handle_import_from_json()` service handler
**File**: [`custom_components/import_statistics/__init__.py`](custom_components/import_statistics/__init__.py)
**Dependencies**: Modified `prepare_json_data_to_import()`
**Testing**: Existing service tests

```
Async Function: handle_import_from_json(call: ServiceCall) -> None
- Change from sync to async
- Get hass from closure context (already available)
- Call prepare_json_data_to_import(call, hass) (await, with hass param)
- Call import_stats() with results (unchanged)
- All existing logic unchanged
```

---

#### Task 4.3: Modify `setup()` function to register async handlers
**File**: [`custom_components/import_statistics/__init__.py`](custom_components/import_statistics/__init__.py)
**Dependencies**: All handler functions
**Testing**: Integration tests

```
Function: setup(hass: HomeAssistant, config: ConfigType) -> bool
- Update handle_import_from_file to be async (already modified in 4.1)
- Update handle_import_from_json to be async (already modified in 4.2)
- Register both as async handlers with hass.services.register()
  - Note: hass.services.register() supports async functions
- All other logic unchanged
```

---

### 5. Const Additions (const.py)

#### Task 5.1: Add delta column constant
**File**: [`custom_components/import_statistics/const.py`](custom_components/import_statistics/const.py)

```
Add:
ATTR_DELTA = "delta"
```

---

## Test Files to Create

### Unit Tests for Phase 1 (Pure Calculation - No Mocks)

1. **`tests/test_get_delta_stat.py`**
   - Test delta value extraction from rows
   - Test validation of full hours
   - Test invalid deltas
   - No Home Assistant mocks needed

2. **`tests/test_are_columns_valid.py`** (modify existing)
   - Add test: delta column detection triggers delta validation
   - All existing tests should pass

3. **`tests/test_convert_deltas_case_1.py`**
   - Test single delta conversion
   - Test multiple delta conversion (ordering)
   - Test unsorted rows → raise error
   - Test positive/negative/zero deltas
   - Test accumulation correctness
   - Test with large values
   - No Home Assistant mocks needed (pure math)

4. **`tests/test_convert_delta_dataframe_with_references.py`**
   - Test single statistic delta frame
   - Test multiple statistics
   - Test column validation triggered
   - Test unit extraction
   - Test reference validation (None → error)
   - No Home Assistant mocks needed (references pre-fetched)

### Unit Tests for Phase 1 (With Recorder Mocks)

5. **`tests/test_get_oldest_statistics_before.py`**
   - Mock recorder API and _statistics_at_time()
   - Test single statistic - record found
   - Test single statistic - no record
   - Test single statistic - record too new (< 1 hour before)
   - Test multiple statistics - mixed results
   - Test metadata lookup failure
   - Test database query failure

### Modified Test Files

6. **`tests/test_handle_dataframe.py`** (modify existing)
   - Add test: delta column detected → calls batch query and conversion
   - Add test: delta column with hass=None → raise error
   - All existing tests should pass unchanged

7. **`tests/test_prepare_data_to_import.py`** (modify existing)
   - Add test: with hass parameter
   - Verify existing tests still pass

---

### Integration Tests

8. **`tests/test_import_service_with_delta.py`** (new)
   - Create test fixture with delta CSV file
   - Mock Home Assistant with existing counter history
   - Mock recorder batch query response
   - Call import_from_file service
   - Verify final imported statistics match expected sum/state values
   - Verify no spike at import boundary
   - Verify metadata correct (mean_type=NONE, has_sum=True)

---

## Test Data Files

Create test CSV files in `tests/testfiles/`:

1. **`delta_single_statistic.csv`**
   ```
   statistic_id	start	unit	delta
   counter.energy	01.01.2022 00:00	kWh	10.5
   counter.energy	01.01.2022 01:00	kWh	5.2
   counter.energy	01.01.2022 02:00	kWh	3.1
   ```

2. **`delta_multiple_statistics.csv`**
   ```
   statistic_id	start	unit	delta
   counter.energy	01.01.2022 00:00	kWh	10.5
   counter.energy	01.01.2022 01:00	kWh	5.2
   counter.gas	01.01.2022 00:00	m³	1.5
   counter.gas	01.01.2022 01:00	m³	2.1
   ```

3. **`delta_external_statistic.csv`**
   ```
   statistic_id	start	unit	delta
   custom:external_counter	01.01.2022 00:00	kWh	10.5
   custom:external_counter	01.01.2022 01:00	kWh	5.2
   ```

4. **`delta_negative_values.csv`**
   ```
   statistic_id	start	unit	delta
   counter.energy	01.01.2022 00:00	kWh	-10.5
   counter.energy	01.01.2022 01:00	kWh	-5.2
   counter.energy	01.01.2022 02:00	kWh	3.1
   ```

---

## Execution Order (Recommended)

### Phase 1 Execution Steps

1. **Task 5.1** - Add ATTR_DELTA constant (no dependencies)
2. **Task 1.1** - Implement `get_delta_stat()` in helpers.py (no dependencies)
3. **Task 1.2** - Implement enhanced `are_columns_valid()` in helpers.py (depends on 1.1)
4. **Task 2.1** - Implement `get_oldest_statistics_before()` in __init__.py (recorder API)
5. **Task 3.1** - Implement `convert_deltas_case_1()` in prepare_data.py (pure calculation)
6. **Task 3.2** - Implement `convert_delta_dataframe_with_references()` in prepare_data.py (depends on 3.1)
7. **Task 3.3** - Modify `handle_dataframe()` in prepare_data.py (depends on 2.1, 3.2)
8. **Task 3.4** - Modify `prepare_data_to_import()` in prepare_data.py (depends on 3.3)
9. **Task 3.5** - Modify `prepare_json_data_to_import()` in prepare_data.py (depends on 3.3)
10. **Task 4.1** - Modify `handle_import_from_file()` in __init__.py (depends on 3.4)
11. **Task 4.2** - Modify `handle_import_from_json()` in __init__.py (depends on 3.5)
12. **Task 4.3** - Modify `setup()` in __init__.py (depends on 4.1, 4.2)
13. **Create Unit Tests** - Tests 1-7 (parallel with code implementation)
14. **Create Integration Test** - Test 8 (after all code complete)
15. **Run Unit Tests** - Verify 100% pass
16. **Run Integration Tests** - Verify delta import works end-to-end
17. **Run Existing Test Suite** - Verify backward compatibility
18. **Manual Testing** - With real counter data

---

## Phase 1 Success Criteria

✅ **Code Implementation**:
- All 9 tasks completed (1 const, 2 helpers, 1 batch query, 2 calculation, 4 modifications)
- Code follows existing patterns and architecture
- Backward compatibility: all existing code paths unchanged

✅ **Unit Tests**:
- All 6 test files created (1-6, with modifications to existing files)
- 100% pass rate
- Pure calculation tests with no mocks (convert_deltas_case_1, convert_delta_dataframe_with_references)
- Batch query tests with recorder mocks (get_oldest_statistics_before)

✅ **Integration Tests**:
- test_import_service_with_delta.py passes
- Service call with delta file works end-to-end
- Metadata correct, spike-free data alignment

✅ **Backward Compatibility**:
- All existing tests pass unchanged
- No changes to existing function behavior (hass parameter optional with default None)
- Non-delta paths unaffected

✅ **Manual Testing**:
- User imports delta CSV with real counter history
- Final values align with expectations
- No spikes at import boundary

---

## Phase 2 (Future)

After Phase 1 validation:
- Implement Case 2 (younger reference with state override)
- Implement Case 3 (internal entity state as reference)
- Implement Case 4 (error handling and fallbacks)
- Expand JSON import support for delta
- Performance optimization

---

## Phase 3 (Future)

- Enhanced testing with edge cases
- Documentation updates
- User guide for delta imports
- Performance benchmarking
