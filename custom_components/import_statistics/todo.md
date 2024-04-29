# ToDo

- OK Distribute code to different files
- OK Fix bug with seconds in timestamp (only support minutes, and add tests for some “crazy” timestamp)
- OK Provide date string like %d.%m.%Y %H:%M as parameter (Allow different dateTime-formats)
- Check if entity with '.' exists
    - found out how to do this: use hass.states.get("sensor.sun_next_dawn"); this also returns the unit
    - Somehow done, manual check needed, esp. if nothing is imported
- Take the unit from existing entity
    - see above, hass.states.get
- Calculate sum automatically, based on the oldest existing value
    - last value of the history can be read with z = hass.components.recorder.get_instance(hass).async_add_executor_job(state_changes_during_period, hass, datetime_object, None, "sensor.sun_solar_azimuth", False, False, 1)

# Later

- Export data
    - Use a second service
        - also with reading the history
- Collect errors, and exist only after complete checking is done