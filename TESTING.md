# Testing Strategy for freecad_tools

This document describes the testing approach for agents developing or maintaining freecad_tools.

## Test Organization

```
tests/
├── __init__.py           # Package marker
├── test_3mf.py         # 3MF file validation (standalone)
├── test_export.py       # FreeCAD document inspection (requires FreeCAD)
├── test_yaml.py         # YAML config parsing (requires config)
├── test_git_utils.py   # Git utilities (unit tests)
└── test_lib3mf_utils.py # 3MF creation utilities (unit tests)
```

## Test Categories

### 1. Unit Tests (No External Dependencies)

**Run anywhere** - These tests use mock data and don't require FreeCAD or external files.

- `test_git_utils.py` - Tests for `git_utils.py` functions
- `test_lib3mf_utils.py` - Tests for STL parsing logic (with temporary STL files)

**Run with:**
```bash
python -m pytest tests/test_git_utils.py tests/test_lib3mf_utils.py -v
```

### 2. Integration Tests (Requires Complete Setup)

**Requires:**
- FreeCAD installed
- Sample FCStd files in `examples/`
- lib3mf installed in the venv

- `test_export.py` - Opens example.FCStd, inspects objects
- `test_3mf.py` - Validates generated 3MF files

**Run from project directory:**
```bash
python tools/export.py
python -m pytest tests/test_3mf.py -v
```

### 3. Validation Tests (Post-Export)

Validates output from completed exports.

- `test_3mf.py` - Validates 3MF file structure

## Running All Tests

### Quick Test (No FreeCAD Required)
```bash
cd /path/to/freecad_tools
python -m pytest tests/test_git_utils.py tests/test_lib3mf_utils.py -v
```

### Full Test (Requires FreeCAD)
```bash
cd /path/to/freecad_tools/examples
python ../tools/export.py
python -m pytest ../tests/ -v
```

## Test Fixtures

### Sample Files in `examples/`

| File | Purpose |
|------|---------|
| `example.FCStd` | Simple FreeCAD document with multiple bodies |
| `example.3mf` | Reference 3MF output for validation comparison |
| `default.3mf` | Template 3MF with printer settings |
| `export_config.yml.example.yml` | Example export configuration |

### Test Data Locations

- **Expected 3MF output**: `examples/example.3mf`
- **Expected STL files**: Generated in `examples/prints/stl/`
- **Expected 3MF from export**: `examples/prints/example.3mf`

## Writing New Tests

### Unit Test Template

```python
#!/usr/bin/env python3
"""Test module description."""
import pytest
import sys
from pathlib import Path

# Add tools/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))


class TestModuleName:
    """Tests for specific module or function."""

    def test_function_name_with_given_then_expected(self):
        """Test description."""
        # Given
        input_data = "test_value"

        # When
        result = function_to_test(input_data)

        # Then
        assert result == expected_value
```

### Integration Test Template

```python
#!/usr/bin/env python3
"""Integration test with external dependencies."""
import pytest
import zipfile
import xml.etree.ElementTree as ET


class Test3MFValidation:
    """Tests for 3MF file output."""

    @pytest.fixture
    def sample_3mf(self, tmp_path):
        """Create a minimal 3MF file for testing."""
        # Use lib3mf or copy from examples/
        pass

    def test_3mf_has_required_files(self, sample_3mf):
        """Verify 3MF contains required files."""
        with zipfile.ZipFile(sample_3mf) as z:
            files = z.namelist()
            assert "[Content_Types].xml" in files
            assert "_rels/.rels" in files
            assert "3D/3dmodel.model" in files
```

## Test Environment Setup

### Using uv (Recommended)
```bash
cd /path/to/freecad_tools

# Create and activate venv
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -e .

# Install dev dependencies
uv pip install -e ".[dev]"
uv pip install pytest
```

### Verify Setup
```bash
# Check pytest is installed
python -m pytest --version

# Check lib3mf is available
python -c "import lib3mf; print(lib3mf.VERSION)"
```

## Continuous Testing

### Pre-commit Hooks

Before committing, ensure tests pass:

```bash
# Run quick tests (no FreeCAD)
python -m pytest tests/test_git_utils.py tests/test_lib3mf_utils.py -v

# Run linting
ruff check tools/ tests/
ruff format tools/ tests/
```

## Troubleshooting

### FreeCAD Not Found
- Ensure FreeCAD is installed at expected paths
- Or set `FREECAD_TOOLS_LOG_LEVEL=DEBUG` to see search paths

### lib3mf ImportError
- Ensure venv is activated: `source .venv/bin/activate`
- Reinstall: `uv pip install lib3mf==2.5.0`

### Test Failures
- Check working directory is correct (tests must run from project root or use absolute paths)
- Ensure example files exist in `examples/`
- Run with `FREECAD_TOOLS_LOG_LEVEL=DEBUG` for verbose output

## CI/CD Considerations

For automated testing in CI:

1. **Fast tests** - Run unit tests first (no FreeCAD)
2. **Slow tests** - Run integration tests with FreeCAD (if available)
3. **Validation** - Always validate generated 3MF files

Example CI test order:
```bash
# 1. Lint
ruff check tools/ tests/
ruff format --check tools/ tests/

# 2. Unit tests
python -m pytest tests/test_git_utils.py -v

# 3. Integration (if FreeCAD available)
if command -v freecadcmd; then
    python tools/export.py
    python -m pytest tests/test_3mf.py -v
fi
```