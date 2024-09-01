# ToDo

- OK Distribute code to different files
- OK Fix bug with seconds in timestamp (only support minutes, and add tests for some “crazy” timestamp)
- OK Provide date string like %d.%m.%Y %H:%M as parameter (Allow different dateTime-formats)
- OK Check if entity with '.' exists
- OK Take the unit from existing entity

- Calculate sum automatically, based on the oldest existing value
    - last value of the history can be read with z = hass.components.recorder.get_instance(hass).async_add_executor_job(state_changes_during_period, hass, datetime_object, None, "sensor.sun_solar_azimuth", False, False, 1)
    # This can be used to get the first value of an entity in the history
# _LOGGER.debug("Start query")
# z = hass.components.recorder.get_instance(hass).async_add_executor_job(state_changes_during_period, hass, datetime_object, None, entity_id, False, False, 1)
# # z is a future
# while not z.done():
#     time.sleep(0.001)
# _LOGGER.debug(f"History of {entity_id}: {z.result()}")
- Import at least one real value before releasing a new version

# Later

- Export data
    - Use a second service
        - also with reading the history
- Collect errors, and exist only after complete checking is done