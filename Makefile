# Makefile for freecad_tools

.PHONY: test test-unit test-integration test-all

# Default pytest flags
PYTEST_FLAGS ?=

# Path to FreeCAD Python (freecadcmd)
FREECAD_CMD ?= /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd

# Run all tests (unit only, without FreeCAD)
test: test-unit

# Run unit tests (without FreeCAD dependency)
test-unit:
	python3 -m pytest tests/ --ignore=tests/test_fc_export_integration.py $(PYTEST_FLAGS)

# Run integration tests (require FreeCAD)
test-integration:
	@if [ ! -x "$(FREECAD_CMD)" ]; then \
		echo "Error: FreeCAD not found at $(FREECAD_CMD)"; \
		echo "Set FREECAD_CMD environment variable or install FreeCAD"; \
		exit 1; \
	fi
	$(FREECAD_CMD) -c "import sys; sys.path.insert(0, 'tests'); sys.path.insert(0, 'tools'); import pytest; sys.exit(pytest.main(['tests/test_fc_export_integration.py', $(PYTEST_FLAGS)]))"

# Run all tests including integration
test-all: test-unit test-integration
