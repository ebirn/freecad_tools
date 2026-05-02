# Justfile for freecad_tools

set shell := ["bash", "-cu"]

# Run all tests (unit only, without FreeCAD)
test: test-unit

# Run unit tests (without FreeCAD dependency)
test-unit:
    python3 -m pytest tests/ --ignore=tests/test_fc_export_integration.py ${PYTEST_FLAGS:-}

# Run integration tests (require FreeCAD)
test-integration:
    freecad_cmd="${FREECAD_CMD:-/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd}"; \
    if [ ! -x "$freecad_cmd" ]; then \
        echo "Error: FreeCAD not found at $freecad_cmd"; \
        echo "Set FREECAD_CMD environment variable or install FreeCAD"; \
        exit 1; \
    fi; \
    "$freecad_cmd" -c "import sys; sys.path.insert(0, 'tests'); sys.path.insert(0, 'tools'); import pytest; sys.exit(pytest.main(['tests/test_fc_export_integration.py', ${PYTEST_FLAGS:-}] ))"

# Run all tests including integration
test-all: test-unit test-integration

# Practical full-feature run using test config
export:
    python3 tools/export.py tests/export_test_config.yml --gui-session run

# Remove generated test output artifacts
clean:
    if [ -d "test_output" ]; then \
        rm -rf test_output/*; \
        echo "Removed test_output artifacts"; \
    else \
        echo "No test_output directory found"; \
    fi
