"""Integration test for delta column imports with running Home Assistant instance."""

import asyncio
from doctest import debug
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import aiohttp
import psutil
import pytest

from custom_components.import_statistics.const import DOMAIN


@pytest.mark.usefixtures("allow_socket_for_integration")
class TestIntegrationDeltaImports:
    """
    Integration tests for delta imports with running Home Assistant instance.

    These tests connect to a running Home Assistant instance (started via scripts/develop)
    and test the import_statistics integration with real database operations.
    """

    ha_process: subprocess.Popen | None = None
    ha_url: str = "http://localhost:8123"
    ha_token: str = os.getenv("HA_TOKEN", "")
    ha_started_by_test: bool = False

    @classmethod
    def setup_class(cls) -> None:
        """Setup class - no HA startup here, will be done in _wait_for_ha_startup."""
        print("\n" + "=" * 80)
        print("Test class setup (HA startup will happen in test)")
        print("=" * 80)
        cls.ha_process = None
        cls.ha_started_by_test = False

    @classmethod
    def teardown_class(cls) -> None:
        """Stop Home Assistant after tests complete (only if we started it)."""
        print("\n" + "=" * 80)
        print("Stopping Home Assistant...")
        print("=" * 80)
        if cls.ha_started_by_test and cls.ha_process is not None:
            try:
                print("Terminating Home Assistant process...")
                print(f"HA process PID: {cls.ha_process.pid}")

                # Kill child processes (especially hass which is a child of the bash script)
                try:
                    parent = psutil.Process(cls.ha_process.pid)
                    children = parent.children(recursive=True)
                    print(f"Found {len(children)} child processes to terminate")
                    for child in children:
                        try:
                            print(f"Terminating child process: PID={child.pid}, name={child.name()}")
                            child.terminate()
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

                # Then terminate the parent bash process
                cls.ha_process.terminate()
                try:
                    cls.ha_process.wait(timeout=10)
                    print("Home Assistant terminated successfully")
                except subprocess.TimeoutExpired:
                    print("Timeout waiting for process to terminate, killing...")
                    cls.ha_process.kill()
                    cls.ha_process.wait()
                    print("Home Assistant killed (timeout on terminate)")
            except Exception as e:  # noqa: BLE001
                print(f"Error stopping Home Assistant: {e}")
        else:
            print("Home Assistant was already running, leaving it running")

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

        print(f"\n[DEBUG] Starting HA startup wait: url={ha_url}, timeout={timeout_seconds}s")
        print(f"[DEBUG] Token: {self.ha_token[:50]}...")

        # First, try to connect without starting
        while (time.time() - start_time) < max_wait:
            attempt += 1
            elapsed = time.time() - start_time
            try:
                headers = {"Authorization": f"Bearer {self.ha_token}"}
                print(f"[DEBUG] Attempt {attempt} (elapsed: {elapsed:.1f}s): Trying to connect to {ha_url}/api/")
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{ha_url}/api/", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        print(f"[DEBUG] Got response: status={response.status}")
                        if response.status in (200, 401):  # 401 means HA is up but needs token
                            print(f"[DEBUG] ✓ HA is responsive! Status: {response.status}")
                            if attempt > 1:
                                await asyncio.sleep(2)  # Give it an extra second to be fully ready
                                print("[DEBUG] ✓ Returning True after waiting 2 more seconds")
                            return True
                        print(f"[DEBUG] Unexpected status {response.status}, retrying...")
            except TimeoutError:
                print(f"[DEBUG] Attempt {attempt} (elapsed: {elapsed:.1f}s): Timeout waiting for response")
                # If we've waited long enough without connection, start HA
                if elapsed > 10 and self.__class__.ha_process is None:
                    await self._start_ha()
            except aiohttp.ClientConnectionError as e:
                print(f"[DEBUG] Attempt {attempt} (elapsed: {elapsed:.1f}s): Connection error: {type(e).__name__} (HA may not be listening yet)")
                # If we've waited long enough without connection, start HA
                if elapsed > 10 and self.__class__.ha_process is None:
                    await self._start_ha()
            except aiohttp.ClientError as e:
                print(f"[DEBUG] Attempt {attempt} (elapsed: {elapsed:.1f}s): Client error: {type(e).__name__}: {e}")
            except Exception as e:  # noqa: BLE001
                print(f"[DEBUG] Attempt {attempt} (elapsed: {elapsed:.1f}s): Unexpected error: {type(e).__name__}: {e}")

            await asyncio.sleep(1)

        print(f"[DEBUG] ✗ Timeout after {timeout_seconds}s - HA did not start")
        return False

    async def _start_ha(self) -> None:
        """Start Home Assistant if not already running."""
        print("\n" + "=" * 80)
        print("Starting Home Assistant...")
        print("=" * 80)
        try:
            script_path = Path(__file__).parent.parent / "scripts" / "develop"
            self.__class__.ha_process = subprocess.Popen(
                ["bash", str(script_path)],
                text=True,
            )
            self.__class__.ha_started_by_test = True
            print(f"Home Assistant process started with PID: {self.__class__.ha_process.pid}")
            print("(HA logs will appear below)\n")
            await asyncio.sleep(3)  # Give it time to start
        except Exception as e:
            print(f"Failed to start Home Assistant: {e}")
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
                print(f"[DEBUG] Calling service {service_name} with data: {data}")
                print(f"[DEBUG] Headers: {headers}")
                async with session.post(
                    f"{ha_url}/api/services/{DOMAIN}/{service_name}",
                    json=data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status not in (200, 201):
                        error_text = await response.text()
                        print(f"Service call failed: {service_name}, Status: {response.status}, Response: {error_text}")
                    else:
                        print(f"Service call succeeded: {service_name}, Status: {response.status}")
                    return response.status in (200, 201)
        except Exception as e:  # noqa: BLE001
            print(f"Error calling service: {e}")
            return False

    @staticmethod
    def _normalize_tsv_for_comparison(file_path: Path) -> list[list[str]]:
        """
        Load and normalize a TSV file for comparison.

        Args:
            file_path: Path to the TSV file

        Returns:
            List of rows with normalized whitespace

        """
        with open(file_path, encoding="utf-8") as f:
            lines = f.read().strip().split("\n")
            return [line.split("\t") for line in lines]

    @staticmethod
    def _compare_tsv_files(actual_path: Path, expected_path: Path, tolerance: float = 0.01) -> bool:
        """
        Compare two TSV files for equality with numeric tolerance.

        Args:
            actual_path: Path to the actual exported file
            expected_path: Path to the expected reference file
            tolerance: Tolerance for numeric comparisons

        Returns:
            True if files match within tolerance, False otherwise

        """
        actual_rows = TestIntegrationDeltaImports._normalize_tsv_for_comparison(actual_path)
        expected_rows = TestIntegrationDeltaImports._normalize_tsv_for_comparison(expected_path)

        if len(actual_rows) != len(expected_rows):
            print(f"Row count mismatch: {len(actual_rows)} vs {len(expected_rows)}")
            return False

        # Skip header row
        for i, (actual_row, expected_row) in enumerate(zip(actual_rows[1:], expected_rows[1:], strict=False), start=2):
            if len(actual_row) != len(expected_row):
                print(f"Column count mismatch at row {i}: {len(actual_row)} vs {len(expected_row)}")
                return False

            for j, (actual_val, expected_val) in enumerate(zip(actual_row, expected_row, strict=False)):
                # Try numeric comparison for numeric fields
                try:
                    actual_num = float(actual_val)
                    expected_num = float(expected_val)
                    if abs(actual_num - expected_num) > tolerance:
                        print(f"Value mismatch at row {i}, col {j}: {actual_num} vs {expected_num}")
                        return False
                except ValueError:
                    # Non-numeric comparison
                    if actual_val != expected_val:
                        print(f"Value mismatch at row {i}, col {j}: '{actual_val}' vs '{expected_val}'")
                        return False

        return True

    @pytest.mark.asyncio
    async def test_import_sum_state_then_delta_unchanged_then_delta_changed(
        self,
    ) -> None:
        """
        Test complete delta workflow with running Home Assistant.

        Prerequisites:
        - Home Assistant is started by setup_class
        - Test data files are in config directory

        Steps:
        1. Wait for Home Assistant to be fully started
        3. Import test_case_1_sum_state.txt (absolute values)
        4. Export and verify values match reference
        5. Import test_case_1_sum_delta_unchanged.txt (unchanged deltas)
        6. Export and verify values are correctly updated
        7. Import test_case_1_sum_delta_changed.txt (changed deltas)
        8. Export and verify values are correctly changed

        """
        config_dir = Path(__file__).parent.parent / "config"

        # Wait for HA to be fully started (up to 3 minutes)
        is_ready = await self._wait_for_ha_startup(timeout_seconds=180)
        assert is_ready, "Home Assistant did not start within 3 minutes"

        test_delta_dir = Path(__file__).parent.parent / "config" / "test_delta"

        # ==================== STEP 1: Import sum_state ====================
        success = await self._call_service(
            "import_from_file",
            {
                "filename": "test_delta/test_case_1_sum_state.txt",
                "timezone_identifier": "Europe/Vienna",
                "delimiter": "\t",
                "decimal": False,
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to call import_from_file service for sum_state"
        await asyncio.sleep(2)  # Wait for import to complete

        # Export and verify step 1
        export_file_1 = config_dir / "test_delta" / "export_after_step1.tsv"
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_delta/export_after_step1.tsv",
                "entities": ["sensor.test_case_1"],
                "start_time": "2025-12-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to export statistics after step 1"
        await asyncio.sleep(1)

        reference_file_1 = test_delta_dir / "expected_after_step1_sum_state.tsv"
        assert export_file_1.exists(), f"Export file not found: {export_file_1}"
        assert reference_file_1.exists(), f"Reference file not found: {reference_file_1}"
        assert self._compare_tsv_files(export_file_1, reference_file_1), "Step 1 export does not match reference"

        # ==================== STEP 2: Import delta_unchanged ====================
        success = await self._call_service(
            "import_from_file",
            {
                "filename": "test_delta/test_case_1_sum_delta_unchanged.txt",
                "timezone_identifier": "Europe/Vienna",
                "delimiter": "\t",
                "decimal": False,
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to call import_from_file service for delta_unchanged"
        await asyncio.sleep(2)  # Wait for import to complete

        # Export and verify step 2
        export_file_2 = config_dir / "test_delta" / "export_after_step2.tsv"
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_delta/export_after_step2.tsv",
                "entities": ["sensor.test_case_1"],
                "start_time": "2025-12-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to export statistics after step 2"
        await asyncio.sleep(1)

        reference_file_2 = test_delta_dir / "expected_after_step2_delta_unchanged.tsv"
        assert export_file_2.exists(), f"Export file not found: {export_file_2}"
        assert reference_file_2.exists(), f"Reference file not found: {reference_file_2}"
        assert self._compare_tsv_files(export_file_2, reference_file_2), "Step 2 export does not match reference"

        # ==================== STEP 3: Import delta_changed ====================
        success = await self._call_service(
            "import_from_file",
            {
                "filename": "test_delta/test_case_1_sum_delta_changed.txt",
                "timezone_identifier": "Europe/Vienna",
                "delimiter": "\t",
                "decimal": False,
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to call import_from_file service for delta_changed"
        await asyncio.sleep(2)  # Wait for import to complete

        # Export and verify step 3
        export_file_3 = config_dir / "test_delta" / "export_after_step3.tsv"
        success = await self._call_service(
            "export_statistics",
            {
                "filename": "test_delta/export_after_step3.tsv",
                "entities": ["sensor.test_case_1"],
                "start_time": "2025-12-29 00:00:00",
                "end_time": "2025-12-31 00:00:00",
                "timezone_identifier": "Europe/Vienna",
            },
            ha_url=self.ha_url,
            token=self.ha_token,
        )
        assert success, "Failed to export statistics after step 3"
        await asyncio.sleep(1)

        reference_file_3 = test_delta_dir / "expected_after_step3_delta_changed.tsv"
        assert export_file_3.exists(), f"Export file not found: {export_file_3}"
        assert reference_file_3.exists(), f"Reference file not found: {reference_file_3}"
        assert self._compare_tsv_files(export_file_3, reference_file_3), "Step 3 export does not match reference"
