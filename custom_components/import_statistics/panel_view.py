"""Panel view for import_statistics integration."""

import logging
from pathlib import Path

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)


class ImportStatisticsPanelView(HomeAssistantView):
    """View to serve the import statistics panel."""

    url = "/api/import_statistics/panel"
    name = "api:import_statistics:panel"
    requires_auth = True

    def __init__(self, panel_dir: Path) -> None:
        """Initialize the panel view."""
        super().__init__()
        self.panel_dir = panel_dir

    async def get(self, request: web.Request) -> web.Response:
        """Serve the panel HTML."""
        index_path = self.panel_dir / "index.html"

        if not index_path.exists():
            return web.Response(
                text="Panel not found. Please build the frontend.",
                status=404,
            )

        try:
            html_content = await request.app["hass"].async_add_executor_job(index_path.read_text, "utf-8")
            return web.Response(
                text=html_content,
                content_type="text/html",
            )
        except Exception as err:
            _LOGGER.error("Failed to serve panel: %s", err)
            return web.Response(
                text=f"Error loading panel: {err}",
                status=500,
            )


class ImportStatisticsAssetView(HomeAssistantView):
    """View to serve panel assets (JS, CSS, etc)."""

    url = "/api/import_statistics/panel/{filename}"
    name = "api:import_statistics:panel:asset"
    requires_auth = True

    def __init__(self, panel_dir: Path) -> None:
        """Initialize the asset view."""
        super().__init__()
        self.panel_dir = panel_dir

    async def get(self, request: web.Request, filename: str) -> web.Response:
        """Serve panel assets."""
        # Security: prevent path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            return web.Response(text="Invalid filename", status=400)

        file_path = self.panel_dir / filename

        if not file_path.exists() or not file_path.is_file():
            return web.Response(text="File not found", status=404)

        # Determine content type
        content_type = "application/octet-stream"
        if filename.endswith(".js"):
            content_type = "application/javascript"
        elif filename.endswith(".css"):
            content_type = "text/css"
        elif filename.endswith(".map"):
            content_type = "application/json"

        try:
            file_content = await request.app["hass"].async_add_executor_job(file_path.read_bytes)
            return web.Response(
                body=file_content,
                content_type=content_type,
            )
        except Exception as err:
            _LOGGER.error("Failed to serve asset %s: %s", filename, err)
            return web.Response(
                text=f"Error loading asset: {err}",
                status=500,
            )
