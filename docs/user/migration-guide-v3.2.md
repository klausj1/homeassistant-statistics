# Migration Guide: Version 3.2.0 Service Parameter Improvements

This guide helps you update your automations and scripts to use the improved service parameters introduced in version 3.2.0.

## Overview of Changes

Version 3.2.0 improves the service parameters for both `import_from_file` and `export_statistics` to make them more intuitive and reliable:

1. **Timezone parameter**: Now optional with smart default (Home Assistant's configured timezone)
2. **Delimiter parameter**: Now required with sensible default (`\t` for tab)
3. **Decimal separator**: Changed from boolean to explicit string selector

## Breaking Change: Decimal Separator Format

### What Changed

The `decimal` parameter changed from a boolean to an explicit string selector.

| Old Format (v3.1.0 and earlier) | New Format (v3.2.0+) |
| ------------------------------- | -------------------- |
| `decimal: false` (for dot)      | `decimal: "."`       |
| `decimal: true` (for comma)     | `decimal: ","`       |

### Why This Change?

- **More explicit**: `decimal: "."` is clearer than `decimal: false`
- **Less confusing**: Boolean values (`true`/`false`) don't intuitively represent decimal separators
- **Better UI**: Dropdown selector shows exactly what you're choosing

### Migration Steps

**Step 1**: Find all service calls using the old format

Search your automations and scripts for:
- `import_statistics.import_from_file`
- `import_statistics.export_statistics`

**Step 2**: Update the `decimal` parameter

Replace:
- `decimal: false` → `decimal: "."`
- `decimal: true` → `decimal: ","`

### Migration Examples

#### Import Service - Before (v3.1.0)

```yaml
action: import_statistics.import_from_file
data:
  filename: my_statistics.tsv
  timezone_identifier: Europe/Vienna
  delimiter: \t
  decimal: false  # ❌ Old boolean format
```

#### Import Service - After (v3.2.0)

```yaml
action: import_statistics.import_from_file
data:
  filename: my_statistics.tsv
  timezone_identifier: Europe/Vienna
  delimiter: \t
  decimal: "."  # ✅ New string format
```

#### Export Service - Before (v3.1.0)

```yaml
action: import_statistics.export_statistics
data:
  filename: exported_statistics.tsv
  entities:
    - sensor.temperature
  start_time: "2025-12-22 12:00:00"
  end_time: "2025-12-25 12:00:00"
  timezone_identifier: Europe/Vienna
  delimiter: \t
  decimal: true  # ❌ Old boolean format (comma)
```

#### Export Service - After (v3.2.0)

```yaml
action: import_statistics.export_statistics
data:
  filename: exported_statistics.tsv
  entities:
    - sensor.temperature
  start_time: "2025-12-22 12:00:00"
  end_time: "2025-12-25 12:00:00"
  timezone_identifier: Europe/Vienna
  delimiter: \t
  decimal: ","  # ✅ New string format (comma)
```

## Improvement: Optional Timezone with Smart Default

### What Changed

The `timezone_identifier` parameter is now optional and defaults to Home Assistant's configured timezone.

### Benefits

- **Simpler service calls**: No need to specify timezone for most users
- **Automatic consistency**: Uses your Home Assistant timezone by default
- **Still flexible**: Can override with explicit timezone when needed

### Migration Examples

#### Before (v3.1.0) - Timezone Required

```yaml
action: import_statistics.import_from_file
data:
  filename: my_statistics.tsv
  timezone_identifier: Europe/Vienna  # Had to specify every time
  delimiter: \t
  decimal: "."
```

#### After (v3.2.0) - Timezone Optional

```yaml
# Option 1: Omit timezone (uses HA's configured timezone)
action: import_statistics.import_from_file
data:
  filename: my_statistics.tsv
  delimiter: \t
  decimal: "."
  # timezone_identifier omitted - uses HA timezone automatically ✅
```

```yaml
# Option 2: Explicitly specify timezone (when needed)
action: import_statistics.import_from_file
data:
  filename: my_statistics.tsv
  timezone_identifier: America/New_York  # Override HA timezone
  delimiter: \t
  decimal: "."
```

### When to Specify Timezone

**Omit timezone (recommended)** when:
- Your data uses your local timezone
- You want timestamps interpreted as local time
- You're exporting for backup/analysis

**Specify timezone explicitly** when:
- Importing data from a different timezone
- Working with data from external sources
- Need precise timezone control for specific use cases

## Improvement: Required Delimiter with Default

### What Changed

The `delimiter` parameter changed from optional (with auto-detect) to required with a sensible default (`\t` for tab).

### Benefits

- **No ambiguity**: Explicit delimiter prevents parsing errors
- **Predictable behavior**: No surprises from auto-detection
- **Better UI**: Dropdown shows common options (tab, semicolon, comma, pipe)

### Migration Impact

**Good news**: This change is backward compatible!

- If you already specified `delimiter`, no changes needed
- If you omitted `delimiter`, it now defaults to `\t` (tab)
- The UI now shows a dropdown with default `\t` selected

### Examples

#### Before (v3.1.0) - Optional Delimiter

```yaml
action: import_statistics.import_from_file
data:
  filename: my_statistics.tsv
  timezone_identifier: Europe/Vienna
  # delimiter omitted - auto-detect attempted
  decimal: "."
```

#### After (v3.2.0) - Required with Default

```yaml
action: import_statistics.import_from_file
data:
  filename: my_statistics.tsv
  delimiter: \t  # Now required, but defaults to tab in UI
  decimal: "."
  # timezone_identifier omitted - uses HA timezone
```

## Complete Migration Example

### Full Service Call - Before (v3.1.0)

```yaml
# Import service
action: import_statistics.import_from_file
data:
  filename: my_statistics.tsv
  timezone_identifier: Europe/Vienna
  delimiter: \t
  decimal: false  # ❌ Boolean format

# Export service
action: import_statistics.export_statistics
data:
  filename: exported_statistics.tsv
  entities:
    - sensor.temperature
    - sensor.humidity
  start_time: "2025-12-22 12:00:00"
  end_time: "2025-12-25 12:00:00"
  timezone_identifier: Europe/Vienna
  delimiter: \t
  decimal: true  # ❌ Boolean format
```

### Full Service Call - After (v3.2.0)

```yaml
# Import service - simplified
action: import_statistics.import_from_file
data:
  filename: my_statistics.tsv
  delimiter: \t
  decimal: "."  # ✅ String format
  # timezone_identifier omitted - uses HA timezone ✅

# Export service - simplified
action: import_statistics.export_statistics
data:
  filename: exported_statistics.tsv
  entities:
    - sensor.temperature
    - sensor.humidity
  start_time: "2025-12-22 12:00:00"
  end_time: "2025-12-25 12:00:00"
  delimiter: \t
  decimal: ","  # ✅ String format
  # timezone_identifier omitted - uses HA timezone ✅
```

## Quick Reference: Parameter Changes

| Parameter             | Old Behavior                    | New Behavior                                  | Action Required |
| --------------------- | ------------------------------- | --------------------------------------------- | --------------- |
| `decimal`             | Boolean (`true`/`false`)        | String (`"."` or `","`)                       | **Yes - Update** |
| `timezone_identifier` | Required                        | Optional (defaults to HA timezone)            | No - Optional   |
| `delimiter`           | Optional (auto-detect)          | Required with default `\t`                    | No - Has default |

## Testing Your Migration

After updating your service calls:

1. **Test with small dataset**: Use a file with 10-20 rows first
2. **Verify decimal handling**: Check that numbers are parsed correctly
3. **Check timezone**: Verify timestamps are interpreted as expected
4. **Review logs**: Look for any warnings or errors
5. **Compare results**: Export and compare with previous exports if possible

## Getting Help

If you encounter issues during migration:

1. Check the [Troubleshooting Guide](./troubleshooting-tips.md)
2. Review the [README](../../README.md) for updated examples
3. Enable debug logging to see detailed error messages
4. Ask in the [Community Forum](https://community.home-assistant.io/t/custom-integration-to-import-long-term-statistics-from-a-file-like-csv-or-tsv)

## Summary

The v3.2.0 parameter improvements make the integration:
- **More intuitive**: Explicit string values instead of boolean flags
- **Simpler to use**: Optional timezone with smart defaults
- **More reliable**: Required delimiter eliminates auto-detect ambiguity

**Required action**: Update `decimal` parameter from boolean to string format in all service calls.

**Optional improvements**: Remove `timezone_identifier` if you want to use Home Assistant's configured timezone.
