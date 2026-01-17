# ToDos

- Troubleshooting section, explain columns, UTF-8, spikes.
  - Done by AI
  - Review docs/troubleshooting-tips.md
  - Search for "Check the delta import documentation" and align
- What is the repair functionality in the developer tools / statistic tab doing?
  - It updates the existing sum from the selected time to the neweset value in the database. Seems fine. Add this to my documentation.

### Later

- Add UTF8-check to import?
- Instead of OK, another text can be returned, but its not shown in the GUI. Its the state of an entity. Maybe create a file? Or forget it.
- Check copilot review comments, see mail from 2026-01-10
- Do not fail silently also for other imports
- In some places, timestamps need to be sorted. But after pandas, timestamps are strings. So, we parse back the timestamps ... See commits on 2026-01-11 after 08:00
  - Not nice, but its not important for the performance. Committing the values to the DB takes the most time
- Export has a timezone identifier as default, import not. Or probably wrong, that only happens when you change from an empty Yaml back to the GUI
- Remove startup of HA in integration test, throw error instead
- Setup a job to run the test in the pipeline as well, for pull requests
- In helpers.py/get_delta_stat, invalid rows should fail; search for # Silent failure - skip invalid rows, compare with import
  - Also in normal import an empty value is returned. I do not understand, maybe this is anyhow checked before already?
  - Fixed for counters, at least for delta
- Allow import of counter and sensor in one file
- Create arc-doc
- test_export_service.py: Separate to unit-tests and integration-tests
- Why is export_json and export_tsv so different? Does it make sense or do we need a refactoring?
- handle_arguments is used in import, but not in export. Should me made consistent
- Collect errors, and exit only after complete checking is done
- Improve changelog

