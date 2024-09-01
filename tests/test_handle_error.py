"""Unit tests for _handle_error function."""

import re

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import handle_error


def test_handle_error() -> None:
    """
    Test the _handle_error function.

    This function calls the _handle_error function with a sample error string and checks that it raises a HomeAssistantError with the same error string.
    """
    # Define the sample error string
    error_string = "Sample error message"

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"{error_string}"),
    ):
        handle_error(error_string)
