#!/usr/bin/env python3
"""Unit tests for tools/export.py CLI passthrough."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

import export as export_cli  # noqa: E402


class TestExportParseArgs:
    def test_parse_args_new_modes(self):
        with patch.object(sys, "argv", ["export.py", "--list-exports", "--gui-only", "--screenshots-only"]):
            args = export_cli.parse_args()

        assert args.list_exports is True
        assert args.gui_only is True
        assert args.screenshots_only is True

    def test_parse_args_gui_session_run(self):
        with patch.object(sys, "argv", ["export.py", "--gui-session", "run"]):
            args = export_cli.parse_args()

        assert args.gui_session == "run"


class TestExportMainPassthrough:
    def test_main_passes_new_flags_to_fc_export(self):
        with (
            patch.object(
                sys,
                "argv",
                ["export.py", "--list-exports", "--gui-only", "--screenshots-only"],
            ),
            patch("export.subprocess.run") as mock_run,
            patch("export.Path.exists", return_value=True),
            patch("export.sys.exit", side_effect=SystemExit) as mock_exit,
        ):
            mock_run.return_value.returncode = 0

            with pytest.raises(SystemExit):
                export_cli.main()

        cmd = mock_run.call_args.args[0]
        assert "--list-exports" in cmd
        assert "--gui-only" in cmd
        assert "--screenshots-only" in cmd
        mock_exit.assert_called_once_with(0)

    def test_main_list_exports_with_name_passthrough(self):
        with (
            patch.object(sys, "argv", ["export.py", "--list-exports", "--name", "Demo"]),
            patch("export.subprocess.run") as mock_run,
            patch("export.Path.exists", return_value=True),
            patch("export.sys.exit", side_effect=SystemExit),
        ):
            mock_run.return_value.returncode = 0
            with pytest.raises(SystemExit):
                export_cli.main()

        cmd = mock_run.call_args.args[0]
        assert "--list-exports" in cmd
        assert "--name" in cmd
        assert "Demo" in cmd

    def test_dry_run_forwards_list_exports_and_gui_modes(self):
        with (
            patch.object(
                sys,
                "argv",
                ["export.py", "--dry-run", "--list-exports", "--gui-only", "--screenshots-only"],
            ),
            patch("export.subprocess.run") as mock_run,
            patch("export.Path.exists", return_value=True),
            patch("export.sys.exit", side_effect=SystemExit),
        ):
            mock_run.return_value.returncode = 0
            with pytest.raises(SystemExit):
                export_cli.main()

        cmd = mock_run.call_args.args[0]
        assert "--dry-run" in cmd
        assert "--list-exports" in cmd
        assert "--gui-only" in cmd
        assert "--screenshots-only" in cmd
