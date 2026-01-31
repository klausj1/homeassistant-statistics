# File Upload Implementation Plan

## Overview

This document provides the step-by-step implementation plan for adding browser-based file upload functionality to the Import Statistics integration.

**Approach**: Simple HTTP View with HTML Form (Phase 1 MVP)

## Implementation Steps

### Step 1: Create Upload View Backend
**File**: `custom_components/import_statistics/upload_view.py`

**Tasks**:
1. Create `ImportStatisticsUploadView` class extending `HomeAssistantView`
2. Implement `post()` method to handle file uploads
3. Add file validation (size, extension, MIME type)
4. Add filename sanitization function
5. Implement file saving to config directory
6. Return JSON response with upload status

**Key Functions**:
- `validate_upload_file()` - Validate file size, type, extension
- `sanitize_upload_filename()` - Create safe filename with timestamp
- `save_uploaded_file()` - Save file to config directory
- `post()` - Main upload handler

**Security Requirements**:
- Use `@require_admin` decorator
- Validate file size (max 50MB)
- Whitelist extensions: `.csv`, `.tsv`, `.txt`, `.json`
- Sanitize filename (prevent path traversal)
- Verify saved path is within config directory

### Step 2: Create Upload Form View
**File**: `custom_components/import_statistics/upload_form_view.py`

**Tasks**:
1. Create `ImportStatisticsUploadFormView` class
2. Implement `get()` method to serve HTML form
3. Design HTML form with file upload field
4. Add optional auto-import checkbox and settings
5. Style form with HA-inspired CSS
6. Add JavaScript for form submission and feedback

**Form Fields**:
- File upload input (required)
- Auto-import checkbox (optional)
- Delimiter dropdown (if auto-import enabled)
- Decimal dropdown (if auto-import enabled)
- Datetime format dropdown (if auto-import enabled)
- Unit from entity checkbox (if auto-import enabled)
- Timezone identifier text field (optional)

### Step 3: Register Views in Integration Setup
**File**: `custom_components/import_statistics/__init__.py`

**Tasks**:
1. Import upload view classes
2. Register `ImportStatisticsUploadView` in `async_setup_entry()`
3. Register `ImportStatisticsUploadFormView` in `async_setup_entry()`
4. Ensure views are registered before integration is ready

**Changes**:
```python
from .upload_view import ImportStatisticsUploadView
from .upload_form_view import ImportStatisticsUploadFormView

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the device based on a config entry."""
    # Register upload views
    hass.http.register_view(ImportStatisticsUploadView())
    hass.http.register_view(ImportStatisticsUploadFormView())

    return True
```

### Step 4: Add Upload Constants
**File**: `custom_components/import_statistics/const.py`

**Tasks**:
1. Add upload-related constants
2. Define max file size
3. Define allowed extensions
4. Define allowed MIME types

**New Constants**:
```python
# Upload settings
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".tsv", ".txt", ".json"}
ALLOWED_MIME_TYPES = {
    "text/csv",
    "text/plain",
    "text/tab-separated-values",
    "application/json",
    "application/octet-stream",  # Some browsers use this for CSV
}

# Upload view URLs
UPLOAD_API_URL = "/api/import_statistics/upload"
UPLOAD_FORM_URL = "/import_statistics/upload"
```

### Step 5: Add Helper Functions for Upload
**File**: `custom_components/import_statistics/helpers.py`

**Tasks**:
1. Add `sanitize_upload_filename()` function
2. Add `validate_upload_file()` function
3. Add `check_disk_space()` function (optional)
4. Reuse existing `handle_error()` for upload errors

**New Functions**:
```python
def sanitize_upload_filename(original_name: str) -> str:
    """Create safe filename for uploaded file with timestamp prefix."""

def validate_upload_file(filename: str, size: int, content_type: str) -> None:
    """Validate uploaded file meets security and size requirements."""
```

### Step 6: Implement Auto-Import Feature (Optional)
**File**: `custom_components/import_statistics/upload_view.py`

**Tasks**:
1. Add logic to parse import settings from upload request
2. Call `handle_import_from_file_impl()` after file is saved
3. Catch and return import errors in upload response
4. Return combined status (upload + import)

**Flow**:
```python
async def post(self, request: web.Request) -> web.Response:
    # 1. Upload and save file
    filename = await save_uploaded_file(...)

    # 2. If auto_import requested
    if auto_import:
        # Create ServiceCall object
        call = ServiceCall(...)

        # Call existing import service
        try:
            await handle_import_from_file_impl(hass, call)
            status = "imported"
        except Exception as e:
            status = "uploaded_only"
            error = str(e)

    # 3. Return response
    return web.json_response({...})
```

### Step 7: Add Unit Tests
**File**: `tests/unit_tests/test_upload_helpers.py`

**Test Cases**:
1. `test_sanitize_upload_filename_basic()` - Normal filename
2. `test_sanitize_upload_filename_path_traversal()` - Reject `../`
3. `test_sanitize_upload_filename_special_chars()` - Remove special chars
4. `test_sanitize_upload_filename_timestamp()` - Verify timestamp added
5. `test_validate_upload_file_valid()` - Accept valid file
6. `test_validate_upload_file_too_large()` - Reject oversized file
7. `test_validate_upload_file_invalid_extension()` - Reject wrong extension
8. `test_validate_upload_file_invalid_mime()` - Reject wrong MIME type

### Step 8: Add Integration Tests
**File**: `tests/integration_tests_mock/test_upload_view.py`

**Test Cases**:
1. `test_upload_csv_file()` - Upload valid CSV
2. `test_upload_json_file()` - Upload valid JSON
3. `test_upload_file_too_large()` - Reject oversized file
4. `test_upload_invalid_extension()` - Reject invalid extension
5. `test_upload_path_traversal()` - Reject path traversal attempt
6. `test_upload_requires_auth()` - Verify authentication required
7. `test_upload_requires_admin()` - Verify admin access required
8. `test_upload_with_auto_import()` - Test auto-import feature
9. `test_upload_saves_to_config_dir()` - Verify file location

### Step 9: Update Documentation
**Files**:
- `README.md`
- `docs/user/troubleshooting-tips.md`
- `CHANGELOG.md`

**Tasks**:
1. Add "Uploading Files" section to README
2. Add upload URL and instructions
3. Add screenshots of upload form
4. Update troubleshooting guide with upload-related issues
5. Add changelog entry for new feature

**README Section**:
```markdown
## Uploading Files

You can upload files directly from your browser instead of manually copying them to the config directory.

### How to Upload

1. Navigate to: `http://<your-ha-instance>:8123/import_statistics/upload`
2. Click "Choose File" and select your CSV/TSV/JSON file
3. (Optional) Enable "Automatically import after upload" and configure settings
4. Click "Upload File"
5. If auto-import is disabled, copy the filename and use it in Developer Tools → Actions

### Upload Limits

- Maximum file size: 50 MB
- Allowed file types: `.csv`, `.tsv`, `.txt`, `.json`
- Files must be UTF-8 encoded

### Security

- Upload requires administrator access
- Filenames are automatically sanitized
- Files are saved to the Home Assistant config directory
```

### Step 10: Add Configuration Options (Optional)
**File**: `custom_components/import_statistics/config_flow.py`

**Tasks**:
1. Add upload configuration options to config flow
2. Add `enable_upload` option (default: true)
3. Add `max_upload_size_mb` option (default: 50)
4. Store config in entry data
5. Use config in upload view

**Config Schema**:
```python
vol.Schema({
    vol.Optional("enable_upload", default=True): bool,
    vol.Optional("max_upload_size_mb", default=50): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=500)
    ),
})
```

### Step 11: Manual Testing
**Checklist**:
1. Start Home Assistant with integration
2. Navigate to upload URL
3. Upload small CSV file (< 1MB)
4. Verify file appears in config directory
5. Import uploaded file via Developer Tools
6. Upload large file (near 50MB limit)
7. Try to upload invalid file type (e.g., `.exe`)
8. Try to upload file with path traversal in name
9. Test auto-import feature
10. Test with special characters in filename
11. Verify error messages are clear and helpful

### Step 12: Create Screenshots for Documentation
**Tasks**:
1. Take screenshot of upload form (empty state)
2. Take screenshot of upload form (file selected)
3. Take screenshot of success message
4. Take screenshot of error message
5. Save to `assets/` directory
6. Reference in README.md

**Screenshots needed**:
- `assets/upload_form_empty.png`
- `assets/upload_form_selected.png`
- `assets/upload_success.png`
- `assets/upload_error.png`

## Code Structure

### New Files to Create

```
custom_components/import_statistics/
├── upload_view.py              # HTTP endpoint for file upload (API)
├── upload_form_view.py         # HTML form view (UI)
└── const.py                    # Add upload constants

tests/
├── unit_tests/
│   └── test_upload_helpers.py  # Test sanitization and validation
└── integration_tests_mock/
    └── test_upload_view.py     # Test upload endpoint

assets/
├── upload_form_empty.png       # Documentation screenshot
├── upload_form_selected.png    # Documentation screenshot
├── upload_success.png          # Documentation screenshot
└── upload_error.png            # Documentation screenshot
```

### Files to Modify

```
custom_components/import_statistics/
├── __init__.py                 # Register upload views
├── const.py                    # Add upload constants
├── helpers.py                  # Add upload helper functions
└── config_flow.py              # Add upload config options (optional)

README.md                       # Add upload documentation
CHANGELOG.md                    # Add feature entry
docs/user/troubleshooting-tips.md  # Add upload troubleshooting
```

## Implementation Order

**Recommended sequence**:

1. **Backend Core** (Steps 1, 4, 5)
   - Create upload view with file handling
   - Add constants
   - Add helper functions
   - No UI yet, test with curl/Postman

2. **Frontend Form** (Step 2)
   - Create HTML form view
   - Basic styling
   - Test in browser

3. **Integration** (Step 3)
   - Register views in `__init__.py`
   - Test end-to-end upload flow

4. **Auto-Import** (Step 6)
   - Add auto-import logic
   - Test combined upload + import

5. **Testing** (Steps 7, 8, 11)
   - Write unit tests
   - Write integration tests
   - Manual testing

6. **Documentation** (Steps 9, 12)
   - Update README
   - Create screenshots
   - Update changelog

7. **Polish** (Step 10)
   - Add configuration options
   - Final testing

## Code Examples

### Example: Upload View Structure

```python
"""File upload view for Import Statistics integration."""

import datetime as dt
import re
from pathlib import Path
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView, require_admin
from homeassistant.core import HomeAssistant

from .const import (
    ALLOWED_MIME_TYPES,
    ALLOWED_UPLOAD_EXTENSIONS,
    MAX_UPLOAD_SIZE_BYTES,
)
from .helpers import handle_error


class ImportStatisticsUploadView(HomeAssistantView):
    """Handle file uploads for import statistics."""

    url = "/api/import_statistics/upload"
    name = "api:import_statistics:upload"
    requires_auth = True

    @require_admin
    async def post(self, request: web.Request) -> web.Response:
        """Handle file upload POST request."""
        hass: HomeAssistant = request.app["hass"]

        try:
            # Parse multipart form data
            reader = await request.multipart()
            field = await reader.next()

            if field.name != "file":
                return web.json_response(
                    {"success": False, "error": "No file field in request"},
                    status=400
                )

            # Get filename and validate
            filename = field.filename
            if not filename:
                return web.json_response(
                    {"success": False, "error": "No filename provided"},
                    status=400
                )

            # Read file data
            file_data = await field.read()
            file_size = len(file_data)

            # Validate file
            validate_upload_file(filename, file_size, field.content_type)

            # Sanitize filename
            safe_filename = sanitize_upload_filename(filename)

            # Save to config directory
            file_path = Path(hass.config.config_dir) / safe_filename

            # Write file
            await hass.async_add_executor_job(
                lambda: file_path.write_bytes(file_data)
            )

            return web.json_response({
                "success": True,
                "filename": safe_filename,
                "size": file_size,
                "path": str(file_path),
                "message": "File uploaded successfully"
            })

        except Exception as e:
            return web.json_response(
                {"success": False, "error": str(e)},
                status=400
            )


def validate_upload_file(filename: str, size: int, content_type: str) -> None:
    """Validate uploaded file meets requirements."""
    # Check size
    if size > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(
            f"File too large: {size / 1024 / 1024:.1f} MB "
            f"(maximum: {MAX_UPLOAD_SIZE_BYTES / 1024 / 1024:.0f} MB)"
        )

    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError(
            f"Invalid file type: {ext}. "
            f"Allowed types: {', '.join(ALLOWED_UPLOAD_EXTENSIONS)}"
        )

    # Check MIME type (optional, some browsers send generic types)
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        # Log warning but don't reject (MIME types can be unreliable)
        _LOGGER.warning(
            "Unexpected content type: %s for file %s",
            content_type,
            filename
        )


def sanitize_upload_filename(original_name: str) -> str:
    """Create safe filename for uploaded file."""
    # Get just the filename (remove any path components)
    name = Path(original_name).name

    # Remove dangerous characters (keep only alphanumeric, dash, underscore, dot)
    name = re.sub(r'[^\w\s\-\.]', '', name)

    # Replace spaces with underscores
    name = name.replace(' ', '_')

    # Add timestamp prefix
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(name).stem
    ext = Path(name).suffix

    return f"uploaded_{stem}_{timestamp}{ext}"
```

### Example: Upload Form HTML

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Import Statistics - Upload File</title>
    <style>
        body {
            font-family: Roboto, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .card {
            background: white;
            border-radius: 8px;
            padding: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 {
            margin-top: 0;
            color: #333;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #555;
        }
        input[type="file"] {
            width: 100%;
            padding: 10px;
            border: 2px dashed #ccc;
            border-radius: 4px;
            cursor: pointer;
        }
        input[type="file"]:hover {
            border-color: #03a9f4;
        }
        select, input[type="text"] {
            width: 100%;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 14px;
        }
        button {
            background-color: #03a9f4;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
            width: 100%;
        }
        button:hover {
            background-color: #0288d1;
        }
        button:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        .status {
            margin-top: 20px;
            padding: 12px;
            border-radius: 4px;
            display: none;
        }
        .status.success {
            background-color: #e8f5e9;
            color: #2e7d32;
            border: 1px solid #4caf50;
        }
        .status.error {
            background-color: #ffebee;
            color: #c62828;
            border: 1px solid #f44336;
        }
        .settings-group {
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 16px;
            margin-top: 12px;
            display: none;
        }
        .settings-group.visible {
            display: block;
        }
        .info {
            background-color: #e3f2fd;
            padding: 12px;
            border-radius: 4px;
            margin-bottom: 20px;
            font-size: 14px;
            color: #1565c0;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>📊 Import Statistics - Upload File</h1>

        <div class="info">
            Upload CSV, TSV, or JSON files to import statistics into Home Assistant.
            Maximum file size: 50 MB.
        </div>

        <form id="uploadForm" enctype="multipart/form-data">
            <div class="form-group">
                <label for="file">Select File</label>
                <input type="file" id="file" name="file" accept=".csv,.tsv,.txt,.json" required>
            </div>

            <div class="form-group">
                <label>
                    <input type="checkbox" id="autoImport" name="auto_import">
                    Automatically import after upload
                </label>
            </div>

            <div id="importSettings" class="settings-group">
                <h3>Import Settings</h3>

                <div class="form-group">
                    <label for="delimiter">Delimiter</label>
                    <select id="delimiter" name="delimiter">
                        <option value="\t" selected>Tab (\t)</option>
                        <option value=";">Semicolon (;)</option>
                        <option value=",">Comma (,)</option>
                        <option value="|">Pipe (|)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="decimal">Decimal Separator</label>
                    <select id="decimal" name="decimal">
                        <option value="." selected>Dot (.)</option>
                        <option value=",">Comma (,)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="datetime_format">Datetime Format</label>
                    <select id="datetime_format" name="datetime_format">
                        <option value="%d.%m.%Y %H:%M" selected>DD.MM.YYYY HH:MM</option>
                        <option value="%Y.%m.%d %H:%M">YYYY.MM.DD HH:MM</option>
                        <option value="%Y-%m-%d %H:%M">YYYY-MM-DD HH:MM</option>
                        <option value="%m/%d/%Y %H:%M">MM/DD/YYYY HH:MM</option>
                        <option value="%d/%m/%Y %H:%M">DD/MM/YYYY HH:MM</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="unit_from_entity" name="unit_from_entity" checked>
                        Get unit from entity (for internal statistics)
                    </label>
                </div>
            </div>

            <button type="submit" id="submitBtn">Upload File</button>
        </form>

        <div id="status" class="status"></div>
    </div>

    <script>
        // Toggle import settings visibility
        document.getElementById('autoImport').addEventListener('change', function(e) {
            const settings = document.getElementById('importSettings');
            if (e.target.checked) {
                settings.classList.add('visible');
            } else {
                settings.classList.remove('visible');
            }
        });

        // Handle form submission
        document.getElementById('uploadForm').addEventListener('submit', async function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const statusDiv = document.getElementById('status');
            const submitBtn = document.getElementById('submitBtn');

            // Disable submit button
            submitBtn.disabled = true;
            submitBtn.textContent = 'Uploading...';

            try {
                const response = await fetch('/api/import_statistics/upload', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    statusDiv.className = 'status success';
                    statusDiv.style.display = 'block';
                    statusDiv.innerHTML = `
                        <strong>✓ File uploaded successfully!</strong><br><br>
                        <strong>Filename:</strong> ${result.filename}<br>
                        <strong>Size:</strong> ${(result.size / 1024).toFixed(1)} KB<br>
                        <strong>Location:</strong> ${result.path}<br><br>
                        ${result.imported ?
                            '<strong>Status:</strong> File imported successfully!' :
                            '<strong>Next steps:</strong><br>• Go to Developer Tools → Actions<br>• Select: import_statistics.import_from_file<br>• Use filename: ' + result.filename
                        }
                    `;

                    // Reset form
                    this.reset();
                } else {
                    throw new Error(result.error || 'Upload failed');
                }
            } catch (error) {
                statusDiv.className = 'status error';
                statusDiv.style.display = 'block';
                statusDiv.innerHTML = `
                    <strong>✗ Upload failed</strong><br><br>
                    ${error.message}
                `;
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Upload File';
            }
        });
    </script>
</body>
</html>
```

## Testing Strategy

### Unit Tests Focus
- Filename sanitization edge cases
- File validation logic
- Path security checks
- Error message formatting

### Integration Tests Focus
- HTTP endpoint behavior
- Authentication and authorization
- File saving to correct location
- Auto-import integration
- Error responses

### Manual Testing Focus
- Browser compatibility (Chrome, Firefox, Safari, Edge)
- Large file uploads
- Network interruption handling
- User experience flow
- Error message clarity

## Rollout Plan

### Phase 1: MVP (Recommended for initial PR)
**Scope**:
- Basic upload view (API endpoint)
- Simple HTML form view
- File validation and sanitization
- Save to config directory
- Manual import via Developer Tools

**Timeline**: Single PR, focused implementation

**User Value**: Can upload files from browser, no SSH needed

### Phase 2: Enhanced UX (Future PR)
**Scope**:
- Auto-import feature
- Drag-and-drop upload
- File preview
- Better error messages
- Progress indicators

**Timeline**: Follow-up PR after MVP feedback

**User Value**: Streamlined workflow, better UX

### Phase 3: Advanced Features (Future)
**Scope**:
- Custom frontend panel (Lit/TypeScript)
- Upload history
- Batch uploads
- Auto-cleanup options
- Download export files directly

**Timeline**: Based on user demand

**User Value**: Professional, integrated experience

## Success Metrics

### Phase 1 Success Criteria
- ✅ User can upload file from browser
- ✅ File is saved to config directory
- ✅ Filename is sanitized and safe
- ✅ User receives clear confirmation
- ✅ File can be imported via existing service
- ✅ All security validations pass
- ✅ Documentation is clear and complete

### User Feedback Goals
- Reduced support requests about "how to copy files"
- Positive feedback on ease of use
- No security incidents related to upload
- Clear error messages reduce confusion

## Risk Mitigation

### Risk: Security Vulnerabilities
**Mitigation**:
- Admin-only access
- Strict file validation
- Path traversal prevention
- File size limits
- Comprehensive security testing

### Risk: Disk Space Issues
**Mitigation**:
- File size limits
- Optional auto-cleanup
- Clear error if disk full
- Document cleanup recommendations

### Risk: User Confusion
**Mitigation**:
- Clear documentation
- Helpful error messages
- Step-by-step instructions
- Screenshots and examples

### Risk: Breaking Existing Functionality
**Mitigation**:
- No changes to existing import services
- Upload is additive feature only
- Comprehensive testing
- Can be disabled via config

## Future Enhancements

### Potential Features (Post-MVP)
1. **Download Export Files**: Add download button to export service
2. **File Browser**: List uploaded files with delete option
3. **Drag-and-Drop**: Enhanced upload UX
4. **File Preview**: Show first 10 rows before import
5. **Batch Upload**: Upload multiple files at once
6. **Upload History**: Track all uploads with timestamps
7. **Auto-Cleanup**: Configurable retention policy
8. **Validation Preview**: Show validation errors before import
9. **Template Files**: Provide downloadable templates
10. **Direct Import**: Combine upload + import in single action

### Integration Opportunities
1. **Home Assistant File Browser**: Integrate with HA's file browser if available
2. **Backup Integration**: Include uploaded files in HA backups
3. **Notification Service**: Send notification when import completes
4. **Automation Triggers**: Trigger automations on successful import

## Conclusion

The recommended implementation is a **Simple HTTP View with HTML Form** that provides:

✅ **Immediate value**: Solves the core problem (upload without SSH)
✅ **Low complexity**: Single Python file + HTML form
✅ **Secure**: Admin-only, validated, sanitized
✅ **Maintainable**: No build process, clear code
✅ **Extensible**: Can enhance later based on feedback

This approach balances user needs, development effort, and architectural consistency with the existing integration.
