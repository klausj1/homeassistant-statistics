# ToDos

## Now

Bugs:

fix: exception with wrong datetime_format / delimiter in service calls

- Import from file with wrong datetime_format (datetime_format: "%d.%m.%Y %H:%xxxMsss") leads to exception instead of an error. Add a test which finds the bug, then fix
- Import from file with wrong delimiter (delimiter: x) leads to exception. Add a test which finds the bug, then fix
- Add Unit tests for these methods. If they find bugs, fix the bugs: _parse_import_timestamps, collect_dataframe_validation_errors, _collect_validation_errors, _validate_dataframe_for_import, _validation_errors_from_exception, _validate_local_import_data

Manual Tests:

- Export, make multiple errors (wrong time, no list, split_by, validCounterFieldValues)
- JSON export with and without errors

Afterwards improve the names of the service response

imported_values -> imported_rows

new_data -> entities_with_new_data
existing_data -> entities_with_existing_data
no_data -> entities_without_any_data

## Bugs

Unit can be empty: Remove get_unit_from_row. Later on its checked anyhow if the unit matches

## Unsorted backlog

- Create a performance test for import and export, which measures the total performance, and writes the INFO traces and the duration to somewhere (run pytest -s to see the output)
- Support webserver, so that its not necessary to upload import file and download export file
- Align the keys in the json with yaml (breaking change, or make it compatible)
- skip unknown entities also for export

## Export

- test_export_service.py: Separate to unit-tests and integration-tests
- handle_arguments is used in import, but not in export. Should me made consistent
- custom_components/import_statistics/export_service_helper.py / get_delta_from_stats has "except (ValueError, AttributeError):" twice, without explanation. Hard to understand.
