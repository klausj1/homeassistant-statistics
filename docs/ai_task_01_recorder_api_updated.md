# Recorder API - Updated Clarification

## Home Assistant Recorder API - Specialized Methods

After your feedback, discovered there are **specialized methods** for querying statistics at specific timestamps:

### For Case 1 (Older Reference - Before tImportOldest)

**Function**: `_statistics_at_time()` 
- **Location**: Internal recorder function (requires access to recorder instance)
- **Purpose**: Return last known statistics **earlier than** start_time
- **Signature**:
```python
def _statistics_at_time(
    instance: Recorder,
    session: Session,
    metadata_ids: set[int],
    table: type[StatisticsBase],
    start_time: datetime,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]]
) -> Sequence[Row] | None
```

**Important Notes**:
- Private function (starts with `_`), but still usable
- Requires Recorder instance, Session, and metadata IDs (more low-level)
- Returns rows earlier than start_time
- Exactly what we need for Case 1

### For Case 2 (Younger Reference - After tImportYoungest)

**Function**: `get_last_statistics()`
- **Location**: Public recorder API
- **Purpose**: Return the last N statistics for a statistic_id
- **Signature**:
```python
def get_last_statistics(
    hass: HomeAssistant,
    number_of_stats: int,
    statistic_id: str,
    convert_units: bool,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]]
) -> dict[str, list[StatisticsRow]]
```

**Returns**:
```python
{
    "statistic_id": [
        {"start": datetime, "end": datetime, "sum": float, "state": float, ...},
        ...  # up to number_of_stats records
    ]
}
```

**Perfect for Case 2**:
- Get last N statistics
- Filter to find first record ≥ 1 hour after tImportYoungest
- Returns newest values to work backward from

## Updated Implementation Strategy

### Case 1: Use `_statistics_at_time()`

**Advantage**: Direct query for "give me data before timestamp"
**Complexity**: Need to:
1. Get metadata_id from statistic_id using `get_metadata()`
2. Get table type from recorder (StatisticsMean or StatisticsShortTerm)
3. Call `_statistics_at_time()` with proper session

**Location**: In `__init__.py` where recorder instance is available

```python
async def get_oldest_statistic_before(
    hass: HomeAssistant,
    statistic_id: str,
    before_timestamp: datetime
) -> dict | None:
    """Get statistic value(s) from just before the given timestamp."""
    recorder_instance = get_instance(hass)
    
    # Get metadata to find metadata_id
    metadata = await recorder_instance.async_add_executor_job(
        lambda: get_metadata(hass, statistic_ids={statistic_id})
    )
    
    if not metadata:
        return None
    
    metadata_id, meta_data = metadata[statistic_id]
    
    # Call _statistics_at_time via executor
    result = await recorder_instance.async_add_executor_job(
        lambda: recorder_instance._statistics_at_time(
            session=...,  # Get from recorder
            metadata_ids={metadata_id},
            table=...,    # Determine from meta_data
            start_time=before_timestamp,
            types={"sum", "state"}
        )
    )
    
    return result[0] if result else None
```

### Case 2: Use `get_last_statistics()`

**Advantage**: Public API, simple interface
**Implementation**:

```python
def get_newest_statistics_after(
    hass: HomeAssistant,
    statistic_id: str,
    after_timestamp: datetime
) -> dict | None:
    """Get statistic value(s) from just after the given timestamp."""
    
    # Get recent statistics (e.g., last 10)
    result = get_last_statistics(
        hass,
        number_of_stats=10,
        statistic_id=statistic_id,
        convert_units=False,
        types={"sum", "state"}
    )
    
    if not result or statistic_id not in result:
        return None
    
    stats_list = result[statistic_id]
    
    # Filter: find first record >= 1 hour after after_timestamp
    min_timestamp = after_timestamp + timedelta(hours=1)
    for stat in stats_list:
        if stat['start'] >= min_timestamp:
            return stat
    
    return None
```

## Design Implications

**Simplified Approach**:
1. **Case 1**: Use `_statistics_at_time()` - direct before-query
2. **Case 2**: Use `get_last_statistics()` - get recent, filter for after
3. **Both**: Async via executor, require recorder instance

**Advantages**:
- ✅ Direct timestamp queries (no 30-day window guessing)
- ✅ Precise filtering (find exact records we need)
- ✅ Matches existing recorder usage patterns
- ✅ Public API for Case 2 (stable)

**Trade-off**:
- Case 1 uses private API (`_statistics_at_time`), but it's the right tool for the job

## Testing Impact

**Mocking simplification**:
- Can mock `_statistics_at_time()` return value directly
- Can mock `get_last_statistics()` return value directly
- No need to mock entire time-period query + filtering

**More precise test cases**:
- Test exact timestamp matching
- Test 1-hour boundary conditions
- Test missing data scenarios
