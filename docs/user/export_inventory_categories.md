# Export Inventory: Categories and Entity States

This project provides the `import_statistics.export_inventory` service, which exports an inventory of long-term statistics from Home Assistant.

The inventory output includes a `category` column with one of the following values:

- `Active`
- `Orphan`
- `Deleted`
- `External`

This document explains:

- What is being classified (statistics, not entities)
- What Home Assistant “entity states” exist from the perspective of the Entity Registry and Recorder
- How those underlying states map to the inventory `category`

## What is being categorized

The inventory categorizes **statistics**, not entities.

Each row in the inventory corresponds to a `statistics_meta` entry identified by `statistics_meta.statistic_id` (shown as `statistic_id` in the exported file).

For **internal recorder statistics**, the `statistic_id` is typically the **entity_id** (for example `sensor.temperature`). In that common case, categorizing a statistic is effectively categorizing the corresponding entity.

For **external statistics**, `statistic_id` is not an entity_id and should not be interpreted as one.

## Home Assistant data sources involved

Home Assistant has two relevant “truth sources”, each with different semantics:

- **Entity Registry**
  - In-memory structure persisted to `.storage/core.entity_registry`
  - Tracks entities known to Home Assistant
  - Has two important collections:
    - `entity_registry.entities`: active registered entities
    - `entity_registry.deleted_entities`: entities that were removed from the active registry but still have a deleted registry record

- **Recorder / Database**
  - Stores state history and long-term statistics
  - Relevant tables/features:
    - `statistics_meta`, `statistics`, `statistics_short_term`
    - `states_meta` and `states` (state history metadata and rows)

Important: **Recorder tables are not authoritative for “entity existence”.** They can be purged, filtered, or incomplete for valid entities.

## Possible “states” of an entity (conceptual model)

The term “entity state” is overloaded in Home Assistant (it also means the runtime state value like `"23.1"` or `"unavailable"`).

In this document, “state” means: **what lifecycle/visibility situation an entity is in**, relative to the Entity Registry and Recorder.

### 1) Registered (active entity registry entry)

- Entity exists in `entity_registry.entities`.
- Entity is currently registered in Home Assistant.
- It may or may not be producing recorder history or statistics right now.

Common reasons an entity can be registered but appear “inactive” elsewhere:

- Integration temporarily unavailable
- Entity disabled
- Recorder excludes this entity
- Recorder purge removed old state history

### 2) Deleted registry entry exists

- Entity is not in `entity_registry.entities`.
- Entity exists in `entity_registry.deleted_entities`.

This means Home Assistant still has a record that the entity once existed, but it is no longer an active registered entity.

Notes:

- Some Home Assistant versions/situations do not populate all metadata fields (for example `orphaned_timestamp` can be `null`).
- Presence in `deleted_entities` is still a strong signal that the entity was removed from active registry.

### 3) Fully absent from the Entity Registry

- Entity is in neither `entity_registry.entities` nor `entity_registry.deleted_entities`.

This is the “no registry knowledge remains” case.

It can happen when:

- The integration was removed a long time ago
- Registry entries were cleaned up during migrations/upgrades
- The registry no longer retains deleted entries for older entities

### 4) Present in Recorder state history (`states_meta`/`states`)

This is not a lifecycle state by itself, but it affects what you can infer from SQL.

- Entity appears in `states_meta` only if Recorder has recorded state changes for it.
- After purge/cleanup, the entity may no longer appear in `states_meta` even if it is still registered and active.

Therefore:

- **Present in `states_meta`** does not guarantee “currently exists”.
- **Absent from `states_meta`** does not imply “deleted”.

## Export inventory category definitions

The inventory `category` aims to answer:

- Is this statistic internal to HA (`recorder`) or external?
- If internal, does HA still have an active registry entry for the corresponding entity?
- If not active, does HA still keep a deleted registry record?
- If neither, the statistic is treated as a leftover (“deleted”) statistic.

### Category: `External`

A statistic is classified as `External` when it is not an internal recorder statistic.

Practical rules used by the exporter:

- If `source != "recorder"` => `External`
- If `statistic_id` contains `:` => `External`

Rationale:

- External statistics IDs are not entity_ids and should not be validated against the Entity Registry.

### Category: `Active`

A statistic is classified as `Active` when:

- It is internal (`source == "recorder"` and no `:` in `statistic_id`), and
- `statistic_id` exists in `entity_registry.entities`.

Interpretation:

- The entity is still registered in Home Assistant.
- Even if the entity is currently unavailable or not producing new statistics, it is still a valid entity from HA’s perspective.

### Category: `Orphan`

A statistic is classified as `Orphan` when:

- It is internal (`source == "recorder"` and no `:` in `statistic_id`), and
- `statistic_id` exists in `entity_registry.deleted_entities`.

Interpretation:

- The entity is no longer an active registered entity, but HA still has a deleted registry record for it.

Important nuance:

- The exporter treats all deleted registry entries as `Orphan`, even when fields like `orphaned_timestamp` are missing (`null`). These fields are not consistently populated across HA versions and deletion scenarios.

### Category: `Deleted`

A statistic is classified as `Deleted` when:

- It is internal (`source == "recorder"` and no `:` in `statistic_id`), and
- `statistic_id` exists in neither `entity_registry.entities` nor `entity_registry.deleted_entities`.

Interpretation:

- The recorder still contains long-term statistics metadata and/or data, but Home Assistant has no entity registry record anymore.
- This commonly happens after integration removal or over time on long-running systems.

## Practical implications for cleanup

- `Active`: do not delete statistics based on inventory alone. If you want to remove them, it should be a deliberate user action.
- `Orphan`: these are good candidates for cleanup if you are sure you will not restore/recreate the entity (for example, integration removed).
- `Deleted`: these are strong candidates for cleanup because HA no longer has a registry record.
- `External`: depends on the external integration; do not treat them as deletable based solely on entity registry checks.

## Troubleshooting notes

- A large `Deleted` count is not necessarily an error on long-running systems.
- A large `Deleted` count in earlier versions of the inventory exporter could indicate misclassification when using Recorder tables as an “existence” proxy.
- If you see unexpected classification, verify the entity in:
  - Settings -> Devices & Services -> Entities
  - Developer Tools -> States
  - Entity Registry (`.storage/core.entity_registry`) if you have access
