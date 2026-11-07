"""Real Home Assistant integration tests for import usability."""
# ruff: noqa: SLF001

import time
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from tests.integration_tests.test_integration_delta_imports import TestIntegrationAll as _IntegrationHarness


@pytest.mark.integration
@pytest.mark.usefixtures("allow_socket_for_integration")
class TestImportUsability:
    """Verify counter mode selection and missing-entity handling against a real HA recorder."""

    @classmethod
    def setup_class(cls) -> None:
        """Initialize the shared Home Assistant startup harness."""
        _IntegrationHarness.setup_class()

    @classmethod
    def teardown_class(cls) -> None:
        """Stop Home Assistant if this test class started it."""
        _IntegrationHarness.teardown_class()

    def setup_method(self) -> None:
        """Create a harness instance for the service and startup helpers."""
        self.ha = _IntegrationHarness()

    @pytest.mark.asyncio
    async def test_export_both_counter_fields_and_import_modes(self) -> None:
        """Verify mixed exports with both counter forms import via explicit modes and persist."""
        config_dir = Path(__file__).parent.parent.parent / "config"
        suffix = str(time.time_ns())
        counter_id = f"sensor:issue282_roundtrip_{suffix}"
        source_name = f"issue282_{suffix}_mixed_source.tsv"
        export_names = [
            f"issue282_{suffix}_mixed_export.tsv",
            f"issue282_{suffix}_mixed_after_sum.tsv",
            f"issue282_{suffix}_mixed_after_delta.tsv",
        ]
        test_paths = [config_dir / source_name, *(config_dir / name for name in export_names)]

        is_ready = await self.ha._wait_for_ha_startup(timeout_seconds=180)
        assert is_ready, "Home Assistant did not start within 3 minutes"

        source_rows = [
            ["sensor.mixed_test_temp", "°C", "15.01.2024 00:00", 18, 22, 20, "", ""],
            ["sensor.mixed_test_temp", "°C", "15.01.2024 01:00", 19, 23, 21, "", ""],
            ["sensor.mixed_test_temp", "°C", "15.01.2024 02:00", 20, 24, 22, "", ""],
            ["sensor.mixed_test_temp", "°C", "15.01.2024 03:00", 21, 25, 23, "", ""],
            [counter_id, "kWh", "15.01.2024 00:00", "", "", "", 50, 500],
            [counter_id, "kWh", "15.01.2024 01:00", "", "", "", 50, 500],
            [counter_id, "kWh", "15.01.2024 02:00", "", "", "", 53, 503],
            [counter_id, "kWh", "15.01.2024 03:00", "", "", "", 57, 507],
        ]
        columns = ["statistic_id", "unit", "start", "min", "max", "mean", "sum", "state"]

        try:
            pd.DataFrame(source_rows, columns=columns).to_csv(config_dir / source_name, sep="\t", index=False)
            assert await self.ha._call_service(
                "import_from_file",
                {
                    "filename": source_name,
                    "timezone_identifier": "Europe/Vienna",
                    "delimiter": "\t",
                    "decimal": "dot ('.')",
                },
                ha_url=self.ha.ha_url,
                token=self.ha.ha_token,
            ), "Failed to seed sensor and counter statistics"

            export_data: dict[str, Any] = {
                "filename": export_names[0],
                "entities": ["sensor.mixed_test_temp", counter_id],
                "start_time": "2024-01-15 01:00:00",
                "end_time": "2024-01-15 03:00:00",
                "timezone_identifier": "Europe/Vienna",
                "counter_fields": "both",
            }
            assert await self.ha._call_service(
                "export_statistics", export_data, ha_url=self.ha.ha_url, token=self.ha.ha_token
            ), "Failed to export both counter fields"

            exported = pd.read_csv(config_dir / export_names[0], sep="\t")
            assert {"min", "max", "mean", "sum", "state", "delta"} <= set(exported.columns)
            counter_rows = exported[exported["statistic_id"] == counter_id]
            assert counter_rows[["sum", "state", "delta"]].notna().all().all()
            assert counter_rows["delta"].tolist() == [0, 3, 4]

            status, body = await self.ha._call_service_with_response(
                "import_from_file",
                {
                    "filename": export_names[0],
                    "timezone_identifier": "Europe/Vienna",
                    "delimiter": "\t",
                    "decimal": "dot ('.')",
                    "counter_mode": "auto",
                },
                ha_url=self.ha.ha_url,
                token=self.ha.ha_token,
            )
            assert status not in (200, 201), f"Auto mode unexpectedly imported ambiguous data: {body}"
            assert "counter_mode" in body, f"Unexpected auto-mode failure: {body}"
            assert "ambiguous" in body.lower(), f"Unexpected auto-mode failure: {body}"

            for mode, export_name in (("sum", export_names[1]), ("delta", export_names[2])):
                assert await self.ha._call_service(
                    "import_from_file",
                    {
                        "filename": export_names[0],
                        "timezone_identifier": "Europe/Vienna",
                        "delimiter": "\t",
                        "decimal": "dot ('.')",
                        "counter_mode": mode,
                    },
                    ha_url=self.ha.ha_url,
                    token=self.ha.ha_token,
                ), f"Failed to import exported data with counter_mode={mode}"

                assert await self.ha._call_service(
                    "export_statistics",
                    {**export_data, "filename": export_name},
                    ha_url=self.ha.ha_url,
                    token=self.ha.ha_token,
                ), f"Failed to export database statistics after counter_mode={mode}"
                persisted = pd.read_csv(config_dir / export_name, sep="\t")
                persisted_counter = persisted[persisted["statistic_id"] == counter_id]
                assert persisted_counter["sum"].tolist() == [50, 53, 57]
                assert persisted_counter["state"].tolist() == [500, 503, 507]
                assert persisted_counter["delta"].tolist() == [0, 3, 4]
                persisted_sensor = persisted[persisted["statistic_id"] == "sensor.mixed_test_temp"]
                assert persisted_sensor["mean"].tolist() == [21, 22, 23]
        finally:
            for path in test_paths:
                path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_import_measurements_with_missing_recorder_entity(self) -> None:
        """Verify missing recorder statistics fail by default and can be skipped explicitly."""
        config_dir = Path(__file__).parent.parent.parent / "config"
        suffix = str(time.time_ns())
        source_name = f"issue282_{suffix}_sensor_missing_entity.tsv"
        export_name = f"issue282_{suffix}_sensor_after_skip.tsv"
        source_path = config_dir / source_name
        export_path = config_dir / export_name
        skipped_reports_before = set(config_dir.glob("skipped_unknown_entities_*.csv"))

        is_ready = await self.ha._wait_for_ha_startup(timeout_seconds=180)
        assert is_ready, "Home Assistant did not start within 3 minutes"

        pd.DataFrame(
            [
                ["sensor.mixed_test_temp", "°C", "16.01.2024 01:00", 19, 23, 21],
                ["sensor.issue282_missing", "°C", "16.01.2024 01:00", 10, 12, 11],
            ],
            columns=["statistic_id", "unit", "start", "min", "max", "mean"],
        ).to_csv(source_path, sep="\t", index=False)

        try:
            status, body = await self.ha._call_service_with_response(
                "import_from_file",
                {
                    "filename": source_name,
                    "timezone_identifier": "Europe/Vienna",
                    "delimiter": "\t",
                    "decimal": "dot ('.')",
                    "ignore_unknown_entities": False,
                },
                ha_url=self.ha.ha_url,
                token=self.ha.ha_token,
            )
            assert status not in (200, 201), f"Missing recorder entity unexpectedly imported: {body}"
            assert "sensor.issue282_missing" in body, f"Unexpected missing-entity failure: {body}"

            no_partial_import_status, no_partial_import_body = await self.ha._call_service_with_response(
                "export_statistics",
                {
                    "filename": export_name,
                    "entities": ["sensor.mixed_test_temp"],
                    "start_time": "2024-01-16 01:00:00",
                    "end_time": "2024-01-16 01:00:00",
                    "timezone_identifier": "Europe/Vienna",
                },
                ha_url=self.ha.ha_url,
                token=self.ha.ha_token,
            )
            assert no_partial_import_status not in (200, 201), f"Failed import partially wrote valid rows: {no_partial_import_body}"

            assert await self.ha._call_service(
                "import_from_file",
                {
                    "filename": source_name,
                    "timezone_identifier": "Europe/Vienna",
                    "delimiter": "\t",
                    "decimal": "dot ('.')",
                    "ignore_unknown_entities": True,
                },
                ha_url=self.ha.ha_url,
                token=self.ha.ha_token,
            ), "Import with ignore_unknown_entities=true failed"

            assert await self.ha._call_service(
                "export_statistics",
                {
                    "filename": export_name,
                    "entities": ["sensor.mixed_test_temp", "sensor.issue282_missing"],
                    "start_time": "2024-01-16 01:00:00",
                    "end_time": "2024-01-16 01:00:00",
                    "timezone_identifier": "Europe/Vienna",
                },
                ha_url=self.ha.ha_url,
                token=self.ha.ha_token,
            ), "Failed to export recorder statistics after skipping the unknown entity"
            persisted = pd.read_csv(export_path, sep="\t")
            assert persisted["statistic_id"].unique().tolist() == ["sensor.mixed_test_temp"]
            assert persisted.loc[0, ["min", "max", "mean"]].tolist() == [19, 23, 21]
        finally:
            source_path.unlink(missing_ok=True)
            export_path.unlink(missing_ok=True)
            for skipped_report in set(config_dir.glob("skipped_unknown_entities_*.csv")) - skipped_reports_before:
                skipped_report.unlink(missing_ok=True)
