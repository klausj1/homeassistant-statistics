# AGENTS.md - Ask Mode

This file provides non-obvious context about the repository's structure and design decisions.

## Project Organization & Counterintuitive Aspects

### Directory Structure
- Custom component lives in `custom_components/import_statistics/` (not in a separate src/ folder)
- Tests are in `tests/` at project root, NOT in `custom_components/` subdirectory
- Config files go in `config/` directory when running via `scripts/develop`
- Test assets are in `tests/testfiles/` (example CSVs, TSVs, JSONs for testing)

### Two-Format Support for Statistics
The integration handles TWO completely different statistic formats that look similar but behave differently:
- **Internal (`.` format, e.g., `sensor.temperature`)**: Must reference existing entities, uses entity's unit of measurement
- **External (`:` format, e.g., `sensor:custom_stat`)**: Creates new statistics, MUST have unit from CSV file, unit from entity is forbidden
- The distinction is enforced at multiple validation points and is NOT optional

### Unit Source Complexity
Units can come from two places, creating a dual-mode system:
- **From entity** (`unit_from_entity=True`): Unit column must NOT exist in CSV, unit fetched from Home Assistant entity
- **From table** (`unit_from_entity=False`): Unit column must exist in CSV, no entity lookup needed
- But external statistics (`:` format) ALWAYS require unit from table - mixing modes is impossible for external stats
- This creates asymmetry: internal stats are flexible, external stats are rigid

### Data Type Mixing in Export
Unlike import (which accepts ONLY sensors or ONLY counters), export can produce mixed files:
- One file can contain both `min/max/mean` columns (sensors) and `sum/state` columns (counters)
- Columns for non-applicable types are filled with empty strings
- This asymmetry exists because export pulls from recorder which may have mixed statistics
- But direct re-import of mixed files is NOT possible (import rejects mixed min/max/sum)

### Service Handler Asymmetry
- Import services (`import_from_file`, `import_from_json`) are synchronous and blocking
- Export service (`export_statistics`) is async with executor calls
- This intentional asymmetry is because import directly modifies Home Assistant state, export uses recorder API
- Services are registered in `setup()` which is synchronous, but the export handler's async nature is preserved

### Timezone Handling Philosophy
- The integration uses `zoneinfo.ZoneInfo` (Python 3.12 stdlib), NOT `pytz` (external package)
- This is a deliberate choice - pytz is imported only for validation of timezone identifier strings
- Import interprets user-provided timestamps in the user's timezone, converts to UTC internally
- Export reverses this: takes UTC timestamps from recorder, formats them in user's timezone
- The default format `"%d.%m.%Y %H:%M"` (DD.MM.YYYY HH:MM) reflects European preferences - no seconds, 24-hour format

### Error Handling Philosophy
- The codebase uses a custom error pattern: [`handle_error()`](custom_components/import_statistics/helpers.py:240) logs AND raises
- This pattern allows Home Assistant UI to display the error message to users while also logging it
- It's not a generic exception handling pattern - it's specific to Home Assistant's error display mechanism

## Code Organization Philosophy

### Separation of Concerns
- `__init__.py`: Service registration and HA integration points only
- `helpers.py`: Validation, transformation, and utility functions
- `prepare_data.py`: Data loading, processing, and export preparation
- `const.py`: Constants and attribute names
- This clean separation means each module can be tested independently

### Validation Is Distributed
- Column validation happens in `are_columns_valid()` BEFORE row processing
- Unit validation happens at unit extraction time in `add_unit_to_dataframe()`
- Min/max/mean validation happens during row processing in `get_mean_stat()`
- Full hour validation happens during row processing in `is_full_hour()`
- This distributed validation means early errors catch problems, but row processing can still fail

### DataFrame Usage Pattern
- Uses pandas for CSV reading convenience, but doesn't heavily rely on pandas features
- Custom iteration with `df.iterrows()` suggests developer preference for explicit control
- Column validation before iteration ensures no surprises during row processing
- Empty dict appends (when row validation fails) suggest silent skipping rather than strict validation

## Testing & Development Context

### Import Paths
- Tests import from `custom_components.import_statistics` - this path is set via PYTHONPATH in `scripts/develop`
- Allows tests to run without installation while maintaining proper import structure
- The develop script sets `PYTHONPATH="${PYTHONPATH}:${PWD}/custom_components"` to enable this

### Test File Patterns
- Test files use `test_*.py` naming convention and reside in `tests/` directory
- pytest.ini specifies `testpaths = tests` - pytest ONLY looks in this directory
- Tests must construct Home Assistant mocks properly - see `test_handle_arguments.py` for ServiceCall pattern

### Configuration Philosophy
- Uses Home Assistant's built-in config validation system (`cv.empty_config_schema`)
- Services are called via Home Assistant's action system, not directly
- No persistent configuration stored by integration (stateless design)
