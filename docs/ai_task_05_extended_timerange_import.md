# Extended Timerange Import Design

## Overview

This document describes the changes required to allow importing statistics with time ranges that extend completely outside the database ranges, and to allow importing timestamps in the future (within constraints).

**Current Behavior**:
- Error when `t_newest_import > t_newest_db`: "Importing values newer than the newest value in the database is not possible"
- Error when import range is completely newer than DB range: "imported timerange is completely newer than timerange in DB"
- Error when import range is completely older than DB range: "imported timerange is completely older than timerange in DB"

**New Behavior**:
1. Allow import ranges completely outside DB ranges by using the nearest DB value as reference
2. Allow future imports with constraint: `t_newest_import` must be ≤ 1 hour before current time
3. Reference timestamp adjustment: keep semantics of "oldest import - 1" or "newest import" from current logic

---

## Validation Rules After Changes

### Rule 1: Future Timestamp Constraint
**Validation Location**: [`_process_delta_references_for_statistic()`](../custom_components/import_statistics/import_service.py) or new helper

**Current Time Check**:
```
current_hour = floor(now to full hour)
allowed_newest_import = current_hour - 1 hour

if t_newest_import > allowed_newest_import:
    ERROR: "Imported values must not be newer than 1 hour before the current hour"
           (e.g., if now=04:30, allowed=03:00; if now=04:00, allowed=03:00; if now=03:59, allowed=02:00)
```

**Implementation Details**:
- Current time should be obtained via `dt.datetime.now(tz=dt.UTC)` or Home Assistant's time utility
- "Current hour" = `now.replace(minute=0, second=0, microsecond=0)`
- Allowed newest = `current_hour - timedelta(hours=1)`
- Only applies to delta imports (affected statistic_id must have delta column)
- Non-delta imports have no future timestamp restrictions

### Rule 2: Nearest Database Value as Reference
**Old Logic** (Lines 60-100 in import_service.py):
```
1. If t_newest_import > t_newest_db: ERROR "Importing values newer..."
2. If t_oldest_reference found AND t_newest_db <= t_oldest_import: ERROR "completely newer..."
3. If no newer_reference found: ERROR "completely older..."
```

**New Logic**:
```
1. (UNCHANGED) Fetch t_newest_db - if None, ERROR "No statistics found in database"
2. (NEW) If t_newest_import > t_newest_db:
   - Check future constraint (Rule 1)
   - Use t_newest_db as NEWER_REFERENCE (instead of error)
   - Reference timestamp = t_newest_import (or t_newest_import itself per current semantics)

3. (UNCHANGED) Try to find OLDER_REFERENCE:
   - Fetch t_oldest_reference (value before t_oldest_import, at least 1 hour away)
   - If found and t_newest_db > t_oldest_import: SUCCESS, use OLDER_REFERENCE

4. (MODIFIED) If no OLDER_REFERENCE found:
   - (NEW) If t_newest_db <= t_oldest_import:
     - Check if t_newest_db is older than t_oldest_import
     - Use t_newest_db as "best available reference" for OLDER_REFERENCE
     - Reference timestamp = t_oldest_import - 1 hour (maintain semantics)
     - Log warning: "Using newest DB value as older reference (DB range is completely before import range)"
   - (UNCHANGED) Else try NEWER_REFERENCE path

5. (MODIFIED) If no NEWER_REFERENCE found via _get_reference_at_or_after_timestamp:
   - (NEW) Use t_newest_db as NEWER_REFERENCE (no existing value after newest import)
   - Log warning: "Using newest DB value as newer reference (DB range is completely before import range)"
```

---

## Detailed Component Changes

### 1. [`import_service.py`](../custom_components/import_statistics/import_service.py)

#### Function: `_process_delta_references_for_statistic()` (async)

**Changes**:
1. Add parameter: `allow_future_timestamps: bool = True`
   - Can be configured per integration or as service parameter
   - Default: True for compatibility

2. Add future timestamp validation:
```python
# After fetching t_newest_db_record, before the first check:
if allow_future_timestamps:
    current_hour = dt.datetime.now(tz=dt.UTC).replace(minute=0, second=0, microsecond=0)
    allowed_newest = current_hour - dt.timedelta(hours=1)
    if t_newest_import > allowed_newest:
        msg = (
            f"Entity '{statistic_id}': Imported values must not be newer than 1 hour "
            f"before the current hour (current: {current_hour}, allowed until: {allowed_newest}, "
            f"import has: {t_newest_import})"
        )
        return None, msg
```

3. Modify the "newer than newest_db" check (currently line 60):
```python
# OLD:
# if t_newest_import > t_newest_db:
#     msg = f"Entity '{statistic_id}': Importing values newer than the newest value in the database ({t_newest_db}) is not possible"
#     return None, msg

# NEW:
if t_newest_import > t_newest_db:
    # Future constraint already validated above
    _LOGGER.warning(
        "Entity '%s': Using newest DB value (%s) as reference for imports newer than DB (%s)",
        statistic_id, t_newest_db, t_newest_import
    )
    return {
        "reference": t_newest_db_record,
        "ref_type": DeltaReferenceType.NEWER_REFERENCE,
    }, None
```

4. Modify "completely newer than DB" check (currently lines 73-76):
```python
# OLD:
# if t_oldest_reference is not None:
#     if t_newest_db <= t_oldest_import:
#         msg = f"Entity '{statistic_id}': imported timerange is completely newer than timerange in DB (database newest: {t_newest_db})"
#         return None, msg

# NEW:
if t_oldest_reference is not None:
    # (Keep existing distance check)
    ref_distance = t_oldest_import - t_oldest_reference["start"]
    if ref_distance >= dt.timedelta(hours=1):
        return {
            "reference": t_oldest_reference,
            "ref_type": DeltaReferenceType.OLDER_REFERENCE,
        }, None
```

5. Add new fallback for completely older case (after line 100, in the NEWER_REFERENCE section):
```python
# NEW: If no newer reference found in DB, use newest_db as fallback
if t_newest_reference is None:
    _LOGGER.warning(
        "Entity '%s': Using newest DB value (%s) as reference (import range completely after DB range)",
        statistic_id, t_newest_db
    )
    return {
        "reference": t_newest_db_record,
        "ref_type": DeltaReferenceType.OLDER_REFERENCE,  # Use as if it's an older reference
    }, None
```

6. Modify "completely older than DB" check (after _get_reference_before_timestamp call for new check):
```python
# After: t_newest_reference = await _get_reference_before_timestamp(...)
# Currently it errors if t_newest_reference is None
# NEW FLOW:
if t_newest_reference is None:
    # Import range is completely before the DB range
    # Use t_newest_db_record as OLDER_REFERENCE (best available)
    _LOGGER.warning(
        "Entity '%s': Using newest DB value (%s) as older reference (import range completely before DB range)",
        statistic_id, t_newest_db
    )
    return {
        "reference": t_newest_db_record,
        "ref_type": DeltaReferenceType.OLDER_REFERENCE,
    }, None
```

#### New Helper Function: `_get_allowed_newest_import_time()` (sync)
```python
def _get_allowed_newest_import_time() -> dt.datetime:
    """
    Calculate the newest allowed import timestamp (1 hour before current full hour).

    Examples:
        - Current: 04:30 → Allowed: 03:00
        - Current: 04:00 → Allowed: 03:00
        - Current: 03:59 → Allowed: 02:00

    Returns:
        datetime: The newest allowed import timestamp in UTC
    """
    current_hour = dt.datetime.now(tz=dt.UTC).replace(minute=0, second=0, microsecond=0)
    return current_hour - dt.timedelta(hours=1)
```

---

### 2. [`import_service_delta_helper.py`](../custom_components/import_statistics/import_service_delta_helper.py)

**Changes**: Minimal - the delta conversion logic in `handle_dataframe_delta()` doesn't change significantly.

However, update comment documentation to reflect that references can be:
- Exactly at the import boundary (not just 1+ hour away)
- From a DB range that doesn't overlap with import range

---

### 3. [`import_service_helper.py`](../custom_components/import_statistics/import_service_helper.py)

**Changes**: Add new parameter documentation to reflect that future timestamps are now allowed (with constraint).

Example in docstrings:
```python
"""
Prepare data from CSV/TSV file for import.

Note: For delta imports, imported timestamps must be ≤ 1 hour before the current hour.
      Non-delta imports have no timestamp restrictions.

Returns:
    Tuple of (df, timezone_identifier, datetime_format, unit_from_entity, is_delta)
...
"""
```

---

### 4. [`const.py`](../custom_components/import_statistics/const.py)

**New Constants**:
```python
# Service parameter: allow future imports (with 1-hour constraint)
ATTR_ALLOW_FUTURE_IMPORTS = "allow_future_imports"  # Default: True

# Maximum age of imported data: must be at least 1 hour before current time
MAX_IMPORT_FUTURE_OFFSET_HOURS = 1
```

---

### 5. Service Handler Interface Changes

#### Service: `import_from_file`
**New Optional Parameter** (optional):
- `allow_future_imports` (boolean, default: True)
  - If False, reverts to old behavior (error on future timestamps)
  - Allows opt-out for integrations that prefer strict old behavior

#### Service: `import_from_json`
**New Optional Parameter** (optional):
- `allow_future_imports` (boolean, default: True)

#### Service: `export_statistics`
**No changes** - export is unaffected.

---

## Error Message Changes

### Error Messages That Disappear
1. ~~"Importing values newer than the newest value in the database is not possible"~~ → Allowed with constraint
2. ~~"imported timerange is completely newer than timerange in DB"~~ → Uses nearest DB value as reference
3. ~~"imported timerange is completely older than timerange in DB"~~ → Uses nearest DB value as reference

### New Error Messages
1. "Imported values must not be newer than 1 hour before the current hour"
   - Format: `"Entity '<entity_id>': Imported values must not be newer than 1 hour before the current hour (current: <time>, allowed until: <time>, import has: <time>)"`

### Updated Error Messages (unchanged but more accurate now)
1. "No statistics found in database for this entity" - Still applies, no DB fallback available

---

## Reference Type Semantics After Changes

The `DeltaReferenceType` enum remains unchanged (OLDER_REFERENCE, NEWER_REFERENCE), but semantics shift:

| Scenario | Reference Type | Reference Used | Notes |
|----------|----------------|-----------------|-------|
| Import range 1h before DB data | OLDER_REFERENCE | Value 1h+ before oldest import | (unchanged) |
| Import range within DB range | OLDER_REFERENCE | Value 1h+ before oldest import | (unchanged) |
| Import range extends after newest DB | NEWER_REFERENCE | Value at/after newest import | (unchanged) |
| Import range completely after DB | OLDER_REFERENCE | Newest DB value | **NEW**: treated as older for semantics |
| Import range completely before DB | OLDER_REFERENCE | Newest DB value | **NEW**: fallback reference |

---

## Testing Strategy

### Unit Tests Required

#### 1. Future Timestamp Validation Tests
**File**: `tests/unit_tests/test_process_delta_references_for_statistic.py`

**New Test Class**: `TestFutureTimestampValidation`

**Test Cases**:
1. `test_future_import_exactly_1_hour_before_allowed()`
   - t_newest_import at exactly allowed_newest_time → SUCCESS

2. `test_future_import_within_1_hour_before_allowed()`
   - t_newest_import between allowed_newest_time and current_hour → SUCCESS

3. `test_future_import_past_allowed_newer_than_1_hour()`
   - t_newest_import > current_hour - 1h → ERROR

4. `test_future_import_in_next_hour()`
   - t_newest_import is 1 hour 30 mins in future → ERROR

5. `test_current_hour_boundary_at_04_30()`
   - Mock current_time = 04:30 → allowed = 03:00
   - t_newest_import = 04:00 → ERROR
   - t_newest_import = 03:00 → SUCCESS

6. `test_current_hour_boundary_at_04_00()`
   - Mock current_time = 04:00 → allowed = 03:00
   - t_newest_import = 04:00 → ERROR
   - t_newest_import = 03:00 → SUCCESS

7. `test_current_hour_boundary_at_03_59()`
   - Mock current_time = 03:59 → allowed = 02:00
   - t_newest_import = 03:00 → ERROR
   - t_newest_import = 02:00 → SUCCESS

#### 2. Nearest Value as Reference Tests
**File**: `tests/unit_tests/test_process_delta_references_for_statistic.py`

**New Test Class**: `TestNearestValueAsReference`

**Test Cases**:
1. `test_import_range_completely_newer_than_db_uses_newest_db_as_reference()`
   - DB: 10:00 - 12:00
   - Import: 14:00 - 16:00
   - Expected: Use 12:00 DB value as NEWER_REFERENCE
   - Mock: current = 17:00, so 16:00 is allowed

2. `test_import_range_completely_older_than_db_uses_newest_db_as_reference()`
   - DB: 14:00 - 16:00
   - Import: 08:00 - 10:00
   - Expected: Use 16:00 DB value as OLDER_REFERENCE (fallback)

3. `test_import_with_partial_overlap_uses_found_reference()`
   - DB: 10:00 - 14:00
   - Import: 12:00 - 16:00 (2h in future)
   - Expected: Find 12:00 DB value, use as reference
   - Mock: current = 17:00

4. `test_no_db_statistics_returns_error()`
   - DB: empty
   - Import: any range
   - Expected: ERROR "No statistics found in database"

#### 3. Integration Tests
**File**: `tests/integration_tests/test_extended_timerange_import.py` (new file)

**Setup**: Use mock Home Assistant with sample DB data

**Test Cases**:
1. `test_import_future_data_within_constraint()`
   - Import data 30 minutes in future (within allowed)
   - Verify statistics added correctly

2. `test_import_future_data_outside_constraint()`
   - Import data 2 hours in future
   - Verify ERROR returned

3. `test_import_completely_outside_db_range_both_directions()`
   - Import 2 ranges: one 5 hours before DB, one 5 hours after DB
   - Verify both succeed with nearest DB values used

4. `test_allow_future_imports_flag_false()`
   - Set `allow_future_imports=False`
   - Try to import 30 min in future
   - Verify ERROR returned

5. `test_timestamp_constraint_varies_with_current_time()`
   - Run multiple times at different current_times
   - Verify allowed_newest changes correctly

---

## Configuration and Service Definition

### manifest.json Changes
No changes needed - existing configuration is compatible.

### services.yaml Changes
Add new optional parameters to import services:

```yaml
import_statistics.import_from_file:
  description: Import statistics from a CSV or TSV file
  fields:
    filename:
      description: File name in the config/import_statistics directory
      example: my_data.csv
    allow_future_imports:
      description: Allow importing timestamps up to 1 hour before current hour
      example: true
      default: true
      selector:
        boolean:

import_statistics.import_from_json:
  description: Import statistics from JSON
  fields:
    entities:
      description: List of entities to import
      example: [...]
    allow_future_imports:
      description: Allow importing timestamps up to 1 hour before current hour
      example: true
      default: true
      selector:
        boolean:
```

---

## Migration and Compatibility

### Backward Compatibility
- **Default Behavior**: Both changes are ENABLED by default
  - This is a breaking change if users relied on future timestamp errors
  - However, imports that previously failed now succeed (improvement)

### Opt-Out Strategy
- Provide `allow_future_imports=False` parameter to revert to old behavior if needed
- Consider adding integration-wide setting in future versions

### Version Notes
- Mark these changes in `manifest.json` version bump
- Add migration notes to README/CONTRIBUTING if needed

---

## Documentation Updates

### README.md
Add section explaining the new behavior:

```markdown
## Extended Time Range Imports

The import service now supports importing statistics with time ranges that extend outside
the database's existing time ranges. When the import range is completely before or after
the database range, the nearest database value is used as a reference for delta conversion.

### Future Timestamp Constraint

Imported timestamps must be at least 1 hour in the past. Specifically:
- Current hour is calculated as the current time rounded down to full hour
- Newest imported timestamp must be ≤ (current hour - 1 hour)
- Example: If current time is 04:30, newest import can be 03:00 or earlier

This constraint prevents importing data far into the future while allowing small delays
in data collection (up to 1 hour).

You can disable this constraint by setting `allow_future_imports: false` in the service call
(reverts to strict past-only imports).
```

### Test README
Add test execution examples showing future timestamp tests:

```bash
# Run extended timerange tests
pytest tests/unit_tests/test_process_delta_references_for_statistic.py::TestFutureTimestampValidation
pytest tests/integration_tests/test_extended_timerange_import.py
```

---

## Implementation Sequence

1. **Phase 1**: Update `_process_delta_references_for_statistic()` logic
   - Add future timestamp check with `allow_future_imports` parameter
   - Implement fallback to nearest DB values for "completely outside" scenarios
   - Update all error paths and add logging/warnings

2. **Phase 2**: Update service handlers
   - Thread `allow_future_imports` parameter through call chain
   - Update service call handlers to extract new parameter
   - Update const.py with new constants

3. **Phase 3**: Testing
   - Implement all unit tests from TestFutureTimestampValidation class
   - Implement all unit tests from TestNearestValueAsReference class
   - Implement integration tests
   - Run full test suite to verify no regressions

4. **Phase 4**: Documentation
   - Update README.md with new feature description
   - Update services.yaml with new parameters
   - Update AGENTS.md if needed with new patterns
   - Add docstring updates to modified functions

5. **Phase 5**: Validation
   - Manual testing with real Home Assistant instance
   - Edge case testing (exact hour boundaries, timezone handling)
   - Performance testing (ensure no degradation from added validations)

---

## Edge Cases and Special Considerations

### 1. Timezone Handling
- All timestamp comparisons should use UTC
- Current time check uses UTC: `dt.datetime.now(tz=dt.UTC)`
- User-provided timestamps are converted to UTC before comparison

### 2. Daylight Saving Time
- Using `dt.datetime` and UTC avoids DST issues
- Hour boundaries are clean in UTC

### 3. Reference Data Quality
- When using nearest DB value, the reference may have been recorded at a different quality
- Log a warning so users are aware the reference is "borrowed"

### 4. Multiple References in Same Hour
- Current `_get_reference_before_timestamp()` handles this internally
- No special handling needed at this level

### 5. Very Old or Very New Data
- Future constraint only applies to newest import
- Oldest import can be arbitrarily old (no constraint)
- This is intentional: allows historical data imports

---

## Logging and Debugging

### New Log Levels

**INFO level**: Normal operations (none new - keep current)

**WARNING level** (new):
- "Using newest DB value as reference for imports newer than DB"
- "Using newest DB value as reference (import range completely before DB range)"
- "Using newest DB value as older reference (import range completely after DB range)"

**DEBUG level** (existing, still used):
- Timestamp comparisons
- Reference lookups
- Current time calculations

These warnings help users understand why their import behaved differently than expected.

---

## Testing Checklist

- [ ] Unit test: Future timestamp exactly at boundary
- [ ] Unit test: Future timestamp 1 second past boundary (error)
- [ ] Unit test: Hour boundary at different times (04:00, 03:59, 04:30)
- [ ] Unit test: Completely newer range with nearest reference
- [ ] Unit test: Completely older range with nearest reference
- [ ] Unit test: No DB statistics at all (error case)
- [ ] Unit test: Mixed overlapping and non-overlapping ranges
- [ ] Integration test: Real HA instance with future data
- [ ] Integration test: Service parameter `allow_future_imports=False`
- [ ] Regression: All existing tests still pass
- [ ] Documentation: README updated with examples
- [ ] Documentation: services.yaml shows new parameters
