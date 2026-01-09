# Waiting for Recorder Statistics to be Written to Database

## Problem

The Home Assistant recorder functions [`async_add_external_statistics()`](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/statistics.py:2690) and [`async_import_statistics()`](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/statistics.py:2655) do not directly write to the database. Instead, they queue an `ImportStatisticsTask` in the recorder's processing queue.

The recorder processes these tasks asynchronously in a separate thread, so simply awaiting the async method is not sufficient to ensure the data has been written to the database.

## Solution

### Option 1: Use Recorder's `async_block_till_done()` method

The best approach is to use the recorder instance's built-in [`async_block_till_done()`](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/core.py:1294) method:

```python
from homeassistant.components.recorder import get_instance

# After calling async_add_external_statistics or async_import_statistics
await get_instance(hass).async_block_till_done()
```

This method:
1. Checks if the queue is empty and there are no pending writes
2. If there's work pending, creates a `SynchronizeTask` with a future
3. Waits for that future to be resolved (which happens after the next commit)

### Option 2: Get a commit future directly

For more granular control, use [`async_get_commit_future()`](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/core.py:1300):

```python
from homeassistant.components.recorder import get_instance

# After calling statistics import functions
if future := get_instance(hass).async_get_commit_future():
    await future
```

This returns:
- `None` if the queue is empty and there are no pending writes
- An `asyncio.Future` that resolves after the next commit

### Option 3: Simple sleep (not recommended for production)

For integration tests where you don't have direct access to the hass object, you can use a simple sleep:

```python
await asyncio.sleep(3)  # Wait for recorder to process and commit
```

This is less reliable but works in test scenarios where timing is predictable.

## How the Recorder Queue Works

1. **Queuing**: When you call `async_add_external_statistics()` or `async_import_statistics()`, the function validates the data and calls `get_instance(hass).async_import_statistics(metadata, statistics, table)` ([line 2651](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/statistics.py:2651))

2. **Task Creation**: This creates an `ImportStatisticsTask` and adds it to the recorder's queue via `queue_task()` ([line 618](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/core.py:618))

3. **Processing**: The recorder thread processes tasks from the queue in `_run_event_loop()` ([line 823](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/core.py:823))

4. **Database Write**: The `ImportStatisticsTask.run()` method calls `import_statistics()` which writes to the database within a session scope ([line 2820](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/statistics.py:2820))

5. **Commit**: The session is committed, making the data persistent

## Implementation in Integration Tests

For integration tests that use REST API calls (without direct hass access), we've added a helper method:

```python
@staticmethod
async def _wait_for_recorder_commit(ha_url: str = "http://localhost:8123", token: str = "") -> None:
    """Wait for the recorder to commit all pending statistics to the database."""
    # Give the recorder time to process queued tasks and commit
    await asyncio.sleep(3)
```

This is used after each import/export service call to ensure the recorder has finished processing before verifying results.

## Key Takeaways

1. **Never assume immediate writes**: Statistics import functions only queue tasks
2. **Always wait for commits**: Use `async_block_till_done()` or `async_get_commit_future()`
3. **For tests**: Use the recorder's synchronization methods or add appropriate delays
4. **Queue processing is asynchronous**: The recorder runs in its own thread with its own event loop

## References

- [`Recorder.async_block_till_done()`](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/core.py:1294)
- [`Recorder.async_get_commit_future()`](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/core.py:1300)
- [`Recorder.async_import_statistics()`](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/core.py:610)
- [`import_statistics()`](../../home/vscode/.local/lib/python3.13/site-packages/homeassistant/components/recorder/statistics.py:2820)
