#!/usr/bin/env python3
"""Unit tests for fc_export.py functions that can be tested without FreeCAD.

This module tests:
- parse_args() - CLI argument parsing
- configure_logging() - Logging configuration
- find_exportable_bodies() - Property-based body discovery
- get_body_export_properties() - Reading export properties
- resolve_object_identifier() - Object resolution by Name/Label
- validate_body_source_config() - Already in test_export_config.py
- get_export_metadata() - Metadata extraction
- load_config() - Config loading and path resolution
- parse_body_specs() - Already in test_export_config.py
- resolve_relative_path() - Already in test_export_config.py
- resolve_template_path() - Already in test_export_config.py
- _col_index_to_letter() - Spreadsheet column conversion
"""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Add tools/ to path for importing fc_export
_test_dir = Path(__file__).parent
_tools_dir = _test_dir.parent / "tools"
sys.path.insert(0, str(_tools_dir))

# Import after path setup
# noqa: E402
import fc_export  # noqa: E402


class TestParseArgs:
    """Tests for CLI argument parsing."""

    def test_parse_args_defaults(self):
        """Should return default values when no arguments provided."""
        # When - simulate no arguments by patching sys.argv
        with patch.object(sys, "argv", ["fc_export.py"]):
            args = fc_export.parse_args()

        # Then
        assert args.config_file is None
        assert args.config is None
        assert args.verbose is False
        assert args.dry_run is False

    def test_parse_args_with_config_positional(self):
        """Should parse config file from positional argument."""
        # When
        with patch.object(sys, "argv", ["fc_export.py", "my_config.yml"]):
            args = fc_export.parse_args()

        # Then
        assert args.config_file == "my_config.yml"
        assert args.config is None
        assert args.verbose is False
        assert args.dry_run is False

    def test_parse_args_with_config_flag(self):
        """Should parse config file from --config flag."""
        # When
        with patch.object(sys, "argv", ["fc_export.py", "--config", "my_config.yml"]):
            args = fc_export.parse_args()

        # Then
        assert args.config_file is None
        assert args.config == "my_config.yml"
        assert args.verbose is False
        assert args.dry_run is False

    def test_parse_args_with_verbose_flag(self):
        """Should parse verbose flag."""
        # When
        with patch.object(sys, "argv", ["fc_export.py", "-v"]):
            args = fc_export.parse_args()

        # Then
        assert args.verbose is True

    def test_parse_args_with_verbose_long_flag(self):
        """Should parse --verbose flag."""
        # When
        with patch.object(sys, "argv", ["fc_export.py", "--verbose"]):
            args = fc_export.parse_args()

        # Then
        assert args.verbose is True

    def test_parse_args_with_dry_run_flag(self):
        """Should parse --dry-run flag."""
        # When
        with patch.object(sys, "argv", ["fc_export.py", "--dry-run"]):
            args = fc_export.parse_args()

        # Then
        assert args.dry_run is True

    def test_parse_args_with_all_flags(self):
        """Should parse all flags together."""
        # When
        with patch.object(sys, "argv", ["fc_export.py", "--config", "test.yml", "-v", "--dry-run"]):
            args = fc_export.parse_args()

        # Then
        assert args.config == "test.yml"
        assert args.verbose is True
        assert args.dry_run is True

    def test_parse_args_with_short_flags(self):
        """Should parse short flag variants."""
        # When
        with patch.object(sys, "argv", ["fc_export.py", "-c", "test.yml", "-v"]):
            args = fc_export.parse_args()

        # Then
        assert args.config == "test.yml"
        assert args.verbose is True


class TestConfigureLogging:
    """Tests for logging configuration.

    Note: These tests verify the function returns a logger and sets up handlers correctly.
    We don't test logger.level directly since basicConfig only works once per process.
    """

    def test_configure_logging_returns_logger(self, tmp_path, caplog):
        """Should return a logger object."""
        # When
        with patch("fc_export.sys.stderr"):
            logger = fc_export.configure_logging(verbose=False, log_level_env=None)

        # Then
        assert logger is not None
        assert isinstance(logger, logging.Logger)
        assert logger.name == "fc_export"

    def test_configure_logging_sets_up_handlers(self, tmp_path, caplog):
        """Should set up FileHandler and StreamHandler."""
        # When
        with patch("fc_export.sys.stderr"):
            logger = fc_export.configure_logging(verbose=False, log_level_env=None)

        # Then
        assert logger is not None
        # Check that handlers were added (basicConfig adds to root logger)
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) >= 2

    def test_configure_logging_verbose_returns_logger(self, tmp_path, caplog):
        """Should return a logger when verbose=True."""
        # When
        with patch("fc_export.sys.stderr"):
            logger = fc_export.configure_logging(verbose=True, log_level_env=None)

        # Then
        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_configure_logging_env_debug_returns_logger(self, tmp_path):
        """Should return a logger with DEBUG env."""
        # When
        with patch("fc_export.sys.stderr"):
            logger = fc_export.configure_logging(verbose=False, log_level_env="DEBUG")

        # Then
        assert logger is not None
        assert isinstance(logger, logging.Logger)


class TestResolveObjectIdentifier:
    """Tests for resolving FreeCAD objects by Name or Label."""

    def test_resolve_by_name(self):
        """Should resolve object by Name."""
        # Given
        mock_doc = MagicMock()
        mock_obj = MagicMock()
        mock_obj.Name = "Body"
        mock_obj.Label = "MyBody"
        mock_doc.getObject.return_value = mock_obj

        # When
        result = fc_export.resolve_object_identifier(mock_doc, "Body")

        # Then
        assert result == (mock_obj, "Body", "MyBody")
        mock_doc.getObject.assert_called_once_with("Body")

    def test_resolve_by_label(self):
        """Should resolve object by Label when Name not found."""
        # Given
        mock_doc = MagicMock()
        mock_obj = MagicMock()
        mock_obj.Name = "Body001"
        mock_obj.Label = "MyBody"
        mock_doc.getObject.return_value = None
        mock_doc.Objects = [mock_obj]

        # When
        result = fc_export.resolve_object_identifier(mock_doc, "MyBody")

        # Then
        assert result == (mock_obj, "Body001", "MyBody")

    def test_resolve_not_found(self):
        """Should return None tuple when object not found."""
        # Given
        mock_doc = MagicMock()
        mock_doc.getObject.return_value = None
        mock_doc.Objects = []

        # When
        result = fc_export.resolve_object_identifier(mock_doc, "NonExistent")

        # Then
        assert result == (None, None, None)

    def test_resolve_prefers_name_over_label(self):
        """Should prefer Name match over Label match."""
        # Given
        mock_doc = MagicMock()
        mock_obj_by_name = MagicMock()
        mock_obj_by_name.Name = "Body"
        mock_obj_by_name.Label = "DifferentLabel"
        mock_doc.getObject.return_value = mock_obj_by_name

        # When
        result = fc_export.resolve_object_identifier(mock_doc, "Body")

        # Then
        assert result[0] == mock_obj_by_name
        mock_doc.getObject.assert_called_once()


class TestColIndexToLetter:
    """Tests for spreadsheet column index to letter conversion."""

    def test_col_index_1_to_a(self):
        """Should convert 1 to 'A'."""
        assert fc_export._col_index_to_letter(1) == "A"

    def test_col_index_26_to_z(self):
        """Should convert 26 to 'Z'."""
        assert fc_export._col_index_to_letter(26) == "Z"

    def test_col_index_27_to_aa(self):
        """Should convert 27 to 'AA'."""
        assert fc_export._col_index_to_letter(27) == "AA"

    def test_col_index_28_to_ab(self):
        """Should convert 28 to 'AB'."""
        assert fc_export._col_index_to_letter(28) == "AB"

    def test_col_index_52_to_az(self):
        """Should convert 52 to 'AZ'."""
        assert fc_export._col_index_to_letter(52) == "AZ"

    def test_col_index_53_to_ba(self):
        """Should convert 53 to 'BA'."""
        assert fc_export._col_index_to_letter(53) == "BA"

    def test_col_index_702_to_zz(self):
        """Should convert 702 to 'ZZ'."""
        assert fc_export._col_index_to_letter(702) == "ZZ"

    def test_col_index_703_to_aaa(self):
        """Should convert 703 to 'AAA'."""
        assert fc_export._col_index_to_letter(703) == "AAA"


class TestFindExportableBodies:
    """Tests for finding bodies with ExportTo3MF property."""

    def test_find_exportable_bodies_none(self):
        """Should return empty list when no bodies have ExportTo3MF."""
        # Given
        mock_doc = MagicMock()
        mock_obj = MagicMock()
        del mock_obj.ExportTo3MF  # Ensure attribute doesn't exist
        mock_obj.getPropertyByName.side_effect = KeyError("ExportTo3MF")
        mock_doc.Objects = [mock_obj]

        # When
        result = fc_export.find_exportable_bodies(mock_doc)

        # Then
        assert result == []

    def test_find_exportable_bodies_one_marked_true(self):
        """Should return list with one body when ExportTo3MF=True."""
        # Given
        mock_doc = MagicMock()
        mock_body = MagicMock()
        mock_body.Name = "Body1"
        mock_body.Label = "TestBody"
        mock_body.ExportTo3MF = True
        mock_doc.Objects = [mock_body]

        # When
        result = fc_export.find_exportable_bodies(mock_doc)

        # Then
        assert len(result) == 1
        assert result[0].Name == "Body1"

    def test_find_exportable_bodies_one_marked_false(self):
        """Should return empty list when ExportTo3MF=False."""
        # Given
        mock_doc = MagicMock()
        mock_body = MagicMock()
        mock_body.ExportTo3MF = False
        mock_doc.Objects = [mock_body]

        # When
        result = fc_export.find_exportable_bodies(mock_doc)

        # Then
        assert result == []

    def test_find_exportable_bodies_multiple(self):
        """Should return all bodies with ExportTo3MF=True."""
        # Given
        mock_doc = MagicMock()
        body1 = MagicMock()
        body1.Name = "Body1"
        body1.ExportTo3MF = True
        body2 = MagicMock()
        body2.Name = "Body2"
        body2.ExportTo3MF = False
        body3 = MagicMock()
        body3.Name = "Body3"
        body3.ExportTo3MF = True
        mock_doc.Objects = [body1, body2, body3]

        # When
        result = fc_export.find_exportable_bodies(mock_doc)

        # Then
        assert len(result) == 2
        names = {obj.Name for obj in result}
        assert names == {"Body1", "Body3"}


class TestGetBodyExportProperties:
    """Tests for reading export properties from FreeCAD objects."""

    def test_get_properties_default_values(self):
        """Should return default values when no properties set."""
        # Given
        mock_obj = MagicMock()
        mock_obj.Name = "TestBody"
        # No ExportTo3MF, ExportCount, or ExportRotation attributes
        delattr(mock_obj, "ExportTo3MF")
        delattr(mock_obj, "ExportCount")
        delattr(mock_obj, "ExportRotation")
        mock_obj.getPropertyByName.side_effect = KeyError

        # When
        result = fc_export.get_body_export_properties(mock_obj)

        # Then
        assert result["count"] == 1
        assert result["rotation"] is None
        assert result["position"] is None

    def test_get_properties_with_count(self):
        """Should read ExportCount property."""
        # Given
        mock_obj = MagicMock()
        mock_obj.Name = "TestBody"
        mock_obj.ExportCount = 3

        # When
        result = fc_export.get_body_export_properties(mock_obj)

        # Then
        assert result["count"] == 3

    def test_get_properties_with_count_via_get_property_by_name(self):
        """Should read ExportCount via getPropertyByName."""
        # Given
        mock_obj = MagicMock()
        mock_obj.Name = "TestBody"
        delattr(mock_obj, "ExportCount")

        def mock_get_property(name):
            if name == "ExportCount":
                return 5
            raise KeyError(name)

        mock_obj.getPropertyByName = mock_get_property

        # When
        result = fc_export.get_body_export_properties(mock_obj)

        # Then
        assert result["count"] == 5


class TestValidateBodySourceConfig:
    """Tests for body_source configuration validation.

    Note: More comprehensive tests in test_export_config.py
    These are additional edge cases.
    """

    def test_body_source_config_with_all_valid_options(self):
        """Should accept both valid body_source values."""
        # Test config mode
        item1 = {"body_source": "config", "bodies": ["Body1"]}
        is_valid, source, warning = fc_export.validate_body_source_config(item1)
        assert is_valid is True
        assert source == "config"
        assert warning is None

        # Test properties mode
        item2 = {"body_source": "properties"}
        is_valid, source, warning = fc_export.validate_body_source_config(item2)
        assert is_valid is True
        assert source == "properties"
        assert warning is None


class TestGetExportMetadata:
    """Tests for export metadata extraction."""

    def test_get_metadata_from_config_only(self, tmp_path):
        """Should extract metadata from config when no git."""
        # Given
        item = {"metadata": {"Project": "Test", "Author": "TestAuthor"}}
        base_dir = str(tmp_path)

        # Mock git_utils to return False for is_git_repo
        with patch("fc_export.git_utils") as mock_git:
            mock_git.is_git_repo.return_value = False

            # When
            result = fc_export.get_export_metadata(item, base_dir)

        # Then
        assert result["Project"] == "Test"
        assert result["Author"] == "TestAuthor"

    def test_get_metadata_with_git_disabled(self, tmp_path):
        """Should return empty dict when git_utils not available."""
        # Given
        item = {}
        base_dir = str(tmp_path)

        # Mock git_utils as None
        with patch.dict("fc_export.__dict__", {"git_utils": None}):
            # When
            result = fc_export.get_export_metadata(item, base_dir)

        # Then
        assert result == {}


class TestLoadConfig:
    """Tests for config loading with path resolution."""

    def test_load_config_with_body_source_validation(self, tmp_path):
        """Should validate body_source and store resolved value."""
        # Given
        config_file = tmp_path / "export.yml"
        config_content = {
            "export": [
                {
                    "name": "TestProject",
                    "source": "test.FCStd",
                    "body_source": "config",
                    "bodies": ["Body1"],
                }
            ]
        }
        config_file.write_text(yaml.dump(config_content))

        # When
        with patch.dict("os.environ", {}, clear=False):
            # Set global vars
            fc_export.CONFIG_FILE = str(config_file)
            fc_export.PROJECT_ROOT = str(tmp_path)

            result = fc_export.load_config()

        # Then
        assert len(result) == 1
        assert result[0]["name"] == "TestProject"
        assert result[0].get("_body_source") == "config"

    def test_load_config_resolves_relative_paths(self, tmp_path):
        """Should resolve relative paths in config."""
        # Given
        config_file = tmp_path / "export.yml"
        config_content = {
            "export": [
                {
                    "name": "TestProject",
                    "source": "models/test.FCStd",
                    "output": "output/output.3mf",
                    "template": "templates/template.3mf",
                    "stl_output_dir": "stl",
                }
            ]
        }
        config_file.write_text(yaml.dump(config_content))

        # When
        with patch.dict("os.environ", {}, clear=False):
            fc_export.CONFIG_FILE = str(config_file)
            fc_export.PROJECT_ROOT = str(tmp_path)

            result = fc_export.load_config()

        # Then
        assert len(result) == 1
        item = result[0]
        assert str(tmp_path) in item["source"]
        assert str(tmp_path) in item["output"]
        assert str(tmp_path) in item["template"]
        assert str(tmp_path) in item["stl_output_dir"]

    def test_load_config_resolves_techdraw_paths(self, tmp_path):
        """Should resolve nested techdraw paths."""
        # Given
        config_file = tmp_path / "export.yml"
        config_content = {
            "export": [
                {
                    "name": "TestProject",
                    "source": "test.FCStd",
                    "techdraw": {
                        "output_dir": "docs",
                        "pages": [],
                    },
                }
            ]
        }
        config_file.write_text(yaml.dump(config_content))

        # When
        with patch.dict("os.environ", {}, clear=False):
            fc_export.CONFIG_FILE = str(config_file)
            fc_export.PROJECT_ROOT = str(tmp_path)

            result = fc_export.load_config()

        # Then
        assert result[0]["techdraw"]["output_dir"] == str(tmp_path / "docs")

    def test_load_config_resolves_bom_paths(self, tmp_path):
        """Should resolve nested bom paths."""
        # Given
        config_file = tmp_path / "export.yml"
        config_content = {
            "export": [
                {
                    "name": "TestProject",
                    "source": "test.FCStd",
                    "bom": {
                        "output": "docs/bom.csv",
                    },
                }
            ]
        }
        config_file.write_text(yaml.dump(config_content))

        # When
        with patch.dict("os.environ", {}, clear=False):
            fc_export.CONFIG_FILE = str(config_file)
            fc_export.PROJECT_ROOT = str(tmp_path)

            result = fc_export.load_config()

        # Then
        assert result[0]["bom"]["output"] == str(tmp_path / "docs" / "bom.csv")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
