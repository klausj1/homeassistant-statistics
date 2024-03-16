# ToDo

- What shall be checked?
  - OK New statistic ID
    - OK . oder : contained
    - NOK for '.': entity must exist: Does not work for test, needs hass-object
- Tests for row
  - Row:
    - OK Timestamp
    - OK valid number (float)
    - OK min <= mean <=max
- OK Tests for columns
    - OK Check without unit column
- OK Tests for handle_dataframe
- Tests for _prepare_data_to_import
    - NOK: Dezimal-separator geht scheinbar nicht ... Check auskommentierten test in test_prepare_data_to_import.py
    - Falsches float-Format, geht das da schon?

- Manual tests
- Create version 1.0, adapt also HACS to this

- Distribute to more files
- Enhance readme with problems from forum

## Later

- Provide date string like %d.%m.%Y %H:%M as parameter