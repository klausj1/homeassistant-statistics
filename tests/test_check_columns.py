"""Test component setup."""
# from homeassistant.components.recorder.statistics import (
# #    async_add_external_statistics,
#     async_import_statistics,
# #    valid_statistic_id,
# )
# from homeassistant.components import recorder
# from homeassistant.setup import async_setup_component
from homeassistant.exceptions import HomeAssistantError
import pytest

import pandas as pd
import custom_components.import_statistics as impstat

from custom_components.import_statistics.const import TESTFILEPATHS

#async def test_async_setup(hass): # does not work, commented out
#    """Test the component gets setup."""
#    assert await async_setup_component(hass, DOMAIN, {}) is True

async def test_check_columns():
    """Checks if the check_columns method is working correctly"""
    #tmp = os.getcwd()
    df = pd.read_csv(f"{TESTFILEPATHS}/correctcolumns.csv", sep="\t", engine="python")
    assert impstat._are_columns_valid(df) is True # pylint: disable=protected-access

    df = pd.read_csv(f"{TESTFILEPATHS}/wrongcolumns.csv", sep="\t", engine="python")
    with pytest.raises(HomeAssistantError) as excinfo:
        impstat._are_columns_valid(df)  # pylint: disable=protected-access
    assert str(excinfo.value) == "The file must contain the columns 'statistic_id', 'start' and 'unit'"
