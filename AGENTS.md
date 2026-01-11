# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Overview

Home Assistant custom integration for importing/exporting long-term statistics from CSV/TSV/JSON files. Python 3.12, uses pandas, pytz, Home Assistant recorder API.

## Build/Test Commands

```bash
scripts/setup              # Install dependencies from requirements.txt
scripts/lint              # Format with ruff and auto-fix issues
scripts/develop           # Run Home Assistant with custom component (sets PYTHONPATH)
pytest                    # Run tests from tests/ directory
pytest -v tests/test_X.py # Run specific test file
```

## Critical Coding Patterns

### Error Handling (Non-Negotiable)
- ALL validation errors MUST use [`helpers.handle_error()`](custom_components/import_statistics/helpers.py:282)
- Never raise `ValueError`, `TypeError`, or generic exceptions directly
- `handle_error()` logs warning AND raises `HomeAssistantError` - this dual behavior is required

### Custom Type: UnitFrom Enum
[`UnitFrom`](custom_components/import_statistics/helpers.py:19) enum (ENTITY or TABLE) is used throughout:
- Determines if unit column is required/forbidden in DataFrame validation
- External statistics (`:` format) MUST use TABLE, never ENTITY
- When adding unit to DataFrame, check both source (`recorder` vs external) AND `unit_from_where`

### Statistic ID Format Validation
[`get_source()`](custom_components/import_statistics/helpers.py:26) must be called for ANY statistic_id:
- Returns `"recorder"` for internal (`.` separator)
- Returns domain name for external (`:` separator)
- Rejects `recorder` domain in both formats (explicit validation)
- Uses Home Assistant's `valid_entity_id()` and `valid_statistic_id()` functions

### Pandas DataFrame Column Rules
[`are_columns_valid()`](custom_components/import_statistics/helpers.py:225) enforces strict rules:
- Require: `statistic_id`, `start`, and conditionally `unit`
- Require EITHER all three of `(min, max, mean)` OR `sum` - never mix
- Reject ANY unknown columns (typos in column names fail immediately)
- Special case: if `unit_from_entity=True`, the `unit` column MUST NOT exist

### Delimiter Handling Edge Case
[`validate_delimiter()`](custom_components/import_statistics/helpers.py:335) converts:
- `None` → `"\t"` (tab character)
- String `"\\t"` → `"\t"` (actual tab, not backslash-t)
- Any other single character → unchanged
- Multi-character or empty string → raises error

### Min/Max/Mean Constraint
[`min_max_mean_are_valid()`](custom_components/import_statistics/helpers.py:204) enforces:
- ALWAYS: `min_value ≤ mean_value ≤ max_value`
- Raises `HomeAssistantError` immediately if violated
- Called in validation chain, not optional

### File Path Security (Export Only)
[`validate_filename()`](custom_components/import_statistics/helpers.py:366) prevents traversal:
- Rejects absolute paths (`/` at start)
- Rejects path separators (both `/` and `\`)
- Rejects `..` sequences
- Validates resolved path stays within config_dir using `Path.relative_to()`
- Used only in export; import paths come from config file

### Timezone & Datetime Handling
- Use `zoneinfo.ZoneInfo` (Python 3.12 stdlib), NOT `pytz`
- Default datetime format: `"%d.%m.%Y %H:%M"` (no seconds, full hours only)
- When parsing input: apply timezone, then convert to UTC with `.astimezone(dt.UTC)`
- When formatting output: convert to target timezone with `.astimezone(tz)`

### Delta Column Processing
[`get_delta_stat()`](custom_components/import_statistics/helpers.py:123) extracts delta values from rows:
- Validates timestamp is full hour
- Validates delta is valid float
- Returns dict with `start` (datetime with timezone) and `delta` (float)
- Returns empty dict on validation failure (silent pattern)

Delta conversion workflow (Case 1 - older database reference):
1. [`handle_dataframe()`](custom_components/import_statistics/prepare_data.py:296) detects delta column and returns marker tuple
2. [`get_oldest_statistics_before()`](custom_components/import_statistics/__init__.py:118) (async) queries recorder for reference records at least 1 hour before import start
3. [`convert_deltas_case_1()`](custom_components/import_statistics/prepare_data.py:27) (pure calculation) accumulates deltas to absolute sum/state values
4. [`convert_delta_dataframe_with_references()`](custom_components/import_statistics/prepare_data.py:88) (pure calculation) groups by statistic_id and applies conversion
- All reference fetching is async; conversions are pure/testable
- Marker tuple format: `("_DELTA_PROCESSING_NEEDED", df, references_needed, timezone_identifier, datetime_format, unit_from_where)`

### Export Data Mixing
[`prepare_export_data()`](custom_components/import_statistics/prepare_data.py:548) allows mixed sensor (mean/min/max) and counter (sum/state) statistics in one export. Columns remain sparse with empty strings for non-applicable types.

### Service Handler Pattern
[`setup()`](custom_components/import_statistics/__init__.py:387) registers services synchronously, but:
- Import handlers (`_handle_import_from_file_impl`, `_handle_import_from_json_impl`) are async for delta processing
- Export handler (`_handle_export_statistics_impl`) is async with executor calls for blocking I/O
- Data preparation (CSV/JSON parsing) is sync via executor to avoid blocking
- Delta reference fetching is async (database queries)
- This mixed pattern is intentional for HA compatibility

## Code Style

From `.ruff.toml`:
- Line length: 160 characters
- All linting rules enabled (select = ["ALL"])
- Exceptions: ANN401 (Any), D203, D212, COM812, ISC001, EXE002
- Test files ignore S101 (assert usage)
- MCCabe complexity max: 25

## Testing

- Location: `tests/` directory (pytest.ini: `testpaths = tests`)
- Framework: pytest with pytest-homeassistant-custom-component
- Import path: `from custom_components.import_statistics import ...` (PYTHONPATH set by develop script)
- Mock Home Assistant dependencies using homeassistant framework
- Test files follow naming convention: `test_*.py`

### Integration test

- There is an integration test: test_integration_delta_imports.py
- This tests tests without mocks, with a running home assistance instance
- The home assistance instance can be running before the test. If not, the test starts it und kills it at the end of the test
- This tests needs the environment variable HA_TOKEN_DEV set
- Before running this test, source .env to set HA_TOKEN_DEV