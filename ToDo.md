# ToDos

## Next

### Docu
- Update screenshots and yaml examples in readme
- In Work Add settings descriptions to import, like what has been done on export.
- Before release, update changelog (bundle changes). Check for the export improvement changes. Check readme.
- Explain how to enable debug logging

### Bugs
- Done: Fix Issue[#167](https://github.com/klausj1/homeassistant-statistics/issues/167)
- Done? [#173](https://github.com/klausj1/homeassistant-statistics/issues/173)
- Fix lint issue after merge from drc


## Later

- Troubleshooting section, explain columns, UTF-8, spikes
- Check copilot review comments, see mail from 2026-01-10
- In some places, timestamps need to be sorted. But after pandas, timestamps are strings. So, we parse back the timestamps ... See commits on 2026-01-11 after 08:00
  - Not nice, but its not important for the performance. Committing the values to the DB takes the most time
- Remove startup of HA in integration test, throw error instead
- Setup a job to run the test in the pipeline as well, for pull requests
- Allow import of counter and sensor in one file
- test_export_service.py: Separate to unit-tests and integration-tests
- Why is export_json and export_tsv so different? Does it make sense or do we need a refactoring?
- handle_arguments is used in import, but not in export. Should me made consistent
- Collect errors, and exit only after complete checking is done
- Instead of OK, another text can be returned, but its not shown in the GUI. Its the state of an entity. Maybe create a file? Or forget it.
