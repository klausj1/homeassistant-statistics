# Plan: Eliminate Silent Failures in Import Statistics

## Executive Summary

Currently, the import statistics integration silently skips invalid rows during import. This plan eliminates all silent failures to ensure **all rows in an import file must be valid, or the entire import fails**. This provides better data integrity and clearer error reporting to users.

## Problem Analysis

### Current Silent Failure Locations

The codebase has **3 critical silent failure points** where invalid rows are silently skipped:

#### 1. [`get_mean_stat()`](custom_components/import_statistics/helpers.py:68) - Lines 68-96
```python
def get_mean_stat(row: pd.Series, timezone: zoneinfo.ZoneInfo, datetime_format: str = DATETIME_DEFAULT_FORMAT) -> dict:
    if (
        is_full_hour(row["start"], datetime_format)
        and is_valid_float(row["min"])
        and is_valid_float(row["max"])
        and is_valid_float(row["mean"])
        and min_max_mean_are_valid(row["min"], row["max"], row["mean"])
    ):
        return {
            "start": dt.datetime.strptime(row["start"], datetime_format).replace(tzinfo=timezone),
            "min": row["min"],
            "max": row["max"],
            "mean": row["mean"],
        }
    return {}  # ❌ SILENT FAILURE
```

**Impact**: Invalid sensor rows (mean/min/max) are silently skipped.

#### 2. [`get_sum_stat()`](custom_components/import_statistics/helpers.py:99) - Lines 99-128
```python
def get_sum_stat(row: pd.Series, timezone: zoneinfo.ZoneInfo, datetime_format: str = DATETIME_DEFAULT_FORMAT) -> dict:
    if is_full_hour(row["start"], datetime_format) and is_valid_float(row["sum"]):
        if "state" in row.index:
            if is_valid_float(row["state"]):
                return {
                    "start": dt.datetime.strptime(row["start"], datetime_format).replace(tzinfo=timezone),
                    "sum": row["sum"],
                    "state": row["state"],
                }
        else:
            return {
                "start": dt.datetime.strptime(row["start"], datetime_format).replace(tzinfo=timezone),
                "sum": row["sum"],
            }

    return {}  # ❌ SILENT FAILURE
```

**Impact**: Invalid counter rows (sum/state) are silently skipped.

#### 3. [`get_delta_stat()`](custom_components/import_statistics/helpers.py:131) - Lines 131-156
```python
def get_delta_stat(row: pd.Series, timezone: zoneinfo.ZoneInfo, datetime_format: str = DATETIME_DEFAULT_FORMAT) -> dict:
    try:
        if is_full_hour(row["start"], datetime_format) and is_valid_float(row["delta"]):
            return {
                "start": dt.datetime.strptime(row["start"], datetime_format).replace(tzinfo=timezone),
                "delta": float(row["delta"]),
            }
    except HomeAssistantError:
        # Silent failure pattern - return empty dict on validation error
        pass
    return {}  # ❌ SILENT FAILURE
```

**Impact**: Invalid delta rows are silently skipped.

### Where Silent Failures Are Used

#### In [`handle_dataframe_no_delta()`](custom_components/import_statistics/import_service_helper.py:190) - Lines 242-263
```python
for _index, row in df.iterrows():
    statistic_id = row["statistic_id"]
    if statistic_id not in stats:  # New statistic id found
        # ... metadata setup ...
        stats[statistic_id] = (metadata, [])

    new_stat = {}
    if has_mean:
        new_stat = helpers.get_mean_stat(row, timezone, datetime_format)
    elif has_sum:
        new_stat = helpers.get_sum_stat(row, timezone, datetime_format)
    if new_stat:  # ❌ Silently skips if empty dict
        stats[statistic_id][1].append(new_stat)
```

**Impact**: Invalid rows are silently excluded from import. User gets no feedback about which rows failed.

#### In [`handle_dataframe_delta()`](custom_components/import_statistics/import_service_delta_helper.py:182) - Lines 246-251
```python
for _index, row in group.iterrows():
    delta_stat = helpers.get_delta_stat(row, timezone, datetime_format)
    if delta_stat:  # ❌ Silently skips if empty dict
        delta_rows.append(delta_stat)
    else:
        handle_error(f"Invalid delta row for {statistic_id}: {row.to_dict()}")
```

**Note**: Delta processing has **partial** error handling - it calls `handle_error()` in the else branch, but this was added later. However, the `get_delta_stat()` function still has a try/except that catches `HomeAssistantError` and returns empty dict, so the else branch may never execute for validation errors.

### Architecture Context

From [`AGENTS.md`](AGENTS.md:93):
> **Delta Column Processing**
> [`get_delta_stat()`](custom_components/import_statistics/helpers.py:131) extracts delta values from rows:
> - Validates timestamp is full hour
> - Validates delta is valid float
> - Returns dict with `start` (datetime with timezone) and `delta` (float)
> - **Returns empty dict on validation failure (silent pattern)**

From [`docs/dev/architecture.md`](docs/dev/architecture.md:423):
> Silent failures occur only at row-level during extraction:
> - `get_delta_stat()` returns empty dict on validation failure
> - Invalid rows are skipped (not imported)
> - Logged as debug or warning, continues processing

This is documented as a **known limitation** (line 512):
> **Row-Level Silent Failures**: Invalid rows skipped, not reported individually

## Solution Design

### Core Principle

**All validation functions must raise exceptions instead of returning empty dicts.**

This ensures:
1. ✅ All rows are validated
2. ✅ First invalid row stops the import immediately
3. ✅ Clear error message shows which row failed and why
4. ✅ No partial imports (all-or-nothing)
5. ✅ Consistent with existing error handling pattern ([`handle_error()`](custom_components/import_statistics/helpers.py:337))

### Strategy: Remove Silent Failure Pattern

Instead of:
```python
if validation_passes:
    return valid_data
return {}  # Silent failure
```

Use:
```python
if not validation_passes:
    handle_error(f"Validation failed: {details}")
return valid_data  # Only reached if valid
```

This aligns with the existing error handling pattern used throughout the codebase.

## Implementation Plan

### Phase 1: Update Core Validation Functions

#### 1.1 Modify [`get_mean_stat()`](custom_components/import_statistics/helpers.py:68)

**Current behavior**: Returns empty dict on validation failure

**New behavior**: Raise exception with detailed error message

**Changes**:
```python
def get_mean_stat(row: pd.Series, timezone: zoneinfo.ZoneInfo, datetime_format: str = DATETIME_DEFAULT_FORMAT) -> dict:
    """
    Process a row and extract mean statistics based on the specified columns and timezone.

    Args:
    ----
        row (pandas.Series): The input row containing the statistics data.
        timezone (zoneinfo.ZoneInfo): The timezone to convert the timestamps.
        datetime_format (str): The format of the provided datetimes, e.g. "%d.%m.%Y %H:%M"

    Returns:
    -------
        dict: A dictionary containing the extracted mean statistics.

    Raises:
    ------
        HomeAssistantError: If any validation fails (timestamp, float values, or min/max/mean constraint).

    """
    # Validate timestamp (raises HomeAssistantError if invalid)
    is_full_hour(row["start"], datetime_format)

    # Validate float values (raises HomeAssistantError if invalid)
    is_valid_float(row["min"])
    is_valid_float(row["max"])
    is_valid_float(row["mean"])

    # Validate constraint (raises HomeAssistantError if invalid)
    min_max_mean_are_valid(row["min"], row["max"], row["mean"])

    # All validations passed, return the data
    return {
        "start": dt.datetime.strptime(row["start"], datetime_format).replace(tzinfo=timezone),
        "min": row["min"],
        "max": row["max"],
        "mean": row["mean"],
    }
```

**Key changes**:
- Remove conditional check
- Call validation functions directly (they already raise exceptions)
- Remove `return {}` - function only returns valid data or raises exception
- Update docstring to document exception behavior

#### 1.2 Modify [`get_sum_stat()`](custom_components/import_statistics/helpers.py:99)

**Current behavior**: Returns empty dict on validation failure

**New behavior**: Raise exception with detailed error message

**Changes**:
```python
def get_sum_stat(row: pd.Series, timezone: zoneinfo.ZoneInfo, datetime_format: str = DATETIME_DEFAULT_FORMAT) -> dict:
    """
    Process a row and extract sum statistics based on the specified columns and timezone.

    Args:
    ----
        row (pandas.Series): The input row containing the statistics data.
        timezone (zoneinfo.ZoneInfo): The timezone to convert the timestamps.
        datetime_format (str): The format of the provided datetimes, e.g. "%d.%m.%Y %H:%M"

    Returns:
    -------
        dict: A dictionary containing the extracted sum statistics.

    Raises:
    ------
        HomeAssistantError: If any validation fails (timestamp or float values).

    """
    # Validate timestamp (raises HomeAssistantError if invalid)
    is_full_hour(row["start"], datetime_format)

    # Validate sum (raises HomeAssistantError if invalid)
    is_valid_float(row["sum"])

    # Build result dict
    result = {
        "start": dt.datetime.strptime(row["start"], datetime_format).replace(tzinfo=timezone),
        "sum": row["sum"],
    }

    # Handle optional state column
    if "state" in row.index:
        is_valid_float(row["state"])  # Raises if invalid
        result["state"] = row["state"]

    return result
```

**Key changes**:
- Remove nested conditionals
- Call validation functions directly
- Remove `return {}` - function only returns valid data or raises exception
- Simplify state handling logic
- Update docstring to document exception behavior

#### 1.3 Modify [`get_delta_stat()`](custom_components/import_statistics/helpers.py:131)

**Current behavior**: Returns empty dict on validation failure, catches HomeAssistantError

**New behavior**: Raise exception with detailed error message

**Changes**:
```python
def get_delta_stat(row: pd.Series, timezone: zoneinfo.ZoneInfo, datetime_format: str = DATETIME_DEFAULT_FORMAT) -> dict:
    """
    Extract delta statistic from a row.

    Args:
    ----
        row (pd.Series): The input row containing the statistics data.
        timezone (zoneinfo.ZoneInfo): The timezone to convert the timestamps.
        datetime_format (str): The format of the provided datetimes, e.g. "%d.%m.%Y %H:%M"

    Returns:
    -------
        dict: A dictionary containing 'start' (datetime with timezone) and 'delta' (float).

    Raises:
    ------
        HomeAssistantError: If any validation fails (timestamp or delta value).

    """
    # Validate timestamp (raises HomeAssistantError if invalid)
    is_full_hour(row["start"], datetime_format)

    # Validate delta (raises HomeAssistantError if invalid)
    is_valid_float(row["delta"])

    # All validations passed, return the data
    return {
        "start": dt.datetime.strptime(row["start"], datetime_format).replace(tzinfo=timezone),
        "delta": float(row["delta"]),
    }
```

**Key changes**:
- Remove try/except block that catches HomeAssistantError
- Remove conditional check
- Call validation functions directly
- Remove `return {}` - function only returns valid data or raises exception
- Update docstring to remove "silent failure pattern" note and document exception behavior

### Phase 2: Update Processing Loops

#### 2.1 Modify [`handle_dataframe_no_delta()`](custom_components/import_statistics/import_service_helper.py:190)

**Current behavior**: Silently skips rows that return empty dict

**New behavior**: Let exceptions propagate (import fails on first invalid row)

**Changes**:
```python
for _index, row in df.iterrows():
    statistic_id = row["statistic_id"]
    if statistic_id not in stats:  # New statistic id found
        source = helpers.get_source(statistic_id)
        metadata = {
            "mean_type": StatisticMeanType.ARITHMETIC if has_mean else StatisticMeanType.NONE,
            "has_sum": has_sum,
            "source": source,
            "statistic_id": statistic_id,
            "name": None,
            "unit_class": None,
            "unit_of_measurement": helpers.add_unit_to_dataframe(source, unit_from_where, row.get("unit", ""), statistic_id),
        }
        stats[statistic_id] = (metadata, [])

    # Extract statistics - will raise HomeAssistantError if invalid
    if has_mean:
        new_stat = helpers.get_mean_stat(row, timezone, datetime_format)
    elif has_sum:
        new_stat = helpers.get_sum_stat(row, timezone, datetime_format)
    else:
        # This should never happen due to column validation, but be defensive
        helpers.handle_error(f"Row has neither mean nor sum columns: {row.to_dict()}")

    # Append the validated statistic
    stats[statistic_id][1].append(new_stat)
```

**Key changes**:
- Remove `if new_stat:` check - function always returns valid data or raises
- Remove `new_stat = {}` initialization
- Add defensive error for impossible case (neither mean nor sum)
- Simplify logic - no conditional append

#### 2.2 Modify [`handle_dataframe_delta()`](custom_components/import_statistics/import_service_delta_helper.py:182)

**Current behavior**: Has partial error handling but get_delta_stat() still returns empty dict

**New behavior**: Let exceptions propagate (import fails on first invalid row)

**Changes**:
```python
# Extract delta rows using get_delta_stat
delta_rows = []
for _index, row in group.iterrows():
    # get_delta_stat now raises HomeAssistantError if invalid
    delta_stat = helpers.get_delta_stat(row, timezone, datetime_format)
    delta_rows.append(delta_stat)

if not delta_rows:
    # This means the group had no rows, which shouldn't happen
    _LOGGER.warning("No delta rows found for statistic_id: %s", statistic_id)
    continue
```

**Key changes**:
- Remove `if delta_stat:` check - function always returns valid data or raises
- Remove `else: handle_error(...)` branch - no longer needed
- Simplify to direct append
- Keep the empty check but change interpretation (now means empty group, not invalid rows)

### Phase 3: Update Tests

#### 3.1 Update [`test_get_delta_stat.py`](tests/unit_tests/test_get_delta_stat.py)

**Current tests expecting empty dict**: Lines 47-65, 67-84, 125-142

**Changes needed**:
```python
# OLD: Test expecting silent failure
def test_get_delta_stat_invalid_timestamp_not_full_hour() -> None:
    """Test get_delta_stat with invalid timestamp (not full hour)."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:30", "delta": "10.5"})
    result = get_delta_stat(row, tz)

    # Silent failure pattern - returns empty dict
    assert result == {}

# NEW: Test expecting exception
def test_get_delta_stat_invalid_timestamp_not_full_hour() -> None:
    """Test get_delta_stat with invalid timestamp (not full hour)."""
    tz = zoneinfo.ZoneInfo("Europe/Vienna")
    row = pd.Series({"start": "01.01.2022 00:30", "delta": "10.5"})

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Invalid timestamp: 01.01.2022 00:30. The timestamp must be a full hour."),
    ):
        get_delta_stat(row, tz)
```

**Tests to update**:
1. `test_get_delta_stat_invalid_timestamp_not_full_hour()` - Line 47
2. `test_get_delta_stat_invalid_timestamp_with_seconds()` - Line 57
3. `test_get_delta_stat_invalid_delta_non_numeric()` - Line 67
4. `test_get_delta_stat_invalid_delta_comma_separator()` - Line 77
5. `test_get_delta_stat_nan_delta()` - Line 125
6. `test_get_delta_stat_empty_string_delta()` - Line 135

#### 3.2 Create New Integration Tests

**New test file**: `tests/integration_tests_mock/test_import_validation_strict.py`

**Purpose**: Verify that imports fail on first invalid row

**Test cases**:
1. Import with one invalid row in middle of file - should fail
2. Import with invalid timestamp format - should fail
3. Import with invalid float value - should fail
4. Import with min > max constraint violation - should fail
5. Import with NaN/empty values - should fail
6. Import with all valid rows - should succeed

**Example test**:
```python
def test_import_fails_on_invalid_row_in_middle(hass, mock_recorder):
    """Test that import fails when invalid row is in middle of file."""
    # Create CSV with 3 rows: valid, invalid, valid
    csv_content = """statistic_id,start,unit,mean,min,max
sensor.test,01.01.2022 00:00,°C,20.0,15.0,25.0
sensor.test,01.01.2022 01:00,°C,invalid,15.0,25.0
sensor.test,01.01.2022 02:00,°C,20.0,15.0,25.0"""

    # Write to temp file
    file_path = write_temp_csv(csv_content)

    # Attempt import - should fail on row 2
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Invalid float value: invalid"),
    ):
        await hass.services.async_call(
            DOMAIN,
            "import_from_file",
            {"file_path": file_path},
            blocking=True,
        )

    # Verify NO data was imported (all-or-nothing)
    stats = await get_statistics(hass, ["sensor.test"])
    assert len(stats) == 0
```

#### 3.3 Update Existing Integration Tests

**Files to review**:
- [`test_import_service_without_delta.py`](tests/integration_tests_mock/test_import_service_without_delta.py)
- [`test_import_service_with_delta.py`](tests/integration_tests_mock/test_import_service_with_delta.py)

**Changes needed**:
- Ensure all test data files have valid rows only
- Add explicit tests for validation failures
- Verify error messages are clear and actionable

### Phase 4: Update Documentation

#### 4.1 Update [`AGENTS.md`](AGENTS.md)

**Section to update**: "Delta Column Processing" (Line 88-93)

**Current text**:
> [`get_delta_stat()`](custom_components/import_statistics/helpers.py:131) extracts delta values from rows:
> - Validates timestamp is full hour
> - Validates delta is valid float
> - Returns dict with `start` (datetime with timezone) and `delta` (float)
> - Returns empty dict on validation failure (silent pattern)

**New text**:
> [`get_delta_stat()`](custom_components/import_statistics/helpers.py:131) extracts delta values from rows:
> - Validates timestamp is full hour
> - Validates delta is valid float
> - Returns dict with `start` (datetime with timezone) and `delta` (float)
> - Raises `HomeAssistantError` on validation failure (strict validation)

#### 4.2 Update [`docs/dev/architecture.md`](docs/dev/architecture.md)

**Section to update**: "Error Handling Strategy" (Line 406-428)

**Current text** (Line 423-428):
> Silent failures occur only at row-level during extraction:
> - `get_delta_stat()` returns empty dict on validation failure
> - Invalid rows are skipped (not imported)
> - Logged as debug or warning, continues processing

**New text**:
> All validation errors raise exceptions immediately:
> - `get_delta_stat()`, `get_mean_stat()`, `get_sum_stat()` raise `HomeAssistantError` on validation failure
> - Invalid rows cause the entire import to fail (all-or-nothing)
> - First invalid row stops processing with clear error message

**Section to update**: "Known Limitations & Design Decisions" (Line 510-516)

**Remove this item** (Line 512):
> 2. **Row-Level Silent Failures**: Invalid rows skipped, not reported individually

**Update numbering** for remaining items.

#### 4.3 Update `.roo/rules-architect/AGENTS.md`

**Section to update**: "Validation Pipeline Architecture" (around line discussing silent failures)

**Add note**:
> **Strict Validation**: All row-level validation functions (`get_mean_stat`, `get_sum_stat`, `get_delta_stat`) raise exceptions on validation failure. There are no silent failures - all rows must be valid or the import fails.

## Testing Strategy

### Unit Tests
- ✅ Update existing tests to expect exceptions instead of empty dicts
- ✅ Verify all validation functions raise appropriate exceptions
- ✅ Test error messages are clear and actionable

### Integration Tests (Mocked)
- ✅ Test import fails on first invalid row
- ✅ Test no partial imports occur
- ✅ Test error messages include row details
- ✅ Test all validation paths (timestamp, float, constraint)

### Integration Tests (Real HA)
- ✅ Verify behavior with real Home Assistant instance
- ✅ Test that database remains unchanged on validation failure
- ✅ Test error reporting in Home Assistant logs

## Migration Impact

### Breaking Changes
⚠️ **This is a breaking change in behavior**:

**Before**: Invalid rows silently skipped, partial import succeeds
**After**: First invalid row fails entire import

### User Impact
Users may discover data quality issues in their import files that were previously hidden. This is **intentional and beneficial**:

1. ✅ Users get immediate feedback about data problems
2. ✅ No more mysterious "missing data" after import
3. ✅ Clear error messages guide users to fix their data
4. ✅ Data integrity is guaranteed (all-or-nothing)

### Rollout Strategy
1. Update code and tests
2. Update documentation with clear examples
3. Add migration notes to CHANGELOG.md
4. Consider adding a validation-only mode (future enhancement)

## Future Enhancements

### Validation-Only Mode (Optional)
Add a service parameter to validate without importing:

```yaml
service: import_statistics.validate_file
data:
  file_path: "test.csv"
```

This would:
- Run all validation checks
- Report ALL invalid rows (not just first)
- Not modify database
- Return detailed validation report

This is **out of scope** for this plan but could be added later.

### Batch Error Reporting (Optional)
Instead of failing on first error, collect all errors and report at end. This is **more complex** and may not align with the all-or-nothing principle.

## Implementation Checklist

### Code Changes
- [ ] Modify [`get_mean_stat()`](custom_components/import_statistics/helpers.py:68)
- [ ] Modify [`get_sum_stat()`](custom_components/import_statistics/helpers.py:99)
- [ ] Modify [`get_delta_stat()`](custom_components/import_statistics/helpers.py:131)
- [ ] Modify [`handle_dataframe_no_delta()`](custom_components/import_statistics/import_service_helper.py:190)
- [ ] Modify [`handle_dataframe_delta()`](custom_components/import_statistics/import_service_delta_helper.py:182)

### Test Updates
- [ ] Update [`test_get_delta_stat.py`](tests/unit_tests/test_get_delta_stat.py) - 6 tests
- [ ] Create `test_import_validation_strict.py` - new integration tests
- [ ] Review and update existing integration tests
- [ ] Add tests for error message clarity

### Documentation Updates
- [ ] Update [`AGENTS.md`](AGENTS.md) - Delta Column Processing section
- [ ] Update [`docs/dev/architecture.md`](docs/dev/architecture.md) - Error Handling Strategy
- [ ] Update [`docs/dev/architecture.md`](docs/dev/architecture.md) - Known Limitations
- [ ] Update `.roo/rules-architect/AGENTS.md` - Validation Pipeline
- [ ] Add migration notes to CHANGELOG.md

### Validation
- [ ] Run all unit tests: `pytest tests/unit_tests/`
- [ ] Run all integration tests: `pytest tests/integration_tests_mock/`
- [ ] Run real HA integration test: `pytest tests/integration_tests/`
- [ ] Run linter: `scripts/lint`
- [ ] Manual testing with invalid data files

## Success Criteria

✅ All validation functions raise exceptions instead of returning empty dicts
✅ Import fails on first invalid row with clear error message
✅ No partial imports occur (all-or-nothing)
✅ All tests pass with new behavior
✅ Documentation accurately reflects new behavior
✅ Error messages are clear and actionable for users

## Risk Assessment

### Low Risk
- Changes are localized to validation functions
- Existing error handling infrastructure is already in place
- Test coverage is comprehensive

### Medium Risk
- Breaking change may surprise users
- Need clear migration documentation

### Mitigation
- Comprehensive testing at all levels
- Clear error messages guide users to fix data
- Documentation updates explain new behavior
- CHANGELOG.md documents breaking change

## Conclusion

This plan eliminates all silent failures in the import statistics integration, ensuring data integrity and providing clear error feedback to users. The changes align with the existing error handling patterns and improve the overall robustness of the integration.

The implementation is straightforward: remove the "return empty dict" pattern and let validation exceptions propagate naturally. This provides immediate, actionable feedback to users about data quality issues.
