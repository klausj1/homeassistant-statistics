# AGENTS.md - Architect Mode

This file provides non-obvious architectural constraints and design patterns discovered in this repository.

## Architectural Constraints & Decisions

### Dual-Mode Statistics System
The architecture supports two mutually exclusive statistic types that require different validation paths:

**Internal Statistics (recorder source)**
- Format: `sensor.name` (uses `.` separator)
- Source: Existing Home Assistant entities
- Unit source: Flexible - can come from entity OR from CSV
- Validation: Entity must exist in Home Assistant state
- Use case: Importing historical data for existing sensors

**External Statistics (custom sources)**
- Format: `domain:name` (uses `:` separator)
- Source: New statistics created by import
- Unit source: MUST come from CSV (unit_from_entity forbidden)
- Validation: Domain cannot be "recorder"
- Use case: Creating synthetic or third-party statistics

This duality is enforced throughout the codebase and represents a fundamental architectural decision. Mixing modes for a single statistic_id is impossible and explicitly forbidden.

### Asymmetric Import/Export Design
The architecture intentionally treats import and export differently:

**Import Path**
- Synchronous processing (blocking operations)
- Stateless service handlers in `setup()`
- Strict validation: rejects mixed sensor/counter data
- Direct Home Assistant state modification
- Format: CSV/TSV or JSON

**Export Path**
- Asynchronous processing with executor calls for I/O
- Recorder API for data retrieval (database queries)
- Allows mixed sensor/counter data in output
- Formatted via timezone-aware transformations
- Format: CSV/TSV (data is sparse) or JSON (data is complete)

This asymmetry exists because import is stateful (modifies Home Assistant) while export is read-only (queries recorder).

### Validation Pipeline Architecture
Validation is distributed across multiple stages rather than centralized:

1. **Pre-processing**: File path security, delimiter normalization
2. **Column-level**: [`are_columns_valid()`](custom_components/import_statistics/helpers.py:197) validates structure
3. **Row-level**: During iteration, individual functions validate values
4. **Constraint-level**: Min/max/mean relationships validated during row processing

This pipeline design means:
- Early validation catches structural problems (missing columns, unknown columns)
- Later validation catches logical problems (constraint violations)
- Silent failures occur at row level (invalid rows append empty dicts)
- No transaction rollback - partial imports succeed if some rows validate

### Unit Extraction Architecture
Unit handling goes through a deliberate conversion pipeline:

```
CSV file → UnitFrom enum → add_unit_to_dataframe() → metadata dict → Home Assistant
```

The pipeline enforces:
- Source type (recorder vs external) determines unit source validity
- External statistics cannot use entity-based units (architectural constraint)
- Internal statistics are flexible (can use either source)
- Unit validation happens during extraction, not at column validation

### Timezone Conversion Architecture
Timezone handling is bidirectional and context-specific:

**Import Path**: User timezone → UTC conversion
- User provides timestamps in their local timezone
- Parsed with user's timezone info
- Converted to UTC for internal storage
- zoneinfo.ZoneInfo used for user timezone

**Export Path**: UTC → User timezone conversion
- Recorder stores all timestamps in UTC
- Converted to user's timezone for display
- Formatted using user's preferred datetime format
- zoneinfo.ZoneInfo used for user timezone

This bidirectional design means timezone identifier must be valid in BOTH directions (checked against pytz.all_timezones).

### Service Handler Pattern
The `setup()` function demonstrates an architectural pattern where services are registered with mixed sync/async handlers:

- `setup()` itself is synchronous (required by Home Assistant)
- Import handlers are synchronous closures that directly modify state
- Export handler is async, preserving async semantics for executor calls
- This pattern allows Home Assistant to call services synchronously while export operations remain async internally

The pattern is necessary because:
- Home Assistant's `hass.services.register()` expects synchronous registration
- But `handle_export_statistics` must be async to use `await hass.async_add_executor_job()`
- Python allows this mixing: `setup()` can register an async handler even though `setup()` is sync

### File Path Security Architecture
File path validation uses a defense-in-depth approach:

1. Reject absolute paths (start with `/`)
2. Reject path separators (contain `/` or `\`)
3. Reject traversal sequences (contain `..`)
4. Resolve the final path using `Path.resolve()`
5. Verify resolved path is within config_dir using `Path.relative_to()`

This multi-stage approach prevents multiple categories of attacks while being clear about each stage's purpose.

### Data Format Asymmetry
A key architectural constraint: export can produce mixed data, import cannot.

**Why this exists**:
- Export queries recorder which may contain both sensor and counter statistics
- Forcing separate exports would lose context (which statistics go together)
- Import doesn't support mixed data because statistic_id format determines type (sensor vs counter)
- Users must export mixed, then split for import if needed

This asymmetry is documented but not enforced at the API level - it's a user responsibility.

## Component Interaction Pattern

The architecture follows this data flow:

```
Service Call → Validation → DataFrame Processing → Metadata Building → HA API Call
```

Each stage is separable:
- `prepare_data.py`: Handles data loading and transformation (testable independently)
- `helpers.py`: Provides validation and utility functions (no HA dependencies)
- `__init__.py`: Orchestrates integration with Home Assistant (requires mocks for testing)

This separation means:
- Core logic can be tested without Home Assistant mocks
- Validation can be tested independently of data sources
- HA integration can be tested with appropriate fixtures

## Ruff Configuration as Architecture
The project enforces strict code style as part of architecture:

- Line length: 160 characters (allows more verbose, explicit code)
- MCCabe complexity: 25 maximum (encourages extracting helpers)
- All linting rules enabled (enforces consistent patterns)
- Type hints required (enforces explicit types)

These constraints drive architectural decisions:
- Functions split to stay under complexity limit
- Imports organized strictly (linting rules enforce order)
- Type hints used for validation boundaries (Where pandas types meet Home Assistant types)
