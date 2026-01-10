# Understanding counter statistics in Home Assistant

## Understanding Counter Statistics (sum/state)

Counters are entities with a state_class `increasing` or `total_increasing`.

Counter statistics (like energy meters) are more complex than sensor statistics. Here's what you need to know:

### What are `sum` and `state`?

| Column | Description | Example |
|--------|-------------|---------|
| **state** | The actual meter reading | `6913.045 kWh` (your meter shows this) |
| **sum** | Cumulative value since sensor creation | Can be identical to `state`, if the sensor started with 0 when connected to HA |
| **delta** | Change of `sum` in previous hour | `0.751 kWh` consumed this hour |

> `last_reset` is not explained. As long as the `sum` attribute increases monotonically, the integration should handle this fine.

### How Home Assistant Records Counter Statistics

The table below demonstrates how Home Assistant processes sensor state changes and converts them into (long term) statistics entries. Each row represents a point in time where either a state change occurs or an hourly statistics record is created.

**Column Definitions:**

- **currentTime**: The actual clock time when the observation is made
- **stateTime**: The timestamp when the entity's state was last updated (only populated when state changes occur)
- **state**: The current sensor value at that moment (only populated when state changes occur)
- **statisticsTime**: The timestamp assigned to the statistics record (typically the start of the hour)
- **statisticsState**: The state value stored in the statistics table for this hour
- **statisticsSum**: The cumulative sum value stored in the statistics table (used for calculating deltas). The sum value starts with 0 when the sensor has been created, and increases with the same amount as the state.
- **statisticsDelta**: The change of the value from the previous hour's statistics sum

> The statisticsDelta is not stored in the HA database, but it can be used for importing.

This demonstrates that:

1. State changes are recorded when they occur
2. At each hour boundary, a statistics entry is created using the most recent state value, with the timestamp one hour earlier
3. The delta is computed from the difference between consecutive statistics entries
4. The statistics timestamp represents the start of the period, not the time the record was created

| currentTime | stateTime | state | statisticsTime | statisticsState | statisticsSum | statisticsDelta | comment
|---|---|---|---|---|---|---|---|
|06:59:50|06:59:50|100|||||state changes
|07:00:00|||06:00:00|100|50||At 7 am, the current value 100 is used as the end value of the interval starting at 6 am, with the timestamp in the statistics 6 am. As this was the first value, no delta is available. Sum is 50 less then state.
|07:59:51|07:59:51|130|||||state changes
|08:00:00|||07:00:00|130|130|30|At 8 am, the current value 130 is used as the end value of the interval starting at 7 am, with the timestamp in the statistics 7 am. Delta is calculated from the statisticsSum: 130 - 100 = 30 (The difference of the state values is the same). The delta with the statistics timestamp 7 am is the difference of the statistic values at 7 am and 6 am (which are the values at 8 am and 7 am), so this delta is the state change between 8 am and 7 am, and gets the timestamp 7 am.

The energy board uses the sum, so the sum is the more important value. Also the delta-attribute in the statistics graph card uses the sum to calculate the delta.

Whats confusing (at least for me) is that in the statistics graph card, the sum in the graph always starts at 0, whereas the state shows the value from the statistics database.

For more details, see

- [Home Assistant blog](https://developers.home-assistant.io/blog/2021/08/16/state_class_total/).
- [Home Assistant documentation](https://developers.home-assistant.io/docs/core/entity/sensor/#state_class_total_increasing).

---

## Delta Import

Instead of importing absolute `sum`/`state` values, you can import **delta** values (the change per hour). This is useful because you

- do not need to calculate sum and state
- do not need to align sum and state values of the import with the sum and state values in the database, which can be a pain.

### How Delta Import Works

1. **Export your current data** using `export_statistics`
2. **Modify the file**:
   - Remove the `sum` and `state` columns
   - Keep or edit the `delta` column
   - Add/remove rows as needed
3. **Import the modified file** using `import_from_file`

The integration automatically converts deltas to absolute values using an existing database entry as reference point.

### Requirements

| Requirement | Details |
|-------------|---------|
| **Reference point** | At least one existing database value 1+ hour before or at/after your import range |
| **Complete coverage** | You must provide values for ALL hours in your import range, which exists in the database (no gaps). This is the case automatically when you start with the exported file |

> §KJ: Gaps see above or below??

### Delta Import Examples

<details>
<summary><strong>Example 1: Add historical data before sensor existed</strong></summary>

You have data from before your sensor was added to Home Assistant.

Use case: The sensor was not available in Home Assistant before, but there are other sources available

**Database before import:**
- 29.12.2025 08:00: sum=0, state=10
- 29.12.2025 09:00: sum=1, state=11
- 29.12.2025 10:00: sum=3, state=13

**Values to import:**

```tsv
statistic_id	start	unit	delta
sensor.imp_before	28.12.2025 09:00	kWh	10
sensor.imp_before	28.12.2025 10:00	kWh	20
sensor.imp_before	28.12.2025 11:00	kWh	30
```

**Result after import:**
- 28.12.2025 08:00: sum=-60, state=-50 (no delta available, as this is the first value in the database)
- 28.12.2025 09:00: sum=-50, state=-40 (delta: 10)
- 28.12.2025 10:00: sum=-30, state=-20 (delta: 20; sum and state calculated from first database value)
- 28.12.2025 11:00: sum=0, state=10 (delta: 30, connects to existing data, sum and state identical to first database value)
- 29.12.2025 08:00: sum=0, state=10 (existing, delta: 0)
- 29.12.2025 09:00: sum=1, state=11 (existing)
- 29.12.2025 10:00: sum=3, state=13 (existing)

</details>

<details>
<summary><strong>Example 2: Correct values in the middle</strong></summary>

Use case: Your sensor was offline and recorded wrong values.

Use case: Correct values in the middle of the timerange available in the database, e.g. if a sensor was not active for some time

**Database before import:**
- 29.12.2025 08:00: sum=0, state=10
- 29.12.2025 09:00: sum=1, state=11 (delta: 1)
- 29.12.2025 10:00: sum=3, state=13 (delta: 2)
- 29.12.2025 11:00: sum=6, state=16 (delta: 3)
- 29.12.2025 12:00: sum=10, state=20 (delta: 4)
- 29.12.2025 13:00: sum=15, state=25 (delta: 5)
- 29.12.2025 14:00: sum=21, state=31 (delta: 6)
- 29.12.2025 15:00: sum=28, state=38 (delta: 7)
- 29.12.2025 16:00: sum=36, state=46 (delta: 8)

**Values to import:**
```tsv
statistic_id	start	unit	delta
sensor:imp_inside	29.12.2025 09:00	kWh	2
sensor:imp_inside	29.12.2025 10:00	kWh	2
sensor:imp_inside	29.12.2025 11:00	kWh	2
sensor:imp_inside	29.12.2025 12:00	kWh	5
sensor:imp_inside	29.12.2025 13:00	kWh	5
sensor:imp_inside	29.12.2025 14:00	kWh	5
```

**Result after import:**
- 29.12.2025 08:00: sum=0, state=10 (unchanged, reference point)
- 29.12.2025 09:00: sum=2, state=12 (delta: 2, corrected)
- 29.12.2025 10:00: sum=4, state=14 (delta: 2, corrected)
- 29.12.2025 11:00: sum=6, state=16 (delta: 2, corrected)
- 29.12.2025 12:00: sum=11, state=21 (delta: 5, corrected)
- 29.12.2025 13:00: sum=16, state=26 (delta: 5, corrected)
- 29.12.2025 14:00: sum=21, state=31 (delta: 5, corrected)
- 29.12.2025 15:00: sum=28, state=38 (delta: 7, unchanged)
- 29.12.2025 16:00: sum=36, state=46 (delta: 8, unchanged)

> **Important**: Please note there is no "spike" at 29.12.2025 15:00 because the sum of the deltas between 29.12.2025 09:00 and 29.12.2025 14:00 is identical in the database and in the import (both are 21). If there is a difference, then the delta at 29.12.2025 15:00 would be different than before the import, which results in a wrong value at this timestamp e.g. in the energy board.

</details>

<details>
<summary><strong>Example 3: Add values after existing data</strong></summary>

Use case: Manually add consumption data for hours not yet in the database.

**Database before import:**
- 29.12.2025 08:00: sum=0, state=10
- 29.12.2025 09:00: sum=1, state=11
- 29.12.2025 10:00: sum=3, state=13

**Values to import:**
```tsv
statistic_id	start	unit	delta
sensor.imp_after	30.12.2025 09:00	kWh	10
sensor.imp_after	30.12.2025 10:00	kWh	20
sensor.imp_after	30.12.2025 11:00	kWh	30
```

**Result after import:**
- 29.12.2025 08:00: sum=0, state=10 (unchanged)
- 29.12.2025 09:00: sum=1, state=11 (unchanged)
- 29.12.2025 10:00: sum=3, state=13 (unchanged, reference point)
- 30.12.2025 09:00: sum=13, state=23 (delta: 10, new)
- 30.12.2025 10:00: sum=33, state=43 (delta: 20, new)
- 30.12.2025 11:00: sum=63, state=73 (delta: 30, new)

> **Warning**: Leaving "holes" create strange results
> If you don't import all DB values in the input time range, you'll create unexpected values. For example, if the database has values at 09:00, 10:00, 11:00, 12:00, 13:00, 14:00 and you only import deltas at 09:00 and 13:00, you will get strange results. You have to provide all values.
