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
- Import older values (e.g. from before HA was used)
  - Probably a bug, see diff expected / exported. Definition is maybe not clear.

Bug explanation:
Orig:
sensor.test_case_2	29.12.2025 08:00	kWh	0	10
sensor.test_case_2	29.12.2025 09:00	kWh	1	11
sensor.test_case_2	29.12.2025 10:00	kWh	3	13
sensor.test_case_2	29.12.2025 11:00	kWh	6	16
sensor.test_case_2	29.12.2025 12:00	kWh	10	20
sensor.test_case_2	29.12.2025 13:00	kWh	15	25
sensor.test_case_2	29.12.2025 14:00	kWh	21	31
sensor.test_case_2	29.12.2025 15:00	kWh	28	38
sensor.test_case_2	29.12.2025 16:00	kWh	36	46
sensor.test_case_2	30.12.2025 08:00	kWh	45	55
sensor.test_case_2	30.12.2025 09:00	kWh	55	65
sensor.test_case_2	30.12.2025 10:00	kWh	66	76

Delta:
sensor.test_case_2	29.12.2025 06:00	kWh	2
sensor.test_case_2	29.12.2025 07:00	kWh	1
sensor.test_case_2	29.12.2025 08:00	kWh	0
sensor.test_case_2	29.12.2025 09:00	kWh	0
sensor.test_case_2	29.12.2025 10:00	kWh	0
sensor.test_case_2	29.12.2025 11:00	kWh	3

Expected:
sensor.test_case_2	kWh	29.12.2025 05:00	0	10
sensor.test_case_2	kWh	29.12.2025 06:00	2	12	2
sensor.test_case_2	kWh	29.12.2025 07:00	3	13	1
sensor.test_case_2	kWh	29.12.2025 08:00	3	13	0
sensor.test_case_2	kWh	29.12.2025 09:00	3	13	0
sensor.test_case_2	kWh	29.12.2025 10:00	3	13	0
sensor.test_case_2	kWh	29.12.2025 11:00	6	16	3
sensor.test_case_2	kWh	29.12.2025 12:00	10	20	4
sensor.test_case_2	kWh	29.12.2025 13:00	15	25	5
sensor.test_case_2	kWh	29.12.2025 14:00	21	31	6
sensor.test_case_2	kWh	29.12.2025 15:00	28	38	7
sensor.test_case_2	kWh	29.12.2025 16:00	36	46	8
sensor.test_case_2	kWh	30.12.2025 08:00	45	55	9
sensor.test_case_2	kWh	30.12.2025 09:00	55	65	10
sensor.test_case_2	kWh	30.12.2025 10:00	66	76	11

Orig:
sensor.imp_before	29.12.2025 08:00	kWh	0	10
sensor.imp_before	29.12.2025 09:00	kWh	1	11
sensor.imp_before	29.12.2025 10:00	kWh	3	13

Delta:
sensor.imp_before	28.12.2025 09:00	kWh	10
sensor.imp_before	28.12.2025 10:00	kWh	20
sensor.imp_before	28.12.2025 11:00	kWh	30

Expected:
sensor.imp_before	kWh	28.12.2025 08:00	-60	-50
sensor.imp_before	kWh	28.12.2025 09:00	-50	-40	10
sensor.imp_before	kWh	28.12.2025 10:00	-30	-20	20
sensor.imp_before	kWh	28.12.2025 11:00	0	10	30
sensor.imp_before	kWh	29.12.2025 08:00	0	10	0
sensor.imp_before	kWh	29.12.2025 09:00	1	11	1
sensor.imp_before	kWh	29.12.2025 10:00	3	13	2


Logic:
- Existing: Take newest delta value from the delta import (29.12. 11:00). This value exists in the DB, from there take state and sum
- Not existing: Take newest delta value from the delta import (28.12. 11:00, delta 30). This value does not exist in the DB.
  Instead, take the oldest value from the DB: 29.12. 08:00, from there take state and sum.
  The current code just takes the delta value from the import, and takes the timestamp from the DB. Thats wrong. It does not even create the entry with the newest delta timestamp.
  Whats necessary is to use delta 0 for the oldest value in the DB, take state and sum from the oldest value in the DB, and copy them to the newest delta timestamp. Then all data are available to create the entry with the newest delta timestamp.

  - mock test does not work
- Import newer values (e.g. manually input data)
- Correct values in the middle (e.g. connection of a sensor to HA did not work for some time)

- Check for import in the future - not allowed

- Rename integration test and methods and test files in the integration test, as they test all cases
  - Also rename entities so that they have a name according to what is tested

- Checks
  - Test what happens with a delta import when there is no entry in the DB at all: homeassistant.exceptions.HomeAssistantError: No metadata found for statistics: ['sensor:test_case_2_ext'] Error Could be returned as info to the UI, do not use delta when there is no reference at all

- User doc
  - warning: do export before delta import, as more data are changed
  - all values in import must overwrite existing values in DB, there must not be additional values in DB between oldest and youngest import. Alternative: Merge, could make sense as delta is the important part, and I did it for case 2 test intuitively. Alternative: document.

- Add non-delta imports to the integration test

- Write a post

### Later
- youngest timestamp to import must be less than current hour -1
  - Remove check for future imports? During that?
- Test repo in other local storage, create developer documentation
- Is it possible to wait until async import task is ready?
- Setup a job to run the test in the pipeline as well, for pull requests
- In helpers.py/get_delta_stat, invalid rows should fail; search for # Silent failure - skip invalid rows, compare with import
  - Also in normal import an empty value is returned. I do not understand, maybe this is anyhow checked before already?
- Code duplication between handle_import_from_file and json
- Allow import of counter and sensor in one file
- Why isn't pandas directly used to read json? prepare_json_data_to_import does some manual stuff, necessary?
- Create arc-doc
- test_export_service.py: Separate to unit-tests and integration-tests
