"""Pytest configuration and shared fixtures for freecad_tools tests."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Check if we're running in FreeCAD's Python environment
# If FreeCAD is already in sys.modules (from freecadcmd initialization), we're in FreeCAD
_in_freecad = "FreeCAD" in sys.modules

# If FreeCAD is in sys.modules, verify it's real (not a mock)
if _in_freecad:
    from unittest.mock import MagicMock

    if isinstance(sys.modules["FreeCAD"], MagicMock):
        _in_freecad = False

# Only set test mode and mock FreeCAD if we're NOT in FreeCAD's Python
if not _in_freecad:
    # Set test mode environment variable before any imports
    # This tells fc_export.py to skip FreeCAD auto-detection
    os.environ["FREECAD_TOOLS_TEST_MODE"] = "1"

    # Mock FreeCAD and related modules before any code imports them
    # This prevents import errors when running tests without FreeCAD installed
    sys.modules["FreeCAD"] = MagicMock()
    sys.modules["FreeCADGui"] = MagicMock()
    sys.modules["Mesh"] = MagicMock()
    sys.modules["Part"] = MagicMock()
    sys.modules["Draft"] = MagicMock()
    sys.modules["Sketcher"] = MagicMock()
    sys.modules["Spreadsheet"] = MagicMock()


# Mock sys.exit to prevent fc_export.py from calling sys.exit() during import
def mock_exit(code=0):
    """Mock sys.exit to prevent termination during module import."""
    # During testing, we want to continue rather than exit
    pass


sys.exit = mock_exit


def pytest_configure(config):
    """Configure pytest to not try to import modules as packages."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "requires_freecad: marks tests that require FreeCAD")


# Test data paths
PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
TESTS_DIR = PROJECT_ROOT / "tests"


@pytest.fixture
def examples_dir():
    """Fixture providing path to examples directory with test data."""
    return EXAMPLES_DIR


@pytest.fixture
def example_fcstd_file():
    """Fixture providing path to example.FCStd test file."""
    fcstd_file = EXAMPLES_DIR / "example.FCStd"
    if not fcstd_file.exists():
        pytest.skip(f"Example FCStd file not found at {fcstd_file}")
    return fcstd_file


@pytest.fixture
def example_3mf_file():
    """Fixture providing path to example.3mf test file."""
    threedmf_file = EXAMPLES_DIR / "example.3mf"
    if not threedmf_file.exists():
        pytest.skip(f"Example 3MF file not found at {threedmf_file}")
    return threedmf_file


@pytest.fixture
def example_config_file():
    """Fixture providing path to example export config."""
    config_file = EXAMPLES_DIR / "config.yml"
    if not config_file.exists():
        pytest.skip(f"Example config file not found at {config_file}")
    return config_file


@pytest.fixture
def default_template_file():
    """Fixture providing path to default template 3MF."""
    template_file = EXAMPLES_DIR / "default.3mf"
    if not template_file.exists():
        pytest.skip(f"Default template not found at {template_file}")
    return template_file


@pytest.fixture
def template_print_settings_file():
    """Fixture providing path to template with printer settings."""
    template_file = PROJECT_ROOT / "templates" / "template_print_settings.3mf"
    if not template_file.exists():
        pytest.skip(f"Template print settings not found at {template_file}")
    return template_file
