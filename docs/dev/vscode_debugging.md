# VSCode Debugging Configuration

This document explains the VSCode launch configurations available for debugging Home Assistant with your custom component.

## Overview

The `.vscode/launch.json` file defines debug configurations that allow you to:

- Launch Home Assistant in debug mode
- Set breakpoints in your custom component code
- Step through code execution
- Inspect variables and call stacks

## Available Configurations

### 1. Home Assistant (Component Dev)

**Purpose**: Debug Home Assistant with your custom component

**Configuration**:

```json
{
    "name": "Home Assistant (Component Dev)",
    "type": "debugpy",
    "request": "launch",
    "module": "homeassistant",
    "justMyCode": false,
    "args": [
        "--debug",
        "-c",
        "${workspaceFolder}/config"
    ],
    "env": {
        "PYTHONPATH": "${workspaceFolder}/custom_components"
    }
}
```

**What it does**:

- Starts Home Assistant in debug mode
- Uses `config/` directory for configuration
- Sets `PYTHONPATH` to include your custom components
- Enables debugging of all code (`justMyCode: false`)

**When to use**:

- Developing and debugging custom components
- Testing new features
- Investigating issues in your code

---

### 2. Home Assistant (skip pip)

**Purpose**: Debug Home Assistant without running pip checks

**Configuration**:

```json
{
    "name": "Home Assistant (skip pip)",
    "type": "debugpy",
    "request": "launch",
    "module": "homeassistant",
    "justMyCode": false,
    "args": [
        "--debug",
        "-c",
        "${workspaceFolder}/config",
        "--skip-pip"
    ],
    "env": {
        "PYTHONPATH": "${workspaceFolder}/custom_components"
    }
}
```

**What it does**:

- Same as Component Dev but skips pip dependency checks
- Faster startup when you know dependencies are correct
- Useful for repeated debug sessions

**When to use**:

- Dependencies are already installed and verified
- Need faster startup for repeated debugging
- Working in a stable environment

---

## How to Use Debugging

### Starting a Debug Session

1. **Open the Debug view**:
   - Press `Ctrl+Shift+D` (Windows/Linux) or `Cmd+Shift+D` (Mac)
   - Or click the bug icon in the sidebar

2. **Select Configuration**:
   - From the dropdown at the top, choose:
     - "Home Assistant (Component Dev)" for full debugging
     - "Home Assistant (skip pip)" for faster startup

3. **Start Debugging**:
   - Press `F5` or click the green play button
   - Home Assistant will start in debug mode

### Setting Breakpoints

1. **In your code**: Click in the gutter next to the line number
2. **Conditional breakpoints**: Right-click → "Add Conditional Breakpoint"
3. **Logpoints**: Right-click → "Add Logpoint" (prints without stopping)

### Debug Controls

- **Continue** (`F5`): Run to next breakpoint
- **Step Over** (`F10`): Execute current line
- **Step Into** (`F11`): Dive into function calls
- **Step Out** (`Shift+F11`): Exit current function
- **Restart** (`Ctrl+Shift+F5`): Restart debug session
- **Stop** (`Shift+F5`): Stop debugging

### Debug Panels

1. **Variables**: Inspect local and global variables
2. **Watch**: Add expressions to monitor
3. **Call Stack**: See the execution path
4. **Debug Console**: Execute Python commands during debug

---

## Common Debugging Workflows

### Debugging Service Calls

1. Set breakpoint in your service handler (e.g., `handle_export_statistics_impl`)
2. Start debug session
3. Call service from HA UI or via `scripts/develop` terminal
4. Debugger will stop at your breakpoint

### Debugging Import Issues

1. Set breakpoint in `__init__.py` setup function
2. Start debug session
3. Check logs for import errors
4. Inspect `sys.path` and module loading

### Debugging Database Access

1. Set breakpoint in database access functions
2. Step through SQL queries
3. Inspect returned data structures

---

## Tips and Best Practices

### Performance

- Use "skip pip" variant for repeated sessions
- Set breakpoints only where needed
- Use `justMyCode: true` to focus on your code (change in config)

### Breakpoint Management

- Use descriptive breakpoint names
- Group related breakpoints
- Disable unused breakpoints instead of deleting

### Variable Inspection

- Use the "Variables" panel for automatic inspection
- Add complex expressions to "Watch" panel
- Use "Set Value" to modify variables during debug

### Logging

- Add `import pdb; pdb.set_trace()` for quick debugging
- Use Python's `logging` module with debug level
- Check HA logs in the debug console

---

## Troubleshooting

### Debug Session Won't Start

**Problem**: "ModuleNotFoundError: No module named 'homeassistant'"

- **Solution**: Run `scripts/setup` to install dependencies
- **Solution**: Check you're in the devcontainer

**Problem**: "PYTHONPATH issues"

- **Solution**: Verify `custom_components` directory exists
- **Solution**: Check path in `.vscode/launch.json`

### Breakpoints Not Hit

**Problem**: Breakpoints ignored

- **Solution**: Ensure code is actually executed
- **Solution**: Check `justMyCode` setting
- **Solution**: Verify file is in the workspace

### Performance Issues

**Problem**: Debug startup is slow

- **Solution**: Use "skip pip" configuration
- **Solution**: Close unused VSCode tabs
- **Solution**: Disable unnecessary extensions

---

## Advanced Configuration

### Custom Environment Variables

Add to your launch configuration:

```json
"env": {
    "PYTHONPATH": "${workspaceFolder}/custom_components",
    "HA_TOKEN_DEV": "your_token_here",
    "DEBUG": "true"
}
```

### Python Path Configuration

For complex setups, modify PYTHONPATH:

```json
"env": {
    "PYTHONPATH": "${workspaceFolder}/custom_components:${workspaceFolder}"
}
```

### Remote Debugging

For debugging on remote hosts:

1. Install `debugpy` on remote host
2. Add remote debug configuration
3. Configure firewall/port forwarding

---

## Integration with Development Workflow

### Typical Debug Session

1. Make code changes
2. Set breakpoints in relevant areas
3. Start debug session
4. Test functionality in HA UI
5. Analyze debug output
6. Fix issues and repeat

### Before Committing

1. Run debug session to verify fixes
2. Test edge cases with breakpoints
3. Ensure no debug code left in commits
4. Run full test suite

### Code Reviews

Use debugging to:

- Demonstrate bug fixes
- Show code flow to reviewers
- Verify edge case handling

---

## Related Resources

- [VSCode Python Debugging](https://code.visualstudio.com/docs/python/debugging)
- [Home Assistant Development](./README.md)
- [VSCode Tasks](./vscode_tasks.md)
- [Testing Guide](../README.md#running-tests)
