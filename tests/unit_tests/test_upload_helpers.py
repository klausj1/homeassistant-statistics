"""Unit tests for upload helper functions."""

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import sanitize_filename, validate_upload_file


class TestSanitizeFilename:
    """Test sanitize_filename function."""

    def test_valid_simple_filename(self) -> None:
        """Test sanitization of a simple valid filename."""
        result = sanitize_filename("test.csv")
        assert result == "test.csv"

    def test_valid_filename_with_underscores(self) -> None:
        """Test sanitization of filename with underscores."""
        result = sanitize_filename("test_file_123.tsv")
        assert result == "test_file_123.tsv"

    def test_valid_filename_with_hyphens(self) -> None:
        """Test sanitization of filename with hyphens."""
        result = sanitize_filename("test-file-123.json")
        assert result == "test-file-123.json"

    def test_valid_filename_with_dots(self) -> None:
        """Test sanitization of filename with dots in stem."""
        result = sanitize_filename("test.file.data.csv")
        assert result == "test.file.data.csv"

    def test_removes_forward_slash(self) -> None:
        """Test that forward slashes are removed (Path extracts filename only)."""
        result = sanitize_filename("path/to/file.csv")
        assert result == "file.csv"

    def test_removes_backward_slash(self) -> None:
        """Test that backward slashes are removed by sanitization."""
        result = sanitize_filename("path\\to\\file.csv")
        # On Linux, backslashes are not path separators, so they're removed by sanitization
        assert result == "pathtofile.csv"

    def test_removes_path_traversal(self) -> None:
        """Test that path traversal sequences are removed (Path extracts filename only)."""
        result = sanitize_filename("../../../etc/passwd.csv")
        assert result == "passwd.csv"

    def test_removes_special_characters(self) -> None:
        """Test that special characters are removed."""
        result = sanitize_filename("test@#$%file!.csv")
        assert result == "testfile.csv"

    def test_preserves_extension(self) -> None:
        """Test that file extension is preserved."""
        result = sanitize_filename("test@file.JSON")
        assert result == "testfile.json"

    def test_mixed_special_chars_and_path_traversal(self) -> None:
        """Test complex filename with multiple issues."""
        result = sanitize_filename("../test@file#123.tsv")
        assert result == "testfile123.tsv"

    def test_strips_leading_dots(self) -> None:
        """Test that leading dots are stripped."""
        result = sanitize_filename("...test.csv")
        assert result == "test.csv"

    def test_strips_trailing_dots(self) -> None:
        """Test that trailing dots are stripped."""
        result = sanitize_filename("test....csv")
        assert result == "test.csv"

    def test_strips_spaces(self) -> None:
        """Test that leading/trailing spaces are stripped (internal spaces removed)."""
        result = sanitize_filename("  test file  .csv")
        assert result == "testfile.csv"

    def test_empty_filename_raises_error(self) -> None:
        """Test that empty filename raises error."""
        with pytest.raises(HomeAssistantError, match="Filename cannot be empty"):
            sanitize_filename("")

    def test_whitespace_only_raises_error(self) -> None:
        """Test that whitespace-only filename raises error."""
        with pytest.raises(HomeAssistantError, match="Filename cannot be empty"):
            sanitize_filename("   ")

    def test_only_special_chars_raises_error(self) -> None:
        """Test that filename with only special characters raises error."""
        with pytest.raises(HomeAssistantError, match="contains only invalid characters"):
            sanitize_filename("@#$%^&*.csv")

    def test_only_path_separators_raises_error(self) -> None:
        """Test that filename with only path separators raises error."""
        with pytest.raises(HomeAssistantError, match="contains only invalid characters"):
            sanitize_filename("///\\\\\\.csv")

    def test_unicode_characters(self) -> None:
        """Test handling of unicode characters (kept as-is if alphanumeric in unicode)."""
        result = sanitize_filename("tëst_fîlé.csv")
        # Unicode letters are considered alphanumeric by Python's isalnum()
        assert result == "tëst_fîlé.csv"

    def test_long_filename(self) -> None:
        """Test handling of long filename."""
        long_name = "a" * 200 + ".csv"
        result = sanitize_filename(long_name)
        assert result.endswith(".csv")
        assert len(result) > 0

    def test_no_extension(self) -> None:
        """Test filename without extension."""
        result = sanitize_filename("testfile")
        assert result == "testfile"

    def test_multiple_extensions(self) -> None:
        """Test filename with multiple extensions."""
        result = sanitize_filename("test.tar.gz")
        # Only last extension is preserved
        assert result == "test.tar.gz"


class TestValidateUploadFile:
    """Test validate_upload_file function."""

    def test_valid_csv_file(self) -> None:
        """Test validation of valid CSV file."""
        # Should not raise any exception
        validate_upload_file("test.csv", 1024)

    def test_valid_tsv_file(self) -> None:
        """Test validation of valid TSV file."""
        validate_upload_file("test.tsv", 1024)

    def test_valid_json_file(self) -> None:
        """Test validation of valid JSON file."""
        validate_upload_file("test.json", 1024)

    def test_case_insensitive_extension(self) -> None:
        """Test that extension check is case-insensitive."""
        validate_upload_file("test.CSV", 1024)
        validate_upload_file("test.TsV", 1024)
        validate_upload_file("test.JSON", 1024)

    def test_invalid_extension_txt(self) -> None:
        """Test that .txt extension is rejected."""
        with pytest.raises(HomeAssistantError, match=r"File extension '\.txt' not allowed"):
            validate_upload_file("test.txt", 1024)

    def test_invalid_extension_xlsx(self) -> None:
        """Test that .xlsx extension is rejected."""
        with pytest.raises(HomeAssistantError, match=r"File extension '\.xlsx' not allowed"):
            validate_upload_file("test.xlsx", 1024)

    def test_invalid_extension_pdf(self) -> None:
        """Test that .pdf extension is rejected."""
        with pytest.raises(HomeAssistantError, match=r"File extension '\.pdf' not allowed"):
            validate_upload_file("test.pdf", 1024)

    def test_no_extension(self) -> None:
        """Test that file without extension is rejected."""
        with pytest.raises(HomeAssistantError, match="File extension '' not allowed"):
            validate_upload_file("testfile", 1024)

    def test_file_size_at_limit(self) -> None:
        """Test file at exactly the size limit."""
        max_size = 50 * 1024 * 1024  # 50 MB
        validate_upload_file("test.csv", max_size)

    def test_file_size_just_under_limit(self) -> None:
        """Test file just under the size limit."""
        max_size = 50 * 1024 * 1024  # 50 MB
        validate_upload_file("test.csv", max_size - 1)

    def test_file_size_exceeds_limit(self) -> None:
        """Test that oversized file is rejected."""
        max_size = 50 * 1024 * 1024  # 50 MB
        with pytest.raises(HomeAssistantError, match="exceeds maximum allowed size"):
            validate_upload_file("test.csv", max_size + 1)

    def test_file_size_way_over_limit(self) -> None:
        """Test that very large file is rejected."""
        huge_size = 100 * 1024 * 1024  # 100 MB
        with pytest.raises(HomeAssistantError, match="exceeds maximum allowed size"):
            validate_upload_file("test.csv", huge_size)

    def test_zero_size_file(self) -> None:
        """Test that zero-size file is allowed (validation doesn't check minimum)."""
        validate_upload_file("test.csv", 0)

    def test_small_file(self) -> None:
        """Test validation of small file."""
        validate_upload_file("test.csv", 100)

    def test_medium_file(self) -> None:
        """Test validation of medium-sized file."""
        validate_upload_file("test.csv", 10 * 1024 * 1024)  # 10 MB

    def test_error_message_includes_allowed_extensions(self) -> None:
        """Test that error message lists allowed extensions."""
        with pytest.raises(HomeAssistantError, match=r"Allowed extensions:.*\.csv.*\.tsv.*\.json"):
            validate_upload_file("test.txt", 1024)

    def test_error_message_includes_file_sizes(self) -> None:
        """Test that error message includes actual and max file sizes."""
        huge_size = 100 * 1024 * 1024  # 100 MB
        with pytest.raises(HomeAssistantError, match=r"100\.00 MB exceeds maximum allowed size of 50 MB"):
            validate_upload_file("test.csv", huge_size)

    def test_combined_valid_checks(self) -> None:
        """Test file that passes both extension and size checks."""
        validate_upload_file("my_statistics_data.csv", 25 * 1024 * 1024)  # 25 MB
        validate_upload_file("export_2024.tsv", 1024)
        validate_upload_file("data.json", 5 * 1024 * 1024)  # 5 MB
