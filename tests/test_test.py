"""Test component setup."""
from homeassistant.setup import async_setup_component
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.import_statistics.const import DOMAIN
import custom_components.import_statistics as impstat

import pandas as pd
import os

TESTFILEPATHS = "tests/testfiles/"

async def xxtest_async_setup(hass):
    """Test the component gets setup."""
#    assert await async_setup_component(hass, "recorder", {}) is True
    assert await async_setup_component(hass, DOMAIN, {}) is True

async def test_xx():
    #tmp = os.getcwd()
    df = pd.read_csv(f"{TESTFILEPATHS}/correctcolumns.csv", sep="\t", engine="python")
    assert impstat._check_columns(df) is True # pylint: disable=protected-access

    df = pd.read_csv(f"{TESTFILEPATHS}/wrongcolumns.csv", sep="\t", engine="python")
    with pytest.raises(HomeAssistantError) as excinfo:
        impstat._check_columns(df)  # pylint: disable=protected-access
    assert str(excinfo.value) == "The file must contain the columns 'statistic_id', 'start' and 'unit'"
