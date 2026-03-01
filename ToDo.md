# ToDos

## Unsorted backlog

- Support webserver, so that its not necessary to upload import file and download export file
- Allow import of counter and measurement in one file
- Collect errors, and exit only after complete checking is done -> when we have a UI

## Export

- test_export_service.py: Separate to unit-tests and integration-tests
- handle_arguments is used in import, but not in export. Should me made consistent
- custom_components/import_statistics/export_service_helper.py / get_delta_from_stats has "except (ValueError, AttributeError):" twice, without explanation. Hard to understand.
