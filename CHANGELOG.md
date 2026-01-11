# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - Delta Import Feature

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
