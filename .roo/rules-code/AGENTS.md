# AGENTS.md - Code Mode

This file provides non-obvious coding rules discovered by reading this repository.

## Critical Coding Patterns

### Error Handling (Non-Negotiable)

- ALL validation errors MUST use [`helpers.handle_error()`](custom_components/import_statistics/helpers.py:240)
- Never raise `ValueError`, `TypeError`, or generic exceptions directly
- `handle_error()` logs warning AND raises `HomeAssistantError` - this dual behavior is required

### Statistic ID Format Validation

[`get_source()`](custom_components/import_statistics/helpers.py:26) must be called for ANY statistic_id:

- Returns `"recorder"` for internal (`.` separator)
- Returns domain name for external (`:` separator)
- Rejects `recorder` domain in both formats (explicit validation)
- Uses Home Assistant's `valid_entity_id()` and `valid_statistic_id()` functions

### Pandas DataFrame Column Rules

[`are_columns_valid()`](custom_components/import_statistics/helpers.py:275) enforces strict rules:

- Require: `statistic_id`, `start`, and `unit` (always required)
- Require EITHER all three of `(min, max, mean)` OR `sum` OR `delta` - never mix
- Reject ANY unknown columns (typos in column names fail immediately)
- Delta column cannot coexist with sum, state, mean, min, or max

### Delimiter Handling Edge Case

[`validate_delimiter()`](custom_components/import_statistics/helpers.py:293) converts:

- `None` → `"\t"` (tab character)
- String `"\\t"` → `"\t"` (actual tab, not backslash-t)
- Any other single character → unchanged
- Multi-character or empty string → raises error

### Min/Max/Mean Constraint

[`min_max_mean_are_valid()`](custom_components/import_statistics/helpers.py:176) enforces:

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

### Unit Validation

[`validate_entities_and_units()`](custom_components/import_statistics/import_service.py:300) validates units during import:

- Input files MUST contain a `unit` column
- For existing statistics, validates input unit matches database unit in statistic_meta
- Raises `HomeAssistantError` if units don't match
- Uses `get_metadata()` from recorder to fetch existing units
- [`get_unit_from_row()`](custom_components/import_statistics/helpers.py:345) extracts unit from input and validates it's not empty

### Service Registration Pattern

[`setup()`](custom_components/import_statistics/__init__.py:16):

- Registers services synchronously
- Import handlers are async (for delta processing and unit validation)
- Export handler is async - must use `async def` and `await` for executor jobs
- This mixed pattern is intentional for Home Assistant compatibility

### Timezone Conversion Details

- Use `zoneinfo.ZoneInfo` (Python 3.12 stdlib), NOT `pytz`
- Default datetime format: `"%d.%m.%Y %H:%M"` (no seconds, full hours only)
- When parsing input: apply timezone, then convert to UTC with `.astimezone(dt.UTC)`
- When formatting output: convert to target timezone with `.astimezone(tz)`

## Ruff Configuration Constraints

- Line length: 160 characters (hard limit)
- Target: Python 3.12
- MCCabe complexity: max 25 per function
- Type hints required (ANN401 ignored for `Any` only)
- All other rules enforced (see .ruff.toml for ignored rules)
