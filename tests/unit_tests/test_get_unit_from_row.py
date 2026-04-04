"""Test get_unit_from_row function."""

import numpy as np
import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import get_unit_from_row


class TestGetUnitFromRow:
    """Test get_unit_from_row function."""

    def test_get_unit_from_row_with_valid_unit(self) -> None:
        """Test extraction of valid unit."""
        assert get_unit_from_row("kWh", "sensor.test") == "kWh"
        assert get_unit_from_row("°C", "sensor.temp") == "°C"
        assert get_unit_from_row("m³", "sensor.volume") == "m³"

    def test_get_unit_from_row_with_empty_unit(self) -> None:
        """Test that empty unit returns None."""
        assert get_unit_from_row("", "sensor.test") is None
        assert get_unit_from_row(None, "sensor.test") is None

    def test_get_unit_from_row_with_pandas_nan(self) -> None:
        """Test that pandas NaN returns None."""
        assert get_unit_from_row(np.nan, "sensor.test") is None
        assert get_unit_from_row(pd.NA, "sensor.test") is None

    def test_get_unit_from_row_rejects_nan_string(self) -> None:
        """Test that string 'nan' is rejected."""
        with pytest.raises(HomeAssistantError, match="Invalid unit value"):
            get_unit_from_row("nan", "sensor.test")
        with pytest.raises(HomeAssistantError, match="Invalid unit value"):
            get_unit_from_row("NaN", "sensor.test")

    def test_get_unit_from_row_rejects_none_string(self) -> None:
        """Test that string 'None' is rejected."""
        with pytest.raises(HomeAssistantError, match="Invalid unit value"):
            get_unit_from_row("None", "sensor.test")
        with pytest.raises(HomeAssistantError, match="Invalid unit value"):
            get_unit_from_row("NONE", "sensor.test")

    def test_get_unit_from_row_strips_whitespace(self) -> None:
        """Test that whitespace is stripped from units."""
        assert get_unit_from_row("  kWh  ", "sensor.test") == "kWh"
        assert get_unit_from_row("\t°C\n", "sensor.test") == "°C"

    def test_get_unit_from_row_with_whitespace_only(self) -> None:
        """Test that whitespace-only string becomes None."""
        assert get_unit_from_row("   ", "sensor.test") is None
        assert get_unit_from_row("\t", "sensor.test") is None
        assert get_unit_from_row("\n", "sensor.test") is None
        assert get_unit_from_row("  \t\n  ", "sensor.test") is None

    def test_get_unit_from_row_rejects_null_string(self) -> None:
        """Test that string 'null' is rejected."""
        with pytest.raises(HomeAssistantError, match="Invalid unit value"):
            get_unit_from_row("null", "sensor.test")
        with pytest.raises(HomeAssistantError, match="Invalid unit value"):
            get_unit_from_row("NULL", "sensor.test")
