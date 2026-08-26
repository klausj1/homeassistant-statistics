"""Unit tests for get_import_status_for_statistic function."""

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from custom_components.import_statistics.import_service_helper import get_import_status_for_statistic


@pytest.fixture
def statistic_id() -> str:
    """Return a sample statistic id."""
    return "custom:energy"


def test_no_data_empty_statistics(statistic_id: str) -> None:
    """Test no data status when no statistics are provided."""
    db_start = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
    result = get_import_status_for_statistic(statistic_id, [], db_start)

    assert result["statistic_id"] == statistic_id
    assert result["status"] == "no data"
    assert result["newest_import_start"] is None
    assert result["newest_db_start"] == "2025-01-01T12:00:00+00:00"


def test_new_data_when_no_db_record(statistic_id: str) -> None:
    """Test new data status when there is no existing database record."""
    import_start = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
    statistics = [{"start": import_start}]
    result = get_import_status_for_statistic(statistic_id, statistics, None)

    assert result["status"] == "new data"
    assert result["newest_import_start"] == "2025-01-01T12:00:00+00:00"
    assert result["newest_db_start"] is None


def test_new_data_when_import_is_newer(statistic_id: str) -> None:
    """Test new data status when the import contains a newer timestamp."""
    import_start = dt.datetime(2025, 1, 2, 12, 0, tzinfo=dt.UTC)
    db_start = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
    statistics = [{"start": import_start}]
    result = get_import_status_for_statistic(statistic_id, statistics, db_start)

    assert result["status"] == "new data"
    assert result["newest_import_start"] == "2025-01-02T12:00:00+00:00"
    assert result["newest_db_start"] == "2025-01-01T12:00:00+00:00"


def test_existing_data_when_import_is_older(statistic_id: str) -> None:
    """Test existing data status when the import only contains older timestamps."""
    import_start = dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.UTC)
    db_start = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
    statistics = [{"start": import_start}]
    result = get_import_status_for_statistic(statistic_id, statistics, db_start)

    assert result["status"] == "existing data"
    assert result["newest_import_start"] == "2025-01-01T10:00:00+00:00"
    assert result["newest_db_start"] == "2025-01-01T12:00:00+00:00"


def test_existing_data_when_import_equals_db(statistic_id: str) -> None:
    """Test existing data status when the import's newest timestamp equals the db."""
    import_start = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.UTC)
    statistics = [{"start": import_start}, {"start": import_start - dt.timedelta(hours=1)}]
    result = get_import_status_for_statistic(statistic_id, statistics, import_start)

    assert result["status"] == "existing data"
    assert result["newest_import_start"] == "2025-01-01T12:00:00+00:00"


def test_newest_import_converted_to_utc(statistic_id: str) -> None:
    """Test that import timestamps are converted to UTC before comparison."""
    local_start = dt.datetime(2025, 1, 1, 13, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    db_start = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.UTC)
    statistics = [{"start": local_start}]
    result = get_import_status_for_statistic(statistic_id, statistics, db_start)

    assert result["status"] == "new data"
    assert result["newest_import_start"] == "2025-01-01T12:00:00+00:00"
