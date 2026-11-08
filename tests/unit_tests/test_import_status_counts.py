"""Unit tests for aggregated import status counts."""

import datetime as dt
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.import_statistics.import_service import _get_import_status_counts


@pytest.mark.asyncio
async def test_import_status_counts_match_previous_classifier() -> None:
    """Aggregate the old per-statistic classifications without changing their rules."""
    stats = {
        "custom:new_without_db": (
            {"statistic_id": "custom:new_without_db"},
            [{"start": dt.datetime(2025, 1, 1, 10, tzinfo=dt.UTC)}],
        ),
        "custom:newer": (
            {"statistic_id": "custom:newer"},
            [
                {"start": dt.datetime(2025, 1, 1, 10, tzinfo=dt.UTC)},
                {"start": dt.datetime(2025, 1, 2, 10, tzinfo=dt.UTC)},
            ],
        ),
        "custom:older": (
            {"statistic_id": "custom:older"},
            [{"start": dt.datetime(2025, 1, 1, 10, tzinfo=dt.UTC)}],
        ),
        "custom:equal": (
            {"statistic_id": "custom:equal"},
            [
                {"start": dt.datetime(2025, 1, 1, 10, tzinfo=dt.UTC)},
                {"start": dt.datetime(2025, 1, 1, 11, tzinfo=dt.UTC)},
            ],
        ),
        "custom:no_data": ({"statistic_id": "custom:no_data"}, []),
    }
    db_starts = {
        "custom:newer": dt.datetime(2025, 1, 2, 9, tzinfo=dt.UTC),
        "custom:older": dt.datetime(2025, 1, 1, 11, tzinfo=dt.UTC),
        "custom:equal": dt.datetime(2025, 1, 1, 11, tzinfo=dt.UTC),
        "custom:no_data": dt.datetime(2025, 1, 3, 10, tzinfo=dt.UTC),
    }

    async def newest_db_record(_hass: object, statistic_id: str) -> dict[str, dt.datetime] | None:
        """Return the test database's newest timestamp for a statistic."""
        db_start = db_starts.get(statistic_id)
        return {"start": db_start} if db_start is not None else None

    with patch(
        "custom_components.import_statistics.import_service._get_newest_db_statistic",
        new=AsyncMock(side_effect=newest_db_record),
    ):
        result = await _get_import_status_counts(object(), stats)

    assert result == {"new_data": 2, "existing_data": 2, "no_data": 1}


@pytest.mark.asyncio
async def test_import_status_counts_compare_timestamps_in_utc() -> None:
    """Normalize imported local timestamps to UTC before comparing with the database."""
    stats = {
        "custom:equal_in_utc": (
            {"statistic_id": "custom:equal_in_utc"},
            [{"start": dt.datetime(2025, 1, 1, 13, tzinfo=ZoneInfo("Europe/Berlin"))}],
        ),
    }
    newest_db_start = dt.datetime(2025, 1, 1, 12, tzinfo=dt.UTC)

    with patch(
        "custom_components.import_statistics.import_service._get_newest_db_statistic",
        new=AsyncMock(return_value={"start": newest_db_start}),
    ):
        result = await _get_import_status_counts(object(), stats)

    assert result == {"new_data": 0, "existing_data": 1, "no_data": 0}


@pytest.mark.asyncio
async def test_import_status_counts_empty_statistics_dict() -> None:
    """Return zero counts when there are no statistics to classify."""
    with patch(
        "custom_components.import_statistics.import_service._get_newest_db_statistic",
        new=AsyncMock(),
    ) as newest_db_statistic:
        result = await _get_import_status_counts(object(), {})

    assert result == {"new_data": 0, "existing_data": 0, "no_data": 0}
    newest_db_statistic.assert_not_awaited()
