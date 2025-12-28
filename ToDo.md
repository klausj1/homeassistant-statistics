# ToDos for Export

- Review integration tests and changes
- Export from real database (times should match when older than 10 days), and import into dev database; check if OK
- 2025-12-28 12:24:33.539 WARNING (MainThread) [homeassistant.helpers.frame] Detected that custom integration 'import_statistics' accesses the database without the database executor; Use homeassistant.components.recorder.get_instance(hass).async_add_executor_job() for faster database operations at custom_components/import_statistics/__init__.py, line 108: statistics_dict = statistics_during_period(. Please create a bug report at https://github.com/klausj1/homeassistant-statistics/issues