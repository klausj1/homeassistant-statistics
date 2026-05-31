"""Tests for the optional 'name' service parameter support in import."""

from zoneinfo import ZoneInfo

import pandas as pd
from homeassistant.components.recorder.models import StatisticMeanType

from custom_components.import_statistics.import_service_helper import handle_dataframe_no_delta


TZ_UTC = ZoneInfo("UTC")


def _make_df_sum(rows: list, tz: ZoneInfo = TZ_UTC) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["statistic_id", "start", "unit", "sum"])
    df["start"] = df["start"].apply(lambda v: pd.to_datetime(v, format="%d.%m.%Y %H:%M").tz_localize(tz))
    return df


# ---------------------------------------------------------------------------
# handle_dataframe_no_delta — name parameter propagation
# ---------------------------------------------------------------------------


def test_name_parameter_set_in_metadata() -> None:
    """name parameter is stored in metadata for all statistic_ids."""
    df = _make_df_sum([["my:stat", "01.01.2022 00:00", "kWh", 100.0]])

    stats = handle_dataframe_no_delta(df, name="Stadtwerke Strom")

    assert stats["my:stat"][0]["name"] == "Stadtwerke Strom"


def test_no_name_parameter_gives_none() -> None:
    """When name parameter is omitted, metadata.name is None."""
    df = _make_df_sum([["my:stat", "01.01.2022 00:00", "kWh", 100.0]])

    stats = handle_dataframe_no_delta(df)

    assert stats["my:stat"][0]["name"] is None


def test_name_none_gives_none() -> None:
    """When name=None is passed explicitly, metadata.name is None."""
    df = _make_df_sum([["my:stat", "01.01.2022 00:00", "kWh", 100.0]])

    stats = handle_dataframe_no_delta(df, name=None)

    assert stats["my:stat"][0]["name"] is None


def test_name_applied_to_all_statistic_ids() -> None:
    """name parameter applies to all statistic_ids in the file."""
    df = _make_df_sum([
        ["my:stat1", "01.01.2022 00:00", "kWh", 10.0],
        ["my:stat2", "01.01.2022 00:00", "kWh", 20.0],
    ])

    stats = handle_dataframe_no_delta(df, name="Shared Name")

    assert stats["my:stat1"][0]["name"] == "Shared Name"
    assert stats["my:stat2"][0]["name"] == "Shared Name"


def test_name_with_mean_type() -> None:
    """name parameter works with mean/min/max data type."""
    df = pd.DataFrame(
        [["my:sensor", "01.01.2022 00:00", "°C", 18.0, 22.0, 20.0]],
        columns=["statistic_id", "start", "unit", "min", "max", "mean"],
    )
    df["start"] = df["start"].apply(lambda v: pd.to_datetime(v, format="%d.%m.%Y %H:%M").tz_localize(TZ_UTC))

    stats = handle_dataframe_no_delta(df, name="Living Room Temp")

    metadata = stats["my:sensor"][0]
    assert metadata["name"] == "Living Room Temp"
    assert metadata["mean_type"] == StatisticMeanType.ARITHMETIC
