# Integration Tests (Real Home Assistant)

This directory contains integration tests that require a running Home Assistant instance.

## Important Notes

⚠️ **These tests are NOT run in CI/CD pipelines** - they require a real Home Assistant instance with web server and authentication.

✅ **Mock integration tests** in `tests/integration_tests_mock/` ARE run in CI/CD and provide good coverage without requiring a real HA instance.

## Running Integration Tests Locally

### Prerequisites

1. **Set up authentication token**:

   ```bash
   source .env  # Sets HA_TOKEN_DEV environment variable
   ```

2. **Ensure dependencies are installed**:

   ```bash
   pip install -r requirements.txt
   pip install -r requirements.test.txt
   ```

### Running the Tests

**Option 1: With existing Home Assistant instance**
If you already have Home Assistant running on `http://localhost:8123`:

```bash
pytest -v tests/integration_tests
```

**Option 2: Let tests start Home Assistant**
If no HA instance is running, the tests will automatically start one:

```bash
pytest -v tests/integration_tests
```

The tests will:

- Detect if HA is already running
- If not, start HA via `scripts/develop`
- Run all integration tests
- Stop HA if it was started by the tests

### Test Execution Order

Integration tests run sequentially in this order:

1. `test_01_import_sensor_mean_min_max_then_changes` - Sensor imports
2. `test_02_import_counter_sum_state_then_changes` - Counter imports
3. `test_03_import_sum_state_then_delta_unchanged_then_delta_changed` - Delta imports
4. `test_04_export_parameter_variations` - Export variations (depends on data from tests 1-3)

All tests share the same Home Assistant instance to avoid startup overhead.

### Troubleshooting

**Missing HA_TOKEN_DEV**:

```bash
# Check if token is set
echo $HA_TOKEN_DEV

# If empty, source the .env file
source .env
```

**Home Assistant fails to start**:

- Check that `scripts/develop` works: `./scripts/develop`
- Some dependencies (ffmpeg, frontend) may fail but tests should still work
- Check logs in the test output for HA startup errors

**Port 8123 already in use**:

- Stop any existing Home Assistant instances
- Or let the tests use the existing instance (ensure it has a clean database)

## CI/CD Behavior

Integration tests are marked with `@pytest.mark.integration` and are **skipped in CI/CD** via:

```bash
pytest -v -m "not integration"
```

This ensures:

- ✅ Unit tests run in CI
- ✅ Mock integration tests run in CI
- ❌ Real integration tests are skipped in CI (run manually before releases)
