# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom integration for importing/exporting long-term statistics from/to CSV, TSV, and JSON files. The integration handles two types of statistics:
- **Internal statistics** (recorder source): Uses format `sensor.name` for existing HA entities
- **External statistics** (custom source): Uses format `domain:name` for synthetic statistics

## Development Environment

This project uses a devcontainer for development with Home Assistant running in the container.

**Setup**:
```bash
# Runs automatically in devcontainer via postCreateCommand
scripts/setup

# Or manually:
pip install -r requirements.txt
pip install -r requirements.test.txt
```

**Start Home Assistant** (in devcontainer):
```bash
hass -c config
```
Home Assistant will be available at http://localhost:8123

## Testing

The test suite has three levels that run sequentially with automatic dependencies:

```bash
# Run all tests (recommended)
pytest

# Run specific test suites
pytest tests/unit_tests                    # Pure unit tests, no HA dependencies
pytest tests/integration_tests_mock        # Integration tests with mocked HA
pytest tests/integration_tests             # Full integration tests with real HA
```

**Test Dependencies**: If unit tests fail, integration tests are automatically skipped. If integration_tests_mock fail, integration_tests are skipped.

**Run specific tests**:
```bash
pytest tests/unit_tests/test_handle_error.py                              # Single file
pytest tests/unit_tests/test_handle_error.py::test_handle_error_with_valid_error_code  # Single test
pytest tests/unit_tests -k "handle_error"                                 # Pattern match
pytest -v                                                                  # Verbose
pytest -v -s                                                               # Show print/logging
```

**Coverage**:
```bash
pytest --cov=custom_components.import_statistics --cov-report=html
```

## Linting and Formatting

```bash
# Format and lint (auto-fix)
scripts/lint

# Or manually:
ruff format .
ruff check . --fix
```

Configuration: Uses Ruff with Home Assistant's style rules (see [.ruff.toml](.ruff.toml))

## Architecture

### Core Design Patterns

**1. Dual Statistics System**
- Internal (`sensor.name`): Must exist in HA, can use entity or file units
- External (`domain:name`): Must not exist, requires unit from file

**2. Delta Import Pipeline** (three-stage async/sync hybrid):
```
CSV with delta column → [sync] detect delta → [async] fetch DB references → [sync] convert to absolute
```
- Stage 1: [import_service_helper.py](custom_components/import_statistics/import_service_helper.py) detects delta column, returns marker tuple
- Stage 2: [delta_database_access.py](custom_components/import_statistics/delta_database_access.py) async queries for reference values (Case 1: before oldest, Case 2: after youngest)
- Stage 3: [import_service_delta_helper.py](custom_components/import_statistics/import_service_delta_helper.py) converts deltas via accumulation (Case 1) or backward subtraction (Case 2)

**3. Validation Pipeline**
- File-level: Path security, delimiter normalization
- Column-level: Required columns, no unknown columns, value types (mean/min/max XOR sum/state XOR delta)
- Row-level: Value validation, silent failures skip invalid rows
- Constraint-level: Relationships (min ≤ mean ≤ max, timestamps at full hour)

**4. Error Handling**
All validation errors use `handle_error()` in [helpers.py](custom_components/import_statistics/helpers.py:282):
- Logs warning AND raises HomeAssistantError
- Ensures consistent error behavior across codebase

**5. Timezone Handling**
- Import: User's local timezone → UTC for database storage
- Export: UTC → User's timezone for display

### Module Organization

```
custom_components/import_statistics/
├── __init__.py                        # Entry point, service registration
├── const.py                           # Constants
├── helpers.py                         # Core validation/conversion (no HA deps)
├── config_flow.py                     # Config flow (minimal)
│
├── import_service.py                  # Import service handlers
├── import_service_helper.py           # CSV/JSON loading & DataFrame processing
├── import_service_delta_helper.py     # Delta-to-absolute conversion (pure calc)
├── delta_database_access.py           # Async DB queries for delta references
│
├── export_service.py                  # Export service handlers
└── export_service_helper.py           # Export formatting & file writing
```

**Key Files**:
- [helpers.py](custom_components/import_statistics/helpers.py): Pure validation/conversion functions, testable without HA
- [import_service.py](custom_components/import_statistics/import_service.py): Orchestrates import flow, detects delta processing
- [delta_database_access.py](custom_components/import_statistics/delta_database_access.py): Two-pass reference lookup (before/after)
- [export_service.py](custom_components/import_statistics/export_service.py): Calls recorder API, detects JSON vs CSV/TSV

### Critical Architectural Constraints

1. **Timestamps must be at full hour** (minutes=0, seconds=0) - Home Assistant long-term statistics requirement
2. **Delta references must be 1+ hour away** from import range to avoid edge cases
3. **No mixed statistics types** in import (either mean/min/max OR sum/state OR delta per file)
4. **Unknown columns are rejected** - prevents typos and schema mismatches
5. **Export allows mixed types** but import requires separation - asymmetric by design

## Common Development Tasks

**Add a new validation**:
1. Add validation function to [helpers.py](custom_components/import_statistics/helpers.py)
2. Call `handle_error(message)` on failure for consistency
3. Add unit tests in `tests/unit_tests/`

**Modify import logic**:
1. Non-delta path: Edit [import_service_helper.py](custom_components/import_statistics/import_service_helper.py) `handle_dataframe()`
2. Delta detection: Same file, check `are_columns_valid()` and DataFrame grouping
3. Delta conversion: Edit [import_service_delta_helper.py](custom_components/import_statistics/import_service_delta_helper.py) conversion functions
4. Database queries: Edit [delta_database_access.py](custom_components/import_statistics/delta_database_access.py)

**Modify export logic**:
1. Data fetching: [export_service.py](custom_components/import_statistics/export_service.py) `get_statistics_from_recorder()`
2. Formatting: [export_service_helper.py](custom_components/import_statistics/export_service_helper.py) `prepare_export_data()` or `prepare_export_json()`

## Testing Strategy

The architecture separates testable pure functions from HA integration:

**Unit tests** ([tests/unit_tests/](tests/unit_tests/)):
- Test pure functions in [helpers.py](custom_components/import_statistics/helpers.py), [import_service_delta_helper.py](custom_components/import_statistics/import_service_delta_helper.py)
- No HA mocks required, fast execution
- Examples: validation functions, delta conversion logic

**Integration tests with mocks** ([tests/integration_tests_mock/](tests/integration_tests_mock/)):
- Test service handlers with mocked Home Assistant
- Uses `pytest-homeassistant-custom-component`
- Tests flow orchestration and delta marker detection

**Integration tests** ([tests/integration_tests/](tests/integration_tests/)):
- Tests against running HA instance (requires `HA_TOKEN_DEV` environment variable)
- Validates full import/export workflow with actual database
- Tests real recorder API interactions

## File Format Reference

**Import formats**:
- CSV/TSV: Delimiter configurable (default tab), decimal separator (dot or comma)
- Timestamp format: `"%d.%m.%Y %H:%M"` (e.g., "17.03.2024 02:00")
- JSON: Entities list with values array

**Required columns**:
- All: `statistic_id`, `start`, conditionally `unit`
- Sensors: `min`, `max`, `mean`
- Counters: `sum`, optionally `state`
- Delta: `delta` (triggers delta processing pipeline)

**Export formats**:
- TSV/CSV/JSON determined by filename suffix
- Includes calculated delta for counters
- Times formatted in user's timezone

See [README.md](README.md) for detailed format examples and [ARCHITECTURE.md](ARCHITECTURE.md) for comprehensive architecture documentation.
