"""Unit tests for aggregated import error logging and row attribution."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import AggregatedValidationError
from custom_components.import_statistics.import_service import _raise_import_error, _validate_dataframe_entities
from custom_components.import_statistics.import_service_helper import collect_unit_validation_errors


@pytest.mark.asyncio
async def test_error_log_preserves_grouped_rows_once_and_sorts_by_row(tmp_path: Path) -> None:
    """Keep one entry per error while retaining its full row list."""
    hass = SimpleNamespace(
        config=SimpleNamespace(config_dir=str(tmp_path)),
        async_add_executor_job=AsyncMock(side_effect=lambda func, *args: func(*args)),
    )
    error = AggregatedValidationError(
        [
            "Inconsistent units for 'sensor.energy' at rows [45, 46]: found ['kWh', 'x'].",
            "Invalid timestamp format at row 35: '07.11k2026 17:00'.",
            "Unit mismatch for 'sensor.energy' at row 46: input file has 'x'.",
        ]
    )

    with pytest.raises(HomeAssistantError, match=r"Inconsistent units.*rows \[45, 46\]"):
        await _raise_import_error(hass, error)

    assert (tmp_path / "import_errors.log").read_text(encoding="utf-8").splitlines() == [
        "35: Invalid timestamp format at row 35: '07.11k2026 17:00'.",
        "45, 46: Inconsistent units for 'sensor.energy' at rows [45, 46]: found ['kWh', 'x'].",
        "46: Unit mismatch for 'sensor.energy' at row 46: input file has 'x'.",
    ]


@pytest.mark.asyncio
async def test_error_log_marks_errors_without_row_context(tmp_path: Path) -> None:
    """Do not assign a real-looking row number to non-row-specific errors."""
    hass = SimpleNamespace(
        config=SimpleNamespace(config_dir=str(tmp_path)),
        async_add_executor_job=AsyncMock(side_effect=lambda func, *args: func(*args)),
    )
    error = AggregatedValidationError(["Invalid timezone identifier.", "Invalid float value at row 7."])

    with pytest.raises(HomeAssistantError, match="Invalid timezone identifier"):
        await _raise_import_error(hass, error)

    assert (tmp_path / "import_errors.log").read_text(encoding="utf-8").splitlines() == [
        "7: Invalid float value at row 7.",
        "No source row: Invalid timezone identifier.",
    ]


@pytest.mark.asyncio
async def test_unit_mismatch_uses_only_rows_with_the_mismatched_unit() -> None:
    """Keep entity and metadata mismatch rows separate from cross-row unit inconsistency."""
    statistic_id = "sensor.energy"
    df = pd.DataFrame(
        {
            "statistic_id": [statistic_id, statistic_id],
            "unit": ["kWh", "x"],
        },
        index=[43, 44],
    )
    hass = MagicMock()
    hass.states.get.return_value = SimpleNamespace(attributes={"unit_of_measurement": "kWh"})
    recorder = MagicMock()
    recorder.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    with (
        patch("custom_components.import_statistics.import_service.get_instance", return_value=recorder),
        patch(
            "custom_components.import_statistics.import_service.get_metadata",
            return_value={statistic_id: (1, {"unit_of_measurement": "kWh"})},
        ),
    ):
        errors = await _validate_dataframe_entities(hass, df, ignore_unknown_entities=False)

    consistency_errors = collect_unit_validation_errors(df)
    assert len(consistency_errors) == 1
    assert "rows [45, 46]" in consistency_errors[0]
    assert len(errors) == 2
    assert all("at row 46:" in error for error in errors)
    assert all("at row 45:" not in error for error in errors)
    assert all("at rows [45, 46]" not in error for error in errors)
