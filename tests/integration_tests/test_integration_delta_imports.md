# Integration Test for Delta Imports

This directory contains an integration test (`test_integration_delta_imports.py`) that tests the delta column import feature with a real Home Assistant instance and actual database operations.

## Prerequisites

1. **Home Assistant Running**: The test expects Home Assistant to be running with the import_statistics component loaded
2. **Test Entity**: The test will create a test entity `sensor.test_case_1` in Home Assistant
3. **Test Data Files**: Test data files are located in `config/test_delta/`:
   - `test_case_1_sum_state.txt` - Initial import with absolute values
   - `test_case_1_sum_delta_unchanged.txt` - Delta values (unchanged from reference)
   - `test_case_1_sum_delta_changed.txt` - Delta values (different from reference)

## Running the Test

### Step 1: Start Home Assistant

Open a terminal and start Home Assistant using the develop script:

```bash
cd /workspaces/homeassistant-statistics
scripts/develop
```

This will:
- Install dependencies
- Set up the PYTHONPATH to include the custom component
- Start Home Assistant on `http://localhost:8123`

**Wait for Home Assistant to fully start** (you should see messages indicating the recorder component is loaded).

### Step 2: Run the Integration Test

In a separate terminal, run:

```bash
cd /workspaces/homeassistant-statistics
python -m pytest tests/test_integration_delta_imports.py -v
```

The test will:
1. Wait up to 3 minutes for Home Assistant to be fully started
2. Copy test data files to the config directory
3. Import the first file (`test_case_1_sum_state.txt`) with absolute values
4. Verify the values are correctly stored in the database
5. Import the second file (`test_case_1_sum_delta_unchanged.txt`) with delta values
6. Verify the deltas are correctly accumulated
7. Import the third file (`test_case_1_sum_delta_changed.txt`) with different delta values
8. Verify the database is updated with the new delta calculations

## Test Workflow

The test validates the complete delta import workflow:

### Initial Import (sum_state)
```
sensor.test_case_1 at 2025-12-29 08:00:00: sum=0, state=10
sensor.test_case_1 at 2025-12-29 09:00:00: sum=1, state=12
...
```

### After Delta Unchanged Import
The deltas (1, 2, 3, ..., 11) are accumulated on top of the initial values:
```
sensor.test_case_1 at 2025-12-29 09:00:00: sum=1+1=2, state=12+1=13
sensor.test_case_1 at 2025-12-29 10:00:00: sum=1+3=4, state=14+3=17
...
```

### After Delta Changed Import
The deltas are different (0, 0, 0, 4, 5, ..., 11), so values are recalculated:
```
sensor.test_case_1 at 2025-12-29 09:00:00: sum=1+0=1, state=12+0=12
sensor.test_case_1 at 2025-12-29 10:00:00: sum=1+0=1, state=14+0=14
sensor.test_case_1 at 2025-12-29 12:00:00: sum=10+4=14, state=20+4=24
...
```

## Expected Behavior

✅ All assertions pass when:
- Home Assistant is running with recorder component
- The import_statistics service is available and working
- Test data files are correctly processed
- Database values match expected calculations after each import step

## Troubleshooting

### "Home Assistant did not start within 3 minutes"
- Check that `scripts/develop` is still running
- Check Home Assistant logs: `config/home-assistant.log`
- Verify recorder component is loaded

### Service call fails
- Check that Home Assistant is running on `http://localhost:8123`
- Verify the import_statistics component is loaded
- Check Home Assistant logs for errors

### Database values don't match
- Check the test data files in `config/test_delta/`
- Verify recorder database is accessible
- Review Home Assistant logs for import errors

## Files Involved

- **Test File**: `tests/test_integration_delta_imports.py` - Main integration test
- **Test Data**:
  - `config/test_delta/test_case_1_sum_state.txt`
  - `config/test_delta/test_case_1_sum_delta_unchanged.txt`
  - `config/test_delta/test_case_1_sum_delta_changed.txt`
- **Component**: `custom_components/import_statistics/` - The component being tested
- **Start Script**: `scripts/develop` - Starts Home Assistant for testing
