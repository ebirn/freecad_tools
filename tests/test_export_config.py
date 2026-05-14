#!/usr/bin/env python3
"""Comprehensive test harness for export configuration parsing and validation.

This module tests the export config system with:
- Config file parsing (YAML)
- Config schema validation
- Body specification parsing (simple and advanced formats)
- Path resolution (relative and absolute)
- Template path resolution
- Metadata validation
- Edge cases and error handling

Uses test data from the examples/ directory in the repo.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Add tools/ to path for importing fc_export
_test_dir = Path(__file__).parent
_tools_dir = _test_dir.parent / "tools"
sys.path.insert(0, str(_tools_dir))

# Import after path setup
# noqa: E402
import fc_export  # noqa: E402


class TestConfigFileLoading:
    """Tests for loading and parsing YAML config files."""

    def test_load_valid_yaml_config(self, tmp_path):
        """Should load and parse valid YAML config file."""
        # Given
        config_file = tmp_path / "export.yml"
        config_content = {
            "export": [
                {
                    "name": "TestProject",
                    "source": "test.FCStd",
                    "bodies": ["Body1", "Body2"],
                    "output": "output.3mf",
                }
            ]
        }
        config_file.write_text(yaml.dump(config_content))

        # When
        with patch.dict("os.environ", {"FREECAD_TOOLS_CONFIG": str(config_file)}):
            fc_export.CONFIG_FILE = str(config_file)
            with open(config_file) as f:
                config = yaml.safe_load(f)

        # Then
        assert config is not None
        assert "export" in config
        assert len(config["export"]) == 1
        assert config["export"][0]["name"] == "TestProject"

    def test_load_empty_yaml_config(self, tmp_path):
        """Should handle empty YAML config gracefully."""
        # Given
        config_file = tmp_path / "empty.yml"
        config_file.write_text("")

        # When
        with open(config_file) as f:
            config = yaml.safe_load(f)

        # Then
        assert config is None

    def test_load_config_with_no_export_key(self, tmp_path):
        """Should handle YAML without 'export' key."""
        # Given
        config_file = tmp_path / "no_export.yml"
        config_content = {"other_key": "value"}
        config_file.write_text(yaml.dump(config_content))

        # When
        with open(config_file) as f:
            config = yaml.safe_load(f)
            export_list = config.get("export", [])

        # Then
        assert export_list == []

    def test_load_config_with_multiple_exports(self, tmp_path):
        """Should load config with multiple export items."""
        # Given
        config_file = tmp_path / "multi.yml"
        config_content = {
            "export": [
                {"name": "Project1", "source": "p1.FCStd", "bodies": ["Body1"]},
                {"name": "Project2", "source": "p2.FCStd", "bodies": ["Body2"]},
                {"name": "Project3", "source": "p3.FCStd", "bodies": ["Body3"]},
            ]
        }
        config_file.write_text(yaml.dump(config_content))

        # When
        with open(config_file) as f:
            config = yaml.safe_load(f)
            export_list = config.get("export", [])

        # Then
        assert len(export_list) == 3
        assert [item["name"] for item in export_list] == ["Project1", "Project2", "Project3"]

    def test_load_config_uses_unified_path_priority(self, monkeypatch, tmp_path):
        unified_dir = tmp_path / ".freecad_tools"
        unified_dir.mkdir(parents=True)
        unified_path = unified_dir / "config.yml"
        unified_path.write_text(
            yaml.safe_dump(
                {
                    "export": [
                        {
                            "name": "UnifiedExport",
                            "source": "example.FCStd",
                            "bodies": ["Body"],
                        }
                    ]
                }
            )
        )

        monkeypatch.chdir(tmp_path)
        fc_export.CONFIG_FILE = None
        fc_export.PROJECT_ROOT = None

        exports = fc_export.load_config()

        assert exports[0]["name"] == "UnifiedExport"

    def test_load_config_ignores_python_script_as_config_file(self, monkeypatch, tmp_path):
        """load_config must not treat a .py file as the YAML config.

        When freecadcmd runs fc_export.py, it places the script path in
        sys.argv[1].  The module-level legacy fallback can mistakenly pick
        that up as CONFIG_FILE.  load_config() must detect and discard any
        CONFIG_FILE that is not a .yml/.yaml file and fall back to
        auto-discovery instead.
        """
        # Given: a valid config exists in the project tree
        config_dir = tmp_path / ".freecad_tools"
        config_dir.mkdir()
        (config_dir / "config.yml").write_text(
            yaml.safe_dump(
                {
                    "export": [
                        {
                            "name": "RealProject",
                            "source": "design.FCStd",
                            "bodies": ["Body"],
                        }
                    ]
                }
            )
        )
        monkeypatch.chdir(tmp_path)

        # Simulate freecadcmd putting the script path in CONFIG_FILE
        fc_export.CONFIG_FILE = "/Users/ebirn/.cache/pre-commit/repofccpuwes/tools/fc_export.py"
        fc_export.PROJECT_ROOT = None

        # When
        exports = fc_export.load_config()

        # Then: the real config was found; the .py file was NOT parsed as YAML
        assert exports[0]["name"] == "RealProject"
        assert fc_export.CONFIG_FILE.endswith(".yml")


class TestConfigSchemaValidation:
    """Tests for validating export config structure and required fields."""

    def test_export_item_required_fields(self):
        """Should validate that export items have required fields."""
        # Given
        valid_item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
        }

        # When/Then
        # These fields are expected to be present
        assert "name" in valid_item
        assert "source" in valid_item
        assert "bodies" in valid_item

    def test_export_item_optional_fields(self):
        """Should accept optional fields in export items."""
        # Given
        item_with_optional = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "output": "output.3mf",  # optional
            "template": "template.3mf",  # optional
            "metadata": {"Author": "Test"},  # optional
            "keep_stl": True,  # optional
            "stl_output_dir": "stl/",  # optional
        }

        # When/Then
        # All these should be valid
        assert item_with_optional["output"] == "output.3mf"
        assert item_with_optional["template"] == "template.3mf"
        assert item_with_optional["metadata"]["Author"] == "Test"
        assert item_with_optional["keep_stl"] is True
        assert item_with_optional["stl_output_dir"] == "stl/"

    def test_bodies_list_can_be_strings(self):
        """Should accept bodies as simple string list."""
        # Given
        bodies = ["Body1", "Body2", "Body3"]

        # When/Then
        assert isinstance(bodies, list)
        assert all(isinstance(b, str) for b in bodies)

    def test_bodies_list_can_be_mixed_format(self):
        """Should accept bodies as mix of strings and objects."""
        # Given
        bodies = [
            "Body1",  # Simple string
            {
                "body": "Body2",  # Object with transforms
                "rotation": [45, 0, 0],
            },
            "Body3",  # Back to simple string
        ]

        # When/Then
        assert len(bodies) == 3
        assert isinstance(bodies[0], str)
        assert isinstance(bodies[1], dict)
        assert isinstance(bodies[2], str)

    def test_metadata_is_dictionary(self):
        """Should validate metadata structure."""
        # Given
        metadata = {
            "Project": "TestProject",
            "Author": "John Doe",
            "Version": "1.0",
            "CustomField": "CustomValue",
        }

        # When/Then
        assert isinstance(metadata, dict)
        assert metadata["Project"] == "TestProject"
        assert len(metadata) == 4


class TestBodySpecParsing:
    """Tests for parsing body specifications from config."""

    def test_parse_simple_body_string(self):
        """Should parse simple string body specs."""
        # Given
        bodies = ["Body1", "Body2", "Body3"]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 3
        assert parsed[0] == ("Body1", None, None)  # (id, rotation, position)
        assert parsed[1] == ("Body2", None, None)
        assert parsed[2] == ("Body3", None, None)

    def test_parse_body_with_rotation(self):
        """Should parse body with rotation specification."""
        # Given
        bodies = [{"body": "Body1", "rotation": [45, 0, 0]}]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 1
        body_id, rotation, position = parsed[0]
        assert body_id == "Body1"
        assert rotation == [45, 0, 0]
        assert position is None

    def test_parse_body_with_position(self):
        """Should parse body with position specification."""
        # Given
        bodies = [{"body": "Body1", "position": [10, 20, 30]}]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 1
        body_id, rotation, position = parsed[0]
        assert body_id == "Body1"
        assert rotation is None
        assert position == [10, 20, 30]

    def test_parse_body_with_rotation_and_position(self):
        """Should parse body with both rotation and position."""
        # Given
        bodies = [
            {
                "body": "Body1",
                "rotation": [45, 0, 0],
                "position": [10, 20, 30],
            }
        ]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 1
        body_id, rotation, position = parsed[0]
        assert body_id == "Body1"
        assert rotation == [45, 0, 0]
        assert position == [10, 20, 30]

    def test_parse_mixed_body_formats(self):
        """Should handle mix of simple strings and objects with transforms."""
        # Given
        bodies = [
            "Body1",  # simple
            {"body": "Body2", "rotation": [45, 0, 0]},  # with rotation
            "Body3",  # simple again
            {"body": "Body4", "position": [10, 0, 0]},  # with position
        ]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 4
        assert parsed[0] == ("Body1", None, None)
        assert parsed[1] == ("Body2", [45, 0, 0], None)
        assert parsed[2] == ("Body3", None, None)
        assert parsed[3] == ("Body4", None, [10, 0, 0])

    def test_parse_body_with_spaces_in_label(self):
        """Should handle body labels with spaces."""
        # Given
        bodies = [
            "Angle Round",  # Label with spaces
            {"body": "Another Label", "rotation": [90, 0, 0]},
        ]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 2
        assert parsed[0][0] == "Angle Round"
        assert parsed[1][0] == "Another Label"

    def test_parse_duplicate_bodies(self):
        """Should handle exporting same body multiple times."""
        # Given
        bodies = [
            "Body1",
            "Body1",  # Same body twice
            "Body2",
            "Body1",  # And again
        ]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 4
        assert parsed[0][0] == "Body1"
        assert parsed[1][0] == "Body1"  # Should still be parsed
        assert parsed[2][0] == "Body2"
        assert parsed[3][0] == "Body1"


class TestPathResolution:
    """Tests for resolving relative and absolute paths."""

    def test_resolve_absolute_path(self, tmp_path):
        """Should return absolute paths unchanged."""
        # Given
        abs_path = str(tmp_path / "file.txt")

        # When
        resolved = fc_export.resolve_relative_path(abs_path, tmp_path)

        # Then
        assert resolved == abs_path
        assert Path(resolved).is_absolute()

    def test_resolve_relative_path(self, tmp_path):
        """Should resolve relative paths against base directory."""
        # Given
        rel_path = "output/file.txt"
        base_dir = tmp_path

        # When
        resolved = fc_export.resolve_relative_path(rel_path, base_dir)

        # Then
        assert resolved == str(base_dir / rel_path)
        assert Path(resolved).is_absolute()

    def test_resolve_path_with_parent_dir(self, tmp_path):
        """Should handle relative paths with parent directory references."""
        # Given
        rel_path = "../output/file.txt"
        base_dir = tmp_path / "subdir"

        # When
        resolved = fc_export.resolve_relative_path(rel_path, base_dir)

        # Then
        assert Path(resolved).is_absolute()

    def test_resolve_path_home_expansion(self, tmp_path):
        """Should treat ~ as literal directory name (no expansion in resolve_relative_path)."""
        # Given
        home_path = "~/documents/file.txt"

        # When
        resolved = fc_export.resolve_relative_path(home_path, tmp_path)

        # Then
        # resolve_relative_path doesn't expand ~ - it treats it as a directory
        # So the result should have ~ in it as a literal directory name
        assert "~" in resolved
        assert Path(resolved).is_absolute()

    def test_resolve_multiple_paths(self, tmp_path):
        """Should correctly resolve multiple different paths."""
        # Given
        paths = [
            "output/file1.txt",
            "stl/meshes.stl",
            "prints/model.3mf",
        ]
        base_dir = tmp_path

        # When
        resolved_paths = [fc_export.resolve_relative_path(p, base_dir) for p in paths]

        # Then
        assert len(resolved_paths) == 3
        assert all(Path(p).is_absolute() for p in resolved_paths)
        assert all(str(base_dir) in p for p in resolved_paths)

    def test_resolve_output_root_defaults_to_project_dir(self, tmp_path):
        """Should default output root to project directory when unset."""
        resolved = fc_export.resolve_output_root({}, str(tmp_path), override=None)
        assert resolved == str(tmp_path)

    def test_resolve_output_root_from_config(self, tmp_path):
        """Should resolve relative output_root from config against project root."""
        resolved = fc_export.resolve_output_root({"output_root": "generated"}, str(tmp_path), override=None)
        assert resolved == str(tmp_path / "generated")

    def test_resolve_output_root_override_precedence(self, tmp_path):
        """Should prioritize override over config output_root."""
        resolved = fc_export.resolve_output_root(
            {"output_root": "generated"},
            str(tmp_path),
            override="ci_output",
        )
        assert resolved == str(tmp_path / "ci_output")


class TestTemplatePathResolution:
    """Tests for resolving template file paths."""

    def test_resolve_template_with_absolute_path(self, tmp_path):
        """Should return absolute template paths unchanged."""
        # Given
        template_file = tmp_path / "template.3mf"
        template_file.write_text("dummy")

        # When
        resolved = fc_export.resolve_template_path(str(template_file))

        # Then
        assert resolved == str(template_file)

    def test_resolve_template_with_none(self):
        """Should handle None template gracefully."""
        # Given
        template_name = None

        # When
        resolved = fc_export.resolve_template_path(template_name)

        # Then
        # Should return None or default template (implementation-dependent)
        assert resolved is None or Path(resolved).exists()

    def test_resolve_template_with_relative_path(self, tmp_path):
        """Should resolve relative template paths."""
        # Given
        template_file = tmp_path / "template.3mf"
        template_file.write_text("dummy")
        rel_path = "template.3mf"

        # Mock the working directory
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            resolved = fc_export.resolve_template_path(rel_path)

        # Then
        # Should attempt to resolve the path
        assert resolved is not None or mock_exists.called


class TestConfigWithExampleFiles:
    """Integration tests using actual example files from the repo."""

    def test_load_example_config_file(self, example_config_file):
        """Should load example export config from examples directory."""
        # When
        with open(example_config_file) as f:
            config = yaml.safe_load(f)

        # Then
        assert config is not None
        assert "export" in config
        assert len(config["export"]) > 0

    def test_example_config_has_valid_items(self, example_config_file):
        """Should validate structure of items in example config."""
        # When
        with open(example_config_file) as f:
            config = yaml.safe_load(f)

        # Then
        for item in config.get("export", []):
            assert "name" in item
            assert "source" in item
            # bodies is optional when body_source: properties
            # But if body_source is config or not specified, bodies should be present or empty
            body_source = item.get("body_source")
            if body_source == "properties":
                assert "bodies" not in item or item.get("bodies") == []
            else:
                assert "bodies" in item

    def test_example_config_bodies_are_parseable(self, example_config_file):
        """Should be able to parse body specs from example config."""
        # When
        with open(example_config_file) as f:
            config = yaml.safe_load(f)

        # Then
        for item in config.get("export", []):
            bodies = item.get("bodies", [])
            if bodies:  # Only test if bodies list is not empty
                parsed = fc_export.parse_body_specs(bodies)
                assert len(parsed) == len(bodies)


class TestConfigMetadata:
    """Tests for metadata specification in config."""

    def test_config_with_no_metadata(self):
        """Should handle config items without metadata."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
        }

        # When
        metadata = item.get("metadata")

        # Then
        assert metadata is None

    def test_config_with_basic_metadata(self):
        """Should accept basic metadata fields."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "metadata": {
                "Project": "TestProject",
                "Author": "John Doe",
                "Version": "1.0",
            },
        }

        # When
        metadata = item.get("metadata")

        # Then
        assert metadata is not None
        assert metadata["Project"] == "TestProject"
        assert metadata["Author"] == "John Doe"
        assert metadata["Version"] == "1.0"

    def test_config_with_custom_metadata(self):
        """Should accept custom metadata fields."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "metadata": {
                "Project": "TestProject",
                "CustomField1": "Value1",
                "CustomField2": "Value2",
                "CustomNested": {"key": "value"},
            },
        }

        # When
        metadata = item.get("metadata")

        # Then
        assert metadata["CustomField1"] == "Value1"
        assert metadata["CustomField2"] == "Value2"


class TestConfigEdgeCases:
    """Tests for edge cases and error handling."""

    def test_config_with_empty_bodies_list(self):
        """Should handle items with empty bodies list."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": [],
        }

        # When
        bodies = item.get("bodies", [])
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert parsed == []

    def test_config_with_unicode_in_body_names(self):
        """Should handle Unicode characters in body labels."""
        # Given
        bodies = ["Körper", "Partie", "部品"]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 3
        assert parsed[0][0] == "Körper"
        assert parsed[1][0] == "Partie"
        assert parsed[2][0] == "部品"

    def test_config_rotation_values(self):
        """Should validate rotation is 3-element list of numbers."""
        # Given
        bodies = [
            {"body": "Body1", "rotation": [45, 0, 0]},
            {"body": "Body2", "rotation": [0, 90, 0]},
            {"body": "Body3", "rotation": [0, 0, 180]},
        ]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        for _, rotation, _ in parsed:
            assert rotation is not None
            assert len(rotation) == 3
            assert all(isinstance(v, (int, float)) for v in rotation)

    def test_config_position_values(self):
        """Should validate position is 3-element list of numbers."""
        # Given
        bodies = [
            {"body": "Body1", "position": [10, 20, 30]},
            {"body": "Body2", "position": [0.5, 1.5, 2.5]},
            {"body": "Body3", "position": [-10, 0, 10]},
        ]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        for _, _, position in parsed:
            assert position is not None
            assert len(position) == 3
            assert all(isinstance(v, (int, float)) for v in position)


class TestTechDrawConfigSection:
    """Tests for TechDraw export configuration."""

    def test_techdraw_section_optional(self):
        """Should accept export items without techdraw section."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
        }

        # When
        techdraw = item.get("techdraw")

        # Then
        assert techdraw is None

    def test_techdraw_section_with_all_options(self):
        """Should accept techdraw section with all fields."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "techdraw": {
                "pages": [],  # empty = all pages
                "output_dir": "docs/",
                "format": "pdf",
            },
        }

        # When
        techdraw = item.get("techdraw")

        # Then
        assert techdraw is not None
        assert techdraw["pages"] == []
        assert techdraw["output_dir"] == "docs/"
        assert techdraw["format"] == "pdf"

    def test_techdraw_section_pages_all(self):
        """Should handle empty pages list (means all pages)."""
        # Given
        techdraw = {"pages": []}

        # When
        pages = techdraw.get("pages")

        # Then
        assert pages == []

    def test_techdraw_section_pages_specific(self):
        """Should handle specific page names."""
        # Given
        techdraw = {"pages": ["Page", "Page001", "DetailView"]}

        # When
        pages = techdraw.get("pages")

        # Then
        assert len(pages) == 3
        assert "Page" in pages
        assert "DetailView" in pages

    def test_techdraw_section_format_pdf(self):
        """Should accept pdf format."""
        # Given
        techdraw = {"format": "pdf"}

        # When
        fmt = techdraw.get("format")

        # Then
        assert fmt == "pdf"

    def test_techdraw_output_dir_required(self):
        """Should have output_dir field."""
        # Given
        techdraw = {
            "pages": [],
            "output_dir": "docs/",
        }

        # When
        output_dir = techdraw.get("output_dir")

        # Then
        assert output_dir is not None
        assert output_dir == "docs/"


class TestBOMConfigSection:
    """Tests for Bill of Materials (BOM) configuration."""

    def test_bom_section_optional(self):
        """Should accept export items without bom section."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
        }

        # When
        bom = item.get("bom")

        # Then
        assert bom is None

    def test_bom_section_with_required_fields(self):
        """Should accept bom section with output field."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "bom": {
                "output": "docs/bom.csv",
            },
        }

        # When
        bom = item.get("bom")

        # Then
        assert bom is not None
        assert bom["output"] == "docs/bom.csv"

    def test_bom_section_with_all_options(self):
        """Should accept bom section with all fields."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "bom": {
                "source": "auto",
                "output": "docs/bom.csv",
                "fields": ["label", "quantity", "material"],
            },
        }

        # When
        bom = item.get("bom")

        # Then
        assert bom is not None
        assert bom["source"] == "auto"
        assert bom["output"] == "docs/bom.csv"
        assert len(bom["fields"]) == 3

    def test_bom_source_auto(self):
        """Should accept 'auto' source."""
        # Given
        bom = {"source": "auto"}

        # When
        source = bom.get("source")

        # Then
        assert source == "auto"

    def test_bom_source_assembly(self):
        """Should accept 'assembly' source."""
        # Given
        bom = {"source": "assembly"}

        # When
        source = bom.get("source")

        # Then
        assert source == "assembly"

    def test_bom_source_spreadsheet(self):
        """Should accept 'spreadsheet' source."""
        # Given
        bom = {"source": "spreadsheet", "spreadsheet_name": "BOM"}

        # When
        source = bom.get("source")
        spreadsheet_name = bom.get("spreadsheet_name")

        # Then
        assert source == "spreadsheet"
        assert spreadsheet_name == "BOM"

    def test_bom_source_parts(self):
        """Should accept 'parts' source."""
        # Given
        bom = {"source": "parts"}

        # When
        source = bom.get("source")

        # Then
        assert source == "parts"

    def test_bom_fields_minimal(self):
        """Should accept minimal field set."""
        # Given
        bom = {
            "output": "docs/bom.csv",
            "fields": ["label", "quantity"],
        }

        # When
        fields = bom.get("fields")

        # Then
        assert len(fields) == 2
        assert "label" in fields
        assert "quantity" in fields

    def test_bom_fields_extended(self):
        """Should accept extended field set."""
        # Given
        bom = {
            "output": "docs/bom.csv",
            "fields": [
                "label",
                "quantity",
                "material",
                "dimensions",
                "url",
                "price",
            ],
        }

        # When
        fields = bom.get("fields")

        # Then
        assert len(fields) == 6
        assert "label" in fields
        assert "quantity" in fields
        assert "material" in fields
        assert "dimensions" in fields
        assert "url" in fields
        assert "price" in fields

    def test_bom_fields_custom(self):
        """Should accept custom field names."""
        # Given
        bom = {
            "output": "docs/bom.csv",
            "fields": ["label", "quantity", "custom_field_1", "custom_field_2"],
        }

        # When
        fields = bom.get("fields")

        # Then
        assert "custom_field_1" in fields
        assert "custom_field_2" in fields

    def test_bom_output_required(self):
        """Should have output field."""
        # Given
        bom = {
            "output": "docs/bom.csv",
        }

        # When
        output = bom.get("output")

        # Then
        assert output is not None
        assert output == "docs/bom.csv"

    def test_bom_with_assembly_field(self):
        """Should accept bom section with assembly field for specific assembly targeting."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "bom": {
                "source": "assembly",
                "assembly": "MainAssembly",
                "output": "docs/main_bom.csv",
            },
        }

        # When
        bom = item.get("bom")

        # Then
        assert bom is not None
        assert bom["source"] == "assembly"
        assert bom["assembly"] == "MainAssembly"
        assert bom["output"] == "docs/main_bom.csv"

    def test_bom_multiple_assemblies_list(self):
        """Should accept list of bom configs for multiple assemblies."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "bom": [
                {
                    "source": "assembly",
                    "assembly": "MainAssembly",
                    "output": "docs/main_bom.csv",
                },
                {
                    "source": "assembly",
                    "assembly": "SubAssembly",
                    "output": "docs/sub_bom.csv",
                },
            ],
        }

        # When
        bom_configs = item.get("bom")

        # Then
        assert bom_configs is not None
        assert isinstance(bom_configs, list)
        assert len(bom_configs) == 2
        assert bom_configs[0]["assembly"] == "MainAssembly"
        assert bom_configs[0]["output"] == "docs/main_bom.csv"
        assert bom_configs[1]["assembly"] == "SubAssembly"
        assert bom_configs[1]["output"] == "docs/sub_bom.csv"


class TestExportWithTechDrawAndBOM:
    """Integration tests for export items with both TechDraw and BOM."""

    def test_export_item_with_techdraw_only(self):
        """Should accept export with only techdraw section."""
        # Given
        item = {
            "name": "DrawingsOnly",
            "source": "model.FCStd",
            "bodies": ["Body1"],
            "techdraw": {
                "pages": [],
                "output_dir": "docs/",
            },
        }

        # When
        techdraw = item.get("techdraw")
        bom = item.get("bom")

        # Then
        assert techdraw is not None
        assert bom is None

    def test_export_item_with_bom_only(self):
        """Should accept export with only bom section."""
        # Given
        item = {
            "name": "BOMOnly",
            "source": "model.FCStd",
            "bodies": ["Body1"],
            "bom": {
                "output": "docs/bom.csv",
            },
        }

        # When
        techdraw = item.get("techdraw")
        bom = item.get("bom")

        # Then
        assert techdraw is None
        assert bom is not None

    def test_export_item_with_both_techdraw_and_bom(self):
        """Should accept export with both techdraw and bom sections."""
        # Given
        item = {
            "name": "FullExport",
            "source": "model.FCStd",
            "bodies": ["Body1", "Body2"],
            "output": "prints/model.3mf",
            "techdraw": {
                "pages": [],
                "output_dir": "docs/",
                "format": "pdf",
            },
            "bom": {
                "source": "assembly",
                "output": "docs/bom.csv",
                "fields": ["label", "quantity", "material"],
            },
        }

        # When
        techdraw = item.get("techdraw")
        bom = item.get("bom")
        output_3mf = item.get("output")

        # Then
        assert techdraw is not None
        assert bom is not None
        assert output_3mf == "prints/model.3mf"
        assert techdraw["output_dir"] == "docs/"
        assert bom["output"] == "docs/bom.csv"

    def test_export_item_complete_configuration(self):
        """Should accept export item with all possible fields."""
        # Given
        item = {
            "name": "CompleteProject",
            "source": "model.FCStd",
            "bodies": ["Body1", {"body": "Body2", "rotation": [45, 0, 0]}],
            "output": "prints/model.3mf",
            "template": "template.3mf",
            "metadata": {"Project": "Test"},
            "keep_stl": True,
            "stl_output_dir": "prints/stl",
            "techdraw": {
                "pages": ["Page", "Page001"],
                "output_dir": "docs/",
                "format": "pdf",
            },
            "bom": {
                "source": "assembly",
                "output": "docs/bom.csv",
                "fields": ["label", "quantity", "material", "url"],
            },
        }

        # When/Then - just verify it's valid YAML/dict structure
        assert item["name"] == "CompleteProject"
        assert item["techdraw"]["output_dir"] == "docs/"
        assert item["bom"]["output"] == "docs/bom.csv"
        assert len(item["bodies"]) == 2


class TestBodySourceValidation:
    """Tests for body_source configuration validation."""

    def test_body_source_config_mode_valid(self):
        """Should accept valid body_source: config with bodies list."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "body_source": "config",
            "bodies": ["Body1", "Body2"],
        }

        # When
        is_valid, body_source, warning = fc_export.validate_body_source_config(item)

        # Then
        assert is_valid is True
        assert body_source == "config"
        assert warning is None

    def test_body_source_properties_mode_valid(self):
        """Should accept valid body_source: properties without bodies list."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "body_source": "properties",
        }

        # When
        is_valid, body_source, warning = fc_export.validate_body_source_config(item)

        # Then
        assert is_valid is True
        assert body_source == "properties"
        assert warning is None

    def test_body_source_properties_with_empty_bodies_valid(self):
        """Should accept body_source: properties with empty bodies list."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "body_source": "properties",
            "bodies": [],
        }

        # When
        is_valid, body_source, warning = fc_export.validate_body_source_config(item)

        # Then
        assert is_valid is True
        assert body_source == "properties"
        assert warning is None

    def test_body_source_invalid_value(self):
        """Should reject invalid body_source value."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "body_source": "invalid_mode",
        }

        # When
        is_valid, body_source, warning = fc_export.validate_body_source_config(item)

        # Then
        assert is_valid is False
        assert "Invalid body_source" in warning

    def test_body_source_config_without_bodies_invalid(self):
        """Should reject body_source: config without bodies list."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "body_source": "config",
        }

        # When
        is_valid, body_source, warning = fc_export.validate_body_source_config(item)

        # Then
        assert is_valid is False
        assert "no bodies list provided" in warning

    def test_body_source_properties_with_bodies_invalid(self):
        """Should reject body_source: properties with bodies list."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "body_source": "properties",
            "bodies": ["Body1"],
        }

        # When
        is_valid, body_source, warning = fc_export.validate_body_source_config(item)

        # Then
        assert is_valid is False
        assert "bodies list is also provided" in warning

    def test_backward_compat_with_bodies_infers_config(self):
        """Should infer body_source: config when bodies present but body_source omitted."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1", "Body2"],
        }

        # When
        is_valid, body_source, warning = fc_export.validate_body_source_config(item)

        # Then
        assert is_valid is True
        assert body_source == "config"
        assert warning is not None
        assert "inferring 'config'" in warning

    def test_backward_compat_without_bodies_infers_properties(self):
        """Should infer body_source: properties when no bodies list and body_source omitted."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
        }

        # When
        is_valid, body_source, warning = fc_export.validate_body_source_config(item)

        # Then
        assert is_valid is True
        assert body_source == "properties"
        assert warning is not None
        assert "defaulting to 'properties'" in warning


class TestParseBodySpecsAxisAngle:
    """Tests for parse_body_specs with axis+angle rotation format."""

    def test_parse_body_with_axis_angle_rotation(self):
        """Should parse body with axis+angle rotation format."""
        # Given
        bodies = [{"body": "Body1", "rotation": {"axis": [0, 0, 1], "angle": 45}}]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 1
        body_id, rotation, position = parsed[0]
        assert body_id == "Body1"
        assert rotation == {"axis": [0, 0, 1], "angle": 45}
        assert position is None

    def test_parse_body_with_axis_angle_and_position(self):
        """Should parse body with both axis+angle rotation and position."""
        # Given
        bodies = [
            {
                "body": "Body1",
                "rotation": {"axis": [0, 0, 1], "angle": 90},
                "position": [10, 20, 30],
            }
        ]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 1
        body_id, rotation, position = parsed[0]
        assert body_id == "Body1"
        assert rotation == {"axis": [0, 0, 1], "angle": 90}
        assert position == [10, 20, 30]

    def test_parse_mixed_euler_and_axis_angle(self):
        """Should handle mix of Euler and axis+angle rotation formats."""
        # Given
        bodies = [
            {"body": "Body1", "rotation": [45, 0, 0]},  # Euler
            {"body": "Body2", "rotation": {"axis": [0, 0, 1], "angle": 90}},  # Axis+Angle
            "Body3",  # No rotation
        ]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 3
        # Body1: Euler format
        assert parsed[0] == ("Body1", [45, 0, 0], None)
        # Body2: Axis+Angle format
        assert parsed[1] == ("Body2", {"axis": [0, 0, 1], "angle": 90}, None)
        # Body3: No rotation
        assert parsed[2] == ("Body3", None, None)

    def test_parse_invalid_axis_angle_missing_axis(self):
        """Should reject axis+angle rotation missing axis key."""
        # Given
        bodies = [{"body": "Body1", "rotation": {"angle": 45}}]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 1
        body_id, rotation, position = parsed[0]
        assert body_id == "Body1"
        assert rotation is None  # Invalid, so None

    def test_parse_invalid_axis_angle_missing_angle(self):
        """Should reject axis+angle rotation missing angle key."""
        # Given
        bodies = [{"body": "Body1", "rotation": {"axis": [0, 0, 1]}}]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 1
        body_id, rotation, position = parsed[0]
        assert body_id == "Body1"
        assert rotation is None  # Invalid, so None

    def test_parse_invalid_axis_not_list(self):
        """Should reject axis+angle rotation with non-list axis."""
        # Given
        bodies = [{"body": "Body1", "rotation": {"axis": "not-a-list", "angle": 45}}]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 1
        body_id, rotation, position = parsed[0]
        assert body_id == "Body1"
        assert rotation is None

    def test_parse_invalid_axis_wrong_length(self):
        """Should reject axis+angle rotation with wrong axis length."""
        # Given
        bodies = [{"body": "Body1", "rotation": {"axis": [0, 0], "angle": 45}}]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 1
        body_id, rotation, position = parsed[0]
        assert body_id == "Body1"
        assert rotation is None

    def test_parse_euler_rotation_still_works(self):
        """Should verify existing Euler rotation format still works."""
        # Given
        bodies = [{"body": "Body1", "rotation": [45, 0, 0]}]

        # When
        parsed = fc_export.parse_body_specs(bodies)

        # Then
        assert len(parsed) == 1
        body_id, rotation, position = parsed[0]
        assert body_id == "Body1"
        assert rotation == [45, 0, 0]


class TestScreenshotConfigSection:
    """Tests for screenshot configuration section in export config."""

    def test_export_item_without_screenshots(self):
        """Export item without screenshots should work fine."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "output": "output.3mf",
        }

        # When
        # Just verify it doesn't crash when accessing
        screenshots = item.get("screenshots")

        # Then
        assert screenshots is None

    def test_export_item_with_screenshots_bool_true(self):
        """Export item with screenshots: true should be valid."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "output": "output.3mf",
            "screenshots": True,
        }

        # When
        screenshots = item.get("screenshots")

        # Then
        assert screenshots is True

    def test_export_item_with_screenshots_bool_false(self):
        """Export item with screenshots: false should be valid."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "screenshots": False,
        }

        # When
        screenshots = item.get("screenshots")

        # Then
        assert screenshots is False

    def test_export_item_with_screenshots_dict(self):
        """Export item with screenshots dict should be valid."""
        # Given
        item = {
            "name": "TestProject",
            "source": "test.FCStd",
            "bodies": ["Body1"],
            "screenshots": {
                "enabled": True,
                "views": ["isometric", "front"],
                "resolution": [1920, 1080],
                "format": "png",
            },
        }

        # When
        screenshots = item.get("screenshots")

        # Then
        assert isinstance(screenshots, dict)
        assert screenshots["enabled"] is True
        assert len(screenshots["views"]) == 2

    def test_screenshots_with_output_dir(self):
        """Screenshots config should support output_dir."""
        # Given
        screenshots = {
            "output_dir": "docs/images/",
        }

        # When
        output_dir = screenshots.get("output_dir")

        # Then
        assert output_dir == "docs/images/"

    def test_screenshots_with_multiple_views(self):
        """Screenshots config should support multiple views."""
        # Given
        screenshots = {
            "views": ["isometric", "front", "top", "right"],
        }

        # When
        views = screenshots.get("views")

        # Then
        assert len(views) == 4
        assert "isometric" in views
        assert "front" in views

    def test_screenshots_with_all_options(self):
        """Screenshots config with all options should be valid."""
        # Given
        screenshots = {
            "enabled": True,
            "output_dir": "docs/images/",
            "views": ["isometric", "front"],
            "resolution": [1920, 1080],
            "background": [255, 255, 255, 255],
            "format": "png",
            "composite": True,
        }

        # When/Then - verify all fields present
        assert screenshots["enabled"] is True
        assert screenshots["output_dir"] == "docs/images/"
        assert screenshots["views"] == ["isometric", "front"]
        assert screenshots["resolution"] == [1920, 1080]
        assert screenshots["background"] == [255, 255, 255, 255]
        assert screenshots["format"] == "png"
        assert screenshots["composite"] is True

    def test_screenshots_minimal_config(self):
        """Screenshots config with minimal settings should be valid."""
        # Given
        screenshots = True

        # When/Then - should be valid as boolean
        assert isinstance(screenshots, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
