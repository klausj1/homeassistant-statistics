# Integration Test Update Summary

**Date:** 2026-01-10
**Changes:** Strict comparison enforcement in integration tests

## Changes Made

### 1. Test Behavior Changes

**Before:**
- `_compare_tsv_files_log_only()` method only logged warnings for mismatches
- Tests would pass even if exported files didn't match expected files
- Separate `_check_export_has_entities()` method to verify entities present

**After:**
- `_compare_tsv_files()` method raises `AssertionError` on any mismatch
- Tests **fail immediately** if exported files don't match expected files exactly
- Removed redundant entity check (file comparison covers this)
- Removed unused `_normalize_tsv_for_comparison()` helper method

### 2. Code Changes

#### Files Modified:
1. [tests/integration_tests/test_integration_sensor_imports.py](../tests/integration_tests/test_integration_sensor_imports.py)
2. [tests/integration_tests/test_integration_counter_imports.py](../tests/integration_tests/test_integration_counter_imports.py)

#### Changes in Both Files:

**Removed methods:**
- `_normalize_tsv_for_comparison()` - No longer needed
- `_check_export_has_entities()` - Redundant with full file comparison
- `_compare_tsv_files_log_only()` - Replaced with strict version

**Added method:**
```python
@staticmethod
def _compare_tsv_files(actual_path: Path, expected_path: Path, tolerance: float = 0.01) -> None:
    """
    Compare two TSV files for equality with numeric tolerance and assert on mismatch.

    Raises:
        AssertionError: If files don't match
    """
```

**Updated test calls:**
```python
# Before:
assert self._check_export_has_entities(export_file_1, entities), "Step 1 export missing entities"
self._compare_tsv_files_log_only(export_file_1, reference_file_1)

# After:
self._compare_tsv_files(export_file_1, reference_file_1)
```

### 3. Comparison Logic

The new `_compare_tsv_files()` method performs strict validation:

1. **Row count check** - Must match exactly
2. **Column count check** - Must match per row
3. **Value comparison** - Cell by cell with:
   - Numeric tolerance of 0.01 for float values
   - Exact string matching for non-numeric values
   - Handles empty values correctly (trailing tabs)

**Assertion failures provide clear error messages:**
```
AssertionError: Row count mismatch: 21 vs 20
AssertionError: Column count mismatch at row 2: 6 vs 5
AssertionError: Value mismatch at row 5, col 3: 25.5 vs 25.0
```

### 4. Test Results

**Status:** ✅ All tests pass

```bash
pytest tests/integration_tests/test_integration_sensor_imports.py \
      tests/integration_tests/test_integration_counter_imports.py -v
```

**Output:**
- Sensor test: PASSED - "COMPARISON OK: Files match perfectly"
- Counter test: PASSED - "COMPARISON OK: Files match perfectly"
- Total time: ~33 seconds
- **2 passed, 0 failed**

### 5. Benefits of Changes

✅ **Stricter validation** - Tests now fail on ANY mismatch
✅ **Clearer intent** - Method name `_compare_tsv_files()` indicates it asserts
✅ **Less code** - Removed 3 helper methods, added 1 comprehensive method
✅ **Better error messages** - Precise location and nature of mismatches
✅ **Maintainability** - Single comparison method to maintain

### 6. Reference Files Status

All reference files are correctly formatted and match exports exactly:

**Sensors:**
- Column order: `statistic_id, unit, start, min, max, mean` ✅
- Decimal precision matches exports ✅

**Counters:**
- Column order: `statistic_id, unit, start, sum, state, delta` ✅
- Empty delta values with trailing tabs for first entity rows ✅

## Testing the Changes

To verify the strict comparison works, you can:

### 1. Test with correct files (should pass):
```bash
pytest tests/integration_tests/test_integration_sensor_imports.py -v
```

### 2. Test with intentional mismatch (should fail):
```bash
# Temporarily modify a value in expected_after_import.tsv
# Run test - it should fail with clear error message
```

Example failure output:
```
AssertionError: Value mismatch at row 2, col 5: 20.5 vs 20.0
```

## Conclusion

The integration tests now enforce strict equality between exported and expected files. Any differences in:
- Row/column counts
- Numeric values (beyond 0.01 tolerance)
- String values (including timestamps, units, entity IDs)

...will cause the test to **fail immediately** with a clear error message indicating exactly what doesn't match.

This ensures that any regression in export functionality will be caught immediately by the test suite.
