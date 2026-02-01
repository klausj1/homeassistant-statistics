"""Upload view for import_statistics integration."""

import datetime as dt
import logging
from pathlib import Path

from aiohttp import web
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.http import HomeAssistantView

from custom_components.import_statistics.const import UPLOAD_URL_PATH
from custom_components.import_statistics.helpers import sanitize_filename, validate_upload_file

_LOGGER = logging.getLogger(__name__)


class ImportStatisticsUploadView(HomeAssistantView):
    """View to handle file uploads for import_statistics."""

    url = UPLOAD_URL_PATH
    name = "api:import_statistics:upload"
    requires_auth = True

    def __init__(self) -> None:
        """Initialize the upload view."""
        super().__init__()

    async def post(self, request: web.Request) -> web.Response:  # noqa: PLR0911
        """
        Handle file upload via HTTP POST.

        Accepts multipart/form-data with a 'file' field containing the uploaded file.
        Validates file extension and size, sanitizes filename, and saves to config directory.
        Requires admin authentication.

        Args:
        ----
            request: aiohttp web request containing the uploaded file

        Returns:
        -------
            web.Response: JSON response with upload status and filename

        """
        hass = request.app["hass"]

        # Check if user is admin
        if not request["hass_user"].is_admin:
            return web.json_response(
                {"success": False, "error": "Admin access required"},
                status=403,
            )

        try:
            # Read multipart form data
            reader = await request.multipart()
            file_field = await reader.next()

            if file_field is None:
                return web.json_response(
                    {"success": False, "error": "No file provided"},
                    status=400,
                )

            # Get field name and filename from the BodyPartReader
            # Type checker doesn't recognize BodyPartReader attributes, but they exist at runtime
            field_name = file_field.name if hasattr(file_field, "name") else None  # type: ignore[attr-defined]
            if field_name != "file":
                return web.json_response(
                    {"success": False, "error": "File must be uploaded in 'file' field"},
                    status=400,
                )

            # Get original filename
            original_filename = file_field.filename if hasattr(file_field, "filename") else None  # type: ignore[attr-defined]
            if not original_filename:
                return web.json_response(
                    {"success": False, "error": "Filename is required"},
                    status=400,
                )

            # Read file content
            file_content = await file_field.read()  # type: ignore[attr-defined]
            file_size = len(file_content)

            # Validate file
            try:
                validate_upload_file(original_filename, file_size)
            except HomeAssistantError as err:
                _LOGGER.warning("File validation failed: %s", err)
                return web.json_response(
                    {"success": False, "error": str(err)},
                    status=400,
                )

            # Sanitize filename
            try:
                sanitized_name = sanitize_filename(original_filename)
            except HomeAssistantError as err:
                _LOGGER.warning("Filename sanitization failed: %s", err)
                return web.json_response(
                    {"success": False, "error": str(err)},
                    status=400,
                )

            # Create unique filename with timestamp
            timestamp = dt.datetime.now(tz=dt.UTC).strftime("%Y%m%d_%H%M%S")
            file_path = Path(sanitized_name)
            stem = file_path.stem
            suffix = file_path.suffix
            unique_filename = f"uploaded_{stem}_{timestamp}{suffix}"

            # Save to config directory
            config_dir = Path(hass.config.path())
            target_path = config_dir / unique_filename

            # Ensure we're writing within config directory (security check)
            try:
                target_path.resolve().relative_to(config_dir.resolve())
            except ValueError:
                _LOGGER.warning("Path traversal attempt detected: %s", target_path)
                return web.json_response(
                    {"success": False, "error": "Invalid file path"},
                    status=400,
                )

            # Write file
            try:
                await hass.async_add_executor_job(target_path.write_bytes, file_content)
            except OSError as err:
                _LOGGER.warning("Failed to write file %s: %s", target_path, err)
                return web.json_response(
                    {"success": False, "error": f"Failed to save file: {err}"},
                    status=500,
                )

            _LOGGER.info("File uploaded successfully: %s (%d bytes)", unique_filename, file_size)

            return web.json_response(
                {
                    "success": True,
                    "filename": unique_filename,
                    "size": file_size,
                    "message": "File uploaded successfully",
                },
                status=200,
            )

        except Exception as err:
            _LOGGER.exception("Unexpected error during file upload")
            return web.json_response(
                {"success": False, "error": f"Upload failed: {err}"},
                status=500,
            )
