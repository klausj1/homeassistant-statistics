"""Unit tests for export_inventory helper functions."""

import datetime as dt
from zoneinfo import ZoneInfo

from custom_components.import_statistics.export_inventory_helper import (
    Category,
    StatType,
    classify_category,
    classify_type,
    compute_days_span,
    format_datetime,
)


class TestClassifyCategory:
    """Tests for classify_category function."""

    def test_external_by_source(self) -> None:
        """Test that non-recorder source is classified as External."""
        result = classify_category("energy:my_stat", "energy", set(), {})
        assert result == Category.EXTERNAL

    def test_external_by_colon_separator(self) -> None:
        """Test that statistic_id with colon is classified as External."""
        result = classify_category("sensor:external_stat", "recorder", set(), {})
        assert result == Category.EXTERNAL

    def test_active_when_in_entity_registry(self) -> None:
        """Test that entity present in entity registry is Active."""
        entity_registry_ids = {"sensor.temperature", "sensor.humidity"}
        result = classify_category("sensor.temperature", "recorder", entity_registry_ids, {})
        assert result == Category.ACTIVE

    def test_orphan_not_applied_to_external(self) -> None:
        """Test that external entities are never classified as Orphan even if in orphaned set."""
        entity_registry_ids = {"energy:my_stat"}
        deleted_entity_orphan_timestamps = {"energy:my_stat": 123.0}
        result = classify_category("energy:my_stat", "energy", entity_registry_ids, deleted_entity_orphan_timestamps)
        assert result == Category.EXTERNAL

    def test_deleted_when_not_in_registry_or_deleted_registry(self) -> None:
        """Test that recorder stat not in entity registry nor deleted entity registry is Deleted."""
        entity_registry_ids = {"sensor.humidity"}
        result = classify_category("sensor.temperature", "recorder", entity_registry_ids, {})
        assert result == Category.DELETED

    def test_deleted_with_empty_registry(self) -> None:
        """Test that recorder stat with empty entity registry is Deleted."""
        result = classify_category("sensor.temperature", "recorder", set(), {})
        assert result == Category.DELETED

    def test_orphan_when_deleted_entry_has_orphaned_timestamp(self) -> None:
        """Test that a deleted registry entry with orphaned_timestamp is Orphan."""
        deleted_entity_orphan_timestamps = {"sensor.temperature": 123.0}
        result = classify_category("sensor.temperature", "recorder", set(), deleted_entity_orphan_timestamps)
        assert result == Category.ORPHAN

    def test_orphan_when_deleted_entry_has_no_orphaned_timestamp(self) -> None:
        """Test that a deleted registry entry without orphaned_timestamp is Orphan."""
        deleted_entity_orphan_timestamps = {"sensor.temperature": None}
        result = classify_category("sensor.temperature", "recorder", set(), deleted_entity_orphan_timestamps)
        assert result == Category.ORPHAN


class TestClassifyType:
    """Tests for classify_type function."""

    def test_counter_when_has_sum_true(self) -> None:
        """Test that has_sum=True is classified as Counter."""
        result = classify_type(has_sum=True)
        assert result == StatType.COUNTER

    def test_measurement_when_has_sum_false(self) -> None:
        """Test that has_sum=False is classified as Measurement."""
        result = classify_type(has_sum=False)
        assert result == StatType.MEASUREMENT


class TestComputeDaysSpan:
    """Tests for compute_days_span function."""

    def test_exact_one_day(self) -> None:
        """Test span of exactly one day."""
        first = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.UTC)
        last = dt.datetime(2024, 1, 2, 0, 0, tzinfo=dt.UTC)
        result = compute_days_span(first, last)
        assert result == 1.0

    def test_partial_day(self) -> None:
        """Test span of partial day (12 hours = 0.5 days)."""
        first = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.UTC)
        last = dt.datetime(2024, 1, 1, 12, 0, tzinfo=dt.UTC)
        result = compute_days_span(first, last)
        assert result == 0.5

    def test_multiple_days(self) -> None:
        """Test span of multiple days."""
        first = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.UTC)
        last = dt.datetime(2024, 1, 11, 12, 0, tzinfo=dt.UTC)
        result = compute_days_span(first, last)
        assert result == 10.5

    def test_zero_span(self) -> None:
        """Test span when first equals last."""
        first = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.UTC)
        result = compute_days_span(first, first)
        assert result == 0.0

    def test_none_first(self) -> None:
        """Test that None first returns 0.0."""
        last = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.UTC)
        result = compute_days_span(None, last)
        assert result == 0.0

    def test_none_last(self) -> None:
        """Test that None last returns 0.0."""
        first = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.UTC)
        result = compute_days_span(first, None)
        assert result == 0.0

    def test_both_none(self) -> None:
        """Test that both None returns 0.0."""
        result = compute_days_span(None, None)
        assert result == 0.0


class TestFormatDatetime:
    """Tests for format_datetime function."""

    def test_utc_timezone(self) -> None:
        """Test formatting with UTC timezone."""
        timestamp = dt.datetime(2024, 1, 15, 14, 30, tzinfo=dt.UTC)
        tz = ZoneInfo("UTC")
        result = format_datetime(timestamp, tz)
        assert result == "2024-01-15 14:30"

    def test_different_timezone(self) -> None:
        """Test formatting with different timezone."""
        timestamp = dt.datetime(2024, 1, 15, 14, 30, tzinfo=dt.UTC)
        tz = ZoneInfo("Europe/Paris")
        result = format_datetime(timestamp, tz)
        # Paris is UTC+1 in winter
        assert result == "2024-01-15 15:30"

    def test_custom_format(self) -> None:
        """Test formatting with custom format string."""
        timestamp = dt.datetime(2024, 1, 15, 14, 30, tzinfo=dt.UTC)
        tz = ZoneInfo("UTC")
        result = format_datetime(timestamp, tz, "%d.%m.%Y %H:%M")
        assert result == "15.01.2024 14:30"

    def test_none_timestamp(self) -> None:
        """Test that None timestamp returns empty string."""
        tz = ZoneInfo("UTC")
        result = format_datetime(None, tz)
        assert result == ""
