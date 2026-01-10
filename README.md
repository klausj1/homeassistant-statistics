# Import statistics integration

This HA integration allows to import / export long term statistics from / to a file like csv or tsv, or JSON.

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

<!-- ![Project Maintenance][maintenance-shield] -->

[![Community Forum][forum-shield]][forum]

**This integration just offers actions (previously known as services)**

## Installation

> This integration requires HA 2025.12.0 or newer

### HACS

The preferred way is to use HACS:

1. Search and download this integration to your HA installation via HACS, or click:

   [![Open HACS Repository][hacs-repo-badge]][hacs-repo]

1. Restart home assistant

1. Add this integration to Home Assistant, or click:

   [![Add Integration][config-flow-badge]][config-flow]

### Manual installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `import_statistics`.
1. Download _all_ the files from the `custom_components/import_statistics/` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Add `import_statistics:` to your configuration .yaml (if it is possible to do this in the UI in some way without directly editing the yaml file, please let me know)
1. Restart Home Assistant

## Usage

This integration offers the action `import_from_file` to import statistics from a file and `import_from_json` to import from an uploaded JSON.

> As this integration uses database-independent methods of the recorder to do the import, it does not depend on the used database - it should work for all databases supported by HA.

### import_from_file

First, create your file. The structure is different for statistics with min/max/mean and counter statistics with state/sum.

Here you can find example files for both.

- [min/max/mean](./assets/min_max_mean.tsv)
- [Counters (state/sum)](./assets/state_sum.tsv)

The examples are hopefully self-explaining, just some additional information:

- You can either import **min/max/mean or counters**, but you cannot mix them in one file
- You can import the same or changed data as often as you like, there will not be duplicate data (as **existing values will be overwritten**). So, you can use this integration to add values or to correct existing values
- You can use different **settings** for the **delimiter** (default is tab (tsv))
- For floats, the **decimal separator** can be **'.' or ','**
- You should be able to find your **timezone** [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones), or check the python documentation (pytz). Keep in mind that the times are local times of the HA server.
- The timestamp (column `start`) **must** be of the **format "%d.%m.%Y %H:%M" (e.g. "17.03.2024 02:00")**
  - Always use 2 digits for all parts except the year, which needs 4 digits - just like the example above
- If you do not import values for every hour, you will get **gaps in the graphs** (depending on the used card and its settings)
- The **minutes of the timestamp must be zero**. This is due to the [long-term statistics](https://data.home-assistant.io/docs/statistics/#:~:text=Home%20Assistant%20has%20support%20for,of%20the%20short%2Dterm%20statistics.), which only store hourly values.
- If you use non-ASCII-characters (like m³) the codepage of your file must be **UTF-8**
- You can import:
    - Either statistics for **existing sensors** (internal statistics). These sensors have a '.' in its name, e.g. sensor.sun_solar_azimuth
        - If you try to import such a sensor which does not exist, you will see this sensor under developer tools / statistics, with an error. You can fix the error there, whereas fix means, remove it from database again
    - Or statistics for **not existing sensors** (external statistics). These sensors have a ':' in its name, e.g. sensor:not_existing_sun_solar_azimuth
- min/max/mean are pretty straight forward, whereas counters are more complex. To understand what `sum`and `state` means, you can e.g. check [this](https://developers.home-assistant.io/blog/2021/08/16/state_class_total/)
    - To be sure that the energy board and your graphs show correct values, import state and sum. You can use the same value for sum and state.
    - You have to align the imported values with the first current value in your database, otherwise there will be a spike, as the difference between e.g. to energy values at 00:00 and 01:00 is the used energy for the hour starting at 00:00
- **Unknown columns are rejected**: Any columns in your file that are not recognized (e.g. typos in column names or extra data columns) will cause an import error. Only the following columns are allowed: `statistic_id`, `start`, `unit` (only allowed if unit comes from the file), `min`, `max`, `mean`, `sum`, `state`
- **Mean always uses average**: The mean value is calculated as a simple arithmetic average. This means that for circular/angular values (like wind direction, compass bearings), the average will give incorrect results.

Then, copy your file to your HA configuration (where you find `configuration.yaml`).

Then, go to `Developer tools / Actions` (called Services in former HA versions), and select the action `import_statistics: import_from_file`.

Fill out the settings in the UI:

![ui_settings](assets/service_ui.png)

or use the yaml syntax:

```yaml
action: import_statistics.import_from_file
data:
  timezone_identifier: Europe/Vienna
  delimiter: \t
  decimal: false
  filename: counterdata.tsv
```

Last, call the action. You will get feedback directly in the GUI.

> The import operation waits until all data is committed to the database. Depending on the size of the import, this may take a moment. You will see the action complete once all data has been successfully imported.

> If importing does not work, and you do not get an error directly in the GUI, but there is an error in the home assistant logs, then this is a bug (this happens if the integration misses some checks, which lead to import errors later). Please create an issue.

### import_from_json

This works similarly to the file import, but can _also_ be called via the homeassistant api.

The JSON format is shown here:

- [state_sum.json](./assets/state_sum.json)

You can upload the json via the api at: `https://<homeassistant.url>/api/services/import_statistics/import_from_json` with the JSON file as the request body.

## Export

This integration also offers the action `export_statistics` to export statistics to a file (TSV/CSV format, or JSON format).

First, go to `Developer tools / Actions`, and select the action `import_statistics: export_statistics`.

Fill out the settings in the UI:

- **Filename**: The name of the file to export to (relative to your configuration directory). E.g., `exported_statistics.tsv`. If the suffix is .json, the file is exported as JSON.
- **Entities**: List of entity IDs or statistic IDs to export. You can export both:
  - **Internal statistics**: Existing sensors like `sensor.temperature` (format with '.')
  - **External statistics**: Custom statistics like `sensor:my_custom_statistic` (format with ':')
  - Make sure to use a Yaml list like:
```yaml
- sensor.temperature
- sensor:my_custom_statistic
```
- **Start time**: The beginning of the time range to export (must be a full hour, e.g., "2025-12-22 12:00:00")
- **End time**: The end of the time range to export (must be a full hour, e.g., "2025-12-25 12:00:00")
- **Timezone identifier** (optional, default: "Europe/Vienna"): Timezone for formatting the timestamps in the exported file
- **Delimiter** (optional, default: tab): Column separator for the export file. Options: tab (`\t`), semicolon (`;`), comma (`,`), or pipe (`|`)
- **Decimal** (optional, default: false==dot): Use comma (true) or dot (false) as decimal separator in numeric values

Or use the YAML syntax, e.g.:

```yaml
action: import_statistics.export_statistics
data:
  filename: exported_statistics.tsv
  entities:
    - sensor.temperature
    - sensor.energy_consumption
  start_time: "2025-12-22 12:00:00"
  end_time: "2025-12-25 12:00:00"
  timezone_identifier: Europe/Vienna
  delimiter: \t
  decimal: false
```

The exported file will contain the following columns:
- `statistic_id`: The ID of the statistic
- `unit`: The unit of measurement
- `start`: The timestamp of the data point (in your specified timezone and format)
- For **sensors**: `min`, `max`, `mean` - the minimum, maximum, and average values for the hour
- For **counters**: `sum`, `state` - the summed value and the state value for the hour
  - The export also includes a calculated `delta` column showing the change between consecutive hours

You can then import this file back into Home Assistant (or another instance) using the `import_from_file` action.

You can mix sensors and counters in one export. However, in this case a direct import is not possible, as `import_from_file` can only import either sensors or counters in one file.

## Understanding state_class total_increasing

For sensors with `state_class: total_increasing` (like energy meters), Home Assistant stores two values in long-term statistics:

- **state**: The actual sensor reading at that point in time (e.g., 6913.045 kWh)
- **sum**: A cumulative value used for calculating deltas and differences (e.g., for the energy board)

### How it works

The table below demonstrates how Home Assistant processes sensor state changes and converts them into long-term statistics entries:

| currentTime | stateTime | state | statisticsTime | statisticsState | statisticsSum | statisticsDelta |
|---|---|---|---|---|---|---|
|06:59:50|06:59:50|6912.294|||||
|07:00:00|||06:00:00|6912.294|912.294||
|07:59:51|07:59:51|6913.045|||||
|08:00:00|||07:00:00|6913.045|913.045|0.751|

**Key Points:**
1. State changes are recorded when they occur
2. At each hour boundary, a statistics entry is created using the most recent state value
3. The statistics timestamp represents the **start** of the hour period (e.g., at 8:00 AM, the timestamp stored is 7:00 AM)
4. The `sum` value starts at 0 when the sensor is created and increases by the same amount as the state
5. The delta is computed from the difference between consecutive statistics entries (913.045 - 912.294 = 0.751)
6. The **delta** column (not stored in HA database) represents the energy consumed **during** that hour

The energy board and statistics graph cards primarily use the `sum` value, which is why it's important to import both `sum` and `state` values correctly. When importing, you can use the same value for both `sum` and `state` if you're working with absolute readings.

For more information, see the [Home Assistant developer documentation on state_class total](https://developers.home-assistant.io/blog/2021/08/16/state_class_total/).

## Importing with Delta Values

Delta import allows you to import changes (deltas) instead of absolute sum/state values. This is useful for correcting or extending your historical data.

### How to prepare a delta import

1. **Export your current data** first using the `export_statistics` action
2. **Edit the exported file**:
   - Remove the `sum` and `state` columns
   - Keep or modify the `delta` column values
   - Delete rows you don't want to change
   - Add new rows with delta values for new time periods
3. **Import the delta file** using `import_from_file`

### Important constraints

- **Complete time range required**: The imported time range must completely overwrite all existing values in the database for that range. If there are existing database values between your oldest and newest import timestamps that you don't include in your import, you will get unexpected results.
- **Reference requirement**: Delta imports require at least one existing database value either 1+ hour before or 1+ hour after your import range as a reference point for calculating absolute values.
- The import operation waits until all data is committed to the database (it is synchronous).

### Common use cases for delta imports

#### 1. Import older values before sensor was available

Use case: The sensor was not available in Home Assistant before, but there are other sources available

**Database before import:**
- 29.12.2025 08:00: sum=0, state=10
- 29.12.2025 09:00: sum=1, state=11
- 29.12.2025 10:00: sum=3, state=13

**Values to import:**

```tsv
statistic_id	start	unit	delta
sensor.imp_before	28.12.2025 09:00	kWh	10
sensor.imp_before	28.12.2025 10:00	kWh	20
sensor.imp_before	28.12.2025 11:00	kWh	30
```

**Result after import:**
- 28.12.2025 08:00: sum=-60, state=-50 (no delta available, as this is the first value in the database)
- 28.12.2025 09:00: sum=-50, state=-40 (delta: 10)
- 28.12.2025 10:00: sum=-30, state=-20 (delta: 20; calculated from first database value)
- 28.12.2025 11:00: sum=0, state=10 (delta: 30, connects to existing data)
- 29.12.2025 08:00: sum=0, state=10 (existing, delta: 0)
- 29.12.2025 09:00: sum=1, state=11 (existing)
- 29.12.2025 10:00: sum=3, state=13 (existing)

#### 2. Correct values in the middle of the time range

Use case: Correct values in the middle of the timerange available in the database, e.g. if a sensor was not active for some time

**Database before import:**
- 29.12.2025 08:00: sum=0, state=10
- 29.12.2025 09:00: sum=1, state=11 (delta: 1)
- 29.12.2025 10:00: sum=3, state=13 (delta: 2)
- 29.12.2025 11:00: sum=6, state=16 (delta: 3)
- 29.12.2025 12:00: sum=10, state=20 (delta: 4)
- 29.12.2025 13:00: sum=15, state=25 (delta: 5)
- 29.12.2025 14:00: sum=21, state=31 (delta: 6)
- 29.12.2025 15:00: sum=28, state=38 (delta: 7)
- 29.12.2025 16:00: sum=36, state=46 (delta: 8)

**Values to import:**
```tsv
statistic_id	start	unit	delta
sensor:imp_inside	29.12.2025 09:00	kWh	2
sensor:imp_inside	29.12.2025 10:00	kWh	2
sensor:imp_inside	29.12.2025 11:00	kWh	2
sensor:imp_inside	29.12.2025 12:00	kWh	5
sensor:imp_inside	29.12.2025 13:00	kWh	5
sensor:imp_inside	29.12.2025 14:00	kWh	5
```

**Result after import:**
- 29.12.2025 08:00: sum=0, state=10 (unchanged, reference point)
- 29.12.2025 09:00: sum=2, state=12 (delta: 2, corrected)
- 29.12.2025 10:00: sum=4, state=14 (delta: 2, corrected)
- 29.12.2025 11:00: sum=6, state=16 (delta: 2, corrected)
- 29.12.2025 12:00: sum=11, state=21 (delta: 5, corrected)
- 29.12.2025 13:00: sum=16, state=26 (delta: 5, corrected)
- 29.12.2025 14:00: sum=21, state=31 (delta: 5, corrected)
- 29.12.2025 15:00: sum=28, state=38 (delta: 7, unchanged)
- 29.12.2025 16:00: sum=36, state=46 (delta: 8, unchanged)

> Please note there is no "spike" at 29.12.2025 15:00 because the sum of the deltas beween 29.12.2025 09:00 and 29.12.2025 14:00 is identical in the database and in the import (both are 21). If there is a difference, then the delta at 29.12.2025 15:00 would be different, which results in a wrong value at this timestamp e.g. in the energy board.

#### 3. Correct or add values after the newest database entry

Use case: manually input values

**Database before import:**
- 29.12.2025 08:00: sum=0, state=10
- 29.12.2025 09:00: sum=1, state=11
- 29.12.2025 10:00: sum=3, state=13

**Values to import:**
```tsv
statistic_id	start	unit	delta
sensor.imp_after	30.12.2025 09:00	kWh	10
sensor.imp_after	30.12.2025 10:00	kWh	20
sensor.imp_after	30.12.2025 11:00	kWh	30
```

**Result after import:**
- 29.12.2025 08:00: sum=0, state=10 (unchanged)
- 29.12.2025 09:00: sum=1, state=11 (unchanged)
- 29.12.2025 10:00: sum=3, state=13 (unchanged, reference point)
- 30.12.2025 09:00: sum=13, state=23 (delta: 10, new)
- 30.12.2025 10:00: sum=33, state=43 (delta: 20, new)
- 30.12.2025 11:00: sum=63, state=73 (delta: 30, new)

#### Warning: Leaving "holes" create strange results

If you don't import all DB values in the input time range, you'll create unexpected values. For example, if the database has values at 09:00, 10:00, 11:00, 12:00, 13:00, 14:00 and you only import deltas at 09:00 and 13:00, you will get strange results. You have to provide all values.

## Concrete examples

[Loading, Manipulating, Recovering and Moving Long Term Statistics in Home Assistant](https://community.home-assistant.io/t/loading-manipulating-recovering-and-moving-long-term-statistics-in-home-assistant/953802) describes concrete examples to enhance/repair your historical data, esp. explaining the complex topic with state and sum. If you have troubles with state/sum, make sure you read this. Thx to Geoffrey!

A guide to migrate from Jeedom statistics data is available [here](./misc/jeedom.md).

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

***

[import_statistics]: https://github.com/klausj1/homeassistant-statistics
[commits-shield]: https://img.shields.io/github/commit-activity/y/klausj1/homeassistant-statistics.svg
[commits]: https://github.com/klausj1/homeassistant-statistics/commits/main
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg
[forum]: https://community.home-assistant.io/t/custom-integration-to-import-long-term-statistics-from-a-file-like-csv-or-tsv
[license-shield]: https://img.shields.io/github/license/klausj1/homeassistant-statistics.svg
[releases-shield]: https://img.shields.io/github/v/release/klausj1/homeassistant-statistics?include_prereleases
[releases]: https://github.com/klausj1/homeassistant-statistics/releases
[hacs-repo-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[hacs-repo]: https://my.home-assistant.io/redirect/hacs_repository/?owner=klausj1&repository=homeassistant-statistics&category=integration
[config-flow-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
[config-flow]: https://my.home-assistant.io/redirect/config_flow_start?domain=import_statistics
