# ToDo

- OK Distribute code to different files
- OK Fix bug with seconds in timestamp (only support minutes, and add tests for some “crazy” timestamp)
- OK Provide date string like %d.%m.%Y %H:%M as parameter (Allow different dateTime-formats)
- OK Check if entity with '.' exists
- OK Take the unit from existing entity

- Calculate sum automatically, based on the oldest existing value
- Requirement: [FR: Supply only the sum value, state automatically calculated · Issue #62 · klausj1/homeassistant-statistics · GitHub](https://github.com/klausj1/homeassistant-statistics/issues/62)
- Setting: Calculate state automatically (only sum or delta are provided); Default true, attention: overwriting is not possible afterwards with this setting
- Setting: Max Delta between oldest value in database and newset value in table (hours)
- Read first value from history, esp timestamp, sum, state. Test manually
    # This can be used to get the first value of an entity in the history
    # import state_changes_during_period from homeassistant.components.recorder.history
    # _LOGGER.debug("Start query")
    # z = hass.components.recorder.get_instance(hass).async_add_executor_job(state_changes_during_period, hass, datetime_object, None, "sensor.sun_solar_azimuth", False, False, 1)
    # # z is a future
    # while not z.done():
    #     time.sleep(0.001)
    # _LOGGER.debug(f"History of {entity_id}: {z.result()}")
- Tabelle einlesen mit delta
- Zeitliche Differenz zwischen jüngstem Wert in der Tabelle und dem ersten Wert checken. Der jüngste Wert in der Tabelle muss älter sein als der erste Wert. Maximale Differenz checken
- state und sum zur Tabelle hinzufügen, und von oben nach unten ausrechnen. Das sollte eigentlich kein Problem sein, schon gar nicht mit python
- Aufpassen, dass nur die wenigsten Methoden das hass-Objekt brauchen, wegen Unit-Tests
- TODO(Klaus): Test with UnitFrom.ENTITY in tests/test_are_columns_valid.py

- Import at least one real value before releasing a new version

# Later

- Export data
    - Use a second service
        - also with reading the history
- Collect errors, and exist only after complete checking is done