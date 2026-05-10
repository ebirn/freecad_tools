#!/usr/bin/env python3
"""
test_macros_bundled_python.py - Verify macros work with FreeCAD's bundled Python only.

This test suite can run in two contexts:
1. STANDALONE: /Applications/FreeCAD.app/Contents/Resources/bin/python tests/test_macros_bundled_python.py
   - Tests that macro_helper works without venv dependencies
   - FreeCAD module will not be available (expected)
   - Tests all bundled packages and macro imports

2. IN FREECAD: freecadcmd -c "exec(open('tests/test_macros_bundled_python.py').read())"
   - Tests that everything works inside FreeCAD GUI context
   - FreeCAD module will be available
   - Tests complete macro functionality

Key constraint: Macros must work STANDALONE in FreeCAD GUI without requiring:
- Virtual environment activation
- External pip packages (beyond what FreeCAD bundles)
- venv installation
"""

import sys
from pathlib import Path

# Track whether we're running inside FreeCAD
FREECAD_CONTEXT = False
try:
    import FreeCAD  # noqa: F401

    FREECAD_CONTEXT = True
except ImportError:
    FREECAD_CONTEXT = False


def test_yaml_available():
    """Verify PyYAML is available in FreeCAD's bundled packages."""
    try:
        import yaml  # noqa: F401

        print("[PASS] PyYAML available")
        return True
    except ImportError as e:
        print("[FAIL] PyYAML NOT available: " + str(e))
        return False


def test_qt_available():
    """Verify Qt (PySide6 or PySide2) is available."""
    try:
        try:
            from PySide6 import QtWidgets  # noqa: F401

            print("[PASS] PySide6.QtWidgets available")
            return True
        except ImportError:
            from PySide2 import QtWidgets  # noqa: F401

            print("[PASS] PySide2.QtWidgets available")
            return True
    except ImportError as e:
        if FREECAD_CONTEXT:
            print("[FAIL] Qt not available (should be in FreeCAD context): " + str(e))
            return False
        else:
            print("[SKIP] Qt not available (expected outside FreeCAD): " + str(e))
            return None  # None = expected in standalone context


def test_stdlib_available():
    """Verify all stdlib modules used by macros are available."""
    stdlib_modules = [
        "logging",
        "pathlib",
        "typing",
        "itertools",
        "decimal",
        "math",
    ]

    all_available = True
    for module_name in stdlib_modules:
        try:
            __import__(module_name)
            print("[PASS] stdlib." + module_name + " available")
        except ImportError as e:
            print("[FAIL] stdlib." + module_name + " NOT available: " + str(e))
            all_available = False

    return all_available


def test_macro_helper_imports():
    """Verify macro_helper.py can be imported with bundled packages only."""
    macros_dir = Path(__file__).parent.parent / "macros"
    if str(macros_dir) not in sys.path:
        sys.path.insert(0, str(macros_dir))

    try:
        import macro_helper  # noqa: F401

        print("[PASS] macro_helper.py imports successfully")
        return True
    except ImportError as e:
        print("[FAIL] macro_helper.py import failed: " + str(e))
        return False


def test_macro_helper_yaml_check():
    """Verify macro_helper correctly detects YAML availability."""
    macros_dir = Path(__file__).parent.parent / "macros"
    if str(macros_dir) not in sys.path:
        sys.path.insert(0, str(macros_dir))

    try:
        import macro_helper

        # In all contexts, with bundled PyYAML, this should be True
        if macro_helper.YAML_AVAILABLE:
            print("[PASS] macro_helper detected YAML availability")
            return True
        else:
            print("[FAIL] macro_helper did not detect YAML (CRITICAL: PyYAML must be bundled)")
            return False
    except Exception as e:
        print("[FAIL] macro_helper YAML check failed: " + str(e))
        return False


def test_macro_helper_functions():
    """Verify macro_helper key functions are callable."""
    macros_dir = Path(__file__).parent.parent / "macros"
    if str(macros_dir) not in sys.path:
        sys.path.insert(0, str(macros_dir))

    try:
        import macro_helper

        required_functions = [
            "get_macro_config_candidates",
            "load_macro_config",
            "save_macro_config",
            "load_or_prompt_config",
            "get_object_by_identifier",
            "get_objects_with_property",
            "get_body_property",
            "set_body_property",
            "find_exportable_bodies",
        ]

        all_present = True
        for func_name in required_functions:
            if hasattr(macro_helper, func_name):
                print("[PASS] macro_helper." + func_name + " available")
            else:
                print("[FAIL] macro_helper." + func_name + " NOT available")
                all_present = False

        return all_present
    except Exception as e:
        print("[FAIL] macro_helper functions check failed: " + str(e))
        return False


def test_macro_helper_freecad_check():
    """Verify macro_helper correctly detects FreeCAD availability."""
    macros_dir = Path(__file__).parent.parent / "macros"
    if str(macros_dir) not in sys.path:
        sys.path.insert(0, str(macros_dir))

    try:
        import macro_helper

        # Result depends on context
        if FREECAD_CONTEXT:
            if macro_helper.FREECAD_AVAILABLE:
                print("[PASS] macro_helper detected FreeCAD availability (in FreeCAD context)")
                return True
            else:
                print("[FAIL] macro_helper did not detect FreeCAD (expected in FreeCAD context)")
                return False
        else:
            # Standalone context - FreeCAD unavailable is expected
            if not macro_helper.FREECAD_AVAILABLE:
                print("[SKIP] FreeCAD unavailable (expected in standalone context)")
                return None
            else:
                print("[FAIL] macro_helper detected FreeCAD in standalone context (unexpected)")
                return False
    except Exception as e:
        print("[FAIL] macro_helper FreeCAD check failed: " + str(e))
        return False


def test_config_section_resolution():
    """Verify config section resolution works correctly."""
    macros_dir = Path(__file__).parent.parent / "macros"
    if str(macros_dir) not in sys.path:
        sys.path.insert(0, str(macros_dir))

    try:
        from macro_helper import _resolve_section

        # Test cases
        test_cases = [
            (
                {"macros": {"generate_variant_configs": {"test": "value"}}},
                "macros.generate_variant_configs",
                {"test": "value"},
            ),
            (
                {"macros": {"variant_array_assignment": {"array_label": "Test"}}},
                "macros.variant_array_assignment",
                {"array_label": "Test"},
            ),
            ({"simple": "value"}, "simple", None),  # Not a dict
            ({"nested": {"deep": {"value": "test"}}}, "nested.deep.value", None),  # Path doesn't resolve to dict
            ({}, "nonexistent", None),  # Missing section
        ]

        all_passed = True
        for config, section, expected in test_cases:
            result = _resolve_section(config, section)
            if result == expected:
                print("[PASS] _resolve_section('" + section + "') correct")
            else:
                print("[FAIL] _resolve_section('" + section + "') = " + str(result) + ", expected " + str(expected))
                all_passed = False

        return all_passed
    except Exception as e:
        print("[FAIL] config section resolution test failed: " + str(e))
        return False


def run_all_tests():
    """Run all tests and report summary."""
    context_label = "IN FREECAD" if FREECAD_CONTEXT else "STANDALONE"

    print("=" * 70)
    print("MACRO BUNDLED PYTHON TESTS (" + context_label + ")")
    print("=" * 70)
    print("")

    tests = [
        ("PyYAML Module", test_yaml_available),
        ("Qt Modules", test_qt_available),
        ("Stdlib Modules", test_stdlib_available),
        ("macro_helper.py Imports", test_macro_helper_imports),
        ("macro_helper YAML Detection", test_macro_helper_yaml_check),
        ("macro_helper FreeCAD Detection", test_macro_helper_freecad_check),
        ("macro_helper Functions", test_macro_helper_functions),
        ("Config Section Resolution", test_config_section_resolution),
    ]

    results = {}
    for test_name, test_func in tests:
        print("")
        print(test_name + ":")
        print("-" * 70)
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print("[FAIL] Test raised exception: " + str(e))
            import traceback

            traceback.print_exc()
            results[test_name] = False

    print("")
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    for test_name, result in results.items():
        if result is True:
            status = "[PASS]"
        elif result is False:
            status = "[FAIL]"
        else:
            status = "[SKIP]"
        print(status + " " + test_name)

    print("")
    print("Passed: " + str(passed) + ", Failed: " + str(failed) + ", Skipped: " + str(skipped))
    print("Context: " + context_label)
    print("")

    if failed > 0:
        print("TESTS FAILED - Macro dependencies incomplete")
        return False
    else:
        print("ALL TESTS PASSED - Macros work with FreeCAD bundled packages only")
        return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success is True else 1)
