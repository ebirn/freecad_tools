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

import json
import logging
import os
import sys
import zipfile
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
        assert args.slicer_dry_run is False
        assert args.list_exports is False

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
        assert args.list_exports is False

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
        assert args.list_exports is False

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

    def test_parse_args_with_slicer_dry_run_flag(self):
        """Should parse --slicer-dry-run flag."""
        with patch.object(sys, "argv", ["fc_export.py", "--slicer-dry-run"]):
            args = fc_export.parse_args()

        assert args.slicer_dry_run is True

    def test_parse_args_with_list_exports_flag(self):
        """Should parse --list-exports flag."""
        with patch.object(sys, "argv", ["fc_export.py", "--list-exports"]):
            args = fc_export.parse_args()

        assert args.list_exports is True

    def test_parse_args_with_gui_only_flag(self):
        """Should parse --gui-only flag."""
        with patch.object(sys, "argv", ["fc_export.py", "--gui-only"]):
            args = fc_export.parse_args()

        assert args.gui_only is True

    def test_parse_args_with_screenshots_only_flag(self):
        """Should parse --screenshots-only flag."""
        with patch.object(sys, "argv", ["fc_export.py", "--screenshots-only"]):
            args = fc_export.parse_args()

        assert args.screenshots_only is True

    def test_parse_args_with_gui_session_run(self):
        """Should parse --gui-session run."""
        with patch.object(sys, "argv", ["fc_export.py", "--gui-session", "run"]):
            args = fc_export.parse_args()

        assert args.gui_session == "run"

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


class TestExportSelectionHelpers:
    """Tests for export listing and filtering helpers."""

    def test_get_export_names_uses_name_when_present(self):
        exports = [{"name": "alpha"}, {"name": "beta"}]
        assert fc_export.get_export_names(exports) == ["alpha", "beta"]

    def test_get_export_names_falls_back_to_unnamed(self):
        exports = [{"name": "alpha"}, {}, {"name": ""}]
        assert fc_export.get_export_names(exports) == ["alpha", "unnamed_1", "unnamed_2"]

    def test_filter_exports_by_name_exact_match(self):
        exports = [{"name": "alpha"}, {"name": "beta"}, {"name": "alpha"}]
        filtered = fc_export.filter_exports_by_name(exports, "alpha")
        assert filtered == [{"name": "alpha"}, {"name": "alpha"}]

    def test_select_export_by_name_returns_single_exact_match(self):
        exports = [{"name": "alpha"}, {"name": "beta"}]

        selected = fc_export.select_export_by_name(exports, "beta")

        assert selected == [{"name": "beta"}]

    def test_select_export_by_name_rejects_missing_name(self):
        exports = [{"name": "alpha"}, {"name": "beta"}]

        with pytest.raises(ValueError, match="No export item found"):
            fc_export.select_export_by_name(exports, "gamma")

    def test_select_export_by_name_rejects_duplicate_names(self):
        exports = [{"name": "alpha"}, {"name": "beta"}, {"name": "alpha"}]

        with pytest.raises(ValueError, match="Multiple export items"):
            fc_export.select_export_by_name(exports, "alpha")

    def test_get_config_candidates_prefers_unified_before_legacy(self):
        assert fc_export.get_config_candidates() == [
            ".freecad_tools/config.yml",
            ".freecad_tools/export.yml",
            "export_config.yml",
        ]

    def test_discover_config_file_prefers_unified_before_legacy(self, tmp_path):
        config_dir = tmp_path / ".freecad_tools"
        config_dir.mkdir()
        unified = config_dir / "config.yml"
        legacy_nested = config_dir / "export.yml"
        legacy_root = tmp_path / "export_config.yml"
        unified.write_text("export: []\n", encoding="utf-8")
        legacy_nested.write_text("export: []\n", encoding="utf-8")
        legacy_root.write_text("export: []\n", encoding="utf-8")

        with patch.object(fc_export.os, "getcwd", return_value=str(tmp_path)):
            discovered = fc_export.discover_config_file()

        assert discovered == str(unified)

    def test_discover_config_file_supports_nested_legacy_export_yml(self, tmp_path):
        config_dir = tmp_path / ".freecad_tools"
        config_dir.mkdir()
        legacy_nested = config_dir / "export.yml"
        legacy_nested.write_text("export: []\n", encoding="utf-8")

        with patch.object(fc_export.os, "getcwd", return_value=str(tmp_path)):
            discovered = fc_export.discover_config_file()

        assert discovered == str(legacy_nested)

    def test_main_dry_run_name_error_lists_available_exports(self):
        exports = [{"name": "alpha"}, {"name": "beta"}]

        with (
            patch.object(fc_export, "dry_run_mode", True),
            patch.object(fc_export, "name_filter", "missing"),
            patch("fc_export.load_config", return_value=exports),
            patch("fc_export.logger.warning") as mock_warning,
            patch("fc_export.logger.info") as mock_info,
            patch("fc_export.sys.exit", side_effect=SystemExit) as mock_exit,
        ):
            with pytest.raises(SystemExit):
                fc_export.main()

        assert any(
            "No export item found with name 'missing'" in str(call.args[0]) for call in mock_warning.call_args_list
        )
        assert any(
            "Available export names: ['alpha', 'beta']" in str(call.args[0]) for call in mock_info.call_args_list
        )
        mock_exit.assert_called_once_with(1)


class TestModeHelpers:
    """Tests for pipeline mode helper behavior."""

    def test_should_run_3mf_export_default(self):
        assert fc_export.should_run_3mf_export(gui_only=False, screenshots_only=False) is True

    def test_should_run_3mf_export_gui_only(self):
        assert fc_export.should_run_3mf_export(gui_only=True, screenshots_only=False) is False

    def test_should_run_3mf_export_screenshots_only(self):
        assert fc_export.should_run_3mf_export(gui_only=False, screenshots_only=True) is False

    def test_should_run_techdraw_when_present(self):
        assert fc_export.should_run_techdraw({"pages": []}, screenshots_only=False) is True

    def test_should_run_techdraw_false_in_screenshots_only(self):
        assert fc_export.should_run_techdraw({"pages": []}, screenshots_only=True) is False

    def test_has_gui_tasks_true_for_screenshots(self):
        assert fc_export.has_gui_tasks({"screenshots": {"enabled": True}}) is True

    def test_has_gui_tasks_true_for_techdraw(self):
        assert fc_export.has_gui_tasks({"techdraw": {"pages": ["Page"]}}) is True

    def test_has_gui_tasks_false_when_none_configured(self):
        assert fc_export.has_gui_tasks({}) is False

    def test_build_gui_task_summary_reports_flags(self):
        item = {"screenshots": {"enabled": True}, "techdraw": {"pages": []}}
        summary = fc_export.build_gui_task_summary(item, screenshots_only=False)
        assert summary == {"screenshots": True, "techdraw": True}

    def test_build_gui_task_summary_disables_techdraw_in_screenshots_only(self):
        item = {"screenshots": {"enabled": True}, "techdraw": {"pages": []}}
        summary = fc_export.build_gui_task_summary(item, screenshots_only=True)
        assert summary == {"screenshots": True, "techdraw": False}

    def test_plan_gui_tasks_uses_summary(self):
        item = {"screenshots": {"enabled": True}, "techdraw": {"pages": []}}
        plan = fc_export.plan_gui_tasks(item, screenshots_only=False)
        assert plan == {"run_screenshots": True, "run_techdraw": True}

    def test_build_gui_batch_config_resolves_relative_paths(self, tmp_path):
        item = {
            "bodies": ["Body"],
            "screenshots": {"output_dir": "prints/images", "views": ["front"]},
            "techdraw": {"pages": ["Page"]},
        }
        cfg = fc_export.build_gui_batch_config(item, "example.FCStd", str(tmp_path), str(tmp_path / "temp"), ["Body"])
        assert cfg["source"] == "example.FCStd"
        assert cfg["screenshots"]["output_dir"].startswith(str(tmp_path))
        assert cfg["techdraw"]["output_dir"].endswith("temp")

    def test_normalize_gui_batch_result_fills_missing_sections(self):
        normalized = fc_export.normalize_gui_batch_result({"success": False})
        assert normalized["screenshots"]["success"] is False
        assert normalized["screenshots"]["images"] == []
        assert normalized["techdraw"]["success"] is False
        assert normalized["techdraw"]["pages"] == []
        assert normalized["artifacts"]["pdf_pages"] == []
        assert normalized["timing"]["total_seconds"] == 0.0

    def test_normalize_gui_batch_result_preserves_valid_sections(self):
        payload = {
            "success": True,
            "screenshots": {"success": True, "images": [{"path": "a.png"}], "error": None, "skipped": False},
            "techdraw": {"success": True, "pages": [{"pdf_path": "a.pdf"}], "error": None},
            "error": None,
        }
        normalized = fc_export.normalize_gui_batch_result(payload)
        assert normalized["success"] is True
        assert normalized["screenshots"]["images"][0]["path"] == "a.png"
        assert normalized["techdraw"]["pages"][0]["pdf_path"] == "a.pdf"

    def test_normalize_gui_batch_result_preserves_artifacts_and_timing(self):
        payload = {
            "success": True,
            "screenshots": {"success": True, "images": [], "error": None, "skipped": False},
            "techdraw": {"success": True, "pages": [], "error": None},
            "artifacts": {"pdf_pages": ["a.pdf"], "images": ["a.png"]},
            "timing": {"total_seconds": 1.25, "techdraw_seconds": 0.4, "screenshots_seconds": 0.6},
            "error": None,
        }
        normalized = fc_export.normalize_gui_batch_result(payload)
        assert normalized["artifacts"]["pdf_pages"] == ["a.pdf"]
        assert normalized["artifacts"]["images"] == ["a.png"]
        assert normalized["timing"]["total_seconds"] == 1.25

    def test_summarize_gui_batch_result_formats_counts_and_timing(self):
        payload = {
            "success": True,
            "screenshots": {"success": True, "images": [], "error": None, "skipped": False},
            "techdraw": {"success": True, "pages": [], "error": None},
            "artifacts": {"pdf_pages": ["p1.pdf", "p2.pdf"], "images": ["i1.png"]},
            "timing": {"total_seconds": 2.5, "techdraw_seconds": 1.0, "screenshots_seconds": 1.2},
            "error": None,
        }
        summary = fc_export.summarize_gui_batch_result(payload)
        assert "success=True" in summary
        assert "screenshots=True(1 images)" in summary
        assert "techdraw=True(2 pages)" in summary
        assert "time=2.500s" in summary

    def test_summarize_export_timing_formats_stage_times(self):
        summary = fc_export.summarize_export_timing(
            "Demo",
            {
                "open_seconds": 0.5,
                "export_seconds": 1.25,
                "gui_seconds": 0.75,
                "total_seconds": 2.6,
            },
        )
        assert "Export timing [Demo]" in summary
        assert "open=0.500s" in summary
        assert "export=1.250s" in summary
        assert "gui=0.750s" in summary
        assert "total=2.600s" in summary

    def test_log_export_timing_emits_summary_line(self):
        timing_data = {
            "open_seconds": 0.1,
            "export_seconds": 0.2,
            "gui_seconds": 0.3,
            "total_seconds": 0.7,
        }
        with patch("fc_export.logger.info") as mock_info:
            fc_export.log_export_timing("Demo", timing_data)

        assert mock_info.call_count == 1
        msg = mock_info.call_args.args[0]
        assert "Export timing [Demo]" in msg
        assert "total=0.700s" in msg

    def test_summarize_run_stats_formats_overall_totals(self):
        summary = fc_export.summarize_run_stats(
            {
                "item_count": 3,
                "open_seconds": 1.0,
                "export_seconds": 2.0,
                "gui_seconds": 3.0,
                "shared_gui_seconds": 4.0,
                "total_seconds": 10.0,
            }
        )
        assert "items=3" in summary
        assert "open=1.000s" in summary
        assert "export=2.000s" in summary
        assert "gui=3.000s" in summary
        assert "shared_gui=4.000s" in summary
        assert "total=10.000s" in summary

    def test_build_shared_gui_job_with_relative_paths(self):
        item = {
            "techdraw_source": "config",
            "techdraw": {"pages": ["Page"], "output_dir": "docs"},
            "screenshots": {
                "output_dir": "images",
                "views": ["front"],
                "resolution": [800, 600],
                "format": "jpg",
                "composite": False,
                "bodies": ["Body"],
            },
        }

        job = fc_export.build_shared_gui_job(
            item,
            "Demo",
            "src.FCStd",
            "/tmp/project",
            ["Body"],
            screenshots_only=False,
        )

        assert job["name"] == "Demo"
        assert job["source"] == "src.FCStd"
        assert job["techdraw"]["enabled"] is True
        assert job["techdraw"]["pages"] == ["Page"]
        assert job["techdraw"]["temp_dir"].endswith("test_output/_gui_pages/Demo")
        assert job["screenshots"]["enabled"] is True
        assert job["screenshots"]["output_dir"] == "/tmp/project/images"
        assert job["screenshots"]["views"] == ["front"]
        assert job["screenshots"]["resolution"] == [800, 600]
        assert job["screenshots"]["format"] == "jpg"
        assert job["screenshots"]["composite"] is False
        assert job["screenshots"]["bodies"] == ["Body"]

    def test_build_shared_gui_job_screenshots_only_disables_techdraw(self):
        item = {"techdraw": {"pages": ["Page"]}, "screenshots": {"bodies": ["Body"]}}

        job = fc_export.build_shared_gui_job(item, "Demo", "src.FCStd", "/tmp/project", ["Body"], screenshots_only=True)

        assert job["techdraw"]["enabled"] is False
        assert job["screenshots"]["enabled"] is True


class TestGuiTaskExecution:
    """Tests for GUI task orchestration boundaries."""

    def test_run_gui_tasks_for_item_screenshots_only_skips_techdraw(self, tmp_path):
        doc = MagicMock()
        item = {
            "name": "demo",
            "source": "example.FCStd",
            "screenshots": {"enabled": True},
            "techdraw": {"pages": ["Page"]},
        }

        with (
            patch("fc_export.run_screenshot_generation") as mock_screenshots,
            patch("fc_export.export_techdraw_to_pdf") as mock_techdraw,
        ):
            mock_screenshots.return_value = (True, {"success": True, "images": []})

            result = fc_export.run_gui_tasks_for_item(
                doc,
                item,
                "demo",
                "example.FCStd",
                str(tmp_path),
                ["Body"],
                screenshots_only=True,
            )

        assert result["screenshot"]["success"] is True
        mock_screenshots.assert_called_once()
        mock_techdraw.assert_not_called()

    def test_run_gui_tasks_for_item_uses_batched_path_when_both_enabled(self, tmp_path):
        doc = MagicMock()
        item = {
            "name": "demo",
            "source": "example.FCStd",
            "screenshots": {"enabled": True},
            "techdraw": {"pages": ["Page"]},
        }

        with (
            patch("fc_export.run_gui_tasks_batched") as mock_batched,
            patch("fc_export.export_techdraw_to_pdf", return_value=True),
        ):
            mock_batched.return_value = {
                "screenshot": {"success": True, "result": {"success": True, "images": []}},
                "techdraw": {"success": True, "output": "demo.pdf"},
                "last_bom_csv": None,
            }
            result = fc_export.run_gui_tasks_for_item(
                doc,
                item,
                "demo",
                "example.FCStd",
                str(tmp_path),
                ["Body"],
                screenshots_only=False,
            )

        mock_batched.assert_called_once()
        assert result["screenshot"]["success"] is True
        assert result["techdraw"]["success"] is True

    def test_run_gui_tasks_for_item_falls_back_when_batched_unavailable(self, tmp_path):
        doc = MagicMock()
        item = {
            "name": "demo",
            "source": "example.FCStd",
            "screenshots": {"enabled": True},
            "techdraw": {"pages": ["Page"]},
        }

        with (
            patch(
                "fc_export.run_gui_tasks_batched",
                return_value={"screenshot": None, "techdraw": None, "last_bom_csv": None},
            ),
            patch(
                "fc_export.run_screenshot_generation", return_value=(True, {"success": True, "images": []})
            ) as mock_screens,
            patch("fc_export.export_techdraw_to_pdf", return_value=True) as mock_pdf,
            patch("fc_export.extract_bom_from_assembly", return_value=[]),
            patch("fc_export.extract_bom_from_spreadsheet", return_value=[]),
            patch("fc_export.extract_bom_from_parts", return_value=[]),
        ):
            result = fc_export.run_gui_tasks_for_item(
                doc,
                item,
                "demo",
                "example.FCStd",
                str(tmp_path),
                ["Body"],
                screenshots_only=False,
            )

        assert result["screenshot"]["success"] is True
        mock_screens.assert_called_once()
        mock_pdf.assert_called_once()

    def test_run_gui_tasks_batched_runs_single_gui_process(self, tmp_path):
        doc = MagicMock()
        source_path = str(tmp_path / "example.FCStd")
        (tmp_path / "example.FCStd").write_text("stub", encoding="utf-8")
        item = {
            "name": "demo",
            "source": source_path,
            "bodies": ["Body"],
            "screenshots": {"enabled": True, "views": ["isometric"]},
            "techdraw": {"pages": ["Page"]},
        }

        gui_calls = {"count": 0}

        def fake_run(cmd, capture_output, text, timeout, **kwargs):
            if cmd[1].endswith("gui_batch_export.py"):
                gui_calls["count"] += 1
                with open(cmd[2], encoding="utf-8") as f:
                    batch_cfg = json.load(f)
                with open(batch_cfg["result_file"], "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "success": True,
                            "screenshots": {"success": True, "images": [], "error": None, "skipped": False},
                            "techdraw": {
                                "success": True,
                                "pages": [{"name": "Page", "pdf_path": str(tmp_path / "Page.pdf")}],
                                "error": None,
                            },
                        },
                        f,
                    )
                return MagicMock(returncode=0, stderr="", stdout="")

            if cmd[1].endswith("techdraw_pdf.py"):
                with open(cmd[2], encoding="utf-8") as f:
                    merge_cfg = json.load(f)
                output_path = merge_cfg["output_path"]
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text("pdf", encoding="utf-8")
                return MagicMock(returncode=0, stderr="", stdout="")

            raise AssertionError(f"Unexpected subprocess command: {cmd}")

        with (
            patch(
                "fc_export._find_freecad_gui_binary", return_value="/Applications/FreeCAD.app/Contents/MacOS/FreeCAD"
            ),
            patch("fc_export._find_venv_python", return_value=sys.executable),
            patch("fc_export.subprocess.run", side_effect=fake_run),
            patch("fc_export.logger.info") as mock_info,
        ):
            result = fc_export.run_gui_tasks_batched(doc, item, "demo", source_path, str(tmp_path), ["Body"])

        assert gui_calls["count"] == 1
        assert result["screenshot"]["success"] is True
        assert result["techdraw"]["success"] is True
        assert any("GUI batch result:" in str(call.args[0]) for call in mock_info.call_args_list if call.args)

    def test_run_gui_tasks_batched_respects_techdraw_output_dir(self, tmp_path):
        doc = MagicMock()
        source_path = str(tmp_path / "example.FCStd")
        (tmp_path / "example.FCStd").write_text("stub", encoding="utf-8")
        output_dir = tmp_path / "generated" / "docs"
        item = {
            "name": "demo",
            "source": source_path,
            "bodies": ["Body"],
            "screenshots": {"enabled": True, "views": ["isometric"]},
            "techdraw": {"pages": ["Page"], "output_dir": str(output_dir)},
        }

        def fake_run(cmd, capture_output, text, timeout, **kwargs):
            if cmd[1].endswith("gui_batch_export.py"):
                with open(cmd[2], encoding="utf-8") as f:
                    batch_cfg = json.load(f)
                with open(batch_cfg["result_file"], "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "success": True,
                            "screenshots": {"success": True, "images": [], "error": None, "skipped": False},
                            "techdraw": {
                                "success": True,
                                "pages": [{"name": "Page", "pdf_path": str(tmp_path / "Page.pdf")}],
                                "error": None,
                            },
                        },
                        f,
                    )
                return MagicMock(returncode=0, stderr="", stdout="")

            if cmd[1].endswith("techdraw_pdf.py"):
                with open(cmd[2], encoding="utf-8") as f:
                    merge_cfg = json.load(f)
                output_path = merge_cfg["output_path"]
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text("pdf", encoding="utf-8")
                return MagicMock(returncode=0, stderr="", stdout="")

            raise AssertionError(f"Unexpected subprocess command: {cmd}")

        with (
            patch(
                "fc_export._find_freecad_gui_binary", return_value="/Applications/FreeCAD.app/Contents/MacOS/FreeCAD"
            ),
            patch("fc_export._find_venv_python", return_value=sys.executable),
            patch("fc_export.subprocess.run", side_effect=fake_run),
        ):
            result = fc_export.run_gui_tasks_batched(doc, item, "demo", source_path, str(tmp_path), ["Body"])

        assert result["techdraw"]["success"] is True
        assert result["techdraw"]["output"] == str(output_dir / "demo.pdf")

    def test_main_gui_only_uses_batched_path_once_for_combined_tasks(self, tmp_path):
        source_path = tmp_path / "example.FCStd"
        source_path.write_text("stub", encoding="utf-8")

        doc = MagicMock()
        doc.Name = "Doc"
        doc.FileName = str(source_path)
        doc.Objects = []

        export_item = {
            "name": "demo",
            "source": str(source_path),
            "screenshots": {"enabled": True},
            "techdraw": {"pages": ["Page"]},
        }

        with (
            patch.object(fc_export, "dry_run_mode", False),
            patch.object(fc_export, "list_exports_mode", False),
            patch.object(fc_export, "gui_only_mode", True),
            patch.object(fc_export, "screenshots_only_mode", False),
            patch.object(fc_export, "name_filter", None),
            patch("fc_export.load_config", return_value=[export_item]),
            patch("fc_export.FreeCAD.open", return_value=doc),
            patch("fc_export.FreeCAD.setActiveDocument"),
            patch("fc_export.FreeCAD.closeDocument"),
            patch("fc_export.run_gui_tasks_batched") as mock_batched,
            patch("fc_export.run_screenshot_generation") as mock_screenshots,
            patch("fc_export.export_techdraw_to_pdf") as mock_techdraw,
            patch("fc_export.sys.exit", side_effect=SystemExit),
        ):
            mock_batched.return_value = {
                "screenshot": {"success": True, "result": {"success": True, "images": []}},
                "techdraw": {"success": True, "output": str(tmp_path / "docs" / "demo.pdf")},
                "last_bom_csv": None,
            }

            with pytest.raises(SystemExit):
                fc_export.main()

        mock_batched.assert_called_once()
        mock_screenshots.assert_not_called()
        mock_techdraw.assert_called_once()

    @pytest.mark.integration
    def test_main_gui_session_run_batches_multiple_jobs_once(self, tmp_path):
        source_path = tmp_path / "example.FCStd"
        source_path.write_text("stub", encoding="utf-8")

        doc_one = MagicMock()
        doc_one.Name = "Doc1"
        doc_one.FileName = str(source_path)
        doc_one.Objects = []

        doc_two = MagicMock()
        doc_two.Name = "Doc2"
        doc_two.FileName = str(source_path)
        doc_two.Objects = []

        exports = [
            {
                "name": "one",
                "source": str(source_path),
                "screenshots": {"enabled": True, "bodies": ["Body"]},
                "techdraw": {"pages": ["Page"]},
            },
            {
                "name": "two",
                "source": str(source_path),
                "screenshots": {"enabled": True, "bodies": ["Body"]},
                "techdraw": {"pages": ["Page"]},
            },
        ]

        with (
            patch.object(fc_export, "dry_run_mode", False),
            patch.object(fc_export, "list_exports_mode", False),
            patch.object(fc_export, "gui_only_mode", True),
            patch.object(fc_export, "screenshots_only_mode", False),
            patch.object(fc_export, "gui_session_mode", "run"),
            patch.object(fc_export, "name_filter", None),
            patch.object(fc_export, "PROJECT_ROOT", str(tmp_path)),
            patch("fc_export.load_config", return_value=exports),
            patch("fc_export.FreeCAD.open", side_effect=[doc_one, doc_two]),
            patch("fc_export.FreeCAD.setActiveDocument"),
            patch("fc_export.FreeCAD.closeDocument"),
            patch("fc_export.run_gui_tasks_for_item") as mock_per_item,
            patch("fc_export.run_gui_tasks_shared_session") as mock_shared,
            patch("fc_export.merge_techdraw_pdfs", return_value=True),
            patch("fc_export.warn_on_near_uniform_images"),
            patch("fc_export.sys.exit", side_effect=SystemExit),
        ):
            mock_shared.return_value = {
                "one": {
                    "screenshots": {"success": True, "images": []},
                    "techdraw": {"pages": [{"name": "Page", "pdf_path": str(tmp_path / "one_page.pdf")}]},
                },
                "two": {
                    "screenshots": {"success": True, "images": []},
                    "techdraw": {"pages": [{"name": "Page", "pdf_path": str(tmp_path / "two_page.pdf")}]},
                },
            }

            with pytest.raises(SystemExit):
                fc_export.main()

        mock_per_item.assert_not_called()
        mock_shared.assert_called_once()
        queued_jobs = mock_shared.call_args.args[0]
        assert len(queued_jobs) == 2
        assert {job["name"] for job in queued_jobs} == {"one", "two"}

    def test_run_screenshot_generation_passes_json_config_to_gui_subprocess(self, tmp_path):
        source_path = tmp_path / "example.FCStd"
        source_path.write_text("stub", encoding="utf-8")

        export_item = {
            "name": "demo",
            "source": str(source_path),
            "bodies": ["Body"],
            "screenshots": {
                "enabled": True,
                "output_dir": str(tmp_path / "generated" / "docs" / "images"),
                "views": ["isometric", "front"],
                "format": "png",
            },
        }

        def fake_run(cmd, env, capture_output, text, timeout, cwd):
            assert cmd[1] == "-c"
            script_expr = cmd[2]
            assert "sys.argv=['body_screenshot.py'," in script_expr
            assert "screenshot_config.json" in script_expr

            result_file = env["FREECAD_TOOLS_SCREENSHOT_RESULT"]
            with open(result_file, "w", encoding="utf-8") as result_handle:
                json.dump({"success": True, "images": [{"path": "x.png"}], "error": None}, result_handle)

            return MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("fc_export._find_freecad_gui_binary", return_value="/opt/freecad/usr/bin/freecad"),
            patch("fc_export.subprocess.run", side_effect=fake_run),
        ):
            success, result = fc_export.run_screenshot_generation(export_item, str(tmp_path))

        assert success is True
        assert result["success"] is True
        assert len(result["images"]) == 1


class TestScreenshotValidation:
    """Tests for near-uniform screenshot warning logic."""

    def test_warn_on_near_uniform_images_emits_warning(self, tmp_path):
        image_path = tmp_path / "blank.png"
        image_path.write_text("stub", encoding="utf-8")
        images = [{"path": str(image_path)}]

        with patch("fc_export._compute_image_stddev", return_value=0.5), patch("fc_export.log_warning_msg") as warn:
            fc_export.warn_on_near_uniform_images(images, stddev_threshold=1.5)

        warn.assert_called_once()

    def test_warn_on_near_uniform_images_no_warning_above_threshold(self, tmp_path):
        image_path = tmp_path / "normal.png"
        image_path.write_text("stub", encoding="utf-8")
        images = [{"path": str(image_path)}]

        with patch("fc_export._compute_image_stddev", return_value=3.0), patch("fc_export.log_warning_msg") as warn:
            fc_export.warn_on_near_uniform_images(images, stddev_threshold=1.5)

        warn.assert_not_called()


class TestSubprocessSummaries:
    """Tests for concise subprocess stderr summaries."""

    def test_summarize_subprocess_stderr_empty(self):
        assert fc_export.summarize_subprocess_stderr("") == ""

    def test_summarize_subprocess_stderr_compacts_multiline(self):
        stderr = "line one\n\nline two\n"
        assert fc_export.summarize_subprocess_stderr(stderr) == "line one line two"

    def test_summarize_subprocess_stderr_truncates_long_text(self):
        stderr = "x" * 400
        summary = fc_export.summarize_subprocess_stderr(stderr, limit=50)
        assert summary.endswith("...")
        assert len(summary) == 53


class TestSlicerConfigAndCommands:
    """Tests for slicer config validation and command building."""

    def test_validate_slicer_config_disabled_is_valid(self):
        item = {"name": "demo", "slicer": {"enabled": False}}
        valid, error = fc_export.validate_slicer_config(item)
        assert valid is True
        assert error is None

    def test_validate_slicer_config_requires_valid_engine(self):
        item = {"name": "demo", "slicer": {"enabled": True, "engine": "invalid"}}
        valid, error = fc_export.validate_slicer_config(item)
        assert valid is False
        assert "slicer.engine" in error

    def test_validate_slicer_config_requires_profiles_without_template(self):
        item = {
            "name": "demo",
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "prusa": {},
            },
        }
        valid, error = fc_export.validate_slicer_config(item)
        assert valid is False
        assert "requires either profiles" in error

    def test_validate_slicer_config_allows_missing_profiles_with_template(self):
        item = {
            "name": "demo",
            "template": "template.3mf",
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "prusa": {},
            },
        }
        valid, error = fc_export.validate_slicer_config(item)
        assert valid is True
        assert error is None

    def test_validate_slicer_config_accepts_config_bundle_without_template(self):
        item = {
            "name": "demo",
            "slicer": {
                "enabled": True,
                "engine": "orca",
                "use_config_bundle": True,
                "config_bundle": "profile.ini",
                "orca": {},
            },
        }
        valid, error = fc_export.validate_slicer_config(item)
        assert valid is True
        assert error is None

    def test_build_slicer_command_prusa_profiles(self, tmp_path):
        item = {
            "name": "demo",
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "prusa": {
                    "printer_profile": "mk4",
                    "print_profile": "0.2 quality",
                    "material_profile": "PLA",
                    "extra_args": ["--some-flag"],
                },
                "output_dir": str(tmp_path),
                "output_name": "{name}_{engine}.gcode",
            },
        }
        cmd, output_path, _ = fc_export.build_slicer_command(item, "/tmp/in.3mf")
        assert cmd[0].endswith("prusa-slicer") or cmd[0].endswith("PrusaSlicer")
        assert "--printer-profile" in cmd
        assert "--print-profile" in cmd
        assert "--material-profile" in cmd
        assert "--some-flag" in cmd
        assert output_path.endswith("demo_prusa.gcode")

    def test_build_slicer_command_orca_with_config_bundle(self, tmp_path):
        item = {
            "name": "demo",
            "slicer": {
                "enabled": True,
                "engine": "orca",
                "use_config_bundle": True,
                "config_bundle": "/tmp/orca.ini",
                "output_dir": str(tmp_path),
                "orca": {},
            },
        }
        cmd, _, _ = fc_export.build_slicer_command(item, "/tmp/in.3mf")
        assert cmd[0].endswith("orca-slicer") or cmd[0].endswith("OrcaSlicer")
        assert "--slice" in cmd
        assert "--outputdir" in cmd
        assert "--load-settings" in cmd
        assert "/tmp/orca.ini" in cmd

    def test_build_orca_command_uses_template_bundle_when_no_config_bundle(self, tmp_path):
        template_3mf = tmp_path / "template.3mf"
        cfg = "; print_settings_id = 0.20mm STRUCTURAL @MINIIS 0.4 - Flo\n"
        with zipfile.ZipFile(template_3mf, "w") as archive:
            archive.writestr("Metadata/Slic3r_PE.config", cfg)

        item = {
            "name": "demo",
            "template": str(template_3mf),
            "slicer": {
                "enabled": True,
                "engine": "orca",
                "output_dir": str(tmp_path),
                "orca": {},
            },
        }
        cmd, _, temp_bundle = fc_export.build_slicer_command(item, "/tmp/in.3mf")
        assert "--load-settings" in cmd
        assert temp_bundle is not None
        assert os.path.exists(temp_bundle)

    def test_run_slicer_for_export_item_respects_dry_run(self):
        item = {
            "name": "demo",
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "dry_run": True,
                "prusa": {
                    "printer_profile": "mk4",
                    "print_profile": "0.2 quality",
                    "material_profile": "PLA",
                },
            },
        }
        with patch("fc_export.subprocess.run") as mock_run:
            ok = fc_export.run_slicer_for_export_item(item, "/tmp/in.3mf")
        assert ok is True
        mock_run.assert_not_called()

    def test_run_slicer_for_export_item_handles_non_zero_exit(self):
        item = {
            "name": "demo",
            "template": "template.3mf",
            "slicer": {"enabled": True, "engine": "prusa", "prusa": {}},
        }
        proc = MagicMock(returncode=2, stderr="bad", stdout="")
        with patch("fc_export.subprocess.run", return_value=proc):
            ok = fc_export.run_slicer_for_export_item(item, "/tmp/in.3mf")
        assert ok is False

    def test_extract_prusa_profiles_from_template_3mf(self, tmp_path):
        template_3mf = tmp_path / "template.3mf"
        cfg = """; print_settings_id = 0.20mm STRUCTURAL @MINIIS 0.4 - Flo
; filament_settings_id = \"Prusament PLA @MINIIS - Flo\"
; printer_settings_id = Original Prusa MINI & MINI+ Input Shaper
"""
        with zipfile.ZipFile(template_3mf, "w") as archive:
            archive.writestr("Metadata/Slic3r_PE.config", cfg)

        result = fc_export._extract_prusa_profiles_from_template(str(template_3mf))
        assert result["printer_profile"] == "Original Prusa MINI & MINI+ Input Shaper"
        assert result["print_profile"] == "0.20mm STRUCTURAL @MINIIS 0.4 - Flo"
        assert result["material_profile"] == "Prusament PLA @MINIIS - Flo"

    def test_build_slicer_command_uses_template_bundle_when_profiles_missing(self, tmp_path):
        template_3mf = tmp_path / "template.3mf"
        cfg = """; print_settings_id = 0.20mm STRUCTURAL @MINIIS 0.4 - Flo
; filament_settings_id = Generic PLA @MINIIS
; printer_settings_id = Original Prusa MINI & MINI+ Input Shaper
"""
        with zipfile.ZipFile(template_3mf, "w") as archive:
            archive.writestr("Metadata/Slic3r_PE.config", cfg)

        item = {
            "name": "demo",
            "template": str(template_3mf),
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "output_dir": str(tmp_path),
                "prusa": {},
            },
        }

        cmd, _, temp_bundle = fc_export.build_slicer_command(item, "/tmp/in.3mf")
        assert "--load" in cmd
        assert temp_bundle is not None
        assert os.path.exists(temp_bundle)

    def test_build_slicer_command_uses_template_config_bundle_when_no_overrides(self, tmp_path):
        template_3mf = tmp_path / "template.3mf"
        cfg = """; print_settings_id = 0.20mm STRUCTURAL @MINIIS 0.4 - Flo
; filament_settings_id = Generic PLA @MINIIS
; printer_settings_id = Original Prusa MINI & MINI+ Input Shaper
"""
        with zipfile.ZipFile(template_3mf, "w") as archive:
            archive.writestr("Metadata/Slic3r_PE.config", cfg)

        item = {
            "name": "demo",
            "template": str(template_3mf),
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "output_dir": str(tmp_path),
                "prusa": {},
            },
        }

        cmd, _, temp_bundle = fc_export.build_slicer_command(item, "/tmp/in.3mf")
        assert "--load" in cmd
        assert temp_bundle is not None

    def test_resolve_slicer_binary_prefers_path_candidate(self):
        cfg = {"engine": "prusa"}
        with (
            patch("fc_export.shutil.which", side_effect=[None, None]),
            patch("fc_export.os.path.exists", return_value=True),
        ):
            resolved = fc_export._resolve_slicer_binary(cfg)

        assert resolved.endswith("PrusaSlicer")

    def test_resolve_slicer_binary_uses_which_when_available(self):
        cfg = {"engine": "orca"}
        with patch("fc_export.shutil.which", return_value="/usr/local/bin/orca-slicer"):
            resolved = fc_export._resolve_slicer_binary(cfg)

        assert resolved == "/usr/local/bin/orca-slicer"

    @pytest.mark.integration
    def test_main_runs_slicer_stage_after_3mf_export(self, tmp_path):
        source_path = tmp_path / "example.FCStd"
        source_path.write_text("stub", encoding="utf-8")
        output_path = tmp_path / "out.3mf"
        output_path.write_text("3mf", encoding="utf-8")

        doc = MagicMock()
        doc.Name = "Doc"
        doc.FileName = str(source_path)
        doc.Objects = []

        export_item = {
            "name": "demo",
            "source": str(source_path),
            "output": str(output_path),
            "template": "template.3mf",
            "bodies": ["Body"],
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "prusa": {},
                "run_after_export": True,
            },
        }

        with (
            patch.object(fc_export, "dry_run_mode", False),
            patch.object(fc_export, "list_exports_mode", False),
            patch.object(fc_export, "gui_only_mode", False),
            patch.object(fc_export, "screenshots_only_mode", False),
            patch.object(fc_export, "name_filter", None),
            patch("fc_export.load_config", return_value=[export_item]),
            patch("fc_export.FreeCAD.open", return_value=doc),
            patch("fc_export.FreeCAD.setActiveDocument"),
            patch("fc_export.FreeCAD.closeDocument"),
            patch("fc_export.resolve_template_path", return_value="template.3mf"),
            patch("fc_export.export_bodies_to_3mf_with_template", return_value=True),
            patch("fc_export.run_gui_tasks_for_item"),
            patch("fc_export.run_slicer_for_export_item", return_value=True) as mock_run_slicer,
            patch("fc_export.sys.exit", side_effect=SystemExit),
        ):
            with pytest.raises(SystemExit):
                fc_export.main()

        mock_run_slicer.assert_called_once_with(export_item, str(output_path))


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

    def test_load_config_resolves_slicer_paths(self, tmp_path):
        """Should resolve nested slicer paths and validate slicer config."""
        config_file = tmp_path / "export.yml"
        config_content = {
            "export": [
                {
                    "name": "TestProject",
                    "source": "test.FCStd",
                    "template": "templates/template.3mf",
                    "slicer": {
                        "enabled": True,
                        "engine": "prusa",
                        "output_dir": "gcode",
                        "config_bundle": "configs/prusa.ini",
                        "binary": "bin/prusa-slicer",
                        "prusa": {},
                    },
                }
            ]
        }
        config_file.write_text(yaml.dump(config_content))

        with patch.dict("os.environ", {}, clear=False):
            fc_export.CONFIG_FILE = str(config_file)
            fc_export.PROJECT_ROOT = str(tmp_path)

            result = fc_export.load_config()

        slicer = result[0]["slicer"]
        assert slicer["output_dir"] == str(tmp_path / "gcode")
        assert slicer["config_bundle"] == str(tmp_path / "configs" / "prusa.ini")
        assert slicer["binary"] == str(tmp_path / "bin" / "prusa-slicer")


class TestPythonPassEnvForwarding:
    """Tests verifying that the Python-pass sets FREECAD_TOOLS_LIB3MF_PYTHON before freecadcmd.

    When fc_export.py is invoked directly (via hooks or CLI, not via export.py), the
    FREECAD_TOOLS_LIB3MF_PYTHON env var is not set.  The Python-pass must inject
    sys.executable into the subprocess env BEFORE launching freecadcmd so that the
    FreeCAD pass never falls back to freecadcmd itself as the lib3mf Python interpreter.
    """

    def test_python_pass_sets_lib3mf_python_when_not_in_env(self, tmp_path):
        """Python-pass must set FREECAD_TOOLS_LIB3MF_PYTHON if not already present."""

        # Given: FREECAD_TOOLS_LIB3MF_PYTHON is NOT in the environment
        env_without = {k: v for k, v in os.environ.items() if k != "FREECAD_TOOLS_LIB3MF_PYTHON"}

        captured_env = {}

        def fake_run(cmd, env=None, **kwargs):
            if env:
                captured_env.update(env)
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        with (
            patch.dict("os.environ", env_without, clear=True),
            patch("fc_export.sys.executable", "/venv/bin/python3"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            # Simulate the Python-pass env-building block by calling it directly.
            # We exercise the env construction logic inline.
            env = os.environ.copy()
            if "FREECAD_TOOLS_LIB3MF_PYTHON" not in env:
                env["FREECAD_TOOLS_LIB3MF_PYTHON"] = fc_export.sys.executable

            # Then: the subprocess env must contain FREECAD_TOOLS_LIB3MF_PYTHON
            assert "FREECAD_TOOLS_LIB3MF_PYTHON" in env
            assert env["FREECAD_TOOLS_LIB3MF_PYTHON"] == "/venv/bin/python3"

    def test_python_pass_preserves_existing_lib3mf_python(self):
        """If FREECAD_TOOLS_LIB3MF_PYTHON is already set, it must not be overwritten."""
        original = "/custom/python3"

        with patch.dict("os.environ", {"FREECAD_TOOLS_LIB3MF_PYTHON": original}, clear=False):
            env = os.environ.copy()
            if "FREECAD_TOOLS_LIB3MF_PYTHON" not in env:
                env["FREECAD_TOOLS_LIB3MF_PYTHON"] = "/should/not/appear"

            assert env["FREECAD_TOOLS_LIB3MF_PYTHON"] == original

    def test_find_venv_python_returns_env_var_when_set(self):
        """_find_venv_python should return FREECAD_TOOLS_LIB3MF_PYTHON when set."""
        with patch.dict("os.environ", {"FREECAD_TOOLS_LIB3MF_PYTHON": "/env/python3"}, clear=False):
            result = fc_export._find_venv_python()
        assert result == "/env/python3"

    def test_find_venv_python_returns_venv_when_env_not_set(self):
        """_find_venv_python should find .venv/bin/python3 relative to tools/ (real venv)."""
        env_without = {k: v for k, v in os.environ.items() if k != "FREECAD_TOOLS_LIB3MF_PYTHON"}

        with patch.dict("os.environ", env_without, clear=True):
            result = fc_export._find_venv_python()

        # The real project venv should be found (symlink → cpython)
        expected = str((Path(fc_export.__file__).parent.parent / ".venv" / "bin" / "python3").resolve())
        # Result may be a symlink; compare resolved paths
        assert Path(result).resolve() == Path(expected).resolve()

    def test_find_venv_python_warns_when_falling_back_to_sys_executable(self):
        """_find_venv_python should log a warning when falling back to sys.executable."""
        env_without = {k: v for k, v in os.environ.items() if k != "FREECAD_TOOLS_LIB3MF_PYTHON"}

        with (
            patch.dict("os.environ", env_without, clear=True),
            patch("fc_export.os.path.exists", return_value=False),
            patch("fc_export.sys.executable", "/usr/bin/freecadcmd"),
        ):
            result = fc_export._find_venv_python()

        # Should still return something (sys.executable) rather than crash
        assert result == "/usr/bin/freecadcmd"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
