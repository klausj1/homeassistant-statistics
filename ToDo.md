# ToDos

## for delta

- Remove startup of HA in integration test, throw error instead

- Check issues in repo. Future is fixed. Add to changelog.

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

- Write a post

- Release and post

### Later
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
