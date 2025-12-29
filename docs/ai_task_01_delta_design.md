# Delta Column Support - High-Level Design

## Overview

This document describes the high-level design for supporting a `delta` column in counter imports as an alternative to `state` and `sum` columns. The delta column allows users to provide incremental changes, which the system will convert to absolute `state` and `sum` values using historical data from the Home Assistant long-term statistics database.

## Architectural Integration

### Data Flow

```
Import File (with delta column)
    ↓
Validate columns (delta cannot coexist with state/sum)
    ↓
Extract tImportOldest and tImportYoungest timestamps
    ↓
Query existing database for reference values
    ↓
Calculate absolute state and sum values
    ↓
Transform to standard format (state + sum)
    ↓
Call existing async_import_statistics / async_add_external_statistics
```

### Design Principles

1. **No Breaking Changes**: Existing import/export functionality remains unchanged
2. **Reuse Existing Pipeline**: Convert delta → (state, sum) before passing to existing import handlers
3. **Stateless Conversion**: Delta-to-absolute conversion happens in `prepare_data.py`, independent of Home Assistant
4. **Type Safety**: Support only counter statistics (has_sum=True, mean_type=NONE)
5. **Atomic Validation**: Either all deltas convert successfully or entire import fails

## Component Architecture

### 1. Constants (`const.py`)

Add support for delta column name:
```
ATTR_DELTA = "delta"  # Column name for delta values
```

### 2. Helpers Enhancement (`helpers.py`)

#### Modified Function: `are_columns_valid()`
- Enhanced to detect and validate delta column case
- No separate method needed - all validation in one function
- **Delta validation rules**:
  - If `delta` column exists: `sum`, `state`, `mean`, `min`, `max` must NOT exist
  - Unit column validation unchanged (required or from entity)
- **Non-delta cases**: Use existing validation logic
- Maintains 100% backward compatibility

#### New Function: `get_delta_stat()`
- **Purpose**: Extract delta value from row
- **Parameters**:
  - `row: pd.Series` - Current row
  - `timezone: zoneinfo.ZoneInfo` - User's timezone
  - `datetime_format: str` - Datetime format string
- **Logic**:
  - Validate timestamp is full hour
  - Validate delta is valid float
  - Return dict with `start` timestamp and `delta` value
- **Returns**: `dict` - Contains `start` (datetime with timezone) and `delta` (float)
- **Returns**: `{}` - If validation fails (silent failure pattern)

### 3. Database Query Functions (`__init__.py`)

#### Implementation Note: Recorder API Methods
The Home Assistant recorder provides specialized methods for querying statistics. See [`docs/ai_task_01_recorder_api_updated.md`](docs/ai_task_01_recorder_api_updated.md) for detailed API documentation.

**For Case 1 (Before Reference)**:
- Use `_statistics_at_time()` - private but direct method to get records before a timestamp
- Returns last known statistics earlier than the given timestamp
- Precise and efficient for finding reference data

**For Case 2 (After Reference)**:
- Use `get_last_statistics()` - public API to get recent statistics
- Returns last N statistics, can filter for records after timestamp
- More straightforward than Case 1 but requires post-filtering

**Note**: Phase 1 implements Case 1 only. See recorder API document for full details on both methods.

#### New Function: `get_oldest_statistic_before()`
- **Purpose**: Find oldest statistic record before a given timestamp
- **Parameters**:
  - `hass: HomeAssistant` - HA instance
  - `statistic_id: str` - The statistic to query
  - `before_timestamp: datetime` - Target timestamp (UTC)
- **Logic**:
  - Query extended period before target
  - Find record closest to (but older than) target
  - Ensure it's at least 1 hour older
- **Returns**: `dict | None` - Single statistic record or None

#### New Function: `get_youngest_statistic_after()`
- **Purpose**: Find youngest statistic record after a given timestamp
- **Parameters**:
  - `hass: HomeAssistant` - HA instance
  - `statistic_id: str` - The statistic to query
  - `after_timestamp: datetime` - Target timestamp (UTC)
- **Logic**:
  - Query extended period after target
  - Find record closest to (but newer than) target
  - Ensure it's at least 1 hour newer
- **Returns**: `dict | None` - Single statistic record or None

#### New Function: `get_current_entity_state()`
- **Purpose**: Get current state of an entity from Home Assistant
- **Parameters**:
  - `hass: HomeAssistant` - HA instance
  - `entity_id: str` - Entity to query
- **Logic**:
  - Uses `hass.states.get(entity_id)`
  - Extracts current state and timestamp
- **Returns**: `tuple | None` - (state_value: float, last_updated: datetime) or None
- **Raises**: `HomeAssistantError` if entity doesn't exist

### 4. Delta Conversion Logic - Strict Separation

Delta conversion uses a **batch query then batch calculate** pattern:
1. Read all statistics_ids from file
2. Query HA recorder **once** for all references
3. Perform all calculations with reference data (HA-independent)
4. Return results ready for import

#### HA-Dependent Batch Query (`__init__.py`)

**New Function: `get_oldest_statistics_before()`** (Batch Query - Single Call)
- **Purpose**: Query recorder once for all reference data before given timestamps
- **Uses**: `_statistics_at_time()` from recorder API (called once with all metadata_ids)
- **Parameters**:
  - `hass: HomeAssistant` - For database access
  - `references_needed: dict` - {statistic_id: before_timestamp}
  - Map of which statistic needs reference before which timestamp
- **Logic**:
  1. Extract all statistic_ids from references_needed
  2. Get metadata for all statistic_ids via `get_metadata()`
  3. Extract metadata_ids (set of all metadata IDs)
  4. Call `_statistics_at_time()` ONCE with all metadata_ids
  5. Parse result and match back to statistic_ids
  6. Filter to only records meeting "at least 1 hour before" requirement per statistic
  7. Return dict: {statistic_id: reference_record or None}
- **Returns**: `dict` - {statistic_id: {start, sum, state} or None}
- **Raises**: `HomeAssistantError` on metadata or database query failure
- **Note**: Single database query for all statistics - maximum efficiency

#### HA-Independent Calculations (`prepare_data.py`)

**New Function: `convert_deltas_case_1()`**
- **Purpose**: Transform delta rows to absolute sum/state (pure math)
- **Parameters**:
  - `delta_rows: list[dict]` - Sorted by timestamp ascending, with `start` and `delta` keys
  - `sum_reference: float` - Starting sum from database reference
  - `state_reference: float` - Starting state from database reference
- **Logic**:
  - Initialize accumulators: current_sum = sum_reference, current_state = state_reference
  - For each delta_row in sorted order:
    - current_sum += delta_row['delta']
    - current_state += delta_row['delta']
    - Append {start: timestamp, sum: current_sum, state: current_state}
  - Return list of converted rows
- **Returns**: `list[dict]` - [{start, sum, state}, ...] in ascending time order
- **Raises**: `HomeAssistantError` if validation fails
- **Note**: Pure calculation, no HA dependency, fully testable standalone

**New Function: `convert_delta_dataframe_with_references()`**
- **Purpose**: Convert all deltas using pre-fetched reference data (pure calculation)
- **Parameters**:
  - `df: pd.DataFrame` - Input with delta column
  - `references: dict` - {statistic_id: reference_record} from `get_oldest_statistics_before()`
  - `timezone_identifier: str` - User's timezone
  - `datetime_format: str` - Datetime format
  - `unit_from_where: UnitFrom` - Unit source
- **Logic**:
  1. Validate column structure (delta present, no sum/state)
  2. Group rows by statistic_id
  3. For each statistic_id:
     a. Get reference from pre-fetched references dict (already validated)
     b. Extract delta rows using `get_delta_stat()` for each row
     c. Get source and unit for this statistic
     d. Call `convert_deltas_case_1()` to accumulate deltas to absolute values
     e. Build metadata dict (mean_type=NONE, has_sum=True, unit, source, statistic_id)
     f. Append to stats dict
  4. Return stats dict: {statistic_id: (metadata, statistics_list), ...}
- **Returns**: `dict` - Ready for `async_import_statistics()` / `async_add_external_statistics()`
- **Raises**: `HomeAssistantError` on validation error
- **Note**: Pure calculation, no HA access (references pre-fetched)

#### Modified Function: `handle_dataframe()`
- Add check: if `delta` column detected:
  1. Extract all unique statistic_ids
  2. For each statistic_id, find oldest delta timestamp
  3. Build references_needed dict: {statistic_id: oldest_delta_timestamp}
  4. Call `get_oldest_statistics_before(hass, references_needed)` to fetch ALL references with single query
  5. Call `convert_delta_dataframe_with_references(df, references, ...)` for pure calculation
  6. Return calculated stats
- Otherwise: use existing non-delta logic
- Pass through `hass` parameter (required for delta case, optional for non-delta)
- Maintains full backward compatibility

### 5. Service Handler Enhancement (`__init__.py`)

#### Modified Function: `handle_import_from_file()`
- **Remains synchronous** (no async conversion needed)
- Add optional `hass: HomeAssistant | None = None` parameter passed to `prepare_data.prepare_data_to_import()`
- All existing logic remains unchanged
- Zero breaking changes

#### Modified Function: `handle_import_from_json()`
- **Remains synchronous** (no async conversion needed)
- Add optional `hass: HomeAssistant | None = None` parameter passed to `prepare_data.prepare_json_data_to_import()`
- All existing logic remains unchanged

#### Modified Function: `prepare_data_to_import()` signature
- Add `hass: HomeAssistant | None = None` parameter
- Pass through to `handle_dataframe()`
- Remains synchronous

#### Modified Function: `prepare_json_data_to_import()` signature
- Add `hass: HomeAssistant | None = None` parameter
- Pass through to `handle_dataframe()`
- Remains synchronous

#### Modified Function: `handle_dataframe()` signature
- Add `hass: HomeAssistant | None = None` parameter (optional for backward compatibility)
- Validate non-None when delta column detected
- Remains synchronous

## Column Validation Rules

### Existing Columns (Unchanged)
- Required: `statistic_id`, `start`
- Conditional: `unit` (required unless `unit_from_entity=True`)
- Either/Or: `(mean, min, max)` OR `(sum, state)` OR `(sum)` OR `(delta)`

### New Delta-Specific Rules
```
IF delta column exists THEN
  - sum column MUST NOT exist
  - state column MUST NOT exist
  - mean column MUST NOT exist
  - min column MUST NOT exist
  - max column MUST NOT exist
  - unit column validation unchanged (required or from entity)
  - Statistics type MUST be counter (has_sum=True, mean_type=NONE)
END IF
```

### Error Messages
- "Delta column cannot coexist with sum/state columns"
- "Delta column cannot be used with mean/min/max columns (counters only)"
- "Delta conversion requires at least one reference point in database or current entity state"
- "Delta reference timestamp is less than 1 hour apart"

## Unit of Measurement Handling

- Delta conversion does not affect unit handling
- Unit validation follows existing rules:
  - Internal statistics: unit from entity OR from table
  - External statistics: unit MUST come from table (unit_from_entity forbidden)
- Unit value remains constant across all delta-converted rows

## Type Safety

- All delta values validated as floats (using existing `is_valid_float()`)
- Sum and state calculated as floats
- All calculations use Python float arithmetic
- No type coercion or silent conversions

## Error Handling Strategy

### Validation Errors (Pre-Conversion)
- Invalid columns: raise `HomeAssistantError` immediately
- Invalid unit configuration: raise `HomeAssistantError` immediately
- Invalid delta float values: raise `HomeAssistantError` immediately

### Conversion Errors (Processing)
- No database reference found: raise `HomeAssistantError` immediately
- Database query fails: raise `HomeAssistantError` immediately
- Entity doesn't exist (Case 3): raise `HomeAssistantError` immediately

### Result
- All-or-nothing: entire import fails if any statistic_id cannot be converted
- Partial success not allowed: consistent with existing behavior

## Testing Strategy

### Unit Tests (helpers.py)
- `test_get_delta_stat()` - Delta value extraction
- `test_are_columns_valid_delta()` - Column validation rules
- Various error cases for delta column conflicts

### Unit Tests (prepare_data.py)
- `test_convert_deltas_to_absolute_values_case_1()` - Older reference
- `test_convert_deltas_to_absolute_values_case_2()` - Younger reference
- `test_convert_deltas_to_absolute_values_case_3()` - Internal current state
- `test_convert_deltas_to_absolute_values_case_error()` - No reference available
- `test_process_delta_dataframe()` - Full dataframe conversion
- `test_process_delta_dataframe_multiple_statistics()` - Mixed statistics
- `test_process_delta_dataframe_unit_validation()` - External statistics unit rules
- Edge cases: single row, large deltas, negative deltas, zero deltas

### Integration Tests (`test_export_integration.py` style)
- Mock Home Assistant with existing database records (Case 1)
- Mock Home Assistant with future database records (Case 2)
- Mock Home Assistant with current entity state (Case 3)
- Verify final imported statistics match expected sum/state values
- Verify metadata correctly set (mean_type=NONE, has_sum=True)

### Manual Testing (User Validation)
- Real counter with 1+ years of history (Case 1)
- Counter with future planned maintenance data (Case 2)
- New internal counter without history (Case 3)
- Verify spike-free transitions between imported and existing data

## Backward Compatibility

- All changes are additive (new columns, new functions)
- Existing imports without delta column unaffected
- Existing exports unaffected
- Service signatures maintained (new parameter optional)
- Can incrementally add delta support without affecting other features

## Out of Scope (Phase 1)

- Export with delta column (export always produces sum/state)
- Delta validation beyond float conversion
- Complex time-series analysis or interpolation
- Handling for gaps in existing database records
- Performance optimization for large datasets
