# modification of export options proposal

## Context

The `import_statistics.export_statistics` service exports long-term statistics from the recorder to a single file (TSV/CSV by delimiter, or JSON by `.json` extension).

This document proposes several changes to make exporting more flexible, especially for large datasets.

## Baseline behavior (original/creator)

- **Entities selection**

  - `entities` is required.
  - If omitted or empty, the service call fails.
- **Time range**

  - `start_time` and `end_time` are currently required by the service schema.
  - Both must be full hours (`minute == 0` and `second == 0`).
  - They are interpreted in `timezone_identifier`, then converted to UTC internally.
- **Export format**

  - If `filename` ends with `.json`, JSON is written.
  - Otherwise the export is CSV/TSV with the chosen `delimiter`.
- **Columns**

  - TSV/CSV export always includes: `statistic_id`, `unit`, `start`.
  - Sensor-like stats export: `min`, `max`, `mean`.
  - Counter-like stats export: `sum`, `state`.
  - For counters, an extra `delta` column is calculated.
  - Mixed exports (sensors + counters) are allowed; non-applicable cells are empty.

## Proposed modifications

### 1) Allow exporting all statistics (make `entities` optional)

#### Specification

Allow exporting *all* statistics when no entities are provided.

- **YAML / service call**
  - Omit `entities:` or pass an empty list.
- **UI**
  - Leaving the entities field empty exports all statistics.

#### Status

- [X] Implemented (partially done)
- [ ] Tested

#### Notes

- This is a standalone change. It should not be coupled to file splitting or limiting.

### 2) Optional `start_time`

#### Specification

Allow omitting `start_time` to export from the earliest available statistics record up to `end_time`.

- **YAML / service call**
  - Omit `start_time`.
- **UI**
  - Make `start_time` optional.
- **Notes / constraints**
  - If provided, `start_time` must still be a full hour.
  - The selected/assumed timezone is still `timezone_identifier`.

#### Status

- [ ] Implemented
- [ ] Tested

### 3) Optional `end_time`

#### Specification

Allow omitting `end_time` to export from `start_time` up to the most recent available statistics record.

- **YAML / service call**
  - Omit `end_time`.
- **UI**
  - Make `end_time` optional.
- **Notes / constraints**
  - If provided, `end_time` must still be a full hour.
  - The selected/assumed timezone is still `timezone_identifier`.

#### Status

- [ ] Implemented
- [ ] Tested

### 4) Split sensors and counters into multiple files

#### Specification

Add an option to write sensor-like statistics and counter-like statistics into separate files instead of mixing them.

- **New option**
  - `split_statistics: true|false` (default: `false`)
- **Behavior**
  - If `false` (default), current behavior remains (single file).
  - If `true`, produce up to two files:
    - Sensors file: `BaseName_sensors.Ext`
    - Counters file: `BaseName_counters.Ext`
  - If only one type is present, only one file is created.
- **Filename rules**
  - For `filename="export.tsv"`, the split outputs become:
    - `export_sensors.tsv`
    - `export_counters.tsv`
  - For JSON (`.json`), the split outputs become:
    - `export_sensors.json`
    - `export_counters.json`

#### Status

- [ ] Implemented
- [ ] Tested

#### Notes

- This is independent of “export all”. It applies equally to exports with a specific `entities` list. This option is useful if you to want to reimport the statistics using import_from_file that only accept one type per file.

### 5) Limit the maximum number of exported statistics IDs

#### Motivation

Exporting statistics (especially “all statistics”) can generate very large files. A limit helps reduce runtime, memory use, and file size.

#### Specification

Add an option to cap the number of statistic IDs included in one export operation.

- **New option**
  - `max_statistics: <int>` (optional, default: `1000`)
- **Behavior**
  - If omitted, use the default (`1000`).
  - If provided:
    - Must be a positive integer (`>= 1`).
    - Only the first `max_statistics` statistic IDs (after sorting) are exported.
    - Sorting should be deterministic (e.g., alphabetical by `statistic_id`).
- **UI**
  - Optional number field with validation.

#### Notes

- This is independent of “export all”. It can be used with either:
  - a provided `entities` list, or
  - no `entities` list (once modification #1 is supported).
- Default value `1000` is a proposal and should be confirmed based on real-world datasets.

#### Status

- [ ] Implemented
- [ ] Tested

## Examples

### Export selected entities only

```yaml
service: import_statistics.export_statistics
data:
  filename: exported_statistics.tsv
  entities:
    - sensor.temperature
    - sensor:external_stat
  start_time: "2025-12-22 12:00:00"
  end_time: "2025-12-25 12:00:00"
```

### Export all statistics (proposed behavior)

```yaml
service: import_statistics.export_statistics
data:
  filename: exported_statistics.tsv
  start_time: "2025-12-22 12:00:00"
  end_time: "2025-12-25 12:00:00"
```

### Proposed: export split into two files (independent of export-all)

```yaml
service: import_statistics.export_statistics
data:
  filename: exported_statistics.tsv
  entities:
    - sensor.temperature
    - sensor:external_stat
  start_time: "2025-12-22 00:00:00"
  end_time: "2025-12-23 00:00:00"
  split_statistics: true
```

### Proposed: export with a maximum number of statistic IDs (independent of export-all)

```yaml
service: import_statistics.export_statistics
data:
  filename: exported_statistics.tsv
  entities:
    - sensor.temperature
    - sensor:external_stat
  start_time: "2025-12-22 00:00:00"
  end_time: "2025-12-23 00:00:00"
  max_statistics: 5000
```
