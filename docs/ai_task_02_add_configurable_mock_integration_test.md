# Create configurable mocked integration test

## Motivation

In order to test the delta logic end2end without the need for a running home assistant before running full integration tests with home assistant, create a configurable mocked integration test, which uses the same input data and expected data as the integration test without mocking.

## Create test

Add the new test to tests/integration_tests_mock/test_import_service_with_delta.py.

For all files: Read the files in the test, do not hardcode the content.

1. As input data for mocking the values which exist in the database, use config/test_delta/test_case_1_sum_state.txt. Filter for the entities containing test_case_1 for now.
2. As data for the import, use config/test_delta/test_case_1_sum_delta_changed.txt.
3. As data for expectedValues, use config/test_delta/expected_after_step3_delta_changed.tsv.

You also have to mock get_oldest_statistics_before, as in the existing tests. Also this mock must be calculated based on the existing values in the database and the imported values. To calculate this per entity, fetch the oldest timestamp per entity from point 2 above, and then take the next older timestamp from point 1 above. If there is no such timestamp, return None.

Do not change other files than test_import_service_with_delta.py.

## Acceptance criteria

- the new test is running and returns OK
- do NOT care about the other tests
- ignore possible lint errors
