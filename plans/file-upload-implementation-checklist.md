# File Upload Implementation Checklist

This checklist provides the step-by-step tasks for implementing the file upload feature in Code mode.

## Phase 1: MVP Implementation

### Backend Core

- [ ] Add upload constants to [`const.py`](custom_components/import_statistics/const.py)
  - [ ] Add `MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024`
  - [ ] Add `ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".tsv", ".txt", ".json"}`
  - [ ] Add `ALLOWED_MIME_TYPES` set
  - [ ] Add `UPLOAD_API_URL = "/api/import_statistics/upload"`
  - [ ] Add `UPLOAD_FORM_URL = "/import_statistics/upload"`

- [ ] Add upload helper functions to [`helpers.py`](custom_components/import_statistics/helpers.py)
  - [ ] Implement `sanitize_upload_filename(original_name: str) -> str`
    - [ ] Remove path components
    - [ ] Remove dangerous characters
    - [ ] Replace spaces with underscores
    - [ ] Add timestamp prefix
    - [ ] Preserve file extension
  - [ ] Implement `validate_upload_file(filename: str, size: int, content_type: str) -> None`
    - [ ] Check file size against `MAX_UPLOAD_SIZE_BYTES`
    - [ ] Check extension against `ALLOWED_UPLOAD_EXTENSIONS`
    - [ ] Log warning for unexpected MIME types
    - [ ] Raise `ValueError` with clear messages on validation failure

- [ ] Create `upload_view.py` for API endpoint
  - [ ] Import required modules (`aiohttp.web`, `HomeAssistantView`, `require_admin`)
  - [ ] Create `ImportStatisticsUploadView` class
    - [ ] Set `url = "/api/import_statistics/upload"`
    - [ ] Set `name = "api:import_statistics:upload"`
    - [ ] Set `requires_auth = True`
  - [ ] Implement `post()` method with `@require_admin` decorator
    - [ ] Parse multipart form data
    - [ ] Extract file field from request
    - [ ] Read file data
    - [ ] Validate file using `validate_upload_file()`
    - [ ] Sanitize filename using `sanitize_upload_filename()`
    - [ ] Construct file path in config directory
    - [ ] Save file using `hass.async_add_executor_job()`
    - [ ] Return JSON response with success status and filename
    - [ ] Handle exceptions and return error responses

- [ ] Create `upload_form_view.py` for HTML form
  - [ ] Import required modules
  - [ ] Create `ImportStatisticsUploadFormView` class
    - [ ] Set `url = "/import_statistics/upload"`
    - [ ] Set `name = "import_statistics:upload_form"`
    - [ ] Set `requires_auth = True`
  - [ ] Implement `get()` method with `@require_admin` decorator
    - [ ] Define HTML template with file upload form
    - [ ] Add CSS styling (HA-inspired)
    - [ ] Add JavaScript for form submission
    - [ ] Add auto-import checkbox and settings
    - [ ] Add status display area
    - [ ] Return HTML response

- [ ] Register views in [`__init__.py`](custom_components/import_statistics/__init__.py)
  - [ ] Import `ImportStatisticsUploadView` and `ImportStatisticsUploadFormView`
  - [ ] Register both views in `async_setup_entry()`
  - [ ] Ensure views are registered before returning True

### Testing

- [ ] Create unit tests in `tests/unit_tests/test_upload_helpers.py`
  - [ ] Test `sanitize_upload_filename()` with normal filename
  - [ ] Test `sanitize_upload_filename()` with path traversal (`../`)
  - [ ] Test `sanitize_upload_filename()` with special characters
  - [ ] Test `sanitize_upload_filename()` with spaces
  - [ ] Test `sanitize_upload_filename()` timestamp format
  - [ ] Test `validate_upload_file()` with valid file
  - [ ] Test `validate_upload_file()` with oversized file
  - [ ] Test `validate_upload_file()` with invalid extension
  - [ ] Test `validate_upload_file()` with invalid MIME type

- [ ] Create integration tests in `tests/integration_tests_mock/test_upload_view.py`
  - [ ] Test upload CSV file successfully
  - [ ] Test upload JSON file successfully
  - [ ] Test upload TSV file successfully
  - [ ] Test reject oversized file
  - [ ] Test reject invalid extension
  - [ ] Test reject path traversal in filename
  - [ ] Test authentication required
  - [ ] Test admin access required
  - [ ] Test file saved to correct location
  - [ ] Test sanitized filename format

### Documentation

- [ ] Update [`README.md`](README.md)
  - [ ] Add "Uploading Files" section after "How to Import"
  - [ ] Document upload URL
  - [ ] Document upload process steps
  - [ ] Document file size and type limits
  - [ ] Add security note about admin access
  - [ ] Add example workflow

- [ ] Update [`CHANGELOG.md`](CHANGELOG.md)
  - [ ] Add entry for new upload feature
  - [ ] Document breaking changes (if any)
  - [ ] Credit contributors

- [ ] Update `docs/user/troubleshooting-tips.md`
  - [ ] Add troubleshooting section for upload issues
  - [ ] Document common upload errors
  - [ ] Add solutions for file size/type errors

- [ ] Create screenshots for documentation
  - [ ] Screenshot: Upload form (empty state)
  - [ ] Screenshot: Upload form (file selected)
  - [ ] Screenshot: Success message
  - [ ] Screenshot: Error message
  - [ ] Save to `assets/` directory
  - [ ] Reference in README

### Manual Testing

- [ ] Test basic upload flow
  - [ ] Navigate to upload URL
  - [ ] Upload small CSV file (< 1MB)
  - [ ] Verify file appears in config directory
  - [ ] Verify filename is sanitized correctly
  - [ ] Import uploaded file via Developer Tools
  - [ ] Verify import succeeds

- [ ] Test file validation
  - [ ] Upload file near size limit (45-50MB)
  - [ ] Try to upload oversized file (> 50MB)
  - [ ] Try to upload invalid file type (`.exe`, `.zip`)
  - [ ] Verify error messages are clear

- [ ] Test security
  - [ ] Try filename with `../` (path traversal)
  - [ ] Try filename with absolute path (`/etc/passwd`)
  - [ ] Try filename with special characters
  - [ ] Verify all attempts are blocked/sanitized
  - [ ] Test without authentication (should fail)
  - [ ] Test with non-admin user (should fail)

- [ ] Test different file types
  - [ ] Upload `.csv` file
  - [ ] Upload `.tsv` file
  - [ ] Upload `.txt` file (CSV format)
  - [ ] Upload `.json` file
  - [ ] Verify all types work correctly

- [ ] Test edge cases
  - [ ] Upload file with very long filename
  - [ ] Upload file with Unicode characters in name
  - [ ] Upload empty file
  - [ ] Upload file with special characters (°, ³, etc.)
  - [ ] Test on different browsers (Chrome, Firefox, Safari, Edge)

## Phase 2: Enhanced UX (Optional Future Work)

### Auto-Import Feature

- [ ] Extend `upload_view.py` for auto-import
  - [ ] Parse import settings from form data
  - [ ] Create `ServiceCall` object with settings
  - [ ] Call `handle_import_from_file_impl()` after upload
  - [ ] Catch import errors and include in response
  - [ ] Return combined status (upload + import)

- [ ] Update HTML form for auto-import
  - [ ] Show/hide import settings based on checkbox
  - [ ] Validate import settings client-side
  - [ ] Display combined status (upload + import)

- [ ] Test auto-import
  - [ ] Upload with auto-import enabled
  - [ ] Verify file uploaded and imported
  - [ ] Test with invalid data (upload succeeds, import fails)
  - [ ] Verify error handling

### Enhanced UI

- [ ] Add drag-and-drop upload zone
  - [ ] Implement drop zone with JavaScript
  - [ ] Add visual feedback on drag over
  - [ ] Handle dropped files

- [ ] Add file preview
  - [ ] Parse first 10 rows of CSV/TSV
  - [ ] Display in table format
  - [ ] Show column headers
  - [ ] Detect delimiter automatically

- [ ] Add progress indicators
  - [ ] Show upload progress bar
  - [ ] Show import progress (if auto-import)
  - [ ] Disable form during processing

- [ ] Improve error messages
  - [ ] Show specific validation errors
  - [ ] Highlight problematic rows
  - [ ] Suggest fixes

## Phase 3: Advanced Features (Future)

### Custom Frontend Panel

- [ ] Set up frontend build process
  - [ ] Add TypeScript configuration
  - [ ] Add build scripts
  - [ ] Configure bundler (webpack/rollup)

- [ ] Create Lit panel component
  - [ ] Design panel layout
  - [ ] Implement file upload with HA components
  - [ ] Add import/export tabs
  - [ ] Integrate with HA design system

- [ ] Register panel in Home Assistant
  - [ ] Add panel registration in `__init__.py`
  - [ ] Add sidebar menu item
  - [ ] Configure panel icon

### Additional Features

- [ ] File browser
  - [ ] List uploaded files
  - [ ] Show file metadata (size, date)
  - [ ] Add delete button
  - [ ] Add download button

- [ ] Upload history
  - [ ] Track all uploads in database
  - [ ] Show upload history in UI
  - [ ] Filter by date/status

- [ ] Auto-cleanup
  - [ ] Add retention policy config
  - [ ] Implement cleanup service
  - [ ] Schedule periodic cleanup
  - [ ] Log cleanup actions

- [ ] Batch operations
  - [ ] Upload multiple files
  - [ ] Import multiple files
  - [ ] Show batch progress

## Dependencies

### Required (Phase 1)
- None (all dependencies already in Home Assistant core)

### Optional (Phase 2+)
- None (vanilla JavaScript approach)

### Optional (Phase 3)
- TypeScript
- Lit
- Home Assistant frontend build tools

## Estimated Scope

### Phase 1 (MVP)
**Files to create**: 3
- `upload_view.py` (~150 lines)
- `upload_form_view.py` (~200 lines including HTML)
- `tests/unit_tests/test_upload_helpers.py` (~150 lines)
- `tests/integration_tests_mock/test_upload_view.py` (~200 lines)

**Files to modify**: 3
- `const.py` (+20 lines)
- `helpers.py` (+60 lines)
- `__init__.py` (+10 lines)
- `README.md` (+50 lines)
- `CHANGELOG.md` (+5 lines)

**Total new code**: ~700 lines
**Total modifications**: ~85 lines

### Phase 2 (Enhanced UX)
**Additional code**: ~300 lines (JavaScript enhancements, auto-import logic)

### Phase 3 (Custom Panel)
**Additional code**: ~1000+ lines (TypeScript panel, build config)

## Notes for Implementation

### Code Style Compliance
- Follow `.ruff.toml` rules (line length 160, all linting enabled)
- Add type hints to all functions
- Use `handle_error()` for all validation errors
- Follow existing patterns from codebase

### Security Checklist
- ✅ Admin-only access (`@require_admin`)
- ✅ File size validation
- ✅ Extension whitelist
- ✅ Filename sanitization
- ✅ Path traversal prevention
- ✅ MIME type checking
- ✅ Save within config directory only

### Integration Checklist
- ✅ No changes to existing import services
- ✅ Reuse existing validation functions
- ✅ Follow existing error handling patterns
- ✅ Maintain backward compatibility
- ✅ Can be disabled if needed

### Testing Checklist
- ✅ Unit tests for all helper functions
- ✅ Integration tests for HTTP endpoints
- ✅ Security tests for path traversal
- ✅ Manual testing on real HA instance
- ✅ Browser compatibility testing

## Ready for Implementation

This plan is ready to be handed off to Code mode for implementation. The architecture is well-defined, security considerations are documented, and the implementation steps are clear and actionable.

**Recommended starting point**: Phase 1 MVP (Simple HTTP View)

**Next step**: Switch to Code mode to begin implementation.
