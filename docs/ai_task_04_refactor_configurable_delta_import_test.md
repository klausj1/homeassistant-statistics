# Refactor configurable delta import test

## Reasoning

Currently the test test_import_delta_with_configurable_mock_data in tests/integration_tests_mock/test_import_service_with_delta.py mocks prepare_delta_handling. This was OK with the previous design. Its not OK anymore.

## Task description

Now, instead of mocking prepare_delta_handling, the helper methods called in _process_delta_references_for_statistic should be mocked. Again, the mocked values have to be calculated based on the same input data as the existing test.

_get_newest_db_statistic: Returns the newest value in the database per entity. This is the newest value of this entity in db_file_path.

_get_reference_before_timestamp:
- Per entity:
  - The first call to this method returns the time of t_oldest_import - 1 hour. If this time is <= the oldest value in db_file_path, return None instead.
  - If None is returned, there is a second call to this method. This call returns the time of t_youngest_import - 1 hour. If this time is <= the oldest value in db_file_path, return None instead.

_get_reference_at_or_after_timestamp:
- Per entity:
  - This call returns the time of t_newest_import. If this time is > than the newest value in db_file_path, return None instead.

For now, as in the current implementation, check for test_case_1 only.

## Acceptance criteria

Test is adapted accordingly.

Test runs without syntax errors.

Do NOT make the test green for now, I will check the results manually.

