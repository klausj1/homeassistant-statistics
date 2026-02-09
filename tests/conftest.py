"""Shared pytest fixtures and utilities for tests."""

import _socket
import socket as socket_module
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def create_mock_recorder_instance() -> MagicMock:
    """Create a mock recorder instance with awaitable async_block_till_done."""
    mock_instance = MagicMock()
    mock_instance.async_block_till_done = AsyncMock()
    return mock_instance


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


def get_service_handler(hass: MagicMock, service_name: str) -> Callable[..., Any]:
    """
    Find a registered service handler by name from mock hass.services.async_register calls.

    Args:
        hass: Mock Home Assistant instance
        service_name: Name of the service (e.g., "export_statistics", "import_from_file")

    Returns:
        The service handler function

    Raises:
        ValueError: If the service handler is not found

    """
    for call in hass.services.async_register.call_args_list:
        # call_args_list contains Call objects with positional args at index 0
        if len(call[0]) >= 3 and call[0][1] == service_name:
            return call[0][2]
    msg = f"Service handler '{service_name}' not found in registered services"
    raise ValueError(msg)


def pytest_configure(config: Any) -> None:
    """Configure pytest."""
    config.addinivalue_line("markers", "integration: mark test as an integration test that requires sockets")
    config.addinivalue_line("markers", "unit_tests: mark test as a unit test")
    config.addinivalue_line("markers", "integration_tests_mock: mark test as an integration test with mocks")
    config.addinivalue_line("markers", "integration_tests: mark test as a full integration test")


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:  # noqa: ARG001
    """Enforce sequential test execution: unit_tests → integration_tests_mock → integration_tests."""
    test_order = {"tests/unit_tests": 0, "tests/integration_tests_mock": 1, "tests/integration_tests": 2}

    def get_test_order(item: Any) -> tuple[int, str]:
        """Get the execution order of a test based on its location."""
        for test_path, order in test_order.items():
            if test_path in str(item.fspath):
                return (order, str(item.fspath))
        return (999, str(item.fspath))

    items.sort(key=get_test_order)


def pytest_runtest_makereport(item: Any, call: Any) -> None:
    """Stop test execution if any test in earlier suites fail."""
    if call.when == "call" and call.excinfo is not None:
        # A test failed
        current_suite = None
        suite_order = {"tests/unit_tests": 0, "tests/integration_tests_mock": 1, "tests/integration_tests": 2}

        for test_path, order in suite_order.items():
            if test_path in str(item.fspath):
                current_suite = order
                break

        if current_suite is not None:
            # Mark that this suite has failed
            if not hasattr(item.config, "_test_suite_failed"):
                item.config._test_suite_failed = {}  # noqa: SLF001 type: ignore[attr-defined]
            item.config._test_suite_failed[current_suite] = True  # noqa: SLF001 type: ignore[attr-defined]


def pytest_runtest_setup(item: Any) -> None:
    """Skip tests in later suites if earlier suites have failed."""
    suite_order = {"tests/unit_tests": 0, "tests/integration_tests_mock": 1, "tests/integration_tests": 2}

    current_suite = None
    for test_path, order in suite_order.items():
        if test_path in str(item.fspath):
            current_suite = order
            break

    if current_suite is not None and hasattr(item.config, "_test_suite_failed"):
        failed_suites = item.config._test_suite_failed  # noqa: SLF001 type: ignore[attr-defined]
        for suite_order_num in range(current_suite):
            if failed_suites.get(suite_order_num, False):
                pytest.skip(f"Skipped because earlier test suite (order {suite_order_num}) failed")


@pytest.fixture
def allow_socket_for_integration() -> None:
    """Allow socket access for integration tests."""
    # Use monkeypatch-style approach to bypass pytest_socket
    # Get the real socket class before pytest wraps it
    real_socket_class = _socket.socket

    # Replace socket.socket temporarily with the real one
    original_socket = socket_module.socket
    socket_module.socket = real_socket_class  # type: ignore[assignment]

    yield

    # Restore the wrapped version
    socket_module.socket = original_socket
