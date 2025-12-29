# ToDos

## for Export

- Review integration tests and other changes

## for delta

- Setup test system
  - Export counters and sensors from real HA, or find already exported data
  - Create template sensors for counter and for sensor with the same name
  - Test import functionality without delta (with "Verlauf" tab)
  - Test import with delta
- When 1 (older history available) is working, implement 2-4.

### Later
- In helpers.py/get_delta_stat, invalid rows should fail; search for # Silent failure - skip invalid rows, compare with import
  - Also in normal import an empty value is returned. I do not understand, maybe this is anyhow checked before already?
- Code duplication between handle_import_from_file and json
  - JSON does not work anyhow
- Check what should be in init and what not; own file for HA-dependent helpers