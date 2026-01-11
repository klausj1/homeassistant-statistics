# AGENTS.md - Debug Mode

This file provides non-obvious debugging discoveries specific to this repository.

## Critical Debugging Patterns

### Error Logging & Visibility
- All validation errors route through [`helpers.handle_error()`](custom_components/import_statistics/helpers.py:240) which logs to `_LOGGER.warning()` BEFORE raising
- Home Assistant logs appear in the integration logs, not stdout
- Look for "import_statistics" logger in Home Assistant logs, not print statements
- Test failures may show logged warnings even if tests pass - check test output carefully

### Silent Failures & Edge Cases
- Empty DataFrames are silently skipped in export (no error, just empty output)
- Unknown columns in CSV cause immediate import error with column list in error message
- Delimiter `"\\t"` (literal backslash-t) is NOT the same as `"\t"` - the code explicitly handles this conversion
- Mixed min/max/mean values cause errors DURING row processing, not at validation time

### Timezone Conversion Gotchas
- `zoneinfo.ZoneInfo` (Python 3.12) may behave differently than pytz in edge cases
- Import uses user's timezone to INTERPRET the timestamps, then converts to UTC
- Export uses user's timezone to FORMAT the timestamps from UTC
- Default format `"%d.%m.%Y %H:%M"` has NO seconds - timestamps with seconds fail validation
- "Full hour" requirement enforces: `timestamp.minute == 0 and timestamp.second == 0`

### DataFrame Processing Order
- Column validation happens in [`are_columns_valid()`](custom_components/import_statistics/helpers.py:197) - BEFORE data processing
- Row processing in [`handle_dataframe()`](custom_components/import_statistics/prepare_data.py:142) iterates with `df.iterrows()`
- Invalid rows silently append empty dicts to statistics (see line 198 in prepare_data.py)
- If no rows validate, the list will contain empty dicts - may cause downstream issues

### Unit Column Edge Cases
- If `unit_from_entity=True` but unit column exists in CSV → error in [`are_columns_valid()`](custom_components/import_statistics/helpers.py:197)
- If `unit_from_entity=False` but unit column missing → error in [`are_columns_valid()`](custom_components/import_statistics/helpers.py:197)
- External statistics (`:` format) CANNOT use `unit_from_entity=True` - enforced in [`add_unit_to_dataframe()`](custom_components/import_statistics/helpers.py:257)
- Missing unit for external statistics causes error during unit extraction

### Service Handler Async/Sync Mismatch
- `setup()` registers services synchronously (no `async def`)
- But `handle_export_statistics()` is `async def`
- Import handlers are regular `def` (synchronous)
- Executor jobs used for blocking I/O: `await hass.async_add_executor_job(lambda: blocking_call())`
- This pattern is intentional - test must account for async export, sync imports

### File Path Validation
- [`validate_filename()`](custom_components/import_statistics/helpers.py:324) uses `Path.resolve()` which resolves symlinks
- After resolution, checks if path is within config_dir using `Path.relative_to()`
- Both absolute paths AND path traversal (`..`) are rejected
- Export creates file in config_dir - import expects file already in config_dir

### Min/Max/Mean Validation Timing
- [`min_max_mean_are_valid()`](custom_components/import_statistics/helpers.py:176) is called DURING row processing in [`get_mean_stat()`](custom_components/import_statistics/helpers.py:60)
- If constraint violated, raises error immediately (not deferred)
- Invalid rows cause errors in import, not silent skipping

## Testing Gotchas

- Tests import from `custom_components.import_statistics` (PYTHONPATH set by develop script)
- pytest uses `testpaths = tests` (pytest.ini) - must run from project root
- Home Assistant mocks require `pytest-homeassistant-custom-component`
- ServiceCall construction differs from real calls - see test_handle_arguments.py for pattern
