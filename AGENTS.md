# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Overview

Home Assistant custom integration for importing/exporting long-term statistics from CSV/TSV/JSON files. Python 3.12, uses pandas, zoneinfo (not pytz), Home Assistant recorder API. The architecture features modular separation: pure validation functions, import/export service handlers, and specialized delta processing with database reference lookups.

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
- ALL validation errors MUST use [`helpers.handle_error()`](custom_components/import_statistics/helpers.py:329)
- Never raise `ValueError`, `TypeError`, or generic exceptions directly
- `handle_error()` logs warning AND raises `HomeAssistantError` - this dual behavior is required

### Custom Type: UnitFrom Enum
[`UnitFrom`](custom_components/import_statistics/helpers.py:20) enum (ENTITY or TABLE) is used throughout:
- Determines if unit column is required/forbidden in DataFrame validation
- External statistics (`:` format) MUST use TABLE, never ENTITY
- When adding unit to DataFrame, check both source (`recorder` vs external) AND `unit_from_where`

### Custom Type: DeltaReferenceType Enum
[`DeltaReferenceType`](custom_components/import_statistics/helpers.py:27) enum (OLDER_REFERENCE or NEWER_REFERENCE):
- OLDER_REFERENCE: Reference is 1+ hour before oldest import (forward accumulation)
- NEWER_REFERENCE: Reference is at or after newest import (backward subtraction)
- Used in delta conversion to determine calculation strategy

### Statistic ID Format Validation
[`get_source()`](custom_components/import_statistics/helpers.py:34) must be called for ANY statistic_id:
- Returns `"recorder"` for internal (`.` separator)
- Returns domain name for external (`:` separator)
- Rejects `recorder` domain in both formats (explicit validation)
- Uses Home Assistant's `valid_entity_id()` and `valid_statistic_id()` functions

### Pandas DataFrame Column Rules
[`are_columns_valid()`](custom_components/import_statistics/helpers.py:272) enforces strict rules:
- Require: `statistic_id`, `start`, and conditionally `unit`
- Require EITHER all three of `(min, max, mean)` OR `sum` OR `delta` - never mix
- Reject ANY unknown columns (typos in column names fail immediately)
- Special case: if `unit_from_entity=True`, the `unit` column MUST NOT exist
- Delta column cannot coexist with sum, state, mean, min, or max

### Delimiter Handling Edge Case
[`validate_delimiter()`](custom_components/import_statistics/helpers.py:382) converts:
- `None` → `"\t"` (tab character)
- String `"\\t"` → `"\t"` (actual tab, not backslash-t)
- Any other single character → unchanged
- Multi-character or empty string → raises error

### Min/Max/Mean Constraint
[`min_max_mean_are_valid()`](custom_components/import_statistics/helpers.py:251) enforces:
- ALWAYS: `min_value ≤ mean_value ≤ max_value`
- Raises `HomeAssistantError` immediately if violated
- Called in validation chain, not optional

### File Encoding Validation (Import Only)
[`validate_file_encoding()`](custom_components/import_statistics/helpers.py:417) validates UTF-8 encoding:
- Reads entire file with strict UTF-8 decoding to detect encoding errors
- Detects common mojibake patterns (Â° for °, Â³ for ³)
- Detects Unicode replacement character (�)
- Called before pandas reads CSV/TSV files in [`prepare_data_to_import()`](custom_components/import_statistics/import_service_helper.py:57)
- Provides clear error messages for encoding issues with special characters

### File Path Security (Export Only)
[`validate_filename()`](custom_components/import_statistics/helpers.py:467) prevents traversal:
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
[`get_delta_stat()`](custom_components/import_statistics/helpers.py:131) extracts delta values from rows:
- Validates timestamp is full hour
- Validates delta is valid float
- Returns dict with `start` (datetime with timezone) and `delta` (float)
- Returns empty dict on validation failure (silent pattern)

Delta conversion workflow:
1. [`handle_dataframe_delta()`](custom_components/import_statistics/import_service_delta_helper.py:178) detects delta column and processes with pre-fetched references
2. [`get_oldest_statistics_before()`](custom_components/import_statistics/delta_database_access.py) (async) queries recorder for reference records
   - First attempts: references 1+ hour before oldest import
   - Falls back to: references at or after newest import
3. [`convert_deltas_with_older_reference()`](custom_components/import_statistics/import_service_delta_helper.py:17) (pure calculation) accumulates deltas forward
4. [`convert_deltas_with_newer_reference()`](custom_components/import_statistics/import_service_delta_helper.py:79) (pure calculation) subtracts deltas backward
- All reference fetching is async; conversions are pure/testable
- Reference type determines conversion strategy (forward vs backward)

### Export Data Mixing
[`prepare_export_data()`](custom_components/import_statistics/export_service_helper.py:42) allows mixed sensor (mean/min/max) and counter (sum/state) statistics in one export. Columns remain sparse with empty strings for non-applicable types.

### Service Handler Pattern
[`setup()`](custom_components/import_statistics/__init__.py:16) registers services synchronously, but:
- Import handlers ([`handle_import_from_file_impl`](custom_components/import_statistics/import_service.py), [`handle_import_from_json_impl`](custom_components/import_statistics/import_service.py)) are async for delta processing
- Export handler ([`handle_export_statistics_impl`](custom_components/import_statistics/export_service.py)) is async with executor calls for blocking I/O
- Data preparation (CSV/JSON parsing) is sync via executor to avoid blocking
- Delta reference fetching is async (database queries)
- This mixed pattern is intentional for HA compatibility

### Module Organization
The codebase is organized into specialized modules:
- [`helpers.py`](custom_components/import_statistics/helpers.py): Pure validation functions, no HA dependencies
- [`import_service.py`](custom_components/import_statistics/import_service.py): Orchestrates import flow, handles async coordination
- [`import_service_helper.py`](custom_components/import_statistics/import_service_helper.py): Data loading and DataFrame processing
- [`import_service_delta_helper.py`](custom_components/import_statistics/import_service_delta_helper.py): Pure delta conversion calculations
- [`delta_database_access.py`](custom_components/import_statistics/delta_database_access.py): Async database queries for delta references
- [`export_service.py`](custom_components/import_statistics/export_service.py): Export service handler
- [`export_service_helper.py`](custom_components/import_statistics/export_service_helper.py): Data formatting and file writing

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

### Test Organization
- `tests/unit_tests/`: Pure function tests (helpers, delta conversion)
- `tests/integration_tests_mock/`: Service tests with mocked HA
- `tests/integration_tests/`: Tests with real HA instance

### Integration test with real Home Assistant

- There is an integration test: [`test_integration_delta_imports.py`](tests/integration_tests/test_integration_delta_imports.py)
- This test runs without mocks, with a running Home Assistant instance
- The Home Assistant instance can be running before the test. If not, the test starts it and kills it at the end
- This test needs the environment variable `HA_TOKEN_DEV` set
- Before running this test, source `.env` to set `HA_TOKEN_DEV`

## Architecture Notes

See [`docs/dev/architecture.md`](docs/dev/architecture.md) for detailed architecture documentation including:
- Component descriptions
- Data flow diagrams (normal import, delta import, export)
- Key architectural patterns
- Data structures
- Module dependencies
