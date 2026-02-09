# ToDos

## Unsorted backlog

- Check copilot review comments, see mail from 2026-01-10
- In some places, timestamps need to be sorted. But after pandas, timestamps are strings. So, we parse back the timestamps ... See commits on 2026-01-11 after 08:00
  - Not nice, but its not important for the performance. Committing the values to the DB takes the most time
- Remove startup of HA in integration test, throw error instead
- Setup a job to run the test in the pipeline as well, for pull requests
- Allow import of counter and measurement in one file
- test_export_service.py: Separate to unit-tests and integration-tests
- Why is export_json and export_tsv so different? Does it make sense or do we need a refactoring?
- handle_arguments is used in import, but not in export. Should me made consistent
- Collect errors, and exit only after complete checking is done
- Support webserver, so that its not necessary to upload import file and download export file
