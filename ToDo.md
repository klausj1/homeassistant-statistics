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

- OK Get all tests running, comment out case 2 for now

- OK Clean up tests
  - unit, integration-mock, integration
  - pytest with levels, start integration only when integration-mock is OK

- OK Clean up init and prepare_data
  - separate database-access-functions
  - separate export and import

- OK Create ITest with mock based in ITest testdata
  - First for case 1, which must be OK

- OK When checking the mock calculation in the mocked ITest, does it make sense to have a method for this in production, when all values needed from the database have been queries before? Or is such a method there already?

- OK Understand different cases
  - Create a figure
  - Create a description
  - How does this fit to the current implementation? If not, refactor

- Refactoring in progress

- Create arc-doc

- ITest with mock for case 2

- ITest without mock for case 2

- get_oldest_statistics_before: name and description are not correct anymore

- test_export_service.py: Separate to unit-tests and integration-tests

- Understand the stuff with the youngest timestamp. Currently the query in _get_youngest_reference_stats uses the oldest timestamp in the imported file, and searches for younger (=larger) timestamps (start_ts >= ts.timestamp())
- Expected files are wrong, because the case 2 import adds new entries -> repair (possibly filter the time range for export of 1 and 2? Will not help I assume ...)
  - Or for now, always delete the sqlite db
  - Or rather with the import at the beginning overwrite the changed values -> does not work, as the timestamp logic is incorrect then ...
- Implemented, unit-tests OK, delta-import for case 2 does not work, the results are very strange. See comparison.
- Problem: Working backward from the latest timestamp and the delta-rows. That does not make sense in this way. Must work backward from the nearest youngest timestamp, and consider every value in the database. Create a design description for this and let the AI work ... Also change the 1 hour timediff for the youngest timestamp. Start with a unit-test and review the results carefully before starting with integration tests, esp. as the database has to be setup again after each test ...

- Rename integration test and methods and test files in the integration test, as they test all cases

- When 1 (older history available) is working, implement 2-4. In work
  - Whats the difference between 2 and 3? And 3 and 1? Isn't overriding 1? Understand before impementation

- Check error messages

- Checks
  - youngest timestamp to import must be less than current hour -1
  - all values in import must overwrite existing values in DB, there must not be additional values in DB between oldest and youngest import. Alternative: Merge, could make sense as delta is the important part, and I did it for case 2 test intuitively
  - Later: homeassistant.exceptions.HomeAssistantError: No metadata found for statistics: ['sensor:test_case_2_ext'] Error Could be returned as info to the UI, do not use delta when there is no reference at all

- User doc
  - warning: do export before delta import, as more data are changed

- Write a post export is working

- Add non-delta imports to the integration test

### Later
- Is it possible to wait until async import task is ready?
- Setup a job to run the test in the pipeline as well, for pull requests
- In helpers.py/get_delta_stat, invalid rows should fail; search for # Silent failure - skip invalid rows, compare with import
  - Also in normal import an empty value is returned. I do not understand, maybe this is anyhow checked before already?
- Code duplication between handle_import_from_file and json
  - JSON does not work anyhow
- Check what should be in init and what not; own file for HA-dependent helpers
- Allow import of counter and sensor in one file