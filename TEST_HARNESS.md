#!/usr/bin/env python3
"""Test Data Inventory and Harness Documentation

This document describes the test data available in the repository and how to use it
for testing the export config system and other freecad_tools features.

## Available Test Data

### Example Files (examples/ directory)

1. **example.FCStd** - Sample FreeCAD document
   - Contains simple test geometry
   - Available for testing config loading and body resolution
   - Can be used for integration tests if FreeCAD is available

2. **example.3mf** - Sample 3MF output
   - Shows expected structure of generated 3MF files
   - Can inspect with `unzip -l example.3mf`
   - Reference for testing 3MF validation

3. **export_config.yml.example.yml** - Template export configuration
   - Comprehensive example showing all config options
   - Includes:
     - Basic single-body export
     - Multiple body exports
     - Body orientation with rotation and position
     - Optional metadata
     - Template usage
     - Keep STL files option
   - Used by config parsing tests

4. **default.3mf** - Default template 3MF
   - Minimal 3MF with metadata structure
   - For template testing

### Template Files (templates/ directory)

1. **template_print_settings.3mf** - Template with printer settings
   - Example of preserved printer configuration
   - For testing metadata merging

## Test Harness Structure

### conftest.py - Pytest Configuration

Provides shared fixtures for all tests:

- `examples_dir` - Path to examples directory
- `example_fcstd_file` - Path to example.FCStd
- `example_3mf_file` - Path to example.3mf
- `example_config_file` - Path to export config example
- `default_template_file` - Path to default template
- `template_print_settings_file` - Path to template with settings

Usage in tests:
```python
def test_something(example_config_file):
    # example_config_file is automatically resolved
    config = load_config(example_config_file)
    assert config is valid
```

### test_export_config.py - Config Testing

Comprehensive test suite covering:

1. **TestConfigFileLoading** - YAML parsing
   - Load valid/invalid/empty configs
   - Handle missing export keys
   - Multiple export items

2. **TestConfigSchemaValidation** - Config structure
   - Required fields (name, source, bodies)
   - Optional fields (output, template, metadata, keep_stl, etc.)
   - Mixed body formats (string and object specs)
   - Metadata dictionary validation

3. **TestBodySpecParsing** - Body specification parsing
   - Simple string format ("Body1")
   - Object format with transforms
   - Rotation specifications [X, Y, Z] degrees
   - Position specifications [X, Y, Z] mm
   - Unicode body names
   - Duplicate body exports
   - Mixed formats in single config

4. **TestPathResolution** - Path handling
   - Absolute path preservation
   - Relative path resolution
   - Parent directory references (..)
   - Home directory expansion (~)
   - Multiple path resolution

5. **TestTemplatePathResolution** - Template file paths
   - Absolute template paths
   - Relative template paths
   - None/default handling

6. **TestConfigWithExampleFiles** - Integration tests
   - Load example config from repo
   - Validate structure
   - Parse body specs from example

7. **TestConfigMetadata** - Metadata handling
   - Config without metadata
   - Basic metadata fields
   - Custom metadata fields

8. **TestConfigEdgeCases** - Error handling
   - Empty bodies list
   - Unicode characters
   - Rotation/position validation
   - Numeric validation

## Running Tests

### All Tests
```bash
pytest tests/test_export_config.py -v
```

### Specific Test Class
```bash
pytest tests/test_export_config.py::TestConfigFileLoading -v
```

### Specific Test
```bash
pytest tests/test_export_config.py::TestBodySpecParsing::test_parse_simple_body_string -v
```

### With Coverage
```bash
pytest tests/test_export_config.py --cov=tools/fc_export --cov-report=html
```

## Test Data Limitations and Coverage Gaps

Current test data covers:

✅ Config file parsing and validation
✅ Body specification parsing (simple and advanced)
✅ Path resolution
✅ Metadata handling
✅ Schema validation

### Areas That Need Additional Test Data:

⚠️ **Actual FreeCAD Document Testing**
   - Current: example.FCStd exists but no integration tests
   - Need: Tests that actually load FCStd and extract bodies
   - Status: Requires FreeCAD to be installed/available
   - Workaround: Mocking FreeCAD objects in tests

⚠️ **3MF Validation**
   - Current: example.3mf exists for reference
   - Need: Tests that validate generated 3MF structure
   - Status: Some lib3mf tests exist but could be expanded
   - Workaround: Using lib3mf bindings for validation

⚠️ **Template Metadata Testing**
   - Current: template_print_settings.3mf exists
   - Need: Tests that verify metadata is actually read from template
   - Status: Unit tests exist but no integration tests
   - Workaround: Mock lib3mf metadata reading

⚠️ **Real Export Workflows**
   - Current: Individual function tests
   - Need: End-to-end export from config
   - Status: Requires FreeCAD available
   - Workaround: Could create mock FreeCAD documents

## Adding New Test Data

To add new test data:

1. Place files in `examples/` or `templates/` directory
2. Add corresponding fixture in `tests/conftest.py`
3. Create tests using the new fixture
4. Document in this file

Example fixture:
```python
@pytest.fixture
def my_test_file():
    file_path = EXAMPLES_DIR / "my_test_data.yml"
    if not file_path.exists():
        pytest.skip(f"Test file not found")
    return file_path
```

## Test Environment

### Requirements Met
- No FreeCAD required for config parsing tests
- No special dependencies beyond what's in pyproject.toml
- All tests run in standard pytest environment
- Tests are isolated and don't require external services

### What's Not Tested (Yet)
- Full export pipeline (requires FreeCAD)
- Actual 3MF file generation (requires lib3mf)
- Real body extraction from FCStd
- Git integration (requires .git directory)
- Template metadata merging with actual 3MF files

## Future Improvements

Potential enhancements to test harness:

1. **Mock FreeCAD Objects** - Create realistic mock FreeCAD documents for testing
2. **Sample FCStd Files** - Add minimal FCStd files with specific body configurations
3. **Reference 3MF Files** - Add various 3MF files for validation testing
4. **Config Variations** - Add multiple config files testing edge cases
5. **Performance Tests** - Add benchmarks for config loading
6. **Schema Validation** - Add JSON schema for config validation

See TODO.md for feature implementation priority.
"""

if __name__ == "__main__":
    print(__doc__)
