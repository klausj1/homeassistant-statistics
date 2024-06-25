"""Unit tests for _handle_error function."""

from homeassistant.exceptions import HomeAssistantError
from custom_components.import_statistics.helpers import handle_error

def test_handle_error():
    """Test the _handle_error function.

    This function calls the _handle_error function with a sample error string and checks that it raises a HomeAssistantError with the same error string.
    """
    # Define the sample error string
    error_string = "Sample error message"

    try:
        # Call the function
        handle_error(error_string)
    except HomeAssistantError as e:
        # Check that the raised exception has the same error string
        assert str(e) == error_string
    else:
        # If no exception is raised, fail the test
        assert False, "Expected HomeAssistantError to be raised"
