"""Shared pytest fixtures and utilities for tests."""

from collections.abc import Callable
from typing import Any

import pytest


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


def pytest_configure(config: Any) -> None:
    """Configure pytest."""
    config.addinivalue_line("markers", "integration: mark test as an integration test that requires sockets")


@pytest.fixture
def allow_socket_for_integration() -> None:
    """Allow socket access for integration tests."""
    # Use monkeypatch-style approach to bypass pytest_socket
    import socket as socket_module

    # Get the real socket class before pytest wraps it
    real_socket_class = None

    # Try to find the original socket by looking in the standard library
    import _socket

    real_socket_class = _socket.socket

    # Replace socket.socket temporarily with the real one
    original_socket = socket_module.socket
    socket_module.socket = real_socket_class  # type: ignore

    yield

    # Restore the wrapped version
    socket_module.socket = original_socket
