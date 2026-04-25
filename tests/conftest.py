"""Empty conftest to disable package collection."""
import pytest


def pytest_configure(config):
    """Configure pytest to not try to import modules as packages."""
    config.addinivalue_line("markers", "slow: marks tests as slow")