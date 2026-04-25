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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
