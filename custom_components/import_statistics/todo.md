# ToDo

- OK Distribute code to different files
- OK Fix bug with seconds in timestamp (only support minutes, and add tests for some “crazy” timestamp)
- OK Provide date string like %d.%m.%Y %H:%M as parameter (Allow different dateTime-formats)
- OK Check if entity with '.' exists
- Take the unit from existing entity
    - see above, hass.states.get
    - add setting take unit from entity
    - are_columns_valid: unit is not necessary if taken from entity, but only for '.'
    - fill unit before calling hass methods, and check if unit is available (necessary? if there was no unit before, also fine)
- Calculate sum automatically, based on the oldest existing value
    - last value of the history can be read with z = hass.components.recorder.get_instance(hass).async_add_executor_job(state_changes_during_period, hass, datetime_object, None, "sensor.sun_solar_azimuth", False, False, 1)
- Import at least one real value before releasing a new version

# Later

- Export data
    - Use a second service
        - also with reading the history
- Collect errors, and exist only after complete checking is done