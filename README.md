# Import Statistics

A Home Assistant custom integration to import and export long-term statistics from CSV, TSV, or JSON files.

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![Community Forum][forum-shield]][forum]

> **Note:** This integration provides actions only (no entities or dashboard cards). You call its actions from Developer Tools or automations.

## Quick Links

- [Installation](#installation) | [Importing](#importing-statistics) | [Exporting](#exporting-statistics) | [Troubleshooting](#troubleshooting)
- [Counter Statistics Explained](#understanding-counter-statistics-sumstate) | [Delta Import](#delta-import-advanced)

## Requirements

- Home Assistant 2026.1.0 or newer

## Installation

### Option 1: HACS (Recommended)

1. Install via HACS, or click: [![Open HACS Repository][hacs-repo-badge]][hacs-repo]
2. Restart Home Assistant
3. Add the integration: [![Add Integration][config-flow-badge]][config-flow]

### Option 2: Manual

1. Download all files from `custom_components/import_statistics/` in this repository
2. Copy them to `<config>/custom_components/import_statistics/` (create folders if needed)
3. Add `import_statistics:` to your `configuration.yaml`
4. Restart Home Assistant

## Available Actions

| Action | Description |
|--------|-------------|
| `import_statistics.import_from_file` | Import statistics from a CSV/TSV file |
| `import_statistics.import_from_json` | Import statistics from JSON (UI or API) |
| `import_statistics.export_statistics` | Export statistics to CSV/TSV or JSON |

> As this integration uses database-independent methods, it works with all databases supported by Home Assistant.

---

## Importing Statistics

### Step 1: Prepare Your File

Your file must contain one type of statistics:
- **Sensors (state_class == measurement)** (temperature, humidity, etc.): columns `min`, `max`, `mean`
- **Counters (state_class == increasing or total_increasing)** (energy, water meters, etc.): columns `sum`, `state` (or `delta`)

Example files:
- [Sensors (min/max/mean)](./assets/min_max_mean.tsv)
- [Counters (sum/state)](./assets/state_sum.tsv)

### Step 2: File Format Requirements

| Requirement | Details |
|-------------|---------|
| **Timestamp format** | `DD.MM.YYYY HH:MM` (e.g., `17.03.2024 02:00`) |
| **Timestamp constraint** | Minutes must be `:00` (full hours only) |
| **Timezone** | Timestamps are interpreted as local time; find yours at [Wikipedia](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) |
| **File encoding** | UTF-8 (required for special characters like m³ or °C) |
| **Delimiter** | Tab (default), comma, semicolon, or pipe |
| **Decimal separator** | `.` (default) or `,` |

### Step 3: Statistic ID Format

| Type | Format | Example | When to use |
|------|--------|---------|-------------|
| **Internal** | `sensor.name` (with `.`) | `sensor.temperature` | For existing Home Assistant entities |
| **External** | `domain:name` (with `:`) | `sensor:imported_energy` | For external (custom/synthetic) statistics |

> **Tip:** Internal statistics must match an existing entity. If you import for a non-existent entity, you'll see an error in Developer Tools → Statistics (where you can remove it).

### Step 4: Run the Import

1. Copy your file to your Home Assistant config folder
2. Go to **Developer Tools → Actions**
3. Select `import_statistics: import_from_file`
4. Fill in the settings:

![ui_settings](assets/service_ui.png)

Or use YAML:

```yaml
action: import_statistics.import_from_file
data:
  filename: my_statistics.tsv
  timezone_identifier: Europe/Vienna
  delimiter: \t
  decimal: false
```

### Import Behavior

- **Overwrites existing data**: Importing the same timestamps replaces old values
- **Gaps are preserved**: Missing hours will show as gaps in graphs
- **Synchronous operation**: The action completes when all data is saved into the database. This can take a longer time for large input data
- **Validation errors**: Shown directly in the UI; check logs if import fails silently

> If importing does not work, and you do not get an error directly in the GUI, but there is an error in the home assistant logs, then this is a bug (this happens if the integration misses some checks, which lead to import errors later). Please create an issue.

### Allowed Columns

Only these columns are accepted (unknown columns cause an error):

| Column | Required | Description |
|--------|----------|-------------|
| `statistic_id` | Yes | The sensor identifier |
| `start` | Yes | Timestamp |
| `unit` | Sometimes | Required for external statistics |
| `min`, `max`, `mean` | For sensors | Cannot mix with counter columns |
| `sum`, `state` | For counters | Cannot mix with sensor columns |
| `delta` | For counters | Alternative to sum/state (see below) |

### JSON Import

You can also import via JSON, either through the UI or the Home Assistant API.

Example format: [state_sum.json](./assets/state_sum.json)

**Via API:**
```
POST https://<your-ha-url>/api/services/import_statistics/import_from_json
Content-Type: application/json

<JSON content>
```

---

## Exporting Statistics

Export your statistics to a file e.g. for backup, analysis, preparing an import with delta, or transfer to another Home Assistant instance.

### How to Export

1. Go to **Developer Tools → Actions**
2. Select `import_statistics: export_statistics`
3. Configure the export:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `filename` | Yes | Output filename (e.g., `backup.tsv` or `backup.json`) |
| `entities` | Yes | List of statistic IDs to export |
| `start_time` | Yes | Start of time range (full hour, e.g., `2025-12-22 12:00:00`) |
| `end_time` | Yes | End of time range (full hour) |
| `timezone_identifier` | No | Timezone for timestamps (default: `Europe/Vienna`) |
| `delimiter` | No | Column separator: `\t`, `;`, `,`, or `\|` (default: tab) |
| `decimal` | No | Use comma as decimal separator: `true` or `false` (default: `false` = dot) |

**YAML example:**

```yaml
action: import_statistics.export_statistics
data:
  filename: exported_statistics.tsv
  entities:
    - sensor.temperature
    - sensor.energy_consumption
    - sensor:ext_value
  start_time: "2025-12-22 12:00:00"
  end_time: "2025-12-25 12:00:00"
  timezone_identifier: Europe/Vienna
  delimiter: \t
  decimal: false
```

### Export Output

The exported file contains:

| For Sensors | For Counters |
|-------------|--------------|
| `min`, `max`, `mean` | `sum`, `state`, `delta` |

> **Note:** You can export sensors and counters together, but you'll need to split them into separate files before re-importing (import only accepts one type per file).

---

## Understanding Counter Statistics (sum/state)

Counters are entities with a state_class increasing or total_increasing.

Counter statistics (like energy meters) are more complex than sensor statistics. Here's what you need to know:

### What are `sum` and `state`?

| Column | Description | Example |
|--------|-------------|---------|
| **state** | The actual meter reading | `6913.045 kWh` (your meter shows this) |
| **sum** | Cumulative value since sensor creation | Used by Energy Dashboard |
| **delta** | Change from previous hour | `0.751 kWh` consumed this hour |

### How Home Assistant Records Counter Statistics

| Time | Meter Reading | Stored Statistics |
|------|---------------|-------------------|
| 06:59:50 | 6912.294 kWh | — |
| 07:00:00 | — | `start`: 06:00, `state`: 6912.294, `sum`: 912.294 |
| 07:59:51 | 6913.045 kWh | — |
| 08:00:00 | — | `start`: 07:00, `state`: 6913.045, `sum`: 913.045, `delta`: 0.751 |

**Key points:**
- Statistics are recorded at **hour boundaries** using the most recent meter reading
- The timestamp represents the **start** of the hour (07:00 entry = data for the 07:00–08:00 hour)
- **delta** = difference between consecutive sums (913.045 − 912.294 = 0.751)
- The Energy Dashboard uses `sum` values, so import both `sum` and `state` for correct graphs

> **Tip:** When importing, you can use the same value for both `sum` and `state` if you're working with absolute meter readings.

For more details, see the [Home Assistant documentation on state_class total](https://developers.home-assistant.io/blog/2021/08/16/state_class_total/).

---

## Delta Import (Simpler)

Instead of importing absolute `sum`/`state` values, you can import **delta** values (the change per hour). This is useful because you do not need to calculate sum and state, and you do not need to align sum and state values of the import with the sum and state values in the database, which can be a pain.

### How Delta Import Works

1. **Export your current data** using `export_statistics`
2. **Modify the file**:
   - Remove the `sum` and `state` columns
   - Keep or edit the `delta` column
   - Add/remove rows as needed
3. **Import the modified file** using `import_from_file`

The integration automatically converts deltas to absolute values using existing database entries as reference points.

### Requirements

| Requirement | Details |
|-------------|---------|
| **Reference point** | At least one existing database value 1+ hour before or at/after your import range |
| **Complete coverage** | You must provide values for ALL hours in your import range, which exists in the database (no gaps). This is the case automatically when you start with the exported file |

> §KJ: Gaps see above

### Delta Import Examples

<details>
<summary><strong>Example 1: Add historical data before sensor existed</strong></summary>

You have data from before your sensor was in Home Assistant.

> §KJ: Readd complete examples

**Existing database:**
| Time | sum | state |
|------|-----|-------|
| 29.12.2025 08:00 | 0 | 10 |
| 29.12.2025 09:00 | 1 | 11 |

**Import file:**
```tsv
statistic_id	start	unit	delta
sensor.my_energy	28.12.2025 09:00	kWh	10
sensor.my_energy	28.12.2025 10:00	kWh	20
sensor.my_energy	28.12.2025 11:00	kWh	30
```

**Result:** The integration calculates backward from your existing data to create the historical entries.

</details>

<details>
<summary><strong>Example 2: Correct values in the middle</strong></summary>

Your sensor was offline and recorded wrong values.

**Existing database (09:00–14:00 need correction):**
| Time | sum | delta |
|------|-----|-------|
| 29.12.2025 08:00 | 0 | — |
| 29.12.2025 09:00 | 1 | 1 |
| ... | ... | ... |
| 29.12.2025 15:00 | 28 | 7 |

**Import file (corrected deltas):**
```tsv
statistic_id	start	unit	delta
sensor:my_energy	29.12.2025 09:00	kWh	2
sensor:my_energy	29.12.2025 10:00	kWh	2
sensor:my_energy	29.12.2025 11:00	kWh	2
sensor:my_energy	29.12.2025 12:00	kWh	5
sensor:my_energy	29.12.2025 13:00	kWh	5
sensor:my_energy	29.12.2025 14:00	kWh	5
```

**Result:** Values 09:00–14:00 are recalculated; 08:00 and 15:00+ remain unchanged.

> **Important:** To avoid spikes, ensure your imported deltas sum to the same total as the original range (here: 21).

</details>

<details>
<summary><strong>Example 3: Add values after existing data</strong></summary>

Manually add consumption data for hours not yet in the database.

**Import file:**
```tsv
statistic_id	start	unit	delta
sensor.my_energy	30.12.2025 09:00	kWh	10
sensor.my_energy	30.12.2025 10:00	kWh	20
sensor.my_energy	30.12.2025 11:00	kWh	30
```

**Result:** New entries are calculated forward from your last existing database value.

</details>

> **Warning:** You must provide values for ALL hours in your import range. Skipping hours creates incorrect results.

---

## Additional Resources

- **[Community Guide: Loading, Manipulating, and Recovering Statistics](https://community.home-assistant.io/t/loading-manipulating-recovering-and-moving-long-term-statistics-in-home-assistant/953802)** — Detailed examples for fixing historical data (thanks to Geoffrey!)
- **[Jeedom Migration Guide](./misc/jeedom.md)** — How to import statistics from Jeedom

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Import shows no error but data doesn't appear | Check Home Assistant logs for details |
| "Unknown column" error | Check for typos in column names; see [Allowed Columns](#allowed-columns) |
| Spikes in Energy Dashboard after import | Your `sum` values don't align with existing data; see [Counter Statistics](#understanding-counter-statistics-sumstate) |
| Mean values wrong for compass/wind direction | Mean uses arithmetic average, which doesn't work for circular values |

---

## Contributing

Contributions are welcome! Please read the [Contribution Guidelines](CONTRIBUTING.md).

---

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
