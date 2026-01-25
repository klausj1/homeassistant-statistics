# Changelog

All notable changes to this project will be documented in this file.

## [4.0.0] - Wild card based export, export all, developer docu, service parameter improvements

### Breaking Changes

- **Strict Row Validation**: All rows in import files must now be valid, or the entire import fails. Previously, invalid rows were silently skipped during import, which could lead to incomplete data without user awareness. Now, the first invalid row stops the import immediately with a clear error message indicating which row failed and why. This ensures data integrity and provides better feedback to users about data quality issues.

- **Decimal separator parameter format**: Changed from boolean to explicit string selector
  - **Old format**: `decimal: false` (dot) or `decimal: true` (comma)
  - **New format**: `decimal: "dot ('.')"` or `decimal: "comma (',')"`
  - **Migration**: Replace `decimal: false` with `decimal: "dot ('.')"` and `decimal: true` with `"comma (',')"`
  - **Reason**: More explicit and intuitive; eliminates confusion about boolean meaning
  - **Applies to**: Both `import_from_file` and `export_statistics` services

### Changes

#### Export improvements

- **Optional `entities` parameter**: Export all statistics when `entities` is omitted or empty
  - Previously required; now **defaults to exporting all** available statistics
  - entities parameter now accepts **glob patterns using `*` (e.g. `sensor.*_temperature`)**. Useful when exporting a subset of statistic IDs without enumerating them all.
- **Optional `start_time` parameter**: Export from earliest available statistics when omitted
  - Allows exporting complete historical data without knowing the exact start date
- **Optional `end_time` parameter**: Export up to most recent statistics when omitted
  - Allows exporting all data up to present without specifying end date
- **Split statistics option**: New `split_by` parameter to separate sensors and counters into different files
  - When `true`, creates separate files: `filename_sensors.ext` and `filename_counters.ext`
  - Useful for re-importing data since `import_from_file` accepts only one type per file
  - Works with both specific entity lists and "export all" mode
- **Max statistics limit**: New `max_statistics` parameter to limit the number of statistic IDs exported
  - Default: 1000 statistic IDs per export operation
  - Helps manage large datasets and reduce file size/memory usage
  - Statistic IDs are sorted deterministically before applying the limit

#### UI Improvements

- **Enhanced service UI**: The import and export service forms now have improved organization with collapsible sections and better field grouping for easier configuration
- **Decimal delimiter clarity**: The decimal parameter now shows explicit labels like "dot ('.')" and "comma (',')" instead of confusing boolean values, making it clearer which format to use

#### Parameter improvements

- **Timezone parameter now optional, uses HA timezone as default**:
  - Defaults to Home Assistant's configured timezone when omitted
  - No longer need to specify timezone for most users
  - Still accepts explicit timezone identifier for special cases
  - **Applies to**: Both `import_from_file` and `export_statistics` services

- **Delimiter parameter now required with tab as default**:
  - Changed from optional (auto-detect) to required with default `\t` (tab)
  - Auto-detection has been removed as it does not work reliably
  - Eliminates ambiguity and potential parsing errors from auto-detection
  - UI provides dropdown with common delimiters: tab, semicolon, comma, pipe
  - **Applies to**: Both `import_from_file` and `export_statistics` services

#### File Encoding Validation

- **UTF-8 encoding validation for import files**: Automatically detects and reports encoding issues before processing
  - Prevents import failures due to encoding problems with special characters in units

#### Developer habitability

- **Added VSCode tasks** for easier development (see [`docs/dev/vscode_tasks.md`](docs/dev/vscode_tasks.md))
  - Tasks for linting, testing, and running Home Assistant

#### Documentation improvements

- **New troubleshooting guide**: Added comprehensive [`docs/user/troubleshooting-tips.md`](docs/user/troubleshooting-tips.md) covering:
  - Installation issues
  - File format problems (column names, delimiters, encoding)
  - Timestamp format requirements
  - Common error messages and solutions
- **Enhanced developer documentation**: Improved [`docs/dev/README.md`](docs/dev/README.md) with detailed setup and testing instructions
- **Improved counter documentation**: Enhanced [`docs/user/counters.md`](docs/user/counters.md) with clearer explanations
- **Developer workflow documentation**: Added comprehensive guides for contributors:
  - [`docs/dev/vscode_debugging.md`](docs/dev/vscode_debugging.md) - VSCode debugging setup and configuration
  - [`docs/dev/vscode_tasks.md`](docs/dev/vscode_tasks.md) - VSCode tasks for common development workflows
  - [`docs/dev/pr_process.md`](docs/dev/pr_process.md) - Pull request process and guidelines
- **Architecture documentation**: Moved and improved architecture documentation to [`docs/dev/architecture.md`](docs/dev/architecture.md)
- **Enhanced README.md**: Significantly improved user documentation with:
  - Better table formatting for all sections
  - Comprehensive export options documentation with detailed parameter descriptions
  - Multiple YAML examples for common export scenarios (selected entities, all statistics, split files, max statistics limit)
  - Clearer structure and improved readability throughout
- **Debug logging guide**: Added comprehensive documentation on how to enable and use debug logging for troubleshooting ([`docs/user/debug-logging.md`](docs/user/debug-logging.md))

### Bug Fixes

- **Better error messages**: Export now provides clearer error messages when no data is found for the specified entities or time range, or when there is no data in the database at all ([#167](https://github.com/klausj1/homeassistant-statistics/issues/167))
- **Improved column validation error messages**: More descriptive errors when unknown columns are detected
  - Now lists all invalid columns found in the file
  - Helps users quickly identify delimiter problems, typos, incorrect column names

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

