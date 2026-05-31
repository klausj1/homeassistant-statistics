# Using External Statistics with the Energy Dashboard

External statistics (statistic IDs with a `:` prefix, e.g. `my_source:electricity_total`) are **not shown in the Energy Dashboard UI source picker** and cannot be added via the Home Assistant UI. This page explains how to make them work.

---

## Why External Statistics Don't Appear in the UI

The Energy Dashboard source picker only lists **entities** (internal statistics with a `.` in the ID, e.g. `sensor.electricity_total`). External statistics have a `:` in their ID and are stored directly in the database without an associated entity.

---

## CSV Format Requirements

The CSV must include **both `state` and `sum` columns**. The `sum` column is mandatory — without it, the import will fail with:

> `No statistics found in database for this entity. Also for external statistics, at least one value must exist in the database to perform delta conversion.`

```csv
statistic_id,start,unit,state,sum
my_source:electricity_total,2026-05-01 00:00,kWh,0.243,0.243
my_source:electricity_total,2026-05-01 01:00,kWh,0.304,0.547
my_source:electricity_total,2026-05-01 02:00,kWh,0.305,0.852
my_source:water_total,2026-05-01 00:00,m³,0.003,0.003
my_source:water_total,2026-05-01 01:00,m³,0.000,0.003
my_source:gas_total,2026-05-01 00:00,m³,0.012,0.012
```

- `state` = consumption during that hour (delta)
- `sum` = running cumulative total from the start of your data

---

## Import Action

```yaml
action: import_statistics.import_from_file
data:
  filename: my-data/electricity.csv
  delimiter: ","
  decimal: "."
  datetime_format: "%Y-%m-%d %H:%M"
```

---

## Adding External Statistics to the Energy Dashboard

Since external statistics are not shown in the UI picker, they must be added by **manually editing** `/config/.storage/energy`.

### 1. Backup the file

```bash
cp /config/.storage/energy /config/.storage/energy.backup
```

### 2. Edit `/config/.storage/energy`

Find the `energy_sources` array and add your entries:

```json
"energy_sources": [
  {
    "type": "grid",
    "stat_energy_from": "my_source:electricity_total"
  },
  {
    "type": "water",
    "stat_energy_from": "my_source:water_total"
  },
  {
    "type": "gas",
    "stat_energy_from": "my_source:gas_total"
  }
]
```

### 3. Restart Home Assistant

After saving the file, restart Home Assistant. The statistics will appear in the Energy Dashboard.

---

## Important Notes

- Use **`"type": "grid"`** for electricity consumption — not `"type": "electricity"` (which is invalid)
- External statistics **cannot have a custom display name** — the UI will show the raw statistic ID (e.g. `my_source:electricity_total`)
- You can verify the import worked via **Developer Tools → Statistics** — search for your statistic ID prefix

---

## Automated Daily Import

To keep data up to date automatically, add an HA automation:

```yaml
alias: Import Energy Data
triggers:
  - at: "06:30:00"
    trigger: time
actions:
  - action: import_statistics.import_from_file
    data:
      filename: my-data/electricity.csv
      delimiter: ","
      decimal: "."
      datetime_format: "%Y-%m-%d %H:%M"
  - delay:
      seconds: 2
  - action: import_statistics.import_from_file
    data:
      filename: my-data/water.csv
      delimiter: ","
      decimal: "."
      datetime_format: "%Y-%m-%d %H:%M"
  - delay:
      seconds: 2
  - action: import_statistics.import_from_file
    data:
      filename: my-data/gas.csv
      delimiter: ","
      decimal: "."
      datetime_format: "%Y-%m-%d %H:%M"
mode: single
```

This of course expects the CSV files to have been updated beforehand (daily)!
