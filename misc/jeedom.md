# Jeedom

If you want to import long term statistics from a Jeedom instance, this guidelines purpose is to prepare your data to a format that the plugin is able to import them into Home Assistant.

# 1 - Export from jeedom

Use Jeedom Interface to export CSV files of each statistics you want to import. For this use the following menu: Jeedom->Analysis->History->Configuration->Action->Export it will trigger a download of a css file which includes the statistics contents.

Format looks like (... is not in the file, just to show you different values)

```
2019-11-17 17:00:00;0,000000
2019-11-17 18:00:00;911,797500
2019-11-18 06:00:00;312,750000
2019-11-19 06:00:00;309,500000
2019-11-20 06:00:00;0,000000
....
2022-02-15 06:17:30;617,267500
2022-02-15 06:50:00;307,630000
...
2025-02-16 02:00:02;336,750000000
2025-02-16 03:03:02;388,550000000
2025-02-16 04:06:01;374,750000000
```

You can see that the timestamps are not full hours (which is needed by HA for import) and the format of the data does not fit.

# 2 - Prepare data

Use the python scripts which do the job to build a new CSV which can be imported.

One script [jeedom2homeassistant_puissance.py](jeedom2homeassistant_puissance.py) has been built for power which provides min/max/mean (with same time the same values as the jeedom export provides only means. It build a good date/time and merge data if more than one is present for one hour). yes mathematically speaking this is ugly to perform a mean but this is enough for basic needs.

And a second one [jeedom2homeassistant_counters.py](jeedom2homeassistant_counters.py) which compute a state, sum file for TOTAL_INCREASING for Total consumption in kWh.

This scripts can be adapted for temperature or other statistics if needed.

```bash
python3 script.py <input_file> <output_file> <prefix>
```

with prefix the name of the entity you want to import into.

# 3 - Import with homeassistant-statistics

Use the plugin to import your new generated csv

# 4 - Checks

Go to the HA statistics page and verify the imported data.

# 5 - Alternative

https://github.com/patrickvorgers/Home-Assistant-Import-Energy-Data could be a good alternative to evaluate.
