# VSCode Tasks

This document describes the predefined VSCode tasks available in this project and how to use them.

## Overview

VSCode tasks are predefined commands that can be run from the Command Palette (`Ctrl+Shift+P` → "Tasks: Run Task") or from the "Terminal" menu's "Run Task" option. They provide a convenient way to run common development commands without remembering the exact syntax.

## Available Tasks

### 1. Run Tests

**Purpose**: Execute all tests with proper environment setup

**Command**:

```bash
bash -lc 'set -a; [ -f .env ] && source .env; set +a; ${command:python.interpreterPath} -m pytest tests/'
```

**What it does**:

- Sources `.env` file to load environment variables (including `HA_TOKEN_DEV`)
- Runs `pytest` on the `tests/` directory
- Executes all test suites: unit → integration_mock → integration

**When to use**:

- Running full test suite
- After making code changes
- Before opening a PR

**Benefits over manual `pytest`**:

- Automatically loads `.env` (no need to manually `source .env`)
- Works after IDE restarts
- Consistent environment for CI

---

### 2. Code Coverage

**Purpose**: Run tests with coverage reporting

**Command**:

```bash
bash -lc 'set -a; [ -f .env ] && source .env; set +a; ${command:python.interpreterPath} -m pytest tests/ --cov=custom_components/import_statistics --cov-report term-missing --cov-report html'
```

**What it does**:

- Sources `.env` file
- Runs pytest with coverage enabled for `custom_components/import_statistics`
- Generates two reports:
  - Terminal summary with missing lines
  - HTML report in `htmlcov/` directory

**When to use**:

- Checking test coverage before PR
- Identifying untested code paths
- After adding new features

**Viewing results**:

- Terminal: Shows coverage percentage and missing lines
- HTML: Open `htmlcov/index.html` in browser for detailed view

---

### 3. Lint

**Purpose**: Format code and check for style issues

**Command**:

```bash
./scripts/lint
```

**What it does**:

- Runs `ruff format .` to format code
- Runs `ruff check . --fix` to check and auto-fix issues
- Follows project's `.ruff.toml` configuration

**When to use**:

- After code changes
- Before committing
- When CI reports linting issues

**Note**: This task does not source `.env` (not needed for linting)

---

### 4. Setup Dev Environment

**Purpose**: Install/update Python dependencies

**Command**:

```bash
./scripts/setup
```

**What it does**:

- Installs dependencies from `requirements.txt`
- Installs test dependencies from `requirements.test.txt`
- Sets up the development environment

**When to use**:

- Initial setup
- After dependency changes
- When tests fail due to missing packages

---

### 5. Clean Config

**Purpose**: Clean Home Assistant config directory for fresh start

**Command**:

```bash
./scripts/clean_config
./scripts/clean_config
```

**What it does**:

- Removes all generated files and directories from `config/`
- Keeps important files: `configuration.yaml`, `*.csv`, `test_*`, `*.md`
- Always removes `.storage/` (authentication and registry data)
- Interactive: shows what will be removed/kept and asks for confirmation

**When to use**:

- Before running integration tests (clean database)
- When HA has configuration issues
- To reset to a clean state without losing your config

**Safety**:

- Preserves your configuration and CSV files
- Shows exactly what will be deleted before proceeding
- Requires confirmation before deletion

---

### 6. Stop Home Assistant

**Purpose**: Stop running Home Assistant processes

**Command**:

```bash
bash -lc 'pkill -f homeassistant || echo "Home Assistant not found or already stopped"'
```

**What it does**:

- Kills any process whose command line contains "homeassistant"
- Prints a friendly message if no such process is found

**When to use**:

- Before running integration tests (to ensure clean database)
- When HA becomes unresponsive
- To free up port 8123

**Safety**:

- Only kills processes with "homeassistant" in the command line
- Won't affect other Python processes

---

## Running Tasks

### From Command Palette

1. Press `Ctrl+Shift+P`
2. Type "Tasks: Run Task"
3. Select the desired task from the list

### From Terminal Menu

1. Go to "Terminal" menu
2. Select "Run Task"
3. Choose the task

### From Keyboard Shortcuts (optional)

You can add keyboard shortcuts in `settings.json`:

```json
{
  "key": "ctrl+shift+t",
  "command": "workbench.action.tasks.runTask",
  "args": "Run Tests"
}
```

---

## Task Configuration

Tasks are defined in `.vscode/tasks.json`. Key features:

### Environment Sourcing

Test-related tasks (`Run Tests`, `Code Coverage`) automatically source `.env`:

```bash
bash -lc 'set -a; [ -f .env ] && source .env; set +a; ...'
```

### Presentation

- **Reveal**: "always" - shows terminal when task runs
- **Panel**: "new" - opens in new terminal panel
- **Focus**: true for some tasks (e.g., Stop Home Assistant)

### Grouping

- **test**: Run Tests, Code Coverage
- **build**: Stop Home Assistant, Setup Dev Environment

---

## Troubleshooting

### Task Not Found

- Ensure `.vscode/tasks.json` exists
- Reload VSCode window (`Ctrl+Shift+P` → "Developer: Reload Window")

### Environment Variables Missing

- Check `.env` file exists and contains `HA_TOKEN_DEV`
- Verify `.env` is in workspace root
- Try running `source .env` manually to check for errors

### Permission Denied

- Ensure `scripts/setup` is executable: `chmod +x scripts/setup`
- Check shell scripts have correct line endings (LF, not CRLF)

### Integration Tests Fail

- Stop Home Assistant first: use "Stop Home Assistant" task
- Check HA_TOKEN_DEV is valid
- Verify HA is accessible at <http://localhost:8123>

---

## Best Practices

1. **Use tasks instead of direct commands**: Ensures consistent environment
2. **Run tests before committing**: Use "Run Tests" task
3. **Check coverage before PR**: Use "Code Coverage" task
4. **Lint before pushing**: Use "Lint" task
5. **Stop HA before integration tests**: Use "Stop Home Assistant" task
6. **Clean config for database issues**: Use "Clean Config" task

---

## Customization

You can modify tasks in `.vscode/tasks.json`:

- Add new tasks for custom commands
- Modify existing task commands
- Change presentation options
- Add problem matchers for better error detection

Example custom task:

```json
{
  "label": "Run Specific Test",
  "type": "shell",
  "command": "bash -lc 'set -a; [ -f .env ] && source .env; set +a; ${command:python.interpreterPath} -m pytest tests/unit_tests/test_handle_error.py'",
  "group": "test",
  "presentation": {
    "reveal": "always",
    "panel": "new"
  }
}
```
