from homeassistant.core import HomeAssistant
from custom_components.import_statistics.const import ATTR_FILENAME, ATTR_DECIMAL, ATTR_TIMEZONE_IDENTIFIER, ATTR_DELIMITER
from custom_components.import_statistics import _handle_arguments

# def test_handle_arguments():
#      hass = HomeAssistant()
#     call = {
#         "data": {
#             ATTR_FILENAME: "test.csv",
#             ATTR_DECIMAL: True,
#             ATTR_TIMEZONE_IDENTIFIER: "Europe/London",
#             ATTR_DELIMITER: ","
#         }
#     }

#     decimal, timezone_identifier, delimiter, file_path = _handle_arguments(hass, call)

#     assert decimal == ","
#     assert timezone_identifier == "Europe/London"
#     assert delimiter == ","
#     assert file_path == "/config/test.csv"