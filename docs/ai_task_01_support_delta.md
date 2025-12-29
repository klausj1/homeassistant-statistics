# Support delta for counters

## Introduction

The action handle_import_from_file supports counters via the columns state and sum. Filling these columns can be hard, because you have to align with the existing values in the HA long term statistics database, otherwise you will get spikes.

## Support delta column

As additional, alternative approach, a column 'delta' shall be supported instead of state and sum.

The user provides values for delta, and this integration calculates the values for state and sum, and writes the calculated values to the HA long term statistics database via the methods async_import_statistics / async_add_external_statistics using the functionality of the existing code.

The delta is the difference of sum and state between two timestamps.

The delta is calculated as follows:

Let tImportOldest be the oldest timestamp to import.
Let tImportYoungest be the youngest timestamp to import.

- 1. if a value in the HA long term statistics database exists, which is at least 1 hour older than tImportOldest, then
  - read sumOldest and stateOldest from the HA long term statistics database using the timestamp tImportOldest minus 1 hour
  - If there is no timestamp tImportOldest minus 1 hour, take the next older existing timestamp from the HA long term statistics database and read stateOldest and sumOldest
  - The delta provided in the import Data from tImportOldest is used to calculate state and sum for tImportOldest as:
    - sum = sumOldest + delta
    - state = stateOldest + delta
  - Continue by adding the delta of the next timestamp (sorted by time ascending) to the sum and state of the previous timestamp
  - Do this until the end of the imported data exist
  - In this way, sum and state are aligned between the older existing history, and the imported older values. There may be a spike between the tImportYoungest and the younger existing values
- 2. else if a value in the HA long term statistics database exists, which is at least 1 hour younger than tImportYoungest
  - Use a similar approach as above, but start from the youngest timestamp and go to the oldest timestamp.
  - In this case you have to substract the delta from the state and sum of the younger timestamp, instead of adding the delta to sum and state of the older timestamp as above
  - In this way, sum and state are aligned between the younger existing history, and the imported younger values. There cannot be a spike on the older values, as no older values in the database exist
- 3. else if its an internal statistic, read the current sum and state plus the timestamp from HA (not from the database), use this as youngest sum, state, timestamp, and continue like in 2.
- 4. Error, import is not possible

If a delta column is present, sum and state must not be there.