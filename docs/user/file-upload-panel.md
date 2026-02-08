# File Upload Panel - User Guide

## Overview

The Import Statistics integration includes a web-based file upload panel that provides a user-friendly interface for uploading and importing statistics files into Home Assistant. This eliminates the need to manually copy files to the config directory or use the Developer Tools service interface.

## Features

- **Web-based file upload** - Upload CSV, TSV, or JSON files directly from your browser
- **Drag-and-drop support** - Simply drag files onto the upload area
- **Real-time feedback** - See upload progress and import status
- **Secure** - Requires admin authentication
- **Automatic file validation** - Validates file type and size before upload

## Accessing the Panel

### Method 1: Direct URL Access (Current Implementation)

The file upload panel is currently accessible via a direct URL. After installing the integration and restarting Home Assistant:

1. Open your web browser
2. Navigate to: `http://YOUR_HOME_ASSISTANT_IP:8123/api/import_statistics/panel/index.html`
   - Replace `YOUR_HOME_ASSISTANT_IP` with your Home Assistant's IP address or hostname
   - Example: `http://192.168.1.100:8123/api/import_statistics/panel/index.html`
   - Example: `http://homeassistant.local:8123/api/import_statistics/panel/index.html`

3. You will be automatically authenticated using your Home Assistant session
4. The panel will load and display the file upload interface

**Note:** You must be logged in as an admin user to access the panel.

### Method 2: Bookmark for Easy Access

To make the panel easier to access:

1. Navigate to the panel URL (see Method 1)
2. Bookmark the page in your browser
3. Give it a descriptive name like "Import Statistics Upload"
4. Access it anytime from your bookmarks

### Method 3: Add to Home Assistant Dashboard (Optional)

You can add a link to the panel in your Home Assistant dashboard:

1. Edit any dashboard
2. Add a **Button Card** or **Webpage Card**
3. Configure it to open the panel URL:
   - For Button Card: Set the tap action to navigate to the URL
   - For Webpage Card: Set the URL to `/api/import_statistics/panel/index.html`

**Example Button Card Configuration:**
```yaml
type: button
name: Import Statistics
icon: mdi:database-import-outline
tap_action:
  action: url
  url_path: /api/import_statistics/panel/index.html
```

**Example Webpage Card Configuration:**
```yaml
type: iframe
url: /api/import_statistics/panel/index.html
aspect_ratio: 75%
```

### Future Enhancement: Sidebar Panel

In a future version, the panel will be automatically registered in the Home Assistant sidebar, making it accessible like any other built-in panel (Settings, Developer Tools, etc.). This feature requires additional Home Assistant panel API integration.

## Using the Panel

### Step 1: Upload a File

1. **Access the panel** using one of the methods above
2. **Select a file** by clicking the file input or dragging a file onto the upload area
3. **Supported file types:**
   - CSV files (`.csv`)
   - TSV files (`.tsv`)
   - JSON files (`.json`)
   - Text files (`.txt`)
4. **Maximum file size:** 50 MB
5. **Click "Upload File"** to upload the file to your Home Assistant config directory
6. Wait for the upload to complete - you'll see a success message with the uploaded filename

### Step 2: Import Statistics

After uploading a file:

1. The panel will display the uploaded filename
2. Review the **import settings** (currently fixed):
   - **Delimiter:** Tab (`\t`) - for TSV files
   - **Decimal:** Dot (`.`) - for decimal numbers
   - **Datetime format:** `%d.%m.%Y %H:%M` (e.g., `01.02.2026 14:30`)
   - **Unit from entity:** `true` - units are read from entity metadata
3. **Click "Import Statistics"** to start the import process
4. Wait for the import to complete - you'll see a success or error message

### Understanding Import Settings

The current implementation uses **fixed import parameters** optimized for the most common use case:

- **Delimiter (`\t`)**: Tab-separated values (TSV format)
  - If your file uses commas, convert it to TSV first
  - Most spreadsheet programs can export as TSV

- **Decimal (`.`)**: Dot as decimal separator
  - Example: `123.45` (not `123,45`)
  - Standard in most English-speaking countries

- **Datetime format (`%d.%m.%Y %H:%M`)**: Day.Month.Year Hour:Minute
  - Example: `01.02.2026 14:30` = February 1, 2026 at 2:30 PM
  - No seconds are included
  - 24-hour format

- **Unit from entity (`true`)**: Units are read from entity metadata
  - The integration will look up the unit from the entity's state
  - Your file should NOT include a `unit` column
  - Only works for internal entities (format: `sensor.name`)

**Future Enhancement:** A future version will allow you to configure these parameters in the panel UI.

## File Format Requirements

### CSV/TSV Files

Your file must include these columns:

**For Sensor Statistics (mean/min/max):**
- `statistic_id` - Entity ID (e.g., `sensor.temperature`)
- `start` - Timestamp in the configured format
- `mean` - Average value
- `min` - Minimum value
- `max` - Maximum value

**For Counter Statistics (sum/state):**
- `statistic_id` - Entity ID (e.g., `sensor.energy_total`)
- `start` - Timestamp in the configured format
- `sum` - Cumulative sum
- `state` - Current state value

**For Delta Statistics:**
- `statistic_id` - Entity ID
- `start` - Timestamp in the configured format
- `delta` - Change in value since last reading

**Example TSV file (sensor):**
```
statistic_id	start	mean	min	max
sensor.temperature	01.02.2026 00:00	20.5	18.0	23.0
sensor.temperature	01.02.2026 01:00	20.3	18.5	22.5
```

**Example TSV file (counter):**
```
statistic_id	start	sum	state
sensor.energy_total	01.02.2026 00:00	1000.0	1000.0
sensor.energy_total	01.02.2026 01:00	1050.0	1050.0
```

### JSON Files

JSON files should follow the Home Assistant statistics format:

```json
[
  {
    "statistic_id": "sensor.temperature",
    "start": "01.02.2026 00:00",
    "mean": 20.5,
    "min": 18.0,
    "max": 23.0
  },
  {
    "statistic_id": "sensor.temperature",
    "start": "01.02.2026 01:00",
    "mean": 20.3,
    "min": 18.5,
    "max": 22.5
  }
]
```

## Security

### Authentication

- The panel requires **Home Assistant session authentication**
- You must be logged in to Home Assistant to access it
- Only **admin users** can upload and import files
- Non-admin users will see an "Admin access required" error

### File Validation

The integration validates all uploaded files:

- **File extension** must be `.csv`, `.tsv`, `.json`, or `.txt`
- **File size** must not exceed 50 MB
- **Filename** is sanitized to prevent path traversal attacks
- **File path** is validated to ensure it stays within the config directory

### Uploaded File Storage

- Files are saved to your Home Assistant **config directory**
- Filenames are automatically prefixed with `uploaded_` and timestamped
- Example: `uploaded_statistics_20260201_143000.tsv`
- Files are NOT automatically deleted after import (manual cleanup required)

## Troubleshooting

### Panel Not Loading

**Problem:** The panel URL returns a 404 error or blank page.

**Solutions:**
1. Verify the integration is installed correctly
2. Restart Home Assistant
3. Check that the frontend was built (see [Frontend Build](#frontend-build) below)
4. Check Home Assistant logs for errors

### Upload Fails

**Problem:** File upload fails with an error message.

**Solutions:**
1. **"Admin access required"** - Log in as an admin user
2. **"File too large"** - Reduce file size to under 50 MB
3. **"Invalid file type"** - Use `.csv`, `.tsv`, `.json`, or `.txt` extension
4. **"Upload failed"** - Check Home Assistant logs for details

### Import Fails

**Problem:** Import fails after successful upload.

**Solutions:**
1. **Check file format** - Ensure columns match requirements
2. **Check datetime format** - Must match `%d.%m.%Y %H:%M`
3. **Check delimiter** - Must be tab-separated (TSV)
4. **Check decimal separator** - Must use dot (`.`)
5. **Check entity exists** - Entity must exist in Home Assistant
6. **Check logs** - See detailed error in Home Assistant logs

### Panel Shows "Service call failed"

**Problem:** Import button shows service call error.

**Solutions:**
1. Verify the `import_statistics` integration is loaded
2. Check that the service is registered: Developer Tools → Services → search for `import_statistics.import_from_file`
3. Restart Home Assistant
4. Check logs for service registration errors

## Frontend Build

### For End Users

The frontend is **pre-built** and included in the repository. You don't need to build it yourself - just install the integration and restart Home Assistant.

### For Developers

If you're modifying the frontend code, you'll need to rebuild it:

**Prerequisites:**
- Node.js 18+ and npm

**Build Steps:**
```bash
cd custom_components/import_statistics/frontend
npm install
npm run build
```

This generates `dist/index.js` which is served by Home Assistant.

**Development Mode (auto-rebuild on changes):**
```bash
npm run dev
```

## Limitations (Current Version)

The current implementation is a **minimal breakthrough version** with these limitations:

- ❌ No sidebar panel registration (must use direct URL)
- ❌ No configurable import parameters (fixed values)
- ❌ No file preview before import
- ❌ No drag-and-drop upload (file input only)
- ❌ No progress indicators during upload/import
- ❌ No upload history or file management
- ❌ No export functionality in the panel

These features are planned for future versions.

## Advanced Usage

### Using with External Statistics

For external statistics (format: `domain:statistic_id`), you must:

1. Include a `unit` column in your file
2. Set `unit_from_entity: false` in the service call
3. **Note:** The current panel uses fixed parameters with `unit_from_entity: true`, so external statistics are not supported via the panel yet

**Workaround:** Use the Developer Tools service interface for external statistics:
1. Go to Developer Tools → Services
2. Select `import_statistics.import_from_file`
3. Set `unit_from_entity: false`
4. Provide the uploaded filename

### Batch Imports

To import multiple files:

1. Upload the first file
2. Import it
3. Upload the next file
4. Import it
5. Repeat as needed

**Note:** Each file must be imported separately in the current version.

### Automation Integration

You can trigger imports from automations using the service call:

```yaml
service: import_statistics.import_from_file
data:
  filename: uploaded_statistics_20260201_143000.tsv
  delimiter: "\t"
  decimal: "."
  datetime_format: "%d.%m.%Y %H:%M"
  unit_from_entity: true
```

## Related Documentation

- [Main README](../../README.md) - Integration overview and installation
- [Counters Guide](counters.md) - Working with counter statistics
- [Troubleshooting Tips](troubleshooting-tips.md) - General troubleshooting
- [Debug Logging](debug-logging.md) - Enabling debug logs

## Support

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Enable [debug logging](debug-logging.md) and check logs
3. Review the [troubleshooting tips](troubleshooting-tips.md)
4. Open an issue on GitHub with logs and file samples

## Future Roadmap

Planned enhancements for the file upload panel:

1. **Sidebar Panel Registration** - Automatic sidebar integration
2. **Configurable Parameters** - UI for delimiter, datetime format, etc.
3. **File Preview** - Preview file contents before import
4. **Drag-and-Drop** - Drag files onto the panel
5. **Progress Indicators** - Real-time upload/import progress
6. **Upload History** - View past uploads and imports
7. **Export Tab** - Export statistics from the panel
8. **File Management** - Delete uploaded files
9. **Validation Preview** - See validation errors before import
10. **Multi-file Upload** - Upload and import multiple files at once
