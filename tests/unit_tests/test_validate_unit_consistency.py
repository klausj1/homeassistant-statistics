"""Test validate_unit_consistency function."""

import re

import numpy as np
import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import validate_unit_consistency


class TestConsistentUnits:
    """Tests where all units are consistent — should pass without error."""

    def test_all_rows_same_unit_string(self) -> None:
        """Test that all rows with the same unit string pass validation."""
        series = pd.Series(["°C", "°C", "°C"])
        validate_unit_consistency(series, "sensor.temperature")

    def test_all_rows_none(self) -> None:
        """Test that all rows with None pass validation."""
        series = pd.Series([None, None, None])
        validate_unit_consistency(series, "sensor.test")

    def test_all_rows_nan(self) -> None:
        """Test that all rows with NaN pass validation."""
        series = pd.Series([np.nan, np.nan, np.nan])
        validate_unit_consistency(series, "sensor.test")

    def test_all_rows_empty_string(self) -> None:
        """Test that all rows with empty string pass validation."""
        series = pd.Series(["", "", ""])
        validate_unit_consistency(series, "sensor.test")

    def test_single_row(self) -> None:
        """Test that a single row is trivially consistent."""
        series = pd.Series(["kWh"])
        validate_unit_consistency(series, "sensor.energy")

    def test_single_row_none(self) -> None:
        """Test that a single None row is trivially consistent."""
        series = pd.Series([None])
        validate_unit_consistency(series, "sensor.test")

    def test_mix_of_nan_none_empty_whitespace(self) -> None:
        """Test that NaN, None, empty string, and whitespace all normalize to None."""
        series = pd.Series([np.nan, None, "", "  ", "\t"])
        validate_unit_consistency(series, "sensor.test")

    def test_whitespace_differences_normalize_to_same_unit(self) -> None:
        """Test that units with whitespace differences normalize to the same value."""
        series = pd.Series(["kWh", "  kWh  ", "kWh"])
        validate_unit_consistency(series, "sensor.energy")

    def test_whitespace_tabs_normalize_to_same_unit(self) -> None:
        """Test that units with tab/newline whitespace normalize to the same value."""
        series = pd.Series(["°C", "\t°C\n", "  °C"])
        validate_unit_consistency(series, "sensor.temperature")


class TestInconsistentUnits:
    """Tests where units are inconsistent — should raise HomeAssistantError."""

    def test_two_different_unit_strings(self) -> None:
        """Test that two different unit strings raise an error."""
        series = pd.Series(["°C", "°F", "°C"])
        with pytest.raises(HomeAssistantError, match=re.escape("Inconsistent units")):
            validate_unit_consistency(series, "sensor.temperature")

    def test_error_message_contains_statistic_id(self) -> None:
        """Test that the error message contains the statistic_id."""
        series = pd.Series(["kWh", "Wh"])
        with pytest.raises(HomeAssistantError, match=re.escape("sensor.energy")):
            validate_unit_consistency(series, "sensor.energy")

    def test_error_message_contains_inconsistent_units(self) -> None:
        """Test that the error message mentions 'Inconsistent units'."""
        series = pd.Series(["kWh", "Wh"])
        with pytest.raises(HomeAssistantError, match="Inconsistent units"):
            validate_unit_consistency(series, "sensor.energy")

    def test_valid_unit_and_nan(self) -> None:
        """Test that a valid unit mixed with NaN raises an error."""
        series = pd.Series(["kWh", np.nan, "kWh"])
        with pytest.raises(HomeAssistantError, match="Inconsistent units"):
            validate_unit_consistency(series, "sensor.energy")

    def test_valid_unit_and_none(self) -> None:
        """Test that a valid unit mixed with None raises an error."""
        series = pd.Series(["kWh", None, "kWh"])
        with pytest.raises(HomeAssistantError, match="Inconsistent units"):
            validate_unit_consistency(series, "sensor.energy")

    def test_valid_unit_and_empty_string(self) -> None:
        """Test that a valid unit mixed with empty string raises an error."""
        series = pd.Series(["kWh", "", "kWh"])
        with pytest.raises(HomeAssistantError, match="Inconsistent units"):
            validate_unit_consistency(series, "sensor.energy")

    def test_three_different_units(self) -> None:
        """Test that three different units raise an error."""
        series = pd.Series(["°C", "°F", "K"])
        with pytest.raises(HomeAssistantError, match="Inconsistent units"):
            validate_unit_consistency(series, "sensor.temperature")

    def test_error_message_shows_empty_for_none(self) -> None:
        """Test that the error message displays '(empty)' for None units."""
        series = pd.Series(["kWh", np.nan])
        with pytest.raises(HomeAssistantError, match=re.escape("(empty)")):
            validate_unit_consistency(series, "sensor.energy")


class TestEdgeCases:
    """Edge cases for validate_unit_consistency."""

    def test_invalid_literal_nan_string_raises_before_consistency_check(self) -> None:
        """Test that 'nan' string raises invalid literal error, not inconsistency error."""
        series = pd.Series(["kWh", "nan"])
        with pytest.raises(HomeAssistantError, match="Invalid unit value"):
            validate_unit_consistency(series, "sensor.energy")

    def test_invalid_literal_none_string_raises_before_consistency_check(self) -> None:
        """Test that 'None' string raises invalid literal error, not inconsistency error."""
        series = pd.Series(["kWh", "None"])
        with pytest.raises(HomeAssistantError, match="Invalid unit value"):
            validate_unit_consistency(series, "sensor.energy")

    def test_invalid_literal_null_string_raises_before_consistency_check(self) -> None:
        """Test that 'null' string raises invalid literal error, not inconsistency error."""
        series = pd.Series(["kWh", "null"])
        with pytest.raises(HomeAssistantError, match="Invalid unit value"):
            validate_unit_consistency(series, "sensor.energy")

    def test_invalid_literal_alone_raises_error(self) -> None:
        """Test that a series with only 'nan' raises invalid literal error."""
        series = pd.Series(["nan", "nan"])
        with pytest.raises(HomeAssistantError, match="Invalid unit value"):
            validate_unit_consistency(series, "sensor.test")

    def test_external_statistic_id_format(self) -> None:
        """Test that external statistic IDs (colon separator) work in error messages."""
        series = pd.Series(["kWh", "Wh"])
        with pytest.raises(HomeAssistantError, match=re.escape("myintegration:energy_total")):
            validate_unit_consistency(series, "myintegration:energy_total")
