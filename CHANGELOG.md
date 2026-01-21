# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Breaking Changes

- **Strict Row Validation**: All rows in import files must now be valid, or the entire import fails. Previously, invalid rows were silently skipped during import, which could lead to incomplete data without user awareness. Now, the first invalid row stops the import immediately with a clear error message indicating which row failed and why. This ensures data integrity and provides better feedback to users about data quality issues.
  - Modified validation functions: [`get_mean_stat()`](custom_components/import_statistics/helpers.py), [`get_sum_stat()`](custom_components/import_statistics/helpers.py), [`get_delta_stat()`](custom_components/import_statistics/helpers.py) now raise `HomeAssistantError` instead of returning empty dicts
  - Import behavior: All-or-nothing - either all rows are valid and imported, or the import fails on the first invalid row
  - Error messages: Clear, actionable feedback showing exactly which row failed and what validation error occurred
  - Impact: Users may discover data quality issues in their import files that were previously hidden. This is intentional and beneficial for data integrity.

## [3.2.0] - Service Parameter Improvements

### Changed

#### Breaking Changes

- **Decimal separator parameter format**: Changed from boolean to explicit string selector
  - **Old format**: `decimal: false` (dot) or `decimal: true` (comma)
  - **New format**: `decimal: "."` or `decimal: ","`
  - **Migration**: Replace `decimal: false` with `decimal: "."` and `decimal: true` with `decimal: ","`
  - **Reason**: More explicit and intuitive; eliminates confusion about boolean meaning
  - **Applies to**: Both `import_from_file` and `export_statistics` services

#### Improvements

- **Timezone parameter now optional with smart default**:
  - Defaults to Home Assistant's configured timezone when omitted
  - No longer need to specify timezone for most users
  - Still accepts explicit timezone identifier for special cases
  - **Applies to**: Both `import_from_file` and `export_statistics` services

- **Delimiter parameter now required with sensible default**:
  - Changed from optional (auto-detect) to required with default `\t` (tab)
  - Eliminates ambiguity and potential parsing errors from auto-detection
  - UI provides dropdown with common delimiters: tab, semicolon, comma, pipe
  - **Applies to**: Both `import_from_file` and `export_statistics` services

### Migration Guide

See [`docs/user/migration-guide-v3.2.md`](docs/user/migration-guide-v3.2.md) for detailed migration instructions and examples.

## [3.1.0] - File Encoding Validation and Export Enhancements

### Added

#### File Encoding Validation

- **UTF-8 encoding validation for import files**: Automatically detects and reports encoding issues before processing
  - Prevents import failures due to encoding problems with special characters in units

#### Export Enhancements

- **Optional `entities` parameter**: Export all statistics when `entities` is omitted or empty
  - Previously required; now defaults to exporting all available statistics
- **Optional `start_time` parameter**: Export from earliest available statistics when omitted
  - Allows exporting complete historical data without knowing the exact start date
- **Optional `end_time` parameter**: Export up to most recent statistics when omitted
  - Allows exporting all data up to present without specifying end date
- **Split statistics option**: New `split_statistics` parameter to separate sensors and counters into different files
  - When `true`, creates separate files: `filename_sensors.ext` and `filename_counters.ext`
  - Useful for re-importing data since `import_from_file` accepts only one type per file
  - Works with both specific entity lists and "export all" mode
- **Max statistics limit**: New `max_statistics` parameter to limit the number of statistic IDs exported
  - Default: 1000 statistic IDs per export operation
  - Helps manage large datasets and reduce file size/memory usage
  - Statistic IDs are sorted deterministically before applying the limit

#### Documentation
- **New troubleshooting guide**: Added comprehensive [`docs/user/troubleshooting-tips.md`](docs/user/troubleshooting-tips.md) covering:
  - Installation issues
  - File format problems (column names, delimiters, encoding)
  - Timestamp format requirements
  - Common error messages and solutions
- **Enhanced developer documentation**: Improved [`docs/dev/README.md`](docs/dev/README.md) with detailed setup and testing instructions
- **Improved counter documentation**: Enhanced [`docs/user/counters.md`](docs/user/counters.md) with clearer explanations
- **Architecture documentation**: Moved and improved architecture documentation to [`docs/dev/architecture.md`](docs/dev/architecture.md)
- **Enhanced README.md**: Significantly improved user documentation with:
  - Better table formatting for all sections
  - Comprehensive export options documentation with detailed parameter descriptions
  - Multiple YAML examples for common export scenarios (selected entities, all statistics, split files, max statistics limit)
  - Clearer structure and improved readability throughout

### Changed

#### Export Behavior
- **More flexible export parameters**: `entities`, `start_time`, and `end_time` are now all optional
  - Backward compatible: existing service calls continue to work unchanged
  - Enables new use cases: full backups, open-ended time ranges, all statistics exports

#### Error Messages
- **Improved column validation error messages**: More descriptive errors when unknown columns are detected
  - Now lists all invalid columns found in the file
  - Helps users quickly identify delimiter problems, typos, incorrect column names

### Fixed

- **Type hints and code quality**: Fixed Pylance type checking issues throughout the codebase

## [3.0.1] - Bug Fixes For Delta Import/Export Feature

### Fixed

#### Timestamp Sorting and Processing
- **Fixed timestamp sorting in CSV/TSV exports**: Export now sorts by numeric timestamps instead of formatted strings
  - Before the values in the delta column have been wrong because of the wrong sorting
- **Fixed timestamp range detection for imports**:
  - Previously used string min/max which gave alphabetical order instead of chronological
  - Affects both delta and non-delta imports when validating timestamp ranges
  - Could cause incorrect reference selection for delta conversion or incorrect future timestamp validation
  - Now ensures correct chronological order when determining import time ranges

## [3.0.0] - Delta Import Feature

### Added

#### Delta Import Support
- **Delta column import**: Import counter statistics using delta (change) values instead of absolute sum/state values
  - Automatically detects when a `delta` column is present in the import file
  - Converts delta values to absolute sum/state values using existing database values as reference points
  - Supports three scenarios:
    1. Import before oldest database value (backward calculation)
    2. Import after newest database value (forward accumulation)
    3. Import in the middle of existing range (overwrites with new deltas)

#### Validation
- Timestamp validation to prevent future values

### Changed

#### Import Behavior
- **Import is now synchronous**: The import action waits until all data is committed to the database before returning
  - Provides immediate feedback on import completion
  - Eliminates race conditions when chaining imports

#### Export Enhancement
- Export now includes calculated `delta` column for counter statistics
- Delta column shows the change between consecutive hours
- Exported files can be directly used for delta imports (after removing sum/state columns)

### Migration Notes

This is a backward-compatible change. Existing imports using sum/state columns continue to work as before. The new delta import functionality is automatically activated when a `delta` column is detected in the import file.

No action required for existing users. New delta import feature is opt-in by using the delta column.

