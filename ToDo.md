# ToDos for Export

- Review integration tests and other changes

- Delete this file when done, there is another todo
- Create version and update real HA, do a quick test

## for delta

- get_oldest_statistics_before: Design bug, cannot be called once, as the oldest timestamp can be different per statistic ID. Change.
- In xxx, invalid rows should fail; search for # Silent failure - skip invalid rows, compare with import
- Delete integration test input files, they are not used
- When 1 (older history available) is working, implement 2-4.

### Later
- Code duplication between handle_import_from_file and json
  - JSON does not work anyhow
- Check what should be in init and what not; own file for HA-dependent helpers