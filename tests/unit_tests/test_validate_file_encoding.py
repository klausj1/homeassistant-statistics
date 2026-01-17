"""Test validate_file_encoding function."""

import tempfile
from pathlib import Path

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import helpers


def test_validate_file_encoding_valid_utf8() -> None:
    """Test that valid UTF-8 file passes validation."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".csv") as f:
        f.write("statistic_id,start,unit,sum\n")
        f.write("sensor.temperature,01.01.2024 00:00,°C,25.5\n")
        f.write("sensor.volume,01.01.2024 00:00,m³,100.0\n")
        temp_path = f.name

    try:
        result = helpers.validate_file_encoding(temp_path)
        assert result is True
    finally:
        Path(temp_path).unlink()


def test_validate_file_encoding_with_replacement_character() -> None:
    """Test that file with replacement character fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".csv") as f:
        f.write("statistic_id,start,unit,sum\n")
        f.write("sensor.temperature,01.01.2024 00:00,\ufffdC,25.5\n")  # Unicode replacement character
        temp_path = f.name

    try:
        with pytest.raises(HomeAssistantError, match="contains invalid characters"):
            helpers.validate_file_encoding(temp_path)
    finally:
        Path(temp_path).unlink()


def test_validate_file_encoding_with_mojibake_degree() -> None:
    """Test that file with mojibake pattern for degree symbol fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".csv") as f:
        f.write("statistic_id,start,unit,sum\n")
        f.write("sensor.temperature,01.01.2024 00:00,Â°C,25.5\n")  # Mojibake for °
        temp_path = f.name

    try:
        with pytest.raises(HomeAssistantError, match=r"contains invalid characters.*Â°"):
            helpers.validate_file_encoding(temp_path)
    finally:
        Path(temp_path).unlink()


def test_validate_file_encoding_with_mojibake_superscript() -> None:
    """Test that file with mojibake pattern for superscript fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".csv") as f:
        f.write("statistic_id,start,unit,sum\n")
        f.write("sensor.volume,01.01.2024 00:00,mÂ³,100.0\n")  # Mojibake for ³
        temp_path = f.name

    try:
        with pytest.raises(HomeAssistantError, match=r"contains invalid characters.*Â³"):
            helpers.validate_file_encoding(temp_path)
    finally:
        Path(temp_path).unlink()


def test_validate_file_encoding_invalid_utf8() -> None:
    """Test that file with invalid UTF-8 bytes fails validation."""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".csv") as f:
        # Write invalid UTF-8 sequence
        f.write(b"statistic_id,start,unit,sum\n")
        f.write(b"sensor.temperature,01.01.2024 00:00,\xc3\x28C,25.5\n")  # Invalid UTF-8
        temp_path = f.name

    try:
        with pytest.raises(HomeAssistantError, match="has encoding errors"):
            helpers.validate_file_encoding(temp_path)
    finally:
        Path(temp_path).unlink()


def test_validate_file_encoding_nonexistent_file() -> None:
    """Test that nonexistent file raises appropriate error."""
    with pytest.raises(HomeAssistantError, match="Cannot read file"):
        helpers.validate_file_encoding("/nonexistent/path/file.csv")


def test_validate_file_encoding_with_various_special_chars() -> None:
    """Test that file with various valid special characters passes."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".csv") as f:
        f.write("statistic_id,start,unit,sum\n")
        f.write("sensor.temp,01.01.2024 00:00,°C,25.5\n")
        f.write("sensor.volume,01.01.2024 00:00,m³,100.0\n")
        f.write("sensor.area,01.01.2024 00:00,m²,50.0\n")
        f.write("sensor.euro,01.01.2024 00:00,€,1000.0\n")
        temp_path = f.name

    try:
        result = helpers.validate_file_encoding(temp_path)
        assert result is True
    finally:
        Path(temp_path).unlink()
