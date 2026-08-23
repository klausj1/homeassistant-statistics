# ToDos

## Now

## Bugs

Unit can be empty: Remove get_unit_from_row. Later on its checked anyhow if the unit matches

## Unsorted backlog

- Support webserver, so that its not necessary to upload import file and download export file
- Collect errors, and exit only after complete checking is done -> when we have a UI
- Align the keys in the json with yaml (breaking change, or make it compatible)

## Export

- test_export_service.py: Separate to unit-tests and integration-tests
- handle_arguments is used in import, but not in export. Should me made consistent
- custom_components/import_statistics/export_service_helper.py / get_delta_from_stats has "except (ValueError, AttributeError):" twice, without explanation. Hard to understand.
