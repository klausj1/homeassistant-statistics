# Debug Logging for Import Statistics Integration

Debug logging provides detailed information about the integration's operations, which is essential for troubleshooting issues and reporting bugs.

## How to Enable Debug Logging

1. Open your Home Assistant `configuration.yaml` file
2. Add or update the `logger` section:

```yaml
logger:
  default: info
  logs:
    custom_components.import_statistics: debug
```

1. Save the file
2. Restart Home Assistant or reload the logger configuration:
   - Go to **Developer Tools → YAML**
   - Click **Reload** next to "Logger"

## How to Collect Debug Logs

After enabling debug logging and reproducing the issue, you need to collect the logs. Here are the methods:

### Method 1: Download Full Log File via Home Assistant UI

1. Go to **Settings → System → Logs**
2. Click **Load Full Logs** at the bottom of the page
3. Wait for the full log to load (may take a few seconds)
4. Search for `import_statistics` entries containing `DEBUG`

### Method 2: Copy file from Home Assistant Server

1. Navigate to the `config`-directory of your :
2. Copy the file `/config/home-assistant.log`
3. Search for `import_statistics` entries containing `DEBUG`

> If you have disabled logging to file, this method is not possible.

## Example Debug Log Output

Example debug log output for an export (contains INFO logs as well, not complete):

```text
2026-01-24 18:31:37.399 INFO (MainThread) [custom_components.import_statistics.helpers] Service handle_export_statistics called
2026-01-24 18:31:37.399 INFO (MainThread) [custom_components.import_statistics.helpers] Exporting entities: ALL
2026-01-24 18:31:37.399 INFO (MainThread) [custom_components.import_statistics.helpers] Time range: AUTO to AUTO
2026-01-24 18:31:37.399 INFO (MainThread) [custom_components.import_statistics.helpers] Output file: xx.tsv
2026-01-24 18:31:37.399 INFO (MainThread) [custom_components.import_statistics.helpers] Fetching statistics from recorder API
2026-01-24 18:31:37.399 INFO (MainThread) [custom_components.import_statistics.helpers] No entities specified, fetching all statistics from database
2026-01-24 18:31:37.408 INFO (MainThread) [custom_components.import_statistics.helpers] Found 25 statistics in database
2026-01-24 18:31:37.446 DEBUG (MainThread) [custom_components.import_statistics.helpers] Global statistics time range determined: start=2025-06-29 05:00:00+00:00 end=2025-12-30 10:00:00+00:00
2026-01-24 18:31:37.463 INFO (SyncWorker_1) [custom_components.import_statistics.helpers] Preparing export data
2026-01-24 18:31:37.464 INFO (SyncWorker_1) [custom_components.import_statistics.helpers] Export contains both measurement (mean/min/max) and counter (sum/state) statistics. Measurement columns will be empty for counters and vice versa.
2026-01-24 18:31:37.465 DEBUG (SyncWorker_1) [custom_components.import_statistics.helpers] Export data prepared with columns: ['statistic_id', 'unit', 'start', 'min', 'max', 'mean', 'sum', 'state', 'delta']
```

## Reporting Bugs with Debug Logs

When reporting a bug, follow these steps to provide helpful debug logs:

### Step-by-Step Process

1. **Enable debug logging** using Method 1 (configuration.yaml) from the "How to Enable Debug Logging" section above
2. **Restart Home Assistant** or reload the logger configuration
3. **Reproduce the issue** by running the import/export action that causes the problem
4. **Collect the logs immediately** using Method 1 (Download Full Log File) from the "How to Collect Debug Logs" section above
5. **Prepare the logs for the bug report:**
   - Open the saved log file in a text editor
   - Search for `import_statistics` to find relevant entries
   - Copy at least **20-30 lines before and after the error**
   - Include the **full error message and stack trace** if present
   - **Redact sensitive information** (file paths with personal info, entity names if needed)

## Disabling Debug Logging

Once you've finished troubleshooting:

1. Edit your `configuration.yaml`
2. Remove the debug logging line or change it to `info`:

```yaml
logger:
  default: info
  logs:
    custom_components.import_statistics: info  # or remove this line entirely
```

1. Restart Home Assistant or reload the logger configuration

## Additional Resources

- [Home Assistant Logger Integration Documentation](https://www.home-assistant.io/integrations/logger/)
- [Troubleshooting Tips](./troubleshooting-tips.md)
- [Report a Bug](https://github.com/klausj1/homeassistant-statistics/issues/new?template=bug.yml)
