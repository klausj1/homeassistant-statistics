# Test Execution Guide

## Sequential Test Execution

By default, pytest runs tests in this order:
1. **unit_tests** - Unit tests (runs first)
2. **integration_tests_mock** - Integration tests with mocks (runs only if unit_tests pass)
3. **integration_tests** - Full integration tests (runs only if integration_tests_mock pass)

If any test suite fails, subsequent test suites are **skipped**.

```bash
# Run all tests sequentially with automatic dependencies
pytest
```

## Running Individual Test Suites

### Unit Tests Only
```bash
pytest tests/unit_tests
```

### Integration Tests with Mocks Only
```bash
pytest tests/integration_tests_mock
```

### Full Integration Tests Only
```bash
pytest tests/integration_tests
```

## Running Specific Tests

Run a specific test file:
```bash
pytest tests/unit_tests/test_handle_error.py
```

Run a specific test function:
```bash
pytest tests/unit_tests/test_handle_error.py::test_handle_error_with_valid_error_code
```

Run tests matching a pattern:
```bash
pytest tests/unit_tests -k "handle_error"
```

## Verbose Output

```bash
# Show test names and results
pytest -v

# Show print statements and logging
pytest -v -s

# Show detailed test execution order
pytest -v --collect-only
```

## Test Dependencies

- **unit_tests** → No dependencies
- **integration_tests_mock** → Requires unit_tests to pass
- **integration_tests** → Requires unit_tests AND integration_tests_mock to pass

If any test in unit_tests fails, integration_tests_mock and integration_tests are skipped.
If any test in integration_tests_mock fails, integration_tests is skipped.
