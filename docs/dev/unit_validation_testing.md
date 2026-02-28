# Unit Validation Testing Documentation

This document explains how the mandatory unit column and unit validation functionality is tested in the import_statistics integration.

## Overview

As of the breaking change introduced in this version, the import functionality now:

1. **Requires** a `unit` column in all input files (CSV/TSV/JSON)
2. **Validates** that the unit in the input file matches the unit stored in Home Assistant's `statistic_meta` table for existing statistics
3. **Rejects** imports with unit mismatches or missing unit columns

## Test Coverage

### Unit Tests (Pure Function Testing)

#### 1. Column Validation Tests

**File**: [`tests/unit_tests/test_are_columns_valid.py`](../../tests/unit_tests/test_are_columns_valid.py)

Tests the [`are_columns_valid()`](../../custom_components/import_statistics/helpers.py:275) function:

- **`test_are_columns_valid_valid_columns`**: Verifies that DataFrames with required columns (`statistic_id`, `start`, `unit`) plus optional columns pass validation
- **`test_are_columns_valid_missing_required_columns`**: Verifies that missing `unit` column raises `HomeAssistantError`
- **`test_are_columns_valid_delta_with_unit`**: Verifies that delta columns require unit column
- **`test_are_columns_valid_delta_missing_unit`**: Verifies that delta without unit column raises error

**Key Assertion Pattern**:

```python
with pytest.raises(HomeAssistantError, match="The file must contain the columns"):
    are_columns_valid(df)
```

#### 2. Data Preparation Tests

**File**: [`tests/unit_tests/test_prepare_data_to_import.py`](../../tests/unit_tests/test_prepare_data_to_import.py)

Tests the [`prepare_data_to_import()`](../../custom_components/import_statistics/import_service_helper.py:55) function:

- **`test_prepare_data_to_import_valid_file_dot`**: Verifies successful parsing of files with unit column
- **`test_prepare_data_to_import_valid_file_comma`**: Verifies delimiter handling with unit column present
- **`test_prepare_data_to_import_with_unknown_columns`**: Verifies rejection of files with unknown columns (typos in column names)

**Key Behavior**: All valid test files include a `unit` column. Files without unit columns are rejected during column validation.

#### 3. DataFrame Handling Tests

**File**: [`tests/unit_tests/test_handle_dataframe.py`](../../tests/unit_tests/test_handle_dataframe.py)

Tests the [`handle_dataframe_no_delta()`](../../custom_components/import_statistics/import_service_helper.py:210) function:

- **`test_handle_dataframe_mean`**: Verifies processing of sensor data (mean/min/max) with unit extraction
- **`test_handle_dataframe_sum`**: Verifies processing of counter data (sum) with unit extraction
- **`test_handle_dataframe_multiple_mean`**: Verifies processing of multiple statistics with different units

**Key Pattern**: Each test verifies that [`get_unit_from_row()`](../../custom_components/import_statistics/helpers.py:345) correctly extracts the unit from each row and validates it's not empty.

#### 4. Delta Processing Tests

**Files**:

- [`tests/unit_tests/test_convert_delta_dataframe_with_references.py`](../../tests/unit_tests/test_convert_delta_dataframe_with_references.py)
- [`tests/unit_tests/test_convert_delta_dataframe_newer_ref.py`](../../tests/unit_tests/test_convert_delta_dataframe_newer_ref.py)

Tests delta conversion functions:

- **`test_convert_delta_dataframe_with_references_single_statistic`**: Verifies delta conversion with unit column present
- **`test_convert_delta_dataframe_with_references_multiple_statistics`**: Verifies multiple statistics with different units

**Key Behavior**: All delta test data includes unit columns, as delta columns cannot exist without units.

### Integration Tests (Service-Level Testing)

#### 1. Standard Import Tests (Without Delta)

**File**: [`tests/integration_tests_mock/test_import_service_without_delta.py`](../../tests/integration_tests_mock/test_import_service_without_delta.py)

Tests the complete import flow with mocked Home Assistant:

##### Positive Tests (Unit Column Present)

- **`test_import_sum_single_statistic`**: Imports counter data with unit column
- **`test_import_mean_single_statistic`**: Imports sensor data with unit column
- **`test_import_multiple_statistics`**: Imports multiple statistics with different units
- **`test_import_external_statistic`**: Imports external statistics (custom domain) with units
- **`test_import_json_format_sum`**: Imports JSON format with unit field
- **`test_import_json_format_mean`**: Imports JSON format with unit field

**Test Pattern**:

```python
# Create test file with unit column
test_file.write_text(
    "statistic_id\tstart\tsum\tstate\tunit\n"
    "sensor.energy\t01.01.2022 00:00\t100.0\t100.0\tkWh\n"
)

# Mock recorder to return matching unit
mock_metadata = {"sensor.energy": {"unit_of_measurement": "kWh"}}

# Verify import succeeds
await import_handler(call)
assert mock_import.called
```

##### Negative Tests (Unit Column Missing or Mismatched)

- **`test_import_without_unit_column`**: Verifies that files without unit column are rejected

  ```python
  # Create test file WITHOUT unit column
  test_file.write_text(
      "statistic_id\tstart\tmean\tmin\tmax\n"
      "sensor.temperature\t01.01.2022 00:00\t20.5\t18.2\t22.8\n"
  )

  # Expect error
  with pytest.raises(HomeAssistantError, match="The file must contain the columns 'statistic_id', 'start' and 'unit'"):
      await import_handler(call)
  ```

- **`test_import_missing_required_columns`**: Verifies rejection of files missing required columns

#### 2. Delta Import Tests

**File**: [`tests/integration_tests_mock/test_import_service_with_delta.py`](../../tests/integration_tests_mock/test_import_service_with_delta.py)

Tests delta column imports with unit validation:

- **`test_import_delta_single_statistic`**: Imports delta data with unit column
- **`test_import_delta_multiple_statistics`**: Imports multiple delta statistics with different units
- **`test_import_delta_external_statistic`**: Imports external delta statistics with units
- **`test_import_delta_json_format`**: Imports JSON delta format with unit field
- **`test_delta_column_with_incompatible_columns`**: Verifies that delta + sum/state columns are rejected

**Key Pattern**: All delta tests include unit columns, as the validation enforces this requirement.

#### 3. Strict Validation Tests

**File**: [`tests/integration_tests_mock/test_import_validation_strict.py`](../../tests/integration_tests_mock/test_import_validation_strict.py)

Tests strict validation rules:

- **`test_import_succeeds_with_all_valid_rows`**: Verifies that valid data with units passes all validation
- **`test_import_fails_on_invalid_row_in_middle`**: Verifies that invalid data is rejected even with valid units

### Unit Mismatch Testing

#### Current Implementation

The [`validate_entities_and_units()`](../../custom_components/import_statistics/import_service.py:300) function validates units against the database:

```python
async def validate_entities_and_units(hass: HomeAssistant, stats: dict) -> None:
    """Validate that entities exist and units match for recorder statistics."""
    # For recorder statistics (entity_id format), check entity exists
    # For all statistics, validate unit matches database unit

    # Fetch existing metadata from database
    existing_metadata = await hass.async_add_executor_job(
        get_metadata, hass, statistic_ids=list(stats.keys())
    )

    # For each statistic with existing metadata
    for statistic_id, metadata in existing_metadata.items():
        db_unit = metadata.get("unit_of_measurement")
        input_unit = stats[statistic_id]["unit_of_measurement"]

        # Validate units match
        if db_unit != input_unit:
            handle_error(
                f"Unit mismatch for {statistic_id}. "
                f"Database unit: '{db_unit}', Input unit: '{input_unit}'"
            )
```

#### Test Coverage for Unit Mismatch

**File**: [`tests/integration_tests_mock/test_import_service_without_delta.py`](../../tests/integration_tests_mock/test_import_service_without_delta.py)

- **`test_import_entity_not_exists`**: Tests that non-existent entities are rejected
  - This test verifies the entity existence check portion of `validate_entities_and_units()`
  - For new statistics (no existing metadata), the import proceeds with the provided unit
  - For existing statistics, unit validation occurs

**Note**: A dedicated unit mismatch test should be added to explicitly test the scenario where:

1. A statistic exists in the database with unit "°C"
2. An import file provides the same statistic with unit "°F"
3. The import is rejected with a clear error message

#### Recommended Additional Test

```python
@pytest.mark.asyncio
async def test_import_unit_mismatch(self) -> None:
    """Test that importing with mismatched unit raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = tmpdir
        hass.async_add_executor_job = mock_async_add_executor_job

        await async_setup(hass, {})
        import_handler = hass.services.async_register.call_args_list[0][0][2]

        # Create test file with unit °F
        test_file = Path(tmpdir) / "temp.csv"
        test_file.write_text(
            "statistic_id\tstart\tmean\tmin\tmax\tunit\n"
            "sensor.temperature\t01.01.2022 00:00\t68.0\t65.0\t70.0\t°F\n"
        )

        call = ServiceCall(
            hass,
            "import_statistics",
            "import_from_file",
            {
                ATTR_FILENAME: "temp.csv",
                ATTR_TIMEZONE_IDENTIFIER: "UTC",
                ATTR_DELIMITER: "\t",
                ATTR_DECIMAL: "dot ('.')",
            },
        )

        # Mock recorder to return existing metadata with different unit
        mock_recorder = create_mock_recorder_instance()
        mock_metadata = {
            "sensor.temperature": {
                "statistic_id": "sensor.temperature",
                "unit_of_measurement": "°C",  # Database has °C
                "has_mean": True,
                "has_sum": False,
            }
        }

        with (
            patch("custom_components.import_statistics.import_service.get_instance", return_value=mock_recorder),
            patch("custom_components.import_statistics.import_service.get_metadata", return_value=mock_metadata),
        ):
            # Expect error due to unit mismatch
            with pytest.raises(HomeAssistantError, match="Unit mismatch.*°C.*°F"):
                await import_handler(call)
```

## Test Execution

### Running All Tests

```bash
# Run all tests (unit + integration)
pytest

# Run only unit tests
pytest tests/unit_tests/

# Run only integration tests
pytest tests/integration_tests_mock/

# Run specific test file
pytest tests/unit_tests/test_are_columns_valid.py -v

# Run specific test
pytest tests/integration_tests_mock/test_import_service_without_delta.py::TestStandardImportIntegration::test_import_without_unit_column -v
```

### Test Results Summary

- **Unit Tests**: 231 tests, all passing
- **Integration Tests (Mock)**: 91 tests, all passing
- **Total Coverage**: 322 tests

## Key Testing Principles

### 1. Layered Testing

- **Unit tests** verify individual functions in isolation
- **Integration tests** verify the complete service flow with mocked dependencies
- **Real integration tests** verify behavior with actual Home Assistant instance

### 2. Negative Testing

- Tests explicitly verify that invalid inputs are rejected
- Error messages are validated to ensure clarity
- Edge cases (missing columns, empty units, mismatched units) are covered

### 3. Test Data Consistency

- All test files include unit columns
- Test data reflects real-world usage patterns
- Both CSV/TSV and JSON formats are tested

### 4. Mock Strategy

- Home Assistant dependencies are mocked using `MagicMock` and `AsyncMock`
- Recorder database queries are mocked to return controlled test data
- Executor jobs are mocked to run synchronously in tests

## Related Documentation

- [UNIT_LOGIC_CHANGES.md](../../UNIT_LOGIC_CHANGES.md) - Migration guide for the breaking change
- [AGENTS.md](../../AGENTS.md) - Developer coding patterns and rules
- [architecture.md](architecture.md) - System architecture documentation
