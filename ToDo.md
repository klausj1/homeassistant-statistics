# ToDos for Export

- Review integration tests and changes
- Are the JSON integration tests working?
- Export from real database (times should match when older than 10 days), and import into dev database; check if OK
- Or rather copy the source to the real HA, and use that for testing export. The exported files can then be imported into the dev DB, and exported again, to see if everything is OK.
- Check: 2025-12-28 12:24:33.539 WARNING (MainThread) [homeassistant.helpers.frame] Detected that custom integration 'import_statistics' accesses the database without the database executor; Use homeassistant.components.recorder.get_instance(hass).async_add_executor_job() for faster database operations at custom_components/import_statistics/__init__.py, line 108: statistics_dict = statistics_during_period(. Please create a bug report at https://github.com/klausj1/homeassistant-statistics/issues
- Why is export_json and export_tsv so different? Does it make sense or do we need a refactoring?