# Developer Documentation

## Quick Start

For experienced developers who want to get started immediately:

1. Clone repository and open in VS Code
2. Reopen in devcontainer (VS Code will prompt)
3. Run `scripts/setup` to install dependencies
4. Run `scripts/develop` to start Home Assistant
5. Access HA at http://localhost:8123
6. Create a token and store it in `HA_TOKEN_DEV` (needed for running integration tests)
6. Run `pytest` to execute tests

For detailed setup instructions, see [Development Environment Setup](#development-environment-setup) below.

---

## Development Environment Setup

### Prerequisites

- Docker Desktop installed and running
- Visual Studio Code with Remote-Containers extension
- Git

### Initial Setup

#### Step 1: Clone and Open in Devcontainer

1. Clone this repository
2. Open the repository in VS Code
3. When prompted, click "Reopen in Container" (or use Command Palette: "Remote-Containers: Reopen in Container")
4. Wait for the devcontainer to build (first time takes several minutes)

> This is tested under Windows using VS Code. As the repo is container-based, it should work in other environments as well.
> Python dependencies from both `requirements.txt` and `requirements.test.txt` are installed as part of the container setup automatically.

#### Step 2: Start Home Assistant

Start the development Home Assistant instance:

```bash
scripts/develop
```

Wait until Home Assistant finishes starting (you'll see `Home Assistant initialized` in the logs, but its not the last message), then access it at http://localhost:8123.

#### Step 3: Configure Authentication Token (Required for Integration Tests)

Integration tests require a Home Assistant authentication token. You have two options:

**Option A: Set token on host (recommended for persistent use)**

1. Generate a token in Home Assistant:
   - Navigate to http://localhost:8123
   - Go to: Settings > Devices & Services > Your Name > Create Token
   - Copy the generated token
2. On your **host machine** (not in container), set environment variable:
   - Linux/Mac: Add `export HA_TOKEN_DEV=your_token_here` to `~/.bashrc` or `~/.zshrc`
   - Windows: Set system environment variable `HA_TOKEN_DEV=your_token_here`
3. Rebuild the devcontainer to pick up the environment variable

**Option B: Set token in container (quick setup)**

1. Generate a token (same as Option A, step 1)
2. Inside the devcontainer, copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` and replace `your_dev_token_here` with your actual token
4. Source the file before running integration tests:
   ```bash
   source .env
   pytest tests/integration_tests
   ```

**Note**: The `.env` file is gitignored and will not be committed.

---

## Common Development Commands

All commands should be run from the workspace root directory inside the devcontainer.

### Setup and Dependencies

```bash
scripts/setup              # Install/update Python dependencies; run on container setup automatically
```

### Running Home Assistant

```bash
scripts/develop           # Start HA with custom component loaded
                          # Sets PYTHONPATH to include custom_components
                          # Access at http://localhost:8123
```

### Code Quality

```bash
scripts/lint              # Format code with ruff and auto-fix issues
                         # Runs: ruff format . && ruff check . --fix
```

### Testing

```bash
pytest                    # Run all tests (unit → integration_mock → integration)
pytest tests/unit_tests   # Run only unit tests
pytest tests/integration_tests_mock  # Run only mocked integration tests
pytest tests/integration_tests       # Run only full integration tests
pytest -v                 # Verbose output with test names
pytest -k "pattern"       # Run tests matching pattern
```

See [Running Tests](#running-tests) for detailed testing information.

---

## Running Tests

The project uses pytest with three test suites that run sequentially by default.

### Test Suite Overview

| Suite | Location | Dependencies | Purpose |
|-------|----------|--------------|---------|
| **Unit Tests** | `tests/unit_tests/` | None | Test pure functions (helpers, delta conversion) |
| **Integration Tests (Mock)** | `tests/integration_tests_mock/` | Mocked HA | Test service handlers with mocked Home Assistant |
| **Integration Tests (Real)** | `tests/integration_tests/` | Running HA + Token | Test against real Home Assistant instance |

### First-Time Integration Test Setup

**Important**: Before running integration tests the first time:

1. Start Home Assistant manually and wait for it to fully initialize:
   ```bash
   scripts/develop
   ```

2. Access http://localhost:8123 to verify it's running

3. Stop Home Assistant (Ctrl+C)

4. Now run integration tests - they will start HA with a fresh database:
   ```bash
   source .env  # If using .env file for token
   pytest tests/integration_tests
   ```

**Why this is needed**: Integration tests create a fresh database. If HA is already running with an existing database, tests will fail.

### Running All Tests

By default, pytest runs tests sequentially with automatic dependencies:

```bash
pytest
```

If any test suite fails, subsequent suites are skipped.

### Running Specific Test Suites

```bash
# Unit tests only (fast, no HA required)
pytest tests/unit_tests

# Integration tests with mocks only
pytest tests/integration_tests_mock

# Full integration tests (requires HA_TOKEN_DEV)
pytest tests/integration_tests
```

### Regular Test Execution

After first-time setup, you can run integration tests directly:

```bash
pytest tests/integration_tests
```

The tests will start Home Assistant automatically if it's not running.

### Additional Test Options

```bash
pytest -v                 # Verbose output with test names
pytest -v -s              # Show print statements and logging
pytest -k "delta"         # Run tests matching "delta" pattern
pytest tests/unit_tests/test_handle_error.py  # Run specific file
```

For complete testing documentation, see [`tests/README.md`](../../tests/README.md).

### Testing Strategy

See [Testing Strategy](./architecture.md#testing-strategy) in the architecture document for detailed information about the test architecture.

---

## Troubleshooting

### Devcontainer Issues

**Problem**: Devcontainer fails to build
- **Solution**: Ensure Docker Desktop is running and has sufficient resources (4GB+ RAM recommended)
- **Solution**: Try rebuilding without cache: Command Palette → "Remote-Containers: Rebuild Container Without Cache"

**Problem**: Extensions not loading in devcontainer
- **Solution**: Check `.devcontainer.json` for required extensions
- **Solution**: Manually install extensions from Extensions panel

### Home Assistant Issues

**Problem**: Home Assistant won't start with `scripts/develop`
- **Solution**: Check if port 8123 is already in use: `lsof -i :8123` (Linux/Mac) or `netstat -ano | findstr :8123` (Windows)
- **Solution**: Check logs for errors in the terminal output
- **Solution**: Delete `config/.storage` directory and restart

**Problem**: Cannot access http://localhost:8123
- **Solution**: Wait longer - first startup takes 1-2 minutes
- **Solution**: Check if HA process is running: `ps aux | grep hass`
- **Solution**: Verify port forwarding in VS Code (Ports panel)

### Test Issues

**Problem**: Integration tests fail with "HA_TOKEN_DEV not set"
- **Solution**: Set up authentication token following [Step 4](#step-4-configure-authentication-token-required-for-integration-tests)
- **Solution**: If using `.env` file, ensure you run `source .env` before tests

**Problem**: Integration tests fail with database errors
- **Solution**: Stop any running Home Assistant instance before running tests
- **Solution**: Delete `config/home-assistant_v2.db*` files and retry

### Code Quality Issues

**Problem**: Linting fails with ruff errors
- **Solution**: Run `scripts/lint` to check for issues. Some issues are fixed automatically
- **Solution**: Check `.ruff.toml` for project-specific rules

---

## Architecture & Design

Architecture and design description: see [architecture.md](./architecture.md).

---

## Contributing

Contributions are welcome! Please read the [Contribution Guidelines](../../CONTRIBUTING.md).
