# ToDos

## for Export

- Review integration tests and other changes

## for delta

### sum and state for sensors with state_class total_increasing explained

**Table Explanation:**

The table below demonstrates how Home Assistant processes sensor state changes and converts them into (long term) statistics entries. Each row represents a point in time where either a state change occurs or an hourly statistics record is created.

**Column Definitions:**

- **currentTime**: The actual clock time when the observation is made
- **stateTime**: The timestamp when the entity's state was last updated (only populated when state changes occur)
- **state**: The current sensor value at that moment (only populated when state changes occur)
- **statisticsTime**: The timestamp assigned to the statistics record (typically the start of the hour)
- **statisticsState**: The state value stored in the statistics table for this hour
- **statisticsSum**: The cumulative sum value stored in the statistics table (used for calculating deltas). The sum value starts with 0 when the sensor has been created, and increases with the same amount as the state.
- **statisticsDelta**: The change of the value from the previous hour's statistics sum

> The statisticsDelta is not stored in the HA database, but it can be used for importing.

This demonstrates that:

1. State changes are recorded when they occur
2. At each hour boundary, a statistics entry is created using the most recent state value, with the timestamp one hour earlier
3. The delta is computed from the difference between consecutive statistics entries
4. The statistics timestamp represents the start of the period, not the time the record was created

| currentTime | stateTime | state | statisticsTime | statisticsState | statisticsSum | statisticsDelta | comment
|---|---|---|---|---|---|---|---|
|06:59:50|06:59:50|6912,294|||||state changes
|07:00:00|||06:00:00|6912,294|912,294||At 7 am, the current value 6912,294 is used as the end value of the interval starting at 6 am, with the timestamp in the statistics 6 am. As this was the first value, no delta is available
|07:59:51|07:59:51|6913,045|||||state changes
|08:00:00|||07:00:00|6913,045|6913,045|0,751|At 8 am, the current value 6913,045 is used as the end value of the interval starting at 7 am, with the timestamp in the statistics 7 am. Delta is calculated from the statisticsSum: 913,045 - 912,294 = 0,751 (The difference of the state values is the same). The delta with the statistics timestamp 7 am is the difference of the statistic values at 7 am and 6 am (which are the values at 8 am and 7 am), so this delta is the state change between 8 am and 7 am, and gets the timestamp 7 am.

The energy board uses the sum, so the sum is the more important value. Also the delta-attribute in the statistics graph card uses the sum to calculate the delta.

Whats confusing for me is that in the statistics graph card, the sum in the graph always starts at 0, whereas the state shows the value from the statistics database.

More information see https://developers.home-assistant.io/blog/2021/08/16/state_class_total/
https://developers.home-assistant.io/docs/core/entity/sensor/#state_class_total_increasing

### Other

- Add integration tests for use cases:
  - imp_inside_spike: As above, but delta values are not correct
  - imp_inside_holes: Not all values in the DB are overwritten by the import
  - imp_partly_after: imp_after, but with overlap

- Checks
  - Test what happens with a delta import when there is no entry in the DB at all: homeassistant.exceptions.HomeAssistantError: No metadata found for statistics: ['sensor:test_case_2_ext'] Error Could be returned as info to the UI, do not use delta when there is no reference at all

- Add counters without delta and sensor to integration test

- User doc
  - warning: do export before delta import, as more data are changed
  - all values in import must overwrite existing values in DB, there must not be additional values in DB between oldest and youngest import. Alternative: Merge, could make sense as delta is the important part, and I did it for case 2 test intuitively. Alternative: document.
  - Import is not async anymore

- Write a post

### Later
- Test repo in other local storage, create developer documentation
- Setup a job to run the test in the pipeline as well, for pull requests
- In helpers.py/get_delta_stat, invalid rows should fail; search for # Silent failure - skip invalid rows, compare with import
  - Also in normal import an empty value is returned. I do not understand, maybe this is anyhow checked before already?
- Code duplication between handle_import_from_file and from json
- Allow import of counter and sensor in one file
- Why isn't pandas directly used to read json? prepare_json_data_to_import does some manual stuff, necessary?
- Create arc-doc
- test_export_service.py: Separate to unit-tests and integration-tests
- Why is export_json and export_tsv so different? Does it make sense or do we need a refactoring?
- handle_arguments is used in import, but not in export. Should me made consistent
- Collect errors, and exit only after complete checking is done