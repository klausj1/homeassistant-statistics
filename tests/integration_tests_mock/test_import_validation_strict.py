"""Integration tests for strict validation - no silent failures."""

import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import setup
from custom_components.import_statistics.const import (
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_FILENAME,
    ATTR_TIMEZONE_IDENTIFIER,
)
from tests.conftest import create_mock_recorder_instance, mock_async_add_executor_job


class TestImportValidationStrict:
    """Integration tests for strict validation behavior."""

    @pytest.mark.asyncio
    async def test_import_fails_on_invalid_row_in_middle(self) -> None:
        """Test that import fails when an invalid row is in the middle of the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test file with invalid row in the middle
            test_file = Path(tmpdir) / "invalid_middle.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\n"
                "counter.energy\t01.01.2022 00:00\tkWh\t100.0\t100.0\n"
                "counter.energy\t01.01.2022 01:30\tkWh\t105.0\t105.0\n"  # Invalid: not full hour
                "counter.energy\t01.01.2022 02:00\tkWh\t110.0\t110.0\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "invalid_middle.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: ".",
                },
            )

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics"),
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
                pytest.raises(HomeAssistantError, match=re.escape("Invalid timestamp: 01.01.2022 01:30. The timestamp must be a full hour.")),
            ):
                await import_handler(call)

    @pytest.mark.asyncio
    async def test_import_fails_on_invalid_timestamp_format(self) -> None:
        """Test that import fails on invalid timestamp format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test file with wrong timestamp format
            test_file = Path(tmpdir) / "invalid_format.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\ncounter.energy\t2022-01-01 00:00\tkWh\t100.0\t100.0\n"  # Wrong format (ISO instead of DD.MM.YYYY)
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "invalid_format.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: ".",
                },
            )

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics"),
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
                pytest.raises(HomeAssistantError, match=re.escape("Invalid timestamp format: 2022-01-01 00:00")),
            ):
                await import_handler(call)

    @pytest.mark.asyncio
    async def test_import_fails_on_invalid_float_value(self) -> None:
        """Test that import fails on invalid float value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test file with non-numeric value
            test_file = Path(tmpdir) / "invalid_float.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\ncounter.energy\t01.01.2022 00:00\tkWh\tabc\t100.0\n"  # Invalid: non-numeric sum
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "invalid_float.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: ".",
                },
            )

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics"),
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
                pytest.raises(HomeAssistantError, match=re.escape("Invalid float value: abc")),
            ):
                await import_handler(call)

    @pytest.mark.asyncio
    async def test_import_fails_on_min_max_constraint_violation(self) -> None:
        """Test that import fails when min > max constraint is violated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test file with min > max
            test_file = Path(tmpdir) / "invalid_minmax.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tmean\tmin\tmax\nsensor.temperature\t01.01.2022 00:00\t°C\t20.0\t25.0\t15.0\n"  # Invalid: min > max
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "invalid_minmax.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: ".",
                },
            )

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics"),
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
                pytest.raises(HomeAssistantError, match=re.escape("Invalid values: min: 25.0, max: 15.0, mean: 20.0")),
            ):
                await import_handler(call)

    @pytest.mark.asyncio
    async def test_import_fails_on_nan_value(self) -> None:
        """Test that import fails on NaN/empty values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test file with empty value
            test_file = Path(tmpdir) / "invalid_nan.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\ncounter.energy\t01.01.2022 00:00\tkWh\t\t100.0\n"  # Invalid: empty sum
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "invalid_nan.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: ".",
                },
            )

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics"),
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
                pytest.raises(HomeAssistantError, match=re.escape("(NaN/empty value not allowed)")),
            ):
                await import_handler(call)

    @pytest.mark.asyncio
    async def test_import_succeeds_with_all_valid_rows(self) -> None:
        """Test that import succeeds when all rows are valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test file with all valid rows
            test_file = Path(tmpdir) / "all_valid.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\n"
                "counter.energy\t01.01.2022 00:00\tkWh\t100.0\t100.0\n"
                "counter.energy\t01.01.2022 01:00\tkWh\t105.0\t105.0\n"
                "counter.energy\t01.01.2022 02:00\tkWh\t110.0\t110.0\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "all_valid.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: ".",
                },
            )

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
            ):
                # Should succeed without errors
                await import_handler(call)

                # Verify async_import_statistics was called
                assert mock_import.called, "async_import_statistics should have been called"

                # Extract the call arguments
                call_args = mock_import.call_args
                statistics = call_args[0][2]

                # Verify all 3 rows were imported
                assert len(statistics) == 3
                assert pytest.approx(statistics[0]["sum"]) == pytest.approx(100.0)
                assert pytest.approx(statistics[1]["sum"]) == pytest.approx(105.0)
                assert pytest.approx(statistics[2]["sum"]) == pytest.approx(110.0)

    @pytest.mark.asyncio
    async def test_import_fails_on_wrong_decimal_separator(self) -> None:
        """Test that import fails when using wrong decimal separator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test file with comma separator but configured for dot
            test_file = Path(tmpdir) / "wrong_separator.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\ncounter.energy\t01.01.2022 00:00\tkWh\t100,5\t100,5\n"  # Comma separator
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "wrong_separator.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: ".",  # Configured for dot, but file has comma
                },
            )

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics"),
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
                pytest.raises(HomeAssistantError, match=re.escape("Invalid float value: 100,5")),
            ):
                await import_handler(call)
