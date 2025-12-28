# Export Statistics Integration Tests - Summary

## Overview

Created comprehensive integration tests for the export statistics feature that mock Home Assistant and compare generated exports with reference files.

## Test Coverage

### Integration Tests (10 tests, 100% passing)

Located in: [tests/test_export_integration.py](tests/test_export_integration.py)

#### 1. File Format Tests
- **test_export_sensor_statistics_tsv** - Export sensor data (mean/min/max) to TSV format
- **test_export_counter_statistics_csv** - Export counter data (sum/state) to CSV format
- **test_export_mixed_statistics_semicolon_delimiter** - Export mixed sensor/counter data with semicolon delimiter

#### 2. JSON Structure Tests
- **test_export_sensor_to_json_format** - Validate JSON structure for sensor data
- **test_export_counter_to_json_format** - Validate JSON structure for counter data
- **test_export_mixed_to_json_format** - Validate JSON structure for mixed types

#### 3. Feature Tests
- **test_export_with_decimal_comma_format** - Decimal separator localization (comma)
- **test_export_with_custom_datetime_format** - Custom datetime format (ISO format)
- **test_export_with_timezone_conversion** - Timezone conversion (UTC to Europe/Vienna)

#### 4. File Generation Tests
- **test_export_file_existence_check** - Verify files are created and contain data

## Reference Files

Created reference files for comparing generated exports:

### TSV Reference Files
- [tests/testfiles/export_sensor_data.tsv](tests/testfiles/export_sensor_data.tsv)
  - Contains sensor statistics with mean, min, max values
  - Tab-separated format

- [tests/testfiles/export_mixed_data.tsv](tests/testfiles/export_mixed_data.tsv)
  - Contains both sensor and counter statistics
  - Semicolon-separated format
  - Shows how different types are handled in mixed exports

### CSV Reference Files
- [tests/testfiles/export_counter_data.csv](tests/testfiles/export_counter_data.csv)
  - Contains counter statistics with sum and state values
  - Comma-separated format

### JSON Reference Files (for documentation)
- [tests/testfiles/export_sensor_data.json](tests/testfiles/export_sensor_data.json)
- [tests/testfiles/export_counter_data.json](tests/testfiles/export_counter_data.json)
- [tests/testfiles/export_mixed_data.json](tests/testfiles/export_mixed_data.json)

## Test Architecture

### File Comparison Strategy

The tests use a `normalize_file_content()` helper that:
1. Strips trailing whitespace from each line
2. Normalizes line endings
3. For JSON files: parses and re-serializes for consistent formatting
4. Compares normalized content byte-by-byte with reference files

### HA Mocking Strategy

Tests mock Home Assistant components:
```python
hass = MagicMock()
hass.config = MagicMock()
hass.config.config_dir = tmpdir  # Use temp directory for exports
```

The mocked `hass` object:
- Allows service registration without a real HA instance
- Enables `get_statistics_from_recorder()` to work with mocked data
- Verifies file paths are constructed correctly

### Data Generation

Tests create representative mock statistics data:
- **Sensor data**: With mean, min, max values
- **Counter data**: With sum and state values
- **Mixed data**: Both sensor and counter statistics in one export

Example structure:
```python
mock_statistics = {
    "sensor.temperature": {
        "statistics": [
            {
                "start": datetime(...),
                "mean": 20.5,
                "min": 20.0,
                "max": 21.0,
            }
        ],
        "unit_of_measurement": "°C",
    }
}
```

## Test Results

```
tests/test_export_integration.py::...test_export_sensor_statistics_tsv        PASSED
tests/test_export_integration.py::...test_export_counter_statistics_csv       PASSED
tests/test_export_integration.py::...test_export_mixed_statistics_semicolon   PASSED
tests/test_export_integration.py::...test_export_sensor_to_json_format        PASSED
tests/test_export_integration.py::...test_export_counter_to_json_format       PASSED
tests/test_export_integration.py::...test_export_mixed_to_json_format         PASSED
tests/test_export_integration.py::...test_export_with_decimal_comma_format    PASSED
tests/test_export_integration.py::...test_export_with_custom_datetime_format  PASSED
tests/test_export_integration.py::...test_export_with_timezone_conversion     PASSED
tests/test_export_integration.py::...test_export_file_existence_check         PASSED

========== 10 passed ==========
```

## Complete Test Suite

Combined with existing tests, the total test coverage is now:

- **Total: 138 tests, 100% passing**
  - Export service tests (HA-dependent): 22 tests
  - Export data tests (HA-independent): 43 tests
  - Integration tests (mocked HA): 10 tests
  - Existing import tests: 63 tests

## Key Features Validated

✅ **File Format Support**
- TSV (tab-separated)
- CSV (comma-separated)
- Custom delimiters (semicolon, pipe)
- JSON structure

✅ **Statistics Type Support**
- Sensor statistics (mean, min, max)
- Counter statistics (sum, state)
- Mixed type exports

✅ **Localization Features**
- Timezone conversion
- Decimal separator localization
- Custom datetime formats

✅ **Error Handling**
- Invalid timezone handling
- Missing data validation
- File path construction

## Test Utilities

Helper functions for test infrastructure:

### load_reference_file(filename)
Loads reference files from `tests/testfiles/` directory

### normalize_file_content(content, is_json=False)
Normalizes files for comparison:
- Removes trailing whitespace
- Normalizes line endings
- Re-serializes JSON for consistent formatting

### load_reference_csv(filename)
Parses CSV/TSV files into list of dicts for validation

### load_reference_json(filename)
Parses JSON reference files for structure validation

## Integration Test Patterns

### Pattern 1: CSV/TSV File Comparison
```python
def test_export_sensor_statistics_tsv(self):
    # Setup mocked HA
    # Create statistics data
    # Call service handler
    # Compare generated file with reference
    assert generated_normalized == reference_normalized
```

### Pattern 2: JSON Structure Validation
```python
def test_export_sensor_to_json_format(self):
    # Call prepare_export_json directly
    # Validate structure (not file content)
    assert result[0]["id"] == "sensor.temperature"
    assert len(result[0]["values"]) == 2
```

### Pattern 3: Feature Validation
```python
def test_export_with_timezone_conversion(self):
    # Export with custom timezone
    # Verify datetime is converted (13:00 instead of 12:00)
    assert "13:00" in content
```

## Benefits

✅ **End-to-End Testing** - Tests the full export flow from service call to file output
✅ **HA Independence** - Validates functionality without running actual HA instance
✅ **Reference Comparison** - Catches unintended formatting changes
✅ **Feature Coverage** - Tests all export options and edge cases
✅ **Regression Prevention** - Maintains expected output format

## No Regressions

All existing tests continue to pass:
- 63 import_statistics tests: ✅ 100% passing
- 75 export tests (service + data + integration): ✅ 100% passing
- **Total: 138 tests passing**
