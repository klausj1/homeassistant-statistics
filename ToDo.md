# ToDos

## for delta

- Write a post

- Release and post

### Later

- Check copilot review comments, see mail from 2026-01-10
- Do not fail silently also for other imports
- In some places, timestamps need to be sorted. But after pandas, timestamps are strings. So, we parse back the timestamps ... See commits on 2026-01-11 after 08:00
- Export has a timezine identifier as default, import not
- Remove startup of HA in integration test, throw error instead

- Developer doc
  - Open in devcontainer
  - run ha with scripts/develop manually
  - get token
  - now
    - either
      - In host, set environment variable
      - rebuild container (then in all shells the variable is set, including AI clients)
    - or
      - set env variable in container (.env)
      - make sure that before running pytest HA_TOKEN_DEV is set
- Test repo in other local storage, create developer documentation
- Setup a job to run the test in the pipeline as well, for pull requests
- In helpers.py/get_delta_stat, invalid rows should fail; search for # Silent failure - skip invalid rows, compare with import
  - Also in normal import an empty value is returned. I do not understand, maybe this is anyhow checked before already?
- Allow import of counter and sensor in one file
- Create arc-doc
- test_export_service.py: Separate to unit-tests and integration-tests
- Why is export_json and export_tsv so different? Does it make sense or do we need a refactoring?
- handle_arguments is used in import, but not in export. Should me made consistent
- Collect errors, and exit only after complete checking is done
- Improve changelog

