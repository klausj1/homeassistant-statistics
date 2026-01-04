# Refactor delta import

Note: Alle times read from a file are using local timezone.

The current design before the planned refactoring see ARCHITECTURE.md.

## Refactoring sesign

prepare_data_to_import should not call handle_dataframe, but instead return my_df, timezone_identifier, datetime_format, unit_from_entity, delta (new; bool) to the caller.

prepare_data_to_import must not use hass.

The callers (handle_import_from_file_impl, handle_import_from_json_impl) continue after prepare_data_to_import returns.

The hack using _DELTA_PROCESSING_NEEDED is not necessary anymore.

If its not delta, call handle_dataframe_no_delta. This method should get the non-delta logic from the current handle_dataframe. No further changes for no delta.

### delta

The delta logic needs further information from the HA database to be able to continue.

handle_dataframe_delta shall be HA independent and only called when all the needed information is there.

Create an own method prepare_delta_handling in import_service which collects this information from the database.

This method needs to check if the time range available in the database intersects with the timerange of the import, and if the intersection is at the start of the import time range or at the end. If there is no intersection, calculation with delta is not possible. If the time range of the database is contained in the time range of the import, calculation with delta is not possible.
This is done as follows:
- fetches t_oldest_import and t_youngest_import per entity from my_df. These are the oldest / youngest timestamp to be imported (this is currently done in handle_dataframe)
- fetches t_youngest_db per entity from the HA database. This should be done using get_last_statistics as in get_youngest_statistic_after
- Another check must be added: If t_youngest_import is younger than t_youngest_db, return the error "Importing values younger than the youngest value in the database is not possible".
- fetches t_youngest_db_time_before_oldest_import per entity from the HA database. This is the youngest value in the database which is older than t_oldest_import, or None if no such value exists (this is currently done in get_oldest_statistics_before; in addition a check must be added if t_youngest_db is younger or equal than t_oldest_import. If this is not the case, return an error ("imported timerange is completely newer than timerange in DB"). This method should be moved to import_service.py, and it should not call get_youngest_statistic_after anymore)
- For all entities where t_youngest_db_time_before_oldest_import is none:
  - fetch t_youngest_db_time_before_youngest_import per entity from the HA database. This is the youngest value in the database which is older than t_youngest_import. Use _get_reference_stats with the t_youngest_import to determine this. If there is no such value, return an error "imported timerange is completely older than timerange in DB".
  - fetch t_oldest_db_time_after_youngest_import. This is the oldest value in the database which is younger or equal than t_youngest_import. If no such value exists, return the error "imported timerange completely overlaps timerange in DB" (this is currently done in get_youngest_statistic_after, but it does not take the oldest value younger than t_youngest_import, but the youngest - correct this. To correct this, query all values from the database between t_youngest_import and the value found via get_last_statistics, and from there take the youngest value.)
- If there was no error until here, either t_youngest_db_time_before_oldest_import or t_oldest_db_time_after_youngest_import must have been set. Otherwise, return an implementation error.
- Make sure to store not only the timestamps for t_youngest_db_time_before_oldest_import and t_oldest_db_time_after_youngest_import, but also state and sum.
- Make sure to include entity in the error message, and if relevant also the timestamp

When we are here without an error, we have all the needed data ho handle the import without further reads from the database.

Call handle_dataframe_delta (this is currently named "convert_delta_dataframe_with_references" - rename it). Provide my_df, timezone_identifier, datetime_format, unit_from_entity, and (t_youngest_db_time_before_oldest_import and t_oldest_db_time_after_youngest_import per entity) to this method. If it makes sense, use the same structure for t_youngest_db_time_before_oldest_import and t_oldest_db_time_after_youngest_import per entity as currently.

This method returns stats, which can then be written to the database like now.

The method handle_dataframe_delta should be used in the test test_import_delta_with_configurable_mock_data instead of _build_mock_reference.

## Tasks

Create a design based on the description above. Do not include the implementation of the methods, but the signatures and the file they are in, and mention the changes to the current solution.
Check the dependencies and if there are existing methods which are not needed anymore.
Describe the effect on the tests. Which tests are not needed anymore, which new tests are needed. Esp. prepare_delta_handling needs thorough unit testing to test all scenarios including the error scenarios described above (this is a new method, do not reuse existing unit tests for this, create new tests). Also handle_dataframe_delta needs thorough unit testing, current unit tests could be used for this.
Do not start any implementation.
