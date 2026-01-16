# Home Assistant Statistics Integration - Implementation Summary

## Project Overview
Home Assistant custom integration for importing/exporting long-term statistics from CSV/TSV/JSON files. Python 3.12, uses pandas, zoneinfo, Home Assistant recorder API.

## Recent Implementation Work (Jan 2025)

### Optional Entities Export Feature
**Status**: ✅ COMPLETED
**Description**: Modified export_statistics service to allow exporting all statistics when entities list is omitted or empty.

**Files Modified:**
1. `services.yaml` - Changed entities field from required: true to required: false
2. `export_service.py` - Added logic to fetch all statistic IDs using list_statistic_ids() when entities is None/empty
3. `translations/en.json` - Updated description to mention "Leave empty to export all statistics"
4. `docs/DrCoolzic/architecture.md` - Updated documentation with new feature and usage examples

**Key Changes:**
- Added import for list_statistic_ids from recorder API
- Modified get_statistics_from_recorder() to accept list[str] | None
- Added entity resolution step in architecture pattern
- Updated logging to show "ALL" when no entities specified

**Usage Examples:**
```yaml
# Export all statistics
action: import_statistics.export_statistics
data:
  filename: all_statistics.tsv
  start_time: "2025-12-22 12:00:00"
  end_time: "2025-12-25 12:00:00"
```

### Development Tools
**Clean Config Script**: Created `scripts/clean_config` for complete Home Assistant reset
- Removes all generated files including .storage/ for fresh start
- Preserves configuration.yaml, *.csv, test_*, *.md files
- Includes preview mode and permission error handling

**VS Code Tasks**: Added "Stop Home Assistant" task using bash/pkill for graceful shutdown

## Architecture Documentation
- Comprehensive architecture.md with Mermaid diagrams
- Module dependency diagram, class structure diagram, data flow diagrams
- Usage examples and implementation guides

## Critical Coding Patterns (from AGENTS.md)
- Error handling: Always use helpers.handle_error()
- Custom types: UnitFrom enum (ENTITY vs TABLE), DeltaReferenceType enum
- Validation: Strict DataFrame column rules, statistic ID format validation
- Timezone: Use zoneinfo.ZoneInfo, not pytz
- Delta processing: Forward/backward accumulation algorithms

## Testing Strategy
- Unit tests in tests/unit_tests/
- Integration tests with mocked HA in tests/integration_tests_mock/
- Real HA integration tests in tests/integration_tests/
- Use pytest with pytest-homeassistant-custom-component

## Open Questions & Future Considerations

### Potential Issues & Questions

**Question 1: Performance**
Exporting all statistics could be a large dataset. Should we:
- Add a warning log when exporting all?
- Add a configuration limit (e.g., max 1000 entities)?
**Recommendation**: Start simple, add warning log only

**Question 2: Empty Result**
What if the database has no statistics in the time range?
- Current behavior: Empty file is created
**Recommendation**: Keep current behavior, log info message

**Question 3: UI Behavior**
In the Home Assistant UI, when required: false:
- Field will be optional
- User can leave it blank
**Status**: Confirmed working as expected

## Development Workflow
1. Use ./scripts/develop to start HA with custom component
2. Use VS Code "Stop Home Assistant" task for graceful shutdown
3. Use ./scripts/clean_config for complete reset to fresh state
4. Use ./scripts/lint for code formatting and checking
