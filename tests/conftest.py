"""Shared pytest hooks and fixtures."""

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach the test docstring so pytest includes it in failure output."""
    outcome = yield
    report = outcome.get_result()
    if call.when == "call" and item.obj.__doc__:
        report.description = item.obj.__doc__.strip().split("\n", 1)[0]
