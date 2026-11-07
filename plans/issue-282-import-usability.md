# Plan: Improve export-to-import usability (#282)

## Goal

Make exported CSV/TSV and JSON files easier to import without changing the
existing export default or silently discarding counter data. Improve import
feedback and allow users to skip missing recorder entities deliberately.

The export service currently includes `sum`, `state`, and `delta` when
`counter_fields: both` is selected. Those counter representations can conflict
on import. The import pipeline also currently validates column combinations
globally, which does not work for sparse mixed files containing both
measurement and counter rows.

## Proposed service parameters

Add the same options to `import_from_file` and `import_from_json`, so the
services have consistent behavior:

### `counter_mode`

Default: `auto`. Accepted values: `auto`, `strict`, `sum`, `delta`.

This option applies only to counter data. It must not change how measurement
rows (`min`, `max`, `mean`) are imported.

| Value | Behavior |
| --- | --- |
| `auto` | Infer the counter representation from populated data. Use `sum`/`state` if those are the only populated counter fields; use `delta` if it is the only populated counter field. If both representations contain data, stop with an actionable ambiguity error. Ignore empty sparse columns when deciding whether counter data conflicts. |
| `strict` | Preserve strict validation: do not discard conflicting counter data. Reject a file when both counter representations are supplied for counter data, even if a particular row has one representation empty. Measurement fields alone do not cause a counter conflict. |
| `sum` | Import `sum`/`state` and ignore `delta` for counters. If counter rows are present but contain no usable `sum`/`state` data, report an error rather than silently dropping those counters. |
| `delta` | Import `delta` and ignore `sum`/`state` for counters. If counter rows are present but contain no usable `delta` data, report an error rather than silently dropping those counters. |

With `auto`, a measurement-only file is imported as measurements, including a
sparse `delta` column with no counter values. A mixed file with measurements
and delta counters is also valid when the counter representation is
unambiguous. In explicit `sum` or `delta` mode, measurement rows are processed
as usual while the selected representation is applied to counter rows.

If a file contains populated `sum`/`state` and `delta` counter data, `auto`
must not guess. The error should tell the user to set `counter_mode` to `sum`
or `delta`, briefly explain the difference, and give the corresponding
service-call YAML.

### `ignore_unknown_entities`

Default: `false`.

When false, retain the current behavior and fail if a recorder statistic's
entity is not present in Home Assistant. When true, skip only recorder
statistics whose entities are missing; do not treat external statistics as
unknown entities. Include skipped statistic IDs in the service response and
log a warning, so the option does not silently hide skipped data. Continue to
validate units and other import data for the statistics that will be imported.

Skipping should be determined before writing any statistics, to avoid a
partially completed import if a later validation fails.

Suggested service-field descriptions:

- `counter_mode`: “Select which counter representation to import when a file
  contains `sum`/`state` and `delta`. `auto` (default) uses the only populated
  representation and reports an error if both are present. `strict` rejects
  conflicting counter data. `sum` imports `sum`/`state`; `delta` imports
  `delta`. Measurement rows are unaffected.”
- `ignore_unknown_entities`: “Skip recorder statistics whose entities do not
  exist in Home Assistant. Skipped statistic IDs are included in the service
  response. Defaults to false.”

## Import behavior and validation

1. Normalize and validate `counter_mode` and `ignore_unknown_entities` before
   processing, using the existing service validation and error-handling
   conventions.
2. Apply the mode consistently to CSV/TSV and JSON input. For CSV/TSV, base
   ambiguity detection on populated counter values rather than column names
   alone, because exports intentionally have sparse columns. For JSON, apply
   the equivalent check to each statistic's populated value keys.
3. Process measurement rows independently from counter rows. Delta conversion
   must operate on counter data only; measurement rows must continue through
   the regular measurement import path.
4. Ensure explicit modes never silently lose all counter data because the
   chosen representation is absent. Fail with a message naming the missing
   fields and the selected mode.
5. Identify unknown recorder entities before import, then either fail as
   today or remove them from the pending import and report the skipped IDs.
   Existing unit validation remains in force for all records not skipped.
6. Write an automatically named error CSV with all skipped IDs (unknown recorder entities).

## Export compatibility and documentation

- Keep the export default `counter_fields: both`; do not change existing
  exports or service calls.
- Document that `both` preserves all counter fields but is ambiguous for
  `counter_mode: auto` when both counter representations contain data.
- Explain the recommended round trip: export as usual, then choose
  `counter_mode: sum` to import `sum`/`state`, or `counter_mode: delta` to
  import deltas. State clearly that `sum` and `delta` are different
  representations and that delta import uses the existing reference
  requirements.
- Add import examples for a counter-only export and a mixed
  measurement/counter export. Include an `ignore_unknown_entities: true`
  example for recovering data when some recorder entities are no longer
  present.
- Add both import options and their descriptions to the Home Assistant service
  schema/translations, and keep the README and counter documentation aligned.
- Update the version and the changelog.

## Tests

Add or update focused tests to cover:

- `auto` imports counter-only `sum`/`state` and delta-only data.
- `auto` rejects populated `sum`/`state` and `delta` together with an error
  that names `counter_mode` and the valid choices.
- Empty sparse counter columns do not cause false ambiguity.
- Measurement-only data is imported regardless of `counter_mode`, including
  when the file has an empty `delta` column.
- Mixed measurement and delta-counter data imports correctly in `auto` when
  counter values are unambiguous, and in explicit `delta` mode when both
  representations are present.
- Explicit `sum` and `delta` select only the requested counter representation
  and report an error if counter data cannot be imported in that mode.
- `strict` rejects conflicting counter representations without rejecting
  measurement rows merely because they share a file with delta counters.
- Both import formats apply identical mode semantics.
- Unknown recorder entities still fail by default; when skipping is enabled,
  only missing recorder entities are skipped and their IDs are returned.
- Existing export output and default `counter_fields: both` remain unchanged.

Make sure to focus on unit tests, and create only a few integration tests to check the whole workflow

## Out of scope

- Changing the export default or removing any exported columns.
- Silently guessing between populated `sum`/`state` and `delta` data.
- Skipping unit mismatches or other validation errors.
