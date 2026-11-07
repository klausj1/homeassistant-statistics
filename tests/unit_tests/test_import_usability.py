"""Unit tests for import usability helpers."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.import_service import (
    _filter_unknown_recorder_entities,
    _prepare_counter_dataframe,
    _process_counter_dataframe,
    _write_skipped_unknown_entities,
)
from custom_components.import_statistics.import_service_helper import (
    CounterDataType,
    ImportDataClassification,
    ImportDataType,
    _has_populated_columns,
    _validate_and_detect_delta,
    resolve_counter_mode,
    validate_counter_mode,
    validate_ignore_unknown_entities,
)


def _counter_dataframe(**values: list) -> pd.DataFrame:
    """Build a counter DataFrame for mode selection tests."""
    return pd.DataFrame({"statistic_id": ["counter.energy"], "unit": ["kWh"], "start": ["2022-01-01"], **values})


def test_has_populated_columns() -> None:
    """Only non-null values count as populated."""
    assert _has_populated_columns(_counter_dataframe(sum=[None], delta=[5]), ["sum", "state"]) is False
    assert _has_populated_columns(_counter_dataframe(sum=[None], delta=[5]), ["delta"]) is True
    assert _has_populated_columns(_counter_dataframe(sum=[1]), ["sum"]) is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "strict"),
        (" STRICT ", "strict"),
        ("strict", "strict"),
        ("sum", "sum"),
        ("delta", "delta"),
    ],
)
def test_validate_counter_mode(value: str | None, expected: str) -> None:
    """Counter modes are normalized and accepted from the supported set."""
    assert validate_counter_mode(value) == expected


def test_validate_counter_mode_rejects_invalid_values() -> None:
    """Unknown and non-string modes fail explicitly."""
    with pytest.raises(HomeAssistantError, match="counter_mode must be one of"):
        validate_counter_mode("something")
    with pytest.raises(HomeAssistantError, match="counter_mode must be one of"):
        validate_counter_mode("auto")
    with pytest.raises(HomeAssistantError, match="counter_mode must be a string"):
        validate_counter_mode(1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("frame", "mode", "expected"),
    [
        (_counter_dataframe(sum=[10]), "strict", CounterDataType.SUM_STATE),
        (_counter_dataframe(delta=[2]), "strict", CounterDataType.DELTA),
        (_counter_dataframe(sum=[10], delta=[2]), "sum", CounterDataType.SUM_STATE),
        (_counter_dataframe(sum=[10], delta=[2]), "delta", CounterDataType.DELTA),
    ],
)
def test_resolve_counter_mode(frame: pd.DataFrame, mode: str, expected: CounterDataType) -> None:
    """Auto and strict modes resolve a single counter representation."""
    assert resolve_counter_mode(frame, mode) == expected


def test_resolve_counter_mode_defaults_to_strict() -> None:
    """The default mode rejects files containing both counter representations."""
    frame = _counter_dataframe(sum=[10], delta=[2])
    with pytest.raises(HomeAssistantError, match=r"counter_mode='sum'.*counter_mode='delta'"):
        resolve_counter_mode(frame)


def test_resolve_counter_mode_strict_rejects_both_columns() -> None:
    """Strict mode rejects both representations on counter rows, even when sparse."""
    frame = _counter_dataframe(sum=[10], delta=[None])
    with pytest.raises(HomeAssistantError, match="both 'sum'/'state' and 'delta' columns"):
        resolve_counter_mode(frame, "strict")


@pytest.mark.parametrize(
    ("frame", "mode"),
    [
        (_counter_dataframe(delta=[2]), "sum"),
        (_counter_dataframe(sum=[10]), "delta"),
        (_counter_dataframe(sum=[None], delta=[None]), "strict"),
    ],
)
def test_resolve_counter_mode_rejects_missing_selected_data(frame: pd.DataFrame, mode: str) -> None:
    """Explicit modes and empty counter inputs cannot silently import no counter data."""
    with pytest.raises(HomeAssistantError):
        resolve_counter_mode(frame, mode)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        (" FALSE ", False),
        ("yes", True),
        ("off", False),
        (1, True),
        (0, False),
    ],
)
def test_validate_ignore_unknown_entities(value: object, expected: object) -> None:
    """Boolean service values are normalized."""
    assert validate_ignore_unknown_entities(value) is expected


@pytest.mark.parametrize("value", ["maybe", 2, None])
def test_validate_ignore_unknown_entities_rejects_invalid_values(value: object) -> None:
    """Invalid ignore-unknown values raise a Home Assistant error."""
    with pytest.raises(HomeAssistantError, match="ignore_unknown_entities must be a boolean"):
        validate_ignore_unknown_entities(value)


def test_validate_and_detect_delta_classifies_data_types() -> None:
    """MIXED denotes measurement plus counter rows; counter representations remain distinct."""
    measurements = pd.DataFrame({"statistic_id": ["sensor.temp"], "start": ["t"], "unit": ["°C"], "mean": [1], "min": [0], "max": [2], "delta": [None]})
    counter_both = _counter_dataframe(sum=[10], delta=[2])
    mixed_counter_both = pd.concat(
        [
            measurements,
            _counter_dataframe(sum=[10], delta=[2]),
        ],
        ignore_index=True,
    )
    mixed = pd.DataFrame(
        {
            "statistic_id": ["sensor.temp", "counter.energy"],
            "start": ["t", "t"],
            "unit": ["°C", "kWh"],
            "mean": [1, None],
            "min": [0, None],
            "max": [2, None],
            "sum": [None, 10],
            "state": [None, 5],
            "delta": [None, None],
        }
    )
    assert _validate_and_detect_delta(measurements) == ImportDataClassification(ImportDataType.SENSOR, None)
    assert _validate_and_detect_delta(counter_both) == ImportDataClassification(ImportDataType.COUNTER, CounterDataType.BOTH)
    assert _validate_and_detect_delta(mixed) == ImportDataClassification(ImportDataType.MIXED, CounterDataType.SUM_STATE)
    assert _validate_and_detect_delta(mixed_counter_both) == ImportDataClassification(ImportDataType.MIXED, CounterDataType.BOTH)


def test_validate_and_detect_delta_collects_no_populated_values_error() -> None:
    """Collect the empty-data error without stopping classification."""
    frame = pd.DataFrame(columns=["statistic_id", "start", "unit", "min", "max", "mean", "sum", "state", "delta"])
    classification = _validate_and_detect_delta(frame)
    assert classification == ImportDataClassification(ImportDataType.SENSOR, None)
    assert any("No populated values" in error for error in frame.attrs["validation_errors"])


def test_prepare_counter_dataframe_selects_only_requested_representation() -> None:
    """Counter dataframe selection drops fields from the unselected representation."""
    frame = _counter_dataframe(sum=[10], state=[5], delta=[2])
    sum_df = _prepare_counter_dataframe(frame, CounterDataType.SUM_STATE)
    delta_df = _prepare_counter_dataframe(frame, CounterDataType.DELTA)
    assert list(sum_df.columns) == ["statistic_id", "unit", "start", "sum", "state"]
    assert list(delta_df.columns) == ["statistic_id", "unit", "start", "delta"]


def test_write_skipped_unknown_entities(tmp_path: Path) -> None:
    """Skipped statistic IDs are written to a generated CSV."""
    path = _write_skipped_unknown_entities(str(tmp_path), ["sensor.missing"])
    assert path.parent == tmp_path
    assert path.name.startswith("skipped_unknown_entities_")
    assert pd.read_csv(path)["statistic_id"].tolist() == ["sensor.missing"]


def test_filter_unknown_recorder_entities_skips_only_missing_recorder_ids(tmp_path: Path) -> None:
    """Filtering skips missing recorder entities but retains existing and external statistics."""
    hass = SimpleNamespace(
        config=SimpleNamespace(config_dir=str(tmp_path)),
        states=MagicMock(),
    )
    hass.states.get.side_effect = lambda entity_id: object() if entity_id == "sensor.exists" else None
    stats = {
        "sensor.missing": ({"source": "recorder", "statistic_id": "sensor.missing"}, []),
        "sensor.exists": ({"source": "recorder", "statistic_id": "sensor.exists"}, []),
        "custom:external": ({"source": "custom", "statistic_id": "custom:external"}, []),
    }

    filtered, skipped = _filter_unknown_recorder_entities(hass, stats)

    assert list(filtered) == ["sensor.exists", "custom:external"]
    assert skipped == ["sensor.missing"]
    csv_files = list(tmp_path.glob("skipped_unknown_entities_*.csv"))
    assert len(csv_files) == 1
    assert pd.read_csv(csv_files[0])["statistic_id"].tolist() == skipped


@pytest.mark.asyncio
async def test_process_counter_dataframe_imports_sum_representation() -> None:
    """Counter processing passes only the selected sum representation downstream."""
    frame = _counter_dataframe(sum=[10], state=[5])
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn: fn())
    with patch("custom_components.import_statistics.import_service.handle_dataframe_no_delta", return_value={"counter.energy": "sum"}) as handler:
        result = await _process_counter_dataframe(hass, frame, "strict")

    assert result == {"counter.energy": "sum"}
    selected_df = handler.call_args.args[0]
    assert list(selected_df.columns) == ["statistic_id", "unit", "start", "sum", "state"]


@pytest.mark.asyncio
async def test_process_counter_dataframe_converts_delta_representation() -> None:
    """Delta selection fetches references and passes only deltas to conversion."""
    frame = _counter_dataframe(sum=[10], delta=[2])
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn: fn())
    with (
        patch(
            "custom_components.import_statistics.import_service.prepare_delta_handling",
            new=AsyncMock(return_value={"counter.energy": {"reference": {}}}),
        ) as prepare_references,
        patch("custom_components.import_statistics.import_service.handle_dataframe_delta", return_value={"counter.energy": "delta"}) as handler,
    ):
        result = await _process_counter_dataframe(hass, frame, "delta")

    assert result == {"counter.energy": "delta"}
    prepare_references.assert_awaited_once()
    selected_df = handler.call_args.args[0]
    assert list(selected_df.columns) == ["statistic_id", "unit", "start", "delta"]
