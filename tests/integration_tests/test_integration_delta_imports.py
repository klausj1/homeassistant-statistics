"""Integration test for delta column imports with running Home Assistant instance."""

import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd
import psutil
import pytest

from custom_components.import_statistics.const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@pytest.mark.usefixtures("allow_socket_for_integration")
@pytest.mark.integration
class TestIntegrationAll:
    """
    Integration tests for all import types with running Home Assistant instance.

    These tests connect to a running Home Assistant instance (started via scripts/develop)
    and test the import_statistics integration with real database operations.

    Tests run in order: sensor → counter → delta, all sharing the same HA instance.
    """

    ha_process: subprocess.Popen | None = None
    ha_url: str = "http://localhost:8123"
    ha_token: str = os.getenv("HA_TOKEN_DEV", "")
    ha_started_by_test: bool = False

    @classmethod
    def setup_class(cls) -> None:
        """Set up class - no HA startup here, will be done in _wait_for_ha_startup."""
        _LOGGER.info("\n%s", "=" * 80)
        _LOGGER.info("Test class setup (HA startup will happen in test)")
        _LOGGER.info("%s", "=" * 80)
        cls.ha_process = None
        cls.ha_started_by_test = False

    @classmethod
    def teardown_class(cls) -> None:
        """Stop Home Assistant after tests complete (only if we started it)."""
        _LOGGER.info("\n%s", "=" * 80)
        _LOGGER.info("Stopping Home Assistant...")
        _LOGGER.info("%s", "=" * 80)
        if cls.ha_started_by_test and cls.ha_process is not None:
            try:
                _LOGGER.info("Terminating Home Assistant process...")
                _LOGGER.info("HA process PID: %s", cls.ha_process.pid)

                # Kill child processes (especially hass which is a child of the bash script)
                try:
                    parent = psutil.Process(cls.ha_process.pid)
                    children = parent.children(recursive=True)
                    _LOGGER.info("Found %s child processes to terminate", len(children))
                    for child in children:
                        try:
                            _LOGGER.info("Terminating child process: PID=%s, name=%s", child.pid, child.name())
                            child.terminate()
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

                # Then terminate the parent bash process
                cls.ha_process.terminate()
                try:
                    cls.ha_process.wait(timeout=10)
                    _LOGGER.info("Home Assistant terminated successfully")
                except subprocess.TimeoutExpired:
                    _LOGGER.info("Timeout waiting for process to terminate, killing...")
                    cls.ha_process.kill()
                    cls.ha_process.wait()
                    _LOGGER.info("Home Assistant killed (timeout on terminate)")
            except Exception:
                _LOGGER.exception("Error stopping Home Assistant")
        else:
            _LOGGER.info("Home Assistant was already running, leaving it running")

    async def _wait_for_ha_startup(
        self,
        timeout_seconds: int = 180,
        ha_url: str = "http://localhost:8123",
    ) -> bool:
        """
        Wait for Home Assistant to be fully started, starting it if needed.

        Checks if HA is responsive via HTTP request. If not running, starts it.

        Args:
            timeout_seconds: Maximum seconds to wait (default 3 minutes)
            ha_url: Home Assistant URL

        Returns:
            True if HA started successfully, False on timeout

        """
        start_time = time.time()
        max_wait = timeout_seconds
        attempt = 0

        _LOGGER.debug("Starting HA startup wait: url=%s, timeout=%ss", ha_url, timeout_seconds)

        # First, try to connect without starting
        while (time.time() - start_time) < max_wait:
            attempt += 1
            elapsed = time.time() - start_time
            try:
                headers = {"Authorization": f"Bearer {self.ha_token}"}
                _LOGGER.debug("Attempt %s (elapsed: %.1fs): Trying to connect to %s/api/", attempt, elapsed, ha_url)
                async with (
                    aiohttp.ClientSession() as session,
                    session.get(f"{ha_url}/api/", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response,
                ):
                    _LOGGER.debug("Got response: status=%s", response.status)
                    if response.status in (200, 401):  # 401 means HA is up but needs token
                        _LOGGER.debug("✓ HA is responsive! Status: %s", response.status)
                        if attempt > 1:
                            await asyncio.sleep(2)  # Give it an extra second to be fully ready
                            _LOGGER.debug("✓ Returning True after waiting 2 more seconds")
                        return True
                    _LOGGER.debug("Unexpected status %s, retrying...", response.status)
            except TimeoutError:
                _LOGGER.debug("Attempt %s (elapsed: %.1fs): Timeout waiting for response", attempt, elapsed)
                # If we've waited long enough without connection, start HA
                if elapsed > 2 and self.__class__.ha_process is None:
                    await self._start_ha()
            except aiohttp.ClientConnectionError as e:
                _LOGGER.debug("Attempt %s (elapsed: %.1fs): Connection error: %s (HA may not be listening yet)", attempt, elapsed, type(e).__name__)
                # If we've waited long enough without connection, start HA
                if elapsed > 2 and self.__class__.ha_process is None:
                    await self._start_ha()
            except aiohttp.ClientError as e:
                _LOGGER.debug("Attempt %s (elapsed: %.1fs): Client error: %s: %s", attempt, elapsed, type(e).__name__, e)
            except Exception as e:  # noqa: BLE001
                _LOGGER.debug("Attempt %s (elapsed: %.1fs): Unexpected error: %s: %s", attempt, elapsed, type(e).__name__, e)

            await asyncio.sleep(1)

        _LOGGER.warning("✗ Timeout after %ss - HA did not start", timeout_seconds)
        return False

    async def _start_ha(self) -> None:
        """Start Home Assistant if not already running."""
        # delete config/home-assistant_v2. sqlite db to start fresh
        _LOGGER.info("Starting Home Assistant - deleting existing DB files first ...")
        for db_file in (Path(__file__).parent.parent.parent / "config").glob("home-assistant_v2.*"):
            try:
                db_file.unlink()
                _LOGGER.info("Deleted existing Home Assistant DB file: %s", db_file)
            except Exception:
                _LOGGER.exception("Failed to delete Home Assistant DB file: %s", db_file)
        _LOGGER.info("\n%s", "=" * 80)
        _LOGGER.info("Starting Home Assistant...")
        _LOGGER.info("%s", "=" * 80)
        try:
            script_path = Path(__file__).parent.parent.parent / "scripts" / "develop"
            self.__class__.ha_process = subprocess.Popen(  # noqa: S603, ASYNC220
                ["/bin/bash", str(script_path)],
                text=True,
            )
            self.__class__.ha_started_by_test = True
            _LOGGER.info("Home Assistant process started with PID: %s", self.__class__.ha_process.pid)
            _LOGGER.info("(HA logs will appear below)\n")
            await asyncio.sleep(3)  # Give it time to start
        except Exception:
            _LOGGER.exception("Failed to start Home Assistant")
            raise

    @staticmethod
    async def _call_service(
        service_name: str,
        data: dict[str, Any],
        ha_url: str = "http://localhost:8123",
        token: str = "",
    ) -> bool:
        """
        Call a Home Assistant service via REST API.

        Args:
            service_name: Name of the service (e.g., "import_from_file")
            data: Service call data dictionary
            ha_url: Home Assistant URL
            token: Authentication token (if needed)

        Returns:
            True if service call succeeded, False otherwise

        """
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with aiohttp.ClientSession() as session:
                _LOGGER.debug("Calling service %s with data: %s", service_name, data)
                async with session.post(
                    f"{ha_url}/api/services/{DOMAIN}/{service_name}",
                    json=data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status not in (200, 201):
                        error_text = await response.text()
                        _LOGGER.error("Service call failed: %s, Status: %s, Response: %s", service_name, response.status, error_text)
                    else:
                        _LOGGER.debug("Service call succeeded: %s, Status: %s", service_name, response.status)
                    return response.status in (200, 201)
        except Exception:
            _LOGGER.exception("Error calling service")
            return False

    @staticmethod
    def _compare_tsv_files_strict(actual_path: Path, expected_path: Path, tolerance: float = 0.01) -> bool:
        """Compare two TSV files for equality with numeric tolerance (strict mode - raises on mismatch)."""
        with actual_path.open(encoding="utf-8") as f:
            actual_rows = [line.split("\t") for line in f.read().strip().split("\n")]

        with expected_path.open(encoding="utf-8") as f:
            expected_rows = [line.split("\t") for line in f.read().strip().split("\n")]

        assert len(actual_rows) == len(expected_rows), f"Row count mismatch: {len(actual_rows)} vs {len(expected_rows)}"

        for i, (actual_row, expected_row) in enumerate(zip(actual_rows, expected_rows, strict=False), start=1):
            assert len(actual_row) == len(expected_row), f"Column count mismatch at row {i}: {len(actual_row)} vs {len(expected_row)}"

            for j, (actual_val_raw, expected_val_raw) in enumerate(zip(actual_row, expected_row, strict=False)):
                actual_val = actual_val_raw.strip()
                expected_val = expected_val_raw.strip()

                try:
                    if actual_val or expected_val:
                        actual_num = float(actual_val) if actual_val else 0
                        expected_num = float(expected_val) if expected_val else 0
                        assert abs(actual_num - expected_num) <= tolerance, f"Value mismatch at row {i}, col {j}: {actual_val} vs {expected_val}"
                except ValueError:
                    assert actual_val == expected_val, f"Value mismatch at row {i}, col {j}: '{actual_val}' vs '{expected_val}'"

        _LOGGER.info("COMPARISON OK: Files match perfectly")
        return True

    @staticmethod
    def _verify_tsv_contains_only_sensors(file_path: Path) -> bool:
        """
        Verify a TSV file contains only sensor data (mean/min/max populated, sum/state empty).

        Args:
            file_path: Path to the TSV file

        Returns:
            True if file contains only sensors, False otherwise

        """
        df = pd.read_csv(file_path, sep="\t")
        # Sensors have mean/min/max populated and sum/state empty
        has_sensor_data = (
            ("mean" in df.columns and df["mean"].notna().any())
            or ("min" in df.columns and df["min"].notna().any())
            or ("max" in df.columns and df["max"].notna().any())
        )
        has_counter_data = ("sum" in df.columns and df["sum"].notna().any()) or ("state" in df.columns and df["state"].notna().any())
        return bool(has_sensor_data and not has_counter_data)

    @staticmethod
    def _verify_tsv_contains_only_counters(file_path: Path) -> bool:
        """
        Verify a TSV file contains only counter data (sum/state populated, mean/min/max empty).

        Args:
            file_path: Path to the TSV file

        Returns:
            True if file contains only counters, False otherwise

        """
        df = pd.read_csv(file_path, sep="\t")
        # Counters have sum/state populated and mean/min/max empty
        has_counter_data = ("sum" in df.columns and df["sum"].notna().any()) or ("state" in df.columns and df["state"].notna().any())
        has_sensor_data = (
            ("mean" in df.columns and df["mean"].notna().any())
            or ("min" in df.columns and df["min"].notna().any())
            or ("max" in df.columns and df["max"].notna().any())
        )
        return bool(has_counter_data and not has_sensor_data)

    @staticmethod
    def _compare_dataframes_strict(df_actual: pd.DataFrame, df_expected: pd.DataFrame, tolerance: float = 0.01) -> bool:
        """
        Compare two DataFrames for equality with numeric tolerance (strict mode - raises on mismatch).

        Args:
            df_actual: Actual DataFrame
            df_expected: Expected DataFrame
            tolerance: Numeric tolerance for float comparisons

        Returns:
            True if DataFrames match

        """
        # Sort both DataFrames by statistic_id and start for consistent comparison
        df_actual_sorted = df_actual.sort_values(by=["statistic_id", "start"]).reset_index(drop=True)
        df_expected_sorted = df_expected.sort_values(by=["statistic_id", "start"]).reset_index(drop=True)

        assert len(df_actual_sorted) == len(df_expected_sorted), f"Row count mismatch: {len(df_actual_sorted)} vs {len(df_expected_sorted)}"
        assert list(df_actual_sorted.columns) == list(df_expected_sorted.columns), "Column mismatch"

        for col in df_actual_sorted.columns:
            for idx in range(len(df_actual_sorted)):
                actual_val = df_actual_sorted.loc[idx, col]
                expected_val = df_expected_sorted.loc[idx, col]

                # Handle NaN/empty values
                if pd.isna(actual_val) and pd.isna(expected_val):
                    continue

                # Try numeric comparison first
                try:
                    actual_num = float(actual_val) if not pd.isna(actual_val) else 0.0  # type: ignore[arg-type]
                    expected_num = float(expected_val) if not pd.isna(expected_val) else 0.0  # type: ignore[arg-type]

                    # For numeric columns, treat NaN and 0.0 as equivalent
                    if abs(actual_num - expected_num) <= tolerance:
                        continue

                    # If one is NaN/0 and the other is not, that's a mismatch
                    msg = f"Value mismatch at row {idx}, col {col}: {actual_val} vs {expected_val}"
                    raise AssertionError(msg)
                except (ValueError, TypeError) as e:
                    # String comparison for non-numeric values
                    # One is NaN and the other is not
                    if pd.isna(actual_val) or pd.isna(expected_val):
                        msg = f"Value mismatch at row {idx}, col {col}: {actual_val} vs {expected_val}"
                        raise AssertionError(msg) from e
                    assert str(actual_val).strip() == str(expected_val).strip(), f"Value mismatch at row {idx}, col {col}: '{actual_val}' vs '{expected_val}'"

        _LOGGER.info("COMPARISON OK: DataFrames match perfectly")
        return True

    @staticmethod
    def _merge_reference_files_for_time_range(
        sensor_ref: Path | None,
        counter_ref: Path | None,
        delta_ref: Path | None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> pd.DataFrame:
        """
        Merge reference files from tests 1, 2, and 3 for a specific time range.

        Args:
            sensor_ref: Path to sensor reference file (test_01), or None to skip
            counter_ref: Path to counter reference file (test_02), or None to skip
            delta_ref: Path to delta reference file (test_03), or None to skip
            start_time: Start time in format "DD.MM.YYYY HH:MM" (optional)
            end_time: End time in format "DD.MM.YYYY HH:MM" (optional)

        Returns:
            Merged DataFrame with all data from the three tests in the time range

        """
        # Read reference files (skip if None)
        dfs = []

        if sensor_ref is not None:
            df_sensor = pd.read_csv(sensor_ref, sep="\t")
            # Filter by time range if specified
            if start_time and end_time:
                df_sensor = df_sensor[(df_sensor["start"] >= start_time) & (df_sensor["start"] <= end_time)]
            dfs.append(df_sensor)

        if counter_ref is not None:
            df_counter = pd.read_csv(counter_ref, sep="\t")
            # Filter by time range if specified
            if start_time and end_time:
                df_counter = df_counter[(df_counter["start"] >= start_time) & (df_counter["start"] <= end_time)]
            dfs.append(df_counter)

        if delta_ref is not None:
            df_delta = pd.read_csv(delta_ref, sep="\t")
            # Filter by time range if specified
            if start_time and end_time:
                df_delta = df_delta[(df_delta["start"] >= start_time) & (df_delta["start"] <= end_time)]
            dfs.append(df_delta)

        # Concatenate all dataframes
        return pd.concat(dfs, ignore_index=True)

    @pytest.mark.asyncio
    async def test_01_import_sensor_mean_min_max_then_changes(self) -> None:
        """Test sensor import workflow (mean/min/max) with running Home Assistant."""
        config_dir = Path(__file__).parent.parent.parent / "config"
        test_dir = config_dir / "test_sensor"

        # Wait for HA to be fully started (up to 3 minutes)
        is_ready = await self._wait_for_ha_startup(timeout_seconds=180)
        assert is_ready, "Home Assistant did not start within 3 minutes"

        # STEP 1: Import sensor_mean_min_max
        success = await self._call_service(
            "import_from_file",
            {"filename": "test_sensor/sensor_mean_min_max.txt", "timezone_identifier": "Europe/Vienna", "delimiter": "\t", "decimal": False},
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to import sensor_mean_min_max"

        # Export and verify step 1
        entities = ["sensor.sens_all_changed", "sensor.sens_part_overlap_new", "sensor:sens_some_changed", "sensor:sens_all_changed_new"]
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_sensor/export_after_step1.tsv",
                "entities": entities,
                "start_time": "2025-12-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to export after step 1"

        export_file_1 = test_dir / "export_after_step1.tsv"
        reference_file_1 = test_dir / "expected_after_import.tsv"
        assert self._compare_tsv_files_strict(export_file_1, reference_file_1), "Step 1 export mismatch"

        # STEP 2: Import changes
        success = await self._call_service(
            "import_from_file",
            {"filename": "test_sensor/sensor_mean_min_max_changes.txt", "timezone_identifier": "Europe/Vienna", "delimiter": "\t", "decimal": False},
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to import sensor_mean_min_max_changes"

        # Export and verify step 2
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_sensor/export_after_step2.tsv",
                "entities": entities,
                "start_time": "2025-12-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to export after step 2"

        export_file_2 = test_dir / "export_after_step2.tsv"
        reference_file_2 = test_dir / "expected_after_changes.tsv"
        assert self._compare_tsv_files_strict(export_file_2, reference_file_2), "Step 2 export mismatch"

    @pytest.mark.asyncio
    async def test_02_import_counter_sum_state_then_changes(self) -> None:
        """Test counter import workflow (sum/state) with running Home Assistant."""
        config_dir = Path(__file__).parent.parent.parent / "config"
        test_dir = config_dir / "test_counter_no_delta"

        # Check if HA is running (will start if needed)
        is_ready = await self._wait_for_ha_startup(timeout_seconds=180)
        assert is_ready, "Home Assistant did not start within 3 minutes"

        # STEP 1: Import counter_sum_state
        success = await self._call_service(
            "import_from_file",
            {"filename": "test_counter_no_delta/counter_sum_state.txt", "timezone_identifier": "Europe/Vienna", "delimiter": "\t", "decimal": False},
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to import counter_sum_state"

        # Export and verify step 1
        entities = ["sensor.cnt_all_changed", "sensor.cnt_part_overlap_new", "sensor:cnt_some_changed", "sensor:cnt_all_changed_new"]
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_counter_no_delta/export_after_step1.tsv",
                "entities": entities,
                "start_time": "2025-12-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to export after step 1"

        export_file_1 = test_dir / "export_after_step1.tsv"
        reference_file_1 = test_dir / "expected_after_import.tsv"
        assert self._compare_tsv_files_strict(export_file_1, reference_file_1), "Step 1 export mismatch"

        # STEP 2: Import changes
        success = await self._call_service(
            "import_from_file",
            {"filename": "test_counter_no_delta/counter_sum_state_changes.txt", "timezone_identifier": "Europe/Vienna", "delimiter": "\t", "decimal": False},
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to import counter_sum_state_changes"

        # Export and verify step 2
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_counter_no_delta/export_after_step2.tsv",
                "entities": entities,
                "start_time": "2025-12-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to export after step 2"

        export_file_2 = test_dir / "export_after_step2.tsv"
        reference_file_2 = test_dir / "expected_after_changes.tsv"
        assert self._compare_tsv_files_strict(export_file_2, reference_file_2), "Step 2 export mismatch"

    @pytest.mark.asyncio
    async def test_03_import_sum_state_then_delta_unchanged_then_delta_changed(
        self,
    ) -> None:
        """
        Test complete delta workflow with running Home Assistant.

        Prerequisites:
        - Home Assistant is started by setup_class
        - Test data files are in config directory

        Steps:
        1. Wait for Home Assistant to be fully started
        3. Import sum_state.txt (absolute values)
        4. Export and verify values match reference
        5. Import sum_delta_unchanged.txt (unchanged deltas)
        6. Export and verify values still the same
        7. Import sum_delta_changed.txt (changed deltas)
        8. Export and verify values are correctly changed

        """
        config_dir = Path(__file__).parent.parent.parent / "config"
        test_delta_dir = Path(__file__).parent.parent.parent / "config" / "test_delta"

        # Wait for HA to be fully started (up to 3 minutes)
        is_ready = await self._wait_for_ha_startup(timeout_seconds=180)
        assert is_ready, "Home Assistant did not start within 3 minutes"

        # ==================== STEP 1: Import sum_state ====================
        success = await self._call_service(
            "import_from_file",
            {
                "filename": "test_delta/sum_state.txt",
                "timezone_identifier": "Europe/Vienna",
                "delimiter": "\t",
                "decimal": False,
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to call import_from_file service for sum_state"

        # Export and verify step 1 (both entities)
        export_file_1 = config_dir / "test_delta" / "export_after_step1.tsv"
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_delta/export_after_step1.tsv",
                "entities": [
                    "sensor.imp_inside_same_newest_1",
                    "sensor:imp_inside_same_newest_2",
                    "sensor.import_partly_before",
                    "sensor:import_partly_at",
                    "sensor.imp_before",
                    "sensor:imp_before",
                    "sensor.imp_after",
                    "sensor:imp_after",
                    "sensor.imp_partly_before",
                    "sensor:imp_partly_at",
                    "sensor:imp_inside",
                    "sensor:imp_inside_spike",
                    "sensor:imp_inside_holes",
                    "sensor:imp_partly_after",
                ],
                "start_time": "2025-06-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to export statistics after step 1"

        reference_file_1 = test_delta_dir / "expected_after_step1_sum_state.tsv"
        assert export_file_1.exists(), f"Export file not found: {export_file_1}"
        assert reference_file_1.exists(), f"Reference file not found: {reference_file_1}"
        assert self._compare_tsv_files_strict(export_file_1, reference_file_1), "Step 1 export does not match reference"

        # ==================== STEP 2: Import delta_unchanged ====================
        success = await self._call_service(
            "import_from_file",
            {
                "filename": "test_delta/sum_delta_unchanged.txt",
                "timezone_identifier": "Europe/Vienna",
                "delimiter": "\t",
                "decimal": False,
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to call import_from_file service for delta_unchanged"

        # Export and verify step 2 (both entities)
        export_file_2 = config_dir / "test_delta" / "export_after_step2.tsv"
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_delta/export_after_step2.tsv",
                "entities": [
                    "sensor.imp_inside_same_newest_1",
                    "sensor:imp_inside_same_newest_2",
                    "sensor.import_partly_before",
                    "sensor:import_partly_at",
                    "sensor.imp_before",
                    "sensor:imp_before",
                    "sensor.imp_after",
                    "sensor:imp_after",
                    "sensor.imp_partly_before",
                    "sensor:imp_partly_at",
                    "sensor:imp_inside",
                    "sensor:imp_inside_spike",
                    "sensor:imp_inside_holes",
                    "sensor:imp_partly_after",
                ],
                "start_time": "2025-06-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to export statistics after step 2"

        reference_file_2 = reference_file_1  # Should be the same as after step 1
        assert export_file_2.exists(), f"Export file not found: {export_file_2}"
        assert reference_file_2.exists(), f"Reference file not found: {reference_file_2}"
        assert self._compare_tsv_files_strict(export_file_2, reference_file_2), "Step 2 export does not match reference"

        # ==================== STEP 3: Import delta_changed ====================
        success = await self._call_service(
            "import_from_file",
            {
                "filename": "test_delta/sum_delta_changed.txt",
                "timezone_identifier": "Europe/Vienna",
                "delimiter": "\t",
                "decimal": False,
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to call import_from_file service for delta_changed"

        # Export and verify step 3 (both entities)
        export_file_3 = config_dir / "test_delta" / "export_after_step3.tsv"
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_delta/export_after_step3.tsv",
                "entities": [
                    "sensor.imp_inside_same_newest_1",
                    "sensor:imp_inside_same_newest_2",
                    "sensor.import_partly_before",
                    "sensor:import_partly_at",
                    "sensor.imp_before",
                    "sensor:imp_before",
                    "sensor.imp_after",
                    "sensor:imp_after",
                    "sensor.imp_partly_before",
                    "sensor:imp_partly_at",
                    "sensor:imp_inside",
                    "sensor:imp_inside_spike",
                    "sensor:imp_inside_holes",
                    "sensor:imp_partly_after",
                ],
                "start_time": "2025-06-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to export statistics after step 3"

        reference_file_3 = test_delta_dir / "expected_after_step3_delta_changed.tsv"
        assert export_file_3.exists(), f"Export file not found: {export_file_3}"
        assert reference_file_3.exists(), f"Reference file not found: {reference_file_3}"
        assert self._compare_tsv_files_strict(export_file_3, reference_file_3), "Step 3 export does not match reference"

    @pytest.mark.asyncio
    async def test_04_export_parameter_variations(self) -> None:  # noqa: PLR0915
        """
        Test export service parameter variations with data from all previous tests.

        IMPORTANT: This test CANNOT run standalone - it depends on data from:
        - test_01: Sensor data (mean/min/max) in time range 2025-12-29 to 2025-12-31
        - test_02: Counter data (sum/state) in time range 2025-12-29 to 2025-12-31
        - test_03: Delta counter data in time range 2025-06-29 to 2025-12-31

        This test verifies the new export service parameters using pairwise testing:
        - Variation 1: Export all entities (omit entities parameter)
        - Variation 2: Open-ended time range (omit start_time/end_time)
        - Variation 3: Split statistics (split_by="both")
        - Variation 4: Split only counters (split_by="counter")
        - Variation 5: Split + all entities (interaction test)
        """
        config_dir = Path(__file__).parent.parent.parent / "config"
        test_delta_dir = config_dir / "test_delta"

        # Wait for HA to be ready
        is_ready = await self._wait_for_ha_startup(timeout_seconds=180)
        assert is_ready, "Home Assistant did not start within 3 minutes"

        # Define entity lists and reference files from all three previous tests
        delta_entities = [
            "sensor.imp_inside_same_newest_1",
            "sensor:imp_inside_same_newest_2",
            "sensor.import_partly_before",
            "sensor:import_partly_at",
            "sensor.imp_before",
            "sensor:imp_before",
            "sensor.imp_after",
            "sensor:imp_after",
            "sensor.imp_partly_before",
            "sensor:imp_partly_at",
            "sensor:imp_inside",
            "sensor:imp_inside_spike",
            "sensor:imp_inside_holes",
            "sensor:imp_partly_after",
        ]

        # Reference files from previous tests
        sensor_ref = config_dir / "test_sensor" / "expected_after_changes.tsv"
        counter_ref = config_dir / "test_counter_no_delta" / "expected_after_changes.tsv"
        delta_ref = config_dir / "test_delta" / "expected_after_step3_delta_changed.tsv"

        # ==================== Variation 1: Export all entities (omit entities parameter) ====================
        _LOGGER.info("Variation 1: Export all entities in delta time range (omit entities parameter)")
        export_file_all_entities = test_delta_dir / "export_variation1_all_entities.tsv"
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_delta/export_variation1_all_entities.tsv",
                "start_time": "2025-06-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Variation 1: Failed to export statistics"
        assert export_file_all_entities.exists(), f"Variation 1: Export file not found: {export_file_all_entities}"

        # Merge reference files without time filtering (we want all data from all tests)
        df_expected_all = self._merge_reference_files_for_time_range(sensor_ref, counter_ref, delta_ref, None, None)

        # Compare exported data with merged reference
        df_actual_all = pd.read_csv(export_file_all_entities, sep="\t")
        assert self._compare_dataframes_strict(df_actual_all, df_expected_all), "Variation 1: Export does not match merged reference data"
        _LOGGER.info("✓ Variation 1: All entities export verified (matches merged reference from all 3 tests)")

        # ==================== Variation 2: Open-ended time range ====================
        _LOGGER.info("Variation 2: Open-ended time range with explicit entities (omit start_time and end_time)")
        export_file_full_range = test_delta_dir / "export_variation2_full_range.tsv"
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_delta/export_variation2_full_range.tsv",
                "entities": delta_entities,
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Variation 2: Failed to export statistics"
        assert export_file_full_range.exists(), f"Variation 2: Export file not found: {export_file_full_range}"

        # Compare with delta reference (should match since we're exporting delta entities with no time limit)
        df_actual_full_range = pd.read_csv(export_file_full_range, sep="\t")
        df_expected_delta = pd.read_csv(delta_ref, sep="\t")
        assert self._compare_dataframes_strict(df_actual_full_range, df_expected_delta), "Variation 2: Export does not match delta reference"
        _LOGGER.info("✓ Variation 2: Full range export verified (matches delta reference)")

        # ==================== Variation 3: Split statistics (split_by="both") ====================
        _LOGGER.info("Variation 3: Split statistics into sensors and counters")
        export_file_split_sensors = test_delta_dir / "export_variation3_split_sensors.tsv"
        export_file_split_counters = test_delta_dir / "export_variation3_split_counters.tsv"
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_delta/export_variation3_split.tsv",
                "start_time": "2025-12-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
                "split_by": "both",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Variation 3: Failed to export statistics"

        # Both files should exist (sensors from test_01, counters from test_02)
        assert export_file_split_sensors.exists(), f"Variation 3: Sensors file not found: {export_file_split_sensors}"
        assert export_file_split_counters.exists(), f"Variation 3: Counters file not found: {export_file_split_counters}"

        # Verify sensors file contains only sensor data and matches sensor reference
        sensors_only = self._verify_tsv_contains_only_sensors(export_file_split_sensors)
        assert sensors_only, "Variation 3: Sensors file should contain only sensor data (mean/min/max)"
        df_actual_sensors = pd.read_csv(export_file_split_sensors, sep="\t")
        df_expected_sensors = pd.read_csv(sensor_ref, sep="\t")
        assert self._compare_dataframes_strict(df_actual_sensors, df_expected_sensors), "Variation 3: Sensors file does not match sensor reference"

        # Verify counters file contains only counter data
        # Note: This includes counters from test_02 AND delta entities from test_03 that fall in this time range
        counters_only = self._verify_tsv_contains_only_counters(export_file_split_counters)
        assert counters_only, "Variation 3: Counters file should contain only counter data (sum/state)"

        # Merge counter and delta references for the time range 2025-12-29 to 2025-12-31
        # Note: We filter the delta reference to only include rows in the December time range
        # The counter reference already only contains December data
        df_counter = pd.read_csv(counter_ref, sep="\t")
        df_delta = pd.read_csv(delta_ref, sep="\t")

        # Filter delta data to December 29-30 range using proper datetime comparison
        # Convert start column to datetime for proper comparison
        df_delta["start_dt"] = pd.to_datetime(df_delta["start"], format="%d.%m.%Y %H:%M")
        start_filter = pd.to_datetime("29.12.2025 00:00", format="%d.%m.%Y %H:%M")
        end_filter = pd.to_datetime("30.12.2025 23:59", format="%d.%m.%Y %H:%M")

        df_delta_filtered = df_delta[(df_delta["start_dt"] >= start_filter) & (df_delta["start_dt"] <= end_filter)].copy()
        df_delta_filtered = df_delta_filtered.drop(columns=["start_dt"])  # Remove helper column

        df_expected_counters = pd.concat([df_counter, df_delta_filtered], ignore_index=True)

        df_actual_counters = pd.read_csv(export_file_split_counters, sep="\t")
        assert self._compare_dataframes_strict(df_actual_counters, df_expected_counters), (
            "Variation 3: Counters file does not match merged counter+delta reference"
        )

        _LOGGER.info("✓ Variation 3: Split statistics verified (both files match their respective references)")

        # ==================== Variation 4: Split only counters (split_by="counter") ====================
        _LOGGER.info("Variation 4: Split only counters (split_by='counter')")
        export_file_counters_only = test_delta_dir / "export_variation4_counters_only_counters.tsv"
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_delta/export_variation4_counters_only.tsv",
                "start_time": "2025-12-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
                "split_by": "counter",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Variation 4: Failed to export statistics"
        assert export_file_counters_only.exists(), f"Variation 4: Counters file not found: {export_file_counters_only}"

        # Verify it contains only counter data and matches counter reference
        counters_only = self._verify_tsv_contains_only_counters(export_file_counters_only)
        assert counters_only, "Variation 4: File should contain only counter data (sum/state)"
        df_actual_counters_only = pd.read_csv(export_file_counters_only, sep="\t")
        assert self._compare_dataframes_strict(df_actual_counters_only, df_expected_counters), (
            "Variation 4: Counters-only file does not match counter reference"
        )
        _LOGGER.info("✓ Variation 4: Split counters only verified (matches counter reference)")

        # ==================== Variation 5: Split + all entities (interaction test) ====================
        _LOGGER.info("Variation 5: Split statistics + all entities (interaction test)")
        export_file_split_all_sensors = test_delta_dir / "export_variation5_split_all_sensors.tsv"
        export_file_split_all_counters = test_delta_dir / "export_variation5_split_all_counters.tsv"
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_delta/export_variation5_split_all.tsv",
                "start_time": "2025-12-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
                "split_by": "both",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Variation 5: Failed to export statistics"

        # Both files should exist (data from test_01 and test_02)
        assert export_file_split_all_sensors.exists(), f"Variation 5: Sensors file not found: {export_file_split_all_sensors}"
        assert export_file_split_all_counters.exists(), f"Variation 5: Counters file not found: {export_file_split_all_counters}"

        # Verify sensors file contains only sensor data and matches sensor reference
        sensors_only = self._verify_tsv_contains_only_sensors(export_file_split_all_sensors)
        assert sensors_only, "Variation 5: Sensors file should contain only sensor data (mean/min/max)"
        df_actual_split_all_sensors = pd.read_csv(export_file_split_all_sensors, sep="\t")
        assert self._compare_dataframes_strict(df_actual_split_all_sensors, df_expected_sensors), "Variation 5: Sensors file does not match sensor reference"

        # Verify counters file contains only counter data and matches counter reference
        counters_only = self._verify_tsv_contains_only_counters(export_file_split_all_counters)
        assert counters_only, "Variation 5: Counters file should contain only counter data (sum/state)"
        df_actual_split_all_counters = pd.read_csv(export_file_split_all_counters, sep="\t")
        assert self._compare_dataframes_strict(df_actual_split_all_counters, df_expected_counters), (
            "Variation 5: Counters file does not match counter reference"
        )

        _LOGGER.info("✓ Variation 5: Split + all entities verified (both files match their respective references)")

        _LOGGER.info("=" * 80)
        _LOGGER.info("All 5 export parameter variations completed successfully!")
        _LOGGER.info("=" * 80)
