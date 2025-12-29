"""Shared pytest fixtures and utilities for tests."""

from collections.abc import Callable
from typing import Any


async def mock_async_add_executor_job(func: Callable[..., Any], *args: Any) -> Any:
    """
    Mock async_add_executor_job that executes the function.

    Args:
        func: Callable to execute
        *args: Arguments to pass to the callable

    Returns:
        Result of the function call

    """
    return func(*args) if args else func()
