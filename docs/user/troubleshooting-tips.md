# Troubleshooting Tips for Import Statistics Integration

## Installation Issues

### Integration Not Appearing After Installation
**Problem:** Service not showing up in Developer Tools

**Solutions:**
- Add `import_statistics:` to your `configuration.yaml` file
- Restart Home Assistant after adding the configuration

## Data Import Issues

### Sum and State Column Confusion
**Problem:** Negative values, spikes, or incorrect energy dashboard readings

**Solutions:**
- Use delta import (version >= v3.0.0)
- Read [Understanding counter statistics in Home Assistant](./user/counters.md) thoroughly

### Missing Hourly Values
**Problem:** Gaps in data or disconnected lines in graphs

**Solutions:**
- Import data for every hour, even if values don't change
- If you only have daily data, decide whether to:
  - Create hourly entries with the same value (flat line)
  - Distribute the change to each hour
- Hourly data provides smoother graphs and better statistics

## File Format Issues

### Invalid Column Names
**Problem:** "The file must contain the columns 'statistic_id', 'start' and 'unit'"

**Solutions:**
- Check if the import file uses the correct delimiter
- Check column names are EXACTLY correct (case-sensitive): `statistic_id`, `unit`, `start`, `state`, `sum`
  - If there are other column names, with a version >= 3.0.0 there will be an error if an unknown column exists
- Do NOT include duplicate header rows in your CSV file
- Remove any empty rows from your CSV file
- Ensure the first row contains headers, not data

### Delimiter Issues
**Problem:** Import fails with delimiter-related errors

**Solutions:**
- Specify the correct delimiter in the import settings (comma `,` or tab `\t`)
- If using tab-separated values, use `\t` as the delimiter
- Ensure your file uses consistent delimiters throughout
- Check for embedded commas in string fields (use quotes if needed)

### Character Encoding Problems
**Problem:** Special characters display incorrectly (e.g., `Â°C` instead of `°C`)

**Solutions:**
- As of v3.1, files with wrong encoding cannot be imported anymore, there is an error message
- For units with special characters (like °C or m³), ensure UTF-8 encoding is used
- Use Notepad++ or similar editor to verify encoding
- Excel may cause encoding issues - verify with a text editor

### Timestamp Format Issues
**Problem:** "Invalid timestamp" or "The timestamp must be a full hour"

**Solutions:**
- Use the exact format: `DD.MM.YYYY HH:MM` (e.g., `24.04.2023 17:00`)
- Timestamps MUST be at the top of the hour (minutes must be `:00`)
- Remove seconds from timestamps (e.g., `17:00:00` should be `17:00`)
- Home Assistant statistics only accept hourly data
- If you have 15-minute or 30-minute data, aggregate it to hourly totals before importing

### Timestamp Conversion from Unix Time
**Problem:** Data is available in Unix timestamp format only (e.g., `1710601200`)

**Solution:**
- Convert Unix timestamps to the required format: `DD.MM.YYYY HH:MM`
- Use Excel, Python, or online converters for batch conversion

## Entity and Sensor Issues

### Invalid Statistic ID Error
**Problem:** "Statistic_id is invalid. Use either an existing entity ID (containing a '.'), or a statistic id (containing a ':')"

**Solutions:**
- For sensors already existing in HA: use format `sensor.entity_name` (with a period `.`)
  - Do not use `entity_name` alone, `sensor.` is needed as well
  - Ensure the entity exists before importing (for internal statistics)
    - Check in developer tools
- For external statistics: use format `sensor:entity_name` (with a colon `:`)
  - You can use a different string as `sensor` here, but the colon is important
- Check for typos in entity names
- Remove any trailing spaces after entity names
- Verify entity name doesn't contain invalid characters or double hyphens

### Template Sensor Import Issues
**Problem:** Importing to a template sensor doesn't work as expected

**Solutions:**
- Create the template sensor with proper `state_class` and `device_class` attributes
- For counters, use `state_class: total_increasing`
- For sensors, use `state_class: measurement`
- Ensure the template sensor exists before attempting import
  - Check in developer tools
