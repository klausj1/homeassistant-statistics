"""Mock integration tests for service responses containing multiple validation errors."""

import csv
import io
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import ServiceCall

from custom_components.import_statistics import async_setup
from custom_components.import_statistics.const import ATTR_DECIMAL, ATTR_DELIMITER, ATTR_FILENAME, ATTR_TIMEZONE_IDENTIFIER
from tests.conftest import (
    create_mock_entity_state,
    create_mock_recorder_instance,
    create_mock_states_with_unit,
    get_service_handler,
    mock_async_add_executor_job,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("import_type", ["file", "json"])
async def test_import_returns_all_errors_without_writing(import_type: str) -> None:
    """File and JSON imports return all row validation errors without database writes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hass = MagicMock()
        hass.config.config_dir = tmpdir
        hass.config.time_zone = "UTC"
        hass.async_add_executor_job = mock_async_add_executor_job
        hass.states = create_mock_states_with_unit("kWh")
        await async_setup(hass, {})

        if import_type == "file":
            test_file = Path(tmpdir) / "invalid.csv"
            await hass.async_add_executor_job(
                lambda: test_file.write_text(
                    "statistic_id\tstart\tunit\tsum\tstate\n"
                    "counter.energy\t01.01.2022 00:30\tkWh\tbad\t100.0\n"
                    "counter.energy\t01.01.2022 01:15\tkWh\tinvalid\t110.0\n",
                    encoding="utf-8",
                )
            )
            service_name = "import_from_file"
            call_data = {
                ATTR_FILENAME: "invalid.csv",
                ATTR_TIMEZONE_IDENTIFIER: "UTC",
                ATTR_DELIMITER: "\t",
                ATTR_DECIMAL: "dot ('.')",
            }
        else:
            service_name = "import_from_json"
            call_data = {
                ATTR_TIMEZONE_IDENTIFIER: "UTC",
                ATTR_DECIMAL: "dot ('.')",
                "entities": [
                    {
                        "id": "counter.energy",
                        "unit": "kWh",
                        "values": [
                            {"datetime": "01.01.2022 00:30", "sum": 100.0, "state": 100.0},
                            {"datetime": "01.01.2022 01:15", "sum": 110.0, "state": 110.0},
                        ],
                    }
                ],
            }

        call = ServiceCall(hass, "import_statistics", service_name, call_data)
        handler = get_service_handler(hass, service_name)
        with (
            patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
            patch("custom_components.import_statistics.import_service.get_metadata", return_value={}),
            patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
            patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_add,
        ):
            response = await handler(call)

        assert response["failed"] is True
        if import_type == "file":
            assert len(response["errors"]) == 4
            assert any("Invalid timestamp" in error for error in response["errors"])
            assert any("Invalid float value" in error for error in response["errors"])
        else:
            assert len(response["errors"]) == 2
            assert all("Invalid timestamp" in error for error in response["errors"])
        mock_import.assert_not_called()
        mock_add.assert_not_called()


@pytest.mark.asyncio
async def test_export_returns_all_time_errors() -> None:
    """Invalid start and end times are both returned in the export response."""
    hass = MagicMock()
    hass.config.time_zone = "UTC"
    await async_setup(hass, {})
    call = ServiceCall(
        hass,
        "import_statistics",
        "export_statistics",
        {
            ATTR_FILENAME: "export.tsv",
            ATTR_TIMEZONE_IDENTIFIER: "UTC",
            "start_time": "invalid start",
            "end_time": "invalid end",
        },
    )
    handler = get_service_handler(hass, "export_statistics")

    response = await handler(call)

    assert response["failed"] is True
    assert len(response["errors"]) == 2
    assert all("Invalid datetime format" in error for error in response["errors"])


@pytest.mark.asyncio
async def test_import_combines_malformed_timestamp_and_missing_entity_errors() -> None:
    """Malformed timestamps do not prevent independent missing-entity errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hass = MagicMock()
        hass.config.config_dir = tmpdir
        hass.config.time_zone = "UTC"
        hass.async_add_executor_job = mock_async_add_executor_job
        hass.states = MagicMock()
        hass.states.get.return_value = None
        await async_setup(hass, {})

        test_file = Path(tmpdir) / "malformed.tsv"
        await hass.async_add_executor_job(
            lambda: test_file.write_text(
                "statistic_id\tstart\tunit\tmean\tmin\tmax\n"
                "sensor.missing_a\t07.11k2026 17:00\t°C\t20\t18\t22\n"
                "sensor.missing_b\t07.11.2026 18:00\t°C\t20\t18\t22\n",
                encoding="utf-8",
            )
        )
        call = ServiceCall(
            hass,
            "import_statistics",
            "import_from_file",
            {
                ATTR_FILENAME: "malformed.tsv",
                ATTR_TIMEZONE_IDENTIFIER: "UTC",
                ATTR_DELIMITER: "\t",
                ATTR_DECIMAL: "dot ('.')",
            },
        )
        recorder = create_mock_recorder_instance()

        with (
            patch("custom_components.import_statistics.import_service.get_instance", return_value=recorder),
            patch("custom_components.import_statistics.import_service.get_metadata", return_value={}),
            patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
        ):
            response = await get_service_handler(hass, "import_from_file")(call)

        assert response["failed"] is True
        assert len(response["errors"]) == 3
        assert any("07.11k2026 17:00" in error for error in response["errors"])
        assert any("sensor.missing_a" in error for error in response["errors"])
        assert any("sensor.missing_b" in error for error in response["errors"])
        mock_import.assert_not_called()


@pytest.mark.asyncio
async def test_import_combines_inconsistent_units_and_missing_entity_errors() -> None:
    """Inconsistent units do not prevent independent missing-entity errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hass = MagicMock()
        hass.config.config_dir = tmpdir
        hass.config.time_zone = "UTC"
        hass.async_add_executor_job = mock_async_add_executor_job
        hass.states = MagicMock()
        hass.states.get.return_value = None
        await async_setup(hass, {})

        test_file = Path(tmpdir) / "inconsistent.tsv"
        await hass.async_add_executor_job(
            lambda: test_file.write_text(
                "statistic_id\tstart\tunit\tmean\tmin\tmax\n"
                "sensor.missing_a\t07.11.2026 17:00\t°C\t20\t18\t22\n"
                "sensor.missing_a\t07.11.2026 18:00\t°F\t20\t18\t22\n"
                "sensor.missing_b\t07.11.2026 19:00\t°C\t20\t18\t22\n",
                encoding="utf-8",
            )
        )
        call = ServiceCall(
            hass,
            "import_statistics",
            "import_from_file",
            {
                ATTR_FILENAME: "inconsistent.tsv",
                ATTR_TIMEZONE_IDENTIFIER: "UTC",
                ATTR_DELIMITER: "\t",
                ATTR_DECIMAL: "dot ('.')",
            },
        )
        recorder = create_mock_recorder_instance()

        with (
            patch("custom_components.import_statistics.import_service.get_instance", return_value=recorder),
            patch("custom_components.import_statistics.import_service.get_metadata", return_value={}),
            patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
        ):
            response = await get_service_handler(hass, "import_from_file")(call)

        assert response["failed"] is True
        assert len(response["errors"]) == 3
        assert any("Inconsistent units" in error and "sensor.missing_a" in error for error in response["errors"])
        assert any("Entity does not exist" in error and "sensor.missing_a" in error for error in response["errors"])
        assert any("Entity does not exist" in error and "sensor.missing_b" in error for error in response["errors"])
        mock_import.assert_not_called()


@pytest.mark.asyncio
async def test_import_response_contains_all_validation_error_types_with_rows() -> None:  # noqa: PLR0912, PLR0915
    """Return all independently detectable validation errors with source row numbers."""
    header = ["statistic_id", "start", "unit", "min", "max", "mean", "sum", "state", "delta"]
    rows = []

    def add_row(statistic_id: str, start: str, unit: str, **values: object) -> None:
        row = dict.fromkeys(header, "")
        row.update({"statistic_id": statistic_id, "start": start, "unit": unit, **values})
        rows.append(row)

    for statistic_id, start in (
        ("sensor.bad_time_a", "07.11k2026 17:00"),
        ("sensor.bad_time_b", "07.11x2026 18:00"),
    ):
        add_row(statistic_id, start, "°C", min=1, max=3, mean=2)
    for statistic_id, start in (
        ("sensor.dst_a", "29.03.2026 02:00"),
        ("sensor.dst_b", "29.03.2026 02:30"),
    ):
        add_row(statistic_id, start, "°C", min=1, max=3, mean=2)
    for statistic_id, start in (
        ("sensor.off_hour_a", "07.11.2026 17:15"),
        ("sensor.off_hour_b", "07.11.2026 18:30"),
    ):
        add_row(statistic_id, start, "°C", min=1, max=3, mean=2)
    for statistic_id, mean in (("sensor.bad_float_a", "bad-a"), ("sensor.bad_float_b", "bad-b")):
        add_row(statistic_id, "07.11.2026 19:00", "°C", min=1, max=3, mean=mean)
    for statistic_id in ("sensor.bad_range_a", "sensor.bad_range_b"):
        add_row(statistic_id, "07.11.2026 20:00", "°C", min=5, max=2, mean=3)
    for statistic_id, unit_a, unit_b in (
        ("sensor.inconsistent_a", "°C", "°F"),
        ("sensor.inconsistent_b", "kWh", "Wh"),
    ):
        add_row(statistic_id, "07.11.2026 21:00", unit_a, min=1, max=3, mean=2)
        add_row(statistic_id, "07.11.2026 22:00", unit_b, min=1, max=3, mean=2)
    for statistic_id in ("sensor.missing_a", "sensor.missing_b"):
        add_row(statistic_id, "07.11.2026 23:00", "°C", min=1, max=3, mean=2)
    for statistic_id in ("sensor.entity_unit_a", "sensor.entity_unit_b"):
        add_row(statistic_id, "08.11.2026 00:00", "°C", min=1, max=3, mean=2)
    for statistic_id, unit in (("sensor.db_unit_a", "°C"), ("sensor.db_unit_b", "kWh")):
        add_row(statistic_id, "08.11.2026 01:00", unit, min=1, max=3, mean=2)
    for statistic_id, unit in (("sensor.invalid_unit_a", "nan"), ("sensor.invalid_unit_b", "null")):
        add_row(statistic_id, "08.11.2026 02:00", unit, min=1, max=3, mean=2)
    for statistic_id in ("invalid id a", "recorder:invalid_id_b"):
        add_row(statistic_id, "08.11.2026 03:00", "°C", min=1, max=3, mean=2)
    for statistic_id in ("sensor.mixed_a", "sensor.mixed_b"):
        add_row(statistic_id, "08.11.2026 04:00", "°C", min=1, max=3, mean=2)
        add_row(statistic_id, "08.11.2026 05:00", "°C", sum=1, state=1)
    for statistic_id, value in (("sensor.bad_sum_a", "bad-sum-a"), ("sensor.bad_sum_b", "bad-sum-b")):
        add_row(statistic_id, "08.11.2026 06:00", "kWh", sum=value, state=1)
    for statistic_id, value in (("sensor.bad_delta_a", "bad-delta-a"), ("sensor.bad_delta_b", "bad-delta-b")):
        add_row(statistic_id, "08.11.2026 07:00", "kWh", delta=value)
    for statistic_id in ("sensor.empty_a", "sensor.empty_b"):
        add_row(statistic_id, "08.11.2026 08:00", "°C")

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    with tempfile.TemporaryDirectory() as tmpdir:
        hass = MagicMock()
        hass.config.config_dir = tmpdir
        hass.config.time_zone = "UTC"
        hass.async_add_executor_job = mock_async_add_executor_job
        states = {
            "sensor.entity_unit_a": create_mock_entity_state("°F"),
            "sensor.entity_unit_b": create_mock_entity_state("Wh"),
            "sensor.db_unit_a": create_mock_entity_state("°C"),
            "sensor.db_unit_b": create_mock_entity_state("kWh"),
            "sensor.invalid_unit_a": create_mock_entity_state(None),
            "sensor.invalid_unit_b": create_mock_entity_state(None),
        }
        hass.states.get.side_effect = states.get
        await async_setup(hass, {})

        test_file = Path(tmpdir) / "all_errors.tsv"
        await hass.async_add_executor_job(lambda: test_file.write_text(buffer.getvalue(), encoding="utf-8"))
        call = ServiceCall(
            hass,
            "import_statistics",
            "import_from_file",
            {
                ATTR_FILENAME: "all_errors.tsv",
                ATTR_TIMEZONE_IDENTIFIER: "Europe/Vienna",
                ATTR_DELIMITER: "\t",
                ATTR_DECIMAL: "dot ('.')",
            },
        )
        metadata = {
            "sensor.db_unit_a": (1, {"unit_of_measurement": "°F"}),
            "sensor.db_unit_b": (2, {"unit_of_measurement": "Wh"}),
        }

        with (
            patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
            patch("custom_components.import_statistics.import_service.get_metadata", return_value=metadata),
            patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
            patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_add,
        ):
            response = await get_service_handler(hass, "import_from_file")(call)

        errors = response["errors"]
        assert response["failed"] is True
        assert sum("Invalid timestamp format" in error for error in errors) >= 2
        assert sum("daylight saving time transition" in error for error in errors) >= 2
        assert sum("Invalid timestamp at row" in error for error in errors) >= 2
        assert sum("Invalid float value" in error for error in errors) >= 2
        assert sum("Invalid values at row" in error for error in errors) >= 2
        assert sum("Inconsistent units" in error for error in errors) >= 2
        assert sum("Entity does not exist" in error for error in errors) >= 2
        assert sum("entity has" in error for error in errors) >= 2
        assert sum("statistic_meta has" in error for error in errors) >= 2
        assert sum("Invalid unit value" in error for error in errors) >= 2
        assert sum("Statistic_id" in error or "Invalid statistic_id" in error for error in errors) >= 2
        assert sum("both sensor" in error for error in errors) >= 2
        assert sum("Counter data is conflicting" in error for error in errors) >= 2
        assert sum("no value data" in error for error in errors) >= 2
        assert all("row" in error.lower() for error in errors), errors
        mock_import.assert_not_called()
        mock_add.assert_not_called()


@pytest.mark.asyncio
async def test_import_reports_column_and_entity_errors_with_rows() -> None:
    """Include line references for independent header, schema, and entity errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hass = MagicMock()
        hass.config.config_dir = tmpdir
        hass.config.time_zone = "UTC"
        hass.async_add_executor_job = mock_async_add_executor_job
        hass.states.get.return_value = None
        await async_setup(hass, {})

        test_file = Path(tmpdir) / "columns.tsv"
        await hass.async_add_executor_job(
            lambda: test_file.write_text(
                "statistic_id\tstart\tunit\tmean\tunknown_a\tunknown_b\n"
                "sensor.missing_a\t07.11.2026 17:00\t°C\t20\t\t\n"
                "sensor.missing_b\t07.11.2026 18:00\t°C\t21\t\t\n",
                encoding="utf-8",
            )
        )
        call = ServiceCall(
            hass,
            "import_statistics",
            "import_from_file",
            {
                ATTR_FILENAME: "columns.tsv",
                ATTR_TIMEZONE_IDENTIFIER: "UTC",
                ATTR_DELIMITER: "\t",
                ATTR_DECIMAL: "dot ('.')",
            },
        )
        with (
            patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
            patch("custom_components.import_statistics.import_service.get_metadata", return_value={}),
            patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
        ):
            response = await get_service_handler(hass, "import_from_file")(call)

        errors = response["errors"]
        assert response["failed"] is True
        assert any("unknown_a, unknown_b" in error and "Source rows: [2, 3]" in error for error in errors), errors
        assert any("Columns 'mean', 'min', and 'max'" in error and "Source rows: [2, 3]" in error for error in errors)
        assert sum("Entity does not exist" in error and "rows [" in error for error in errors) == 2
        assert all("row" in error.lower() for error in errors)
        mock_import.assert_not_called()
