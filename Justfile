# Justfile for freecad_tools

set shell := ["bash", "-cu"]

test_config := "tests/export_test_config.yml"
container_engine := env_var_or_default("CONTAINER_ENGINE", "podman")
image_repo := env_var_or_default("IMAGE_REPO", "ghcr.io/ebirn/freecad_tools")
image_tag := env_var_or_default("IMAGE_TAG", "local")

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
    python3 tools/export.py {{test_config}} --gui-session run

# List export item names from test config
export-list:
    python3 tools/export.py {{test_config}} --list-exports

# Run a single export item by name, e.g. `just export-item basic_export`
export-item name:
    python3 tools/export.py {{test_config}} --name {{name}} --gui-session run

# Validate one export item (no export), e.g. `just export-item-dry-run basic_export`
export-item-dry-run name:
    python3 tools/export.py {{test_config}} --name {{name}} --dry-run --slicer-dry-run

# Print shell commands for all export items (auto-detected from YAML)
export-show-commands:
    python3 -c "import yaml; cfg=yaml.safe_load(open('{{test_config}}', encoding='utf-8')) or {}; ex=cfg.get('export', []); [print(f'python3 tools/export.py {{test_config}} --name {i.get(\"name\", \"\")} --gui-session run') for i in ex if i.get('name')]"

# Report XY extents from G-code, e.g. `just gcode-bounds test_output/gcode/file.gcode`
gcode-bounds file:
    python3 tools/gcode_bounds.py {{file}}

# Remove generated test output artifacts
clean:
    if [ -d "test_output" ]; then \
        rm -rf test_output/*; \
        echo "Removed test_output artifacts"; \
    else \
        echo "No test_output directory found"; \
    fi

# Build slim runtime image (Python-only)
build-image-slim:
    {{container_engine}} build \
        --target slim \
        -t {{image_repo}}:slim-{{image_tag}} \
        .

# Build FreeCAD runtime image (GUI-capable)
build-image-freecad:
    {{container_engine}} build \
        --target freecad \
        -t {{image_repo}}:freecad-{{image_tag}} \
        .

# Build both container image variants with standard tags
build-images: build-image-slim build-image-freecad

# Add conventional latest-style aliases to locally built images
tag-images:
    {{container_engine}} tag {{image_repo}}:slim-{{image_tag}} {{image_repo}}:latest
    {{container_engine}} tag {{image_repo}}:freecad-{{image_tag}} {{image_repo}}:freecad-latest

# Build both images and add latest aliases
build-and-tag-images: build-images tag-images
