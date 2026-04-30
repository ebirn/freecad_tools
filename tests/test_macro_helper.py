#!/usr/bin/env python3
"""Basic import/guard tests for FreeCAD macro helpers.

These tests run outside FreeCAD. They ensure importing macro_helper does not
crash when Qt/FreeCAD are not available.
"""

import sys
from pathlib import Path


def test_macro_helper_import_and_dialog_guard():
    macros_dir = Path(__file__).parent.parent / "macros"
    sys.path.insert(0, str(macros_dir))
    try:
        import macro_helper

        # In unit test runs, FreeCAD is mocked by conftest; macro_helper should
        # treat that as not available.
        assert macro_helper.FREECAD_AVAILABLE is False
        assert macro_helper.show_config_dialog(title="Test", fields=[]) is None
    finally:
        sys.path.remove(str(macros_dir))
