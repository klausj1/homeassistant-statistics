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

## Critical Non-Obvious Patterns

### Error Handling
All validation errors use [`helpers.handle_error()`](custom_components/import_statistics/helpers.py:240) which logs a warning AND raises `HomeAssistantError`. Never use standard exceptions for validation errors.

### Statistic ID Types & Validation
Two supported formats determined by [`helpers.get_source()`](custom_components/import_statistics/helpers.py:26):
- **Internal (recorder source)**: `sensor.name` format with `.` separator - must be existing entity
- **External**: `domain:name` format with `:` separator - creates new statistics
Domain `recorder` is explicitly forbidden in both formats.

### Unit Source Tracking
[`UnitFrom` enum](custom_components/import_statistics/helpers.py:19) (ENTITY or TABLE) determines:
- Whether `unit` column is required in CSV (not required if ENTITY, must exist if TABLE)
- External statistics MUST have unit from TABLE (unit_from_entity=True forbidden)
- Unit extraction happens in [`add_unit_to_dataframe()`](custom_components/import_statistics/helpers.py:257)

### Timezone & Datetime Handling
- Uses `zoneinfo.ZoneInfo` (Python 3.12), not pytz, for conversions
- Default format: `"%d.%m.%Y %H:%M"` (DD.MM.YYYY HH:MM) - 24-hour, full hours only
- Input format for export: `"%Y-%m-%d %H:%M:%S"` (ISO format)
- Minutes and seconds must be 0 (full hour requirement enforced)
- Timezone-aware conversions in [`get_mean_stat()`](custom_components/import_statistics/helpers.py:60) and [`get_sum_stat()`](custom_components/import_statistics/helpers.py:91)

### Delimiter Conversion
[`validate_delimiter()`](custom_components/import_statistics/helpers.py:293) has special case: literal string `"\\t"` must be converted to actual tab character `"\t"`. This is not intuitive from the code.

### DataFrame Column Validation
[`are_columns_valid()`](custom_components/import_statistics/helpers.py:197) enforces:
- Required columns: `statistic_id`, `start`, plus `unit` (unless unit_from_entity=True)
- Either `(mean, min, max)` OR `(sum)` - never both mixed
- Unknown columns rejected unless they're expected
- Special case: `unit` column forbidden if unit_from_entity=True

### Export Data Mixing
[`prepare_export_data()`](custom_components/import_statistics/prepare_data.py:287) allows mixed sensor (mean/min/max) and counter (sum/state) statistics in one export. Columns remain sparse with empty strings for non-applicable types.

### File Path Security
[`validate_filename()`](custom_components/import_statistics/helpers.py:324) prevents directory traversal:
- Rejects absolute paths, `..` sequences, and path separators
- Resolves path and verifies it stays within config_dir
- Used in export operations only (import uses file provided in config)

### Service Handler Pattern
[`setup()`](custom_components/import_statistics/__init__.py:132) registers services synchronously, but:
- Import handlers (`handle_import_from_file`, `handle_import_from_json`) are synchronous
- Export handler (`handle_export_statistics`) is async with executor calls for blocking I/O
- This mixed pattern is intentional for HA compatibility

### Min/Max/Mean Validation
[`min_max_mean_are_valid()`](custom_components/import_statistics/helpers.py:176) enforces: `min ≤ mean ≤ max`. Violating this raises error immediately.

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
