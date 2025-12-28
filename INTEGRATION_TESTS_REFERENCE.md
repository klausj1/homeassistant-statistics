# Integration Tests Quick Reference

## Running Integration Tests

```bash
# Run all integration tests
pytest tests/test_export_integration.py -v

# Run specific test
pytest tests/test_export_integration.py::TestExportIntegration::test_export_sensor_statistics_tsv -v

# Run with output
pytest tests/test_export_integration.py -v -s

# Run all tests (unit + service + integration + existing)
pytest tests/ -v
```

## Test Organization

### Directory Structure
```
tests/
├── test_export_integration.py    # Integration tests (NEW)
├── test_export_service.py        # Service handler tests
├── test_prepare_export_data.py   # Data function tests
├── testfiles/
│   ├── export_sensor_data.tsv    # TSV reference
│   ├── export_counter_data.csv   # CSV reference
│   ├── export_mixed_data.tsv     # Mixed type reference
│   ├── export_sensor_data.json   # JSON reference
│   ├── export_counter_data.json  # JSON reference
│   └── export_mixed_data.json    # JSON reference
└── (existing import tests...)
```

## Test Types Explained

### Unit Tests (test_prepare_export_data.py)
- Test pure Python functions
- No HA dependency
- 43 tests covering:
  - Datetime formatting with timezones
  - Decimal separator localization
  - Statistic type detection
  - Data transformation
  - File I/O operations
  - JSON export structure

### Service Tests (test_export_service.py)
- Test HA service handler
- Mock HA instance
- 22 tests covering:
  - Recorder API wrapper (10 tests)
  - Service handler with all options (12 tests)

### Integration Tests (test_export_integration.py) - NEW
- Test end-to-end workflow
- Mock HA instance
- Compare generated files with references
- 10 tests covering:
  - TSV export with sensor data
  - CSV export with counter data
  - Mixed type exports
  - JSON structure validation
  - Feature options (timezone, datetime format, decimal separator)
  - File generation verification

## Key Test Patterns

### Pattern 1: File Comparison
```python
def test_export_sensor_statistics_tsv(self):
    # 1. Setup mocked HA
    hass = MagicMock()
    hass.config = MagicMock()
    hass.config.config_dir = tmpdir

    # 2. Create mock statistics
    mock_statistics = {
        "sensor.temperature": {
            "statistics": [...],
            "unit_of_measurement": "°C"
        }
    }

    # 3. Call service handler
    service_handler(call)

    # 4. Compare files
    assert generated_normalized == reference_normalized
```

### Pattern 2: JSON Structure Validation
```python
def test_export_sensor_to_json_format(self):
    # Call function directly (not through service)
    result = prepare_export_json(mock_statistics, "UTC", format)

    # Validate structure
    assert len(result) == 2
    assert result[0]["id"] == "sensor.temperature"
    assert all("datetime" in v for v in result[0]["values"])
```

### Pattern 3: Feature Validation
```python
def test_export_with_timezone_conversion(self):
    # Export with custom timezone
    call = ServiceCall(..., {
        ATTR_TIMEZONE_IDENTIFIER: "Europe/Vienna"
    })

    # Verify datetime is converted
    assert "13:00" in content  # UTC 12:00 → Vienna 13:00
```

## Helper Functions

### normalize_file_content(content, is_json=False)
Normalizes content for comparison:
- Removes trailing whitespace
- Normalizes line endings
- For JSON: re-serializes for consistent formatting

### load_reference_file(filename)
Loads reference file from `tests/testfiles/`

### load_reference_csv(filename)
Parses CSV/TSV into list of dicts

### load_reference_json(filename)
Parses JSON reference file

## Reference Files Format

### TSV Format (Tab-Separated)
```
statistic_id    unit    start           min     max     mean
sensor.temp     °C      26.01.2024 12:00        20      21      20.5
```

### CSV Format (Comma-Separated)
```
statistic_id,unit,start,sum,state
counter.energy,kWh,26.01.2024 12:00,10.5,100
```

### Mixed Format (Semicolon-Separated)
```
statistic_id;unit;start;min;max;mean;sum;state
sensor.temp;°C;26.01.2024 12:00;20;21;20.5;;
counter.energy;kWh;26.01.2024 12:00;;;;10.5;100
```

### JSON Format
```json
{
  "sensor.temperature": {
    "unit_of_measurement": "°C",
    "statistics": [
      {
        "start": "2024-01-26 12:00:00",
        "mean": 20.5,
        "min": 20.0,
        "max": 21.0
      }
    ]
  }
}
```

## Updating Reference Files

When intentional changes are made to export format:

1. Generate new output
2. Verify it's correct
3. Update reference files in `tests/testfiles/`
4. Run tests to verify they pass

```python
# Generate current output
python3 << 'EOF'
from custom_components.import_statistics import setup
# ... generate statistics ...
# Copy output to reference file
EOF
```

## Troubleshooting

### Test Fails: AssertionError on file comparison
1. Check if actual output format changed
2. Regenerate reference file if change is intentional
3. Or fix code if change is unintended

### Test Fails: TypeError on JSON
- Ensure prepare_export_json returns list, not string
- JSON export tests validate structure, not raw JSON

### Test Fails: AttributeError on hass.config
- Use `hass = MagicMock()` without spec
- Manually set nested attributes: `hass.config = MagicMock()`

## Maintenance

### Adding New Integration Test
1. Create test method in TestExportIntegration
2. Follow existing patterns
3. Use meaningful test names
4. Add docstring describing what's tested
5. Update reference files if needed
6. Run test locally before committing

### Updating Reference Files
1. Verify new format is correct
2. Update corresponding reference file
3. Run tests to confirm they pass
4. Commit reference file changes with code changes

## Coverage Goals

- All export formats: ✅ Tested
- All statistics types: ✅ Tested
- All localization options: ✅ Tested
- Error scenarios: ✅ Tested (in unit/service tests)
- File I/O operations: ✅ Tested
- Mixed type exports: ✅ Tested

## Integration with CI/CD

Tests are designed to run in CI/CD:
- No external dependencies
- Use temporary directories
- All mocked (no real HA instance needed)
- Deterministic output
- Reference files enable regression detection
