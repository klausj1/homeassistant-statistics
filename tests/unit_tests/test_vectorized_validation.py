"""Unit tests for vectorized validation helper functions."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import (
    validate_floats_vectorized,
    validate_min_max_mean_vectorized,
    validate_timestamps_vectorized,
)


class TestValidateTimestampsVectorized:
    """Test validate_timestamps_vectorized function."""

    def test_valid_timestamps_all_full_hours(self) -> None:
        """Test that valid full-hour timestamps pass validation."""
        df = pd.DataFrame(
            {
                "start": [
                    datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    datetime(2022, 1, 1, 1, 0, tzinfo=ZoneInfo("UTC")),
                    datetime(2022, 1, 1, 2, 0, tzinfo=ZoneInfo("UTC")),
                ]
            }
        )

        # Should not raise
        validate_timestamps_vectorized(df)

    def test_invalid_timestamp_with_minutes(self) -> None:
        """Test that timestamps with non-zero minutes are rejected."""
        df = pd.DataFrame(
            {
                "start": [
                    datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    datetime(2022, 1, 1, 1, 30, tzinfo=ZoneInfo("UTC")),  # Invalid at row 3 (0-based index 1 + 2)
                    datetime(2022, 1, 1, 2, 0, tzinfo=ZoneInfo("UTC")),
                ]
            }
        )

        with pytest.raises(HomeAssistantError, match=r"Invalid timestamp at row 3.*01:30.*must be a full hour"):
            validate_timestamps_vectorized(df)

    def test_invalid_timestamp_with_seconds(self) -> None:
        """Test that timestamps with non-zero seconds are rejected."""
        df = pd.DataFrame(
            {
                "start": [
                    datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    datetime(2022, 1, 1, 1, 0, 30, tzinfo=ZoneInfo("UTC")),  # Invalid at row 3
                ]
            }
        )

        with pytest.raises(HomeAssistantError, match=r"Invalid timestamp at row 3.*must be a full hour"):
            validate_timestamps_vectorized(df)

    def test_invalid_timestamp_with_both_minutes_and_seconds(self) -> None:
        """Test that timestamps with both minutes and seconds are rejected."""
        df = pd.DataFrame(
            {
                "start": [
                    datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    datetime(2022, 1, 1, 1, 15, 45, tzinfo=ZoneInfo("UTC")),  # Invalid at row 3
                ]
            }
        )

        with pytest.raises(HomeAssistantError, match=r"Invalid timestamp at row 3.*must be a full hour"):
            validate_timestamps_vectorized(df)

    def test_reports_first_invalid_timestamp(self) -> None:
        """Test that the first invalid timestamp is reported in error."""
        df = pd.DataFrame(
            {
                "start": [
                    datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    datetime(2022, 1, 1, 1, 15, tzinfo=ZoneInfo("UTC")),  # First invalid at row 3
                    datetime(2022, 1, 1, 2, 30, tzinfo=ZoneInfo("UTC")),  # Second invalid at row 4
                ]
            }
        )

        # Should report the first invalid (row 3 with 01:15, not row 4 with 02:30)
        with pytest.raises(HomeAssistantError, match=r"row 3.*01:15"):
            validate_timestamps_vectorized(df)

    def test_works_with_different_timezones(self) -> None:
        """Test that validation works with different timezones."""
        df = pd.DataFrame(
            {
                "start": [
                    datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("Europe/Vienna")),
                    datetime(2022, 1, 1, 1, 0, tzinfo=ZoneInfo("Europe/Vienna")),
                ]
            }
        )

        # Should not raise
        validate_timestamps_vectorized(df)


class TestValidateFloatsVectorized:
    """Test validate_floats_vectorized function."""

    def test_valid_floats_all_columns(self) -> None:
        """Test that valid float values pass validation."""
        df = pd.DataFrame(
            {
                "sum": [100.0, 105.5, 110.0],
                "state": [100.0, 105.5, 110.0],
                "delta": [5.5, 4.5, 0.0],
            }
        )

        # Should not raise
        validate_floats_vectorized(df, ["sum", "state", "delta"])

    def test_valid_floats_single_column(self) -> None:
        """Test validation with single column."""
        df = pd.DataFrame({"sum": [100.0, 105.5, 110.0]})

        # Should not raise
        validate_floats_vectorized(df, ["sum"])

    def test_invalid_float_nan_value(self) -> None:
        """Test that NaN values are rejected with column, row, and value info."""
        df = pd.DataFrame(
            {
                "sum": [100.0, float("nan"), 110.0],
            }
        )

        with pytest.raises(HomeAssistantError, match=r"Invalid float value in column 'sum' at row 3.*NaN/empty"):
            validate_floats_vectorized(df, ["sum"])

    def test_invalid_float_none_value(self) -> None:
        """Test that None values are rejected with column and row info."""
        df = pd.DataFrame(
            {
                "sum": [100.0, None, 110.0],
            }
        )

        with pytest.raises(HomeAssistantError, match=r"Invalid float value in column 'sum' at row 3"):
            validate_floats_vectorized(df, ["sum"])

    def test_invalid_float_string_value(self) -> None:
        """Test that string values are rejected with column and row info."""
        df = pd.DataFrame(
            {
                "sum": [100.0, "abc", 110.0],
            }
        )

        with pytest.raises(HomeAssistantError, match=r"Invalid float value in column 'sum' at row 3"):
            validate_floats_vectorized(df, ["sum"])

    def test_reports_first_invalid_value(self) -> None:
        """Test that the first invalid value is reported."""
        df = pd.DataFrame(
            {
                "sum": [100.0, float("nan"), 110.0, float("nan")],
            }
        )

        # Should report row 3 (first NaN at index 1, +2 = row 3)
        with pytest.raises(HomeAssistantError, match=r"row 3"):
            validate_floats_vectorized(df, ["sum"])

    def test_validates_multiple_columns(self) -> None:
        """Test that all specified columns are validated with column and row info."""
        df = pd.DataFrame(
            {
                "min": [1.0, 2.0, 3.0],
                "max": [10.0, float("nan"), 30.0],  # Invalid in max at row 3
                "mean": [5.0, 15.0, 20.0],
            }
        )

        with pytest.raises(HomeAssistantError, match=r"Invalid float value in column 'max' at row 3"):
            validate_floats_vectorized(df, ["min", "max", "mean"])

    def test_skips_missing_columns(self) -> None:
        """Test that missing columns are skipped without error."""
        df = pd.DataFrame(
            {
                "sum": [100.0, 105.0, 110.0],
            }
        )

        # Should not raise even though 'state' column doesn't exist
        validate_floats_vectorized(df, ["sum", "state"])

    def test_negative_values_are_valid(self) -> None:
        """Test that negative float values are accepted."""
        df = pd.DataFrame(
            {
                "delta": [-5.5, -10.0, 3.5],
            }
        )

        # Should not raise
        validate_floats_vectorized(df, ["delta"])

    def test_zero_values_are_valid(self) -> None:
        """Test that zero values are accepted."""
        df = pd.DataFrame(
            {
                "sum": [0.0, 0.0, 0.0],
            }
        )

        # Should not raise
        validate_floats_vectorized(df, ["sum"])


class TestValidateMinMaxMeanVectorized:
    """Test validate_min_max_mean_vectorized function."""

    def test_valid_min_max_mean_all_rows(self) -> None:
        """Test that valid min <= mean <= max passes validation."""
        df = pd.DataFrame(
            {
                "min": [1.0, 2.0, 3.0],
                "max": [10.0, 20.0, 30.0],
                "mean": [5.0, 15.0, 20.0],
            }
        )

        # Should not raise
        validate_min_max_mean_vectorized(df)

    def test_valid_when_min_equals_mean(self) -> None:
        """Test that min == mean is valid."""
        df = pd.DataFrame(
            {
                "min": [5.0, 10.0],
                "max": [10.0, 20.0],
                "mean": [5.0, 15.0],  # First row: min == mean
            }
        )

        # Should not raise
        validate_min_max_mean_vectorized(df)

    def test_valid_when_mean_equals_max(self) -> None:
        """Test that mean == max is valid."""
        df = pd.DataFrame(
            {
                "min": [5.0, 10.0],
                "max": [10.0, 20.0],
                "mean": [10.0, 20.0],  # mean == max
            }
        )

        # Should not raise
        validate_min_max_mean_vectorized(df)

    def test_valid_when_all_equal(self) -> None:
        """Test that min == mean == max is valid."""
        df = pd.DataFrame(
            {
                "min": [10.0, 20.0],
                "max": [10.0, 20.0],
                "mean": [10.0, 20.0],
            }
        )

        # Should not raise
        validate_min_max_mean_vectorized(df)

    def test_invalid_when_mean_less_than_min(self) -> None:
        """Test that mean < min is rejected."""
        df = pd.DataFrame(
            {
                "min": [10.0, 20.0],
                "max": [20.0, 30.0],
                "mean": [5.0, 25.0],  # First row (row 2): mean < min
            }
        )

        with pytest.raises(HomeAssistantError, match=r"Invalid values at row 2.*min: 10.0.*max: 20.0.*mean: 5.0"):
            validate_min_max_mean_vectorized(df)

    def test_invalid_when_mean_greater_than_max(self) -> None:
        """Test that mean > max is rejected."""
        df = pd.DataFrame(
            {
                "min": [10.0, 20.0],
                "max": [20.0, 30.0],
                "mean": [15.0, 35.0],  # Second row (row 3): mean > max
            }
        )

        with pytest.raises(HomeAssistantError, match=r"Invalid values at row 3.*min: 20.0.*max: 30.0.*mean: 35.0"):
            validate_min_max_mean_vectorized(df)

    def test_invalid_when_min_greater_than_max(self) -> None:
        """Test that min > max is rejected."""
        df = pd.DataFrame(
            {
                "min": [25.0, 20.0],
                "max": [15.0, 30.0],  # First row (row 2): min > max
                "mean": [20.0, 25.0],
            }
        )

        with pytest.raises(HomeAssistantError, match=r"Invalid values at row 2.*min: 25.0.*max: 15.0.*mean: 20.0"):
            validate_min_max_mean_vectorized(df)

    def test_reports_first_invalid_row(self) -> None:
        """Test that the first invalid row is reported."""
        df = pd.DataFrame(
            {
                "min": [10.0, 25.0, 30.0],  # Second (row 3) and third (row 4) rows invalid
                "max": [20.0, 15.0, 10.0],
                "mean": [15.0, 20.0, 20.0],
            }
        )

        # Should report second row (row 3), not third (row 4)
        with pytest.raises(HomeAssistantError, match=r"row 3.*min: 25.0.*max: 15.0"):
            validate_min_max_mean_vectorized(df)

    def test_works_with_negative_values(self) -> None:
        """Test that negative values work correctly."""
        df = pd.DataFrame(
            {
                "min": [-10.0, -5.0],
                "max": [0.0, 5.0],
                "mean": [-5.0, 0.0],
            }
        )

        # Should not raise
        validate_min_max_mean_vectorized(df)

    def test_works_with_large_ranges(self) -> None:
        """Test that large value ranges work correctly."""
        df = pd.DataFrame(
            {
                "min": [0.0, -1000000.0],
                "max": [1000000.0, 1000000.0],
                "mean": [500000.0, 0.0],
            }
        )

        # Should not raise
        validate_min_max_mean_vectorized(df)
