# ToDos

## for Export

- Review integration tests and other changes

## for delta

- Document mcp-server installation. In container use /home/vscode/.vscode-server/data/User/mcp.json
  - See docs/mcp/mcp.json.
  - For roo see https://docs.roocode.com/features/mcp/using-mcp-in-roo
  - Worked only after pressing refresh servers a number of times (in roo / settings / mcp). Roo-config see docs/mcp/mcp.roo.json
  - Try with input variables instead of fixed token

- Setup test system
  - OK Export counters and sensors from real HA, or find already exported data
  - OK Create template sensors for counter and for sensor with the same name
  - Import does not work for counters, entity does not exist error (temperatures are OK)
  - Export hat erst ab September exportiert, obwohl das ganze Jahr angegeben wurde
  - Test import functionality without delta (with "Verlauf" tab)
  - Test import with delta
- When 1 (older history available) is working, implement 2-4.

### Later
- Setup a job to run the test in the pipeline as well, for pull requests
- In helpers.py/get_delta_stat, invalid rows should fail; search for # Silent failure - skip invalid rows, compare with import
  - Also in normal import an empty value is returned. I do not understand, maybe this is anyhow checked before already?
- Code duplication between handle_import_from_file and json
  - JSON does not work anyhow
- Check what should be in init and what not; own file for HA-dependent helpers
