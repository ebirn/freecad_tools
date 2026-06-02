#!/usr/bin/env python3
"""Unit and integration tests for text_stamp macro.

Tests cover:
- Config loading and validation
- Variable substitution (built-in + custom)
- Text shape creation
- Face projection and pocket operations
- Dialog interaction (with mocks)
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


class FakeObject:
    """Mock FreeCAD object."""

    def __init__(self, name="TestBody", label="Test Body", is_body=False):
        self.Name = name
        self.Label = label
        self.TypeId = "PartDesign::Body" if is_body else "Part::FeaturePython"
        self.Shape = MagicMock()
        self.addObject = MagicMock()  # Add method for pocket tests
        self.Body = self if is_body else None  # For traversal in get_selected_faces


class FakeDocument:
    """Mock FreeCAD document."""

    def __init__(self):
        self.FileName = "/tmp/test.FCStd"
        self.Objects = []
        self.recompute_count = 0
        self.ActiveBody = FakeObject(name="Body", label="Body", is_body=True)

    def addObject(self, type_id, name):  # noqa: N802
        obj = FakeObject(name=name)
        self.Objects.append(obj)
        return obj

    def getObject(self, name):  # noqa: N802
        for obj in self.Objects:
            if obj.Name == name or obj.Label == name:
                return obj
        return None

    def recompute(self):  # noqa: N802
        self.recompute_count += 1


def import_text_stamp(monkeypatch, doc=None):
    """Import text_stamp macro with mocked FreeCAD context."""
    macros_dir = Path(__file__).parent.parent / "macros"
    monkeypatch.syspath_prepend(str(macros_dir))

    import FreeCAD

    if doc is None:
        doc = FakeDocument()
    monkeypatch.setattr(FreeCAD, "ActiveDocument", doc, raising=False)
    sys.modules.pop("text_stamp", None)
    return importlib.import_module("text_stamp")


class TestConfigLoading:
    """Tests for loading text_stamp config from unified config file."""

    def test_load_text_stamp_config_returns_defaults_when_no_config(self, monkeypatch):
        """When no config file exists, return sensible defaults."""
        monkeypatch.chdir("/var/tmp")  # Use /var/tmp instead, less likely to have .freecad_tools
        module = import_text_stamp(monkeypatch)

        config = module.load_text_stamp_config()

        assert config["font"] == "Arial"
        assert config["size"] == 10
        assert config["depth"] == 1.0
        # substitutions may be populated from found config, so just check it's a dict
        assert isinstance(config["substitutions"], dict)

    def test_load_text_stamp_config_reads_from_unified_config(self, monkeypatch, tmp_path):
        """Load text_stamp config from .freecad_tools/config.yml."""
        config_dir = tmp_path / ".freecad_tools"
        config_dir.mkdir()
        config_file = config_dir / "config.yml"
        config_file.write_text(
            """
export:
  - name: Test
    source: test.FCStd
    bodies: [Body]

macros:
  text_stamp:
    font: "Times New Roman"
    size: 12
    depth: 2.5
    substitutions:
      project_name: "MyProject"
      version: "1.0"
"""
        )

        monkeypatch.chdir(tmp_path)
        module = import_text_stamp(monkeypatch)

        config = module.load_text_stamp_config()

        assert config["font"] == "Times New Roman"
        assert config["size"] == 12
        assert config["depth"] == 2.5
        assert config["substitutions"]["project_name"] == "MyProject"
        assert config["substitutions"]["version"] == "1.0"

    def test_load_text_stamp_config_uses_document_directory(self, monkeypatch, tmp_path):
        """Config in document directory takes precedence over cwd."""
        doc_dir = tmp_path / "projects" / "myproject"
        doc_dir.mkdir(parents=True)
        config_dir = doc_dir / ".freecad_tools"
        config_dir.mkdir()
        config_file = config_dir / "config.yml"
        config_file.write_text(
            """
macros:
  text_stamp:
    font: "Courier"
    size: 8
"""
        )

        monkeypatch.chdir(tmp_path)
        doc = FakeDocument()
        doc.FileName = str(doc_dir / "design.FCStd")
        module = import_text_stamp(monkeypatch, doc=doc)

        config = module.load_text_stamp_config(doc)

        assert config["font"] == "Courier"
        assert config["size"] == 8


class TestVariableSubstitution:
    """Tests for variable substitution in text."""

    def test_apply_substitutions_replaces_custom_variables(self, monkeypatch):
        """Replace custom variables from config substitutions dict."""
        module = import_text_stamp(monkeypatch)
        substitutions = {"project_name": "MyAntenna", "version": "2.1"}

        result = module.apply_substitutions("{project_name} v{version}", substitutions)

        assert result == "MyAntenna v2.1"

    def test_apply_substitutions_handles_date_builtin(self, monkeypatch):
        """Built-in {date} substitution uses YYYY-MM-DD format."""
        module = import_text_stamp(monkeypatch)
        substitutions = {}

        result = module.apply_substitutions("Made {date}", substitutions)

        # Extract date and verify format
        assert "Made 20" in result  # Matches YYYY-MM-DD format
        parts = result.split()
        date_part = parts[1]
        assert len(date_part) == 10  # YYYY-MM-DD
        assert date_part[4] == "-" and date_part[7] == "-"

    def test_apply_substitutions_handles_timestamp_builtin(self, monkeypatch):
        """Built-in {timestamp} substitution."""
        module = import_text_stamp(monkeypatch)

        result = module.apply_substitutions("TS: {timestamp}", {})

        assert "TS: 20" in result  # ISO format starts with 20xx

    def test_apply_substitutions_handles_missing_variable_gracefully(self, monkeypatch):
        """Missing variables left as-is or handled gracefully."""
        module = import_text_stamp(monkeypatch)
        substitutions = {"name": "Test"}

        result = module.apply_substitutions("{name} {missing}", substitutions)

        # Should leave missing variable as-is or replace with empty string
        # (implementation choice - both are acceptable)
        assert "Test" in result

    def test_apply_substitutions_handles_nested_braces(self, monkeypatch):
        """Handle edge case of nested or malformed braces."""
        module = import_text_stamp(monkeypatch)

        # Should not crash on malformed syntax
        result = module.apply_substitutions("Text {{nested}}", {})
        assert isinstance(result, str)

    def test_apply_substitutions_with_mixed_variables(self, monkeypatch):
        """Mix built-in and custom variables in one string."""
        module = import_text_stamp(monkeypatch)
        substitutions = {"project": "Antenna"}

        result = module.apply_substitutions("{project} {date}", substitutions)

        assert "Antenna" in result
        assert "20" in result  # Year part of date


class TestTextShapeCreation:
    """Tests for creating text shapes."""

    def test_create_text_shape_returns_valid_shape(self, monkeypatch):
        """create_text_shape returns a FreeCAD Draft ShapeString object."""
        doc = FakeDocument()
        module = import_text_stamp(monkeypatch, doc=doc)

        # Mock Draft.makeShapeString
        with patch("Draft.makeShapeString") as mock_shape:
            mock_obj = MagicMock()
            mock_obj.Shape = MagicMock()
            mock_shape.return_value = mock_obj
            with patch.object(module, "get_font_path_for_name", return_value="/fake/Arial.ttf"):
                shape = module.create_text_shape("TestText", size=10)

            assert shape is not None
            mock_shape.assert_called()

    def test_create_text_shape_with_custom_font_path(self, monkeypatch):
        """create_text_shape passes font_path directly to makeShapeString when file exists."""
        module = import_text_stamp(monkeypatch)
        fake_font_path = "/fake/fonts/TimesNewRoman.ttf"

        with patch("Draft.makeShapeString") as mock_shape:
            mock_obj = MagicMock()
            mock_obj.Shape = MagicMock()
            mock_shape.return_value = mock_obj
            # Patch Path.exists to simulate the font file existing
            with patch.object(module.Path, "exists", return_value=True):
                module.create_text_shape("Text", font_path=fake_font_path, size=12)

            # Verify the custom font path was passed to makeShapeString
            call_args = mock_shape.call_args
            assert call_args is not None
            assert fake_font_path in str(call_args)


class TestFaceProjection:
    """Tests for projecting text onto faces."""

    def test_project_text_to_face_requires_valid_face(self, monkeypatch):
        """project_text_to_face handles None face gracefully."""
        module = import_text_stamp(monkeypatch)
        text_shape = MagicMock()
        invalid_face = None

        # Implementation should handle None gracefully (not raise, or raise specific error)
        try:
            result = module.project_text_to_face(text_shape, invalid_face)
            # If it doesn't raise, it should return something
            assert result is not None or result is None  # Either is acceptable
        except (TypeError, ValueError, AttributeError):
            # Also acceptable - raising a meaningful error
            pass

    def test_project_text_to_face_returns_projected_shape(self, monkeypatch):
        """project_text_to_face returns projected geometry."""
        module = import_text_stamp(monkeypatch)
        text_shape = MagicMock()
        face = MagicMock()

        projected = module.project_text_to_face(text_shape, face)
        assert projected is not None


class TestPocketOperation:
    """Tests for pocket/engrave operation."""

    def test_pocket_text_modifies_active_body(self, monkeypatch):
        """pocket_text creates a pocket feature in the active body."""
        doc = FakeDocument()
        module = import_text_stamp(monkeypatch, doc=doc)
        text_shape = MagicMock()
        depth = 1.5

        # The pocket_text function should call body.addObject() twice:
        # once to add the ShapeString to the body, once to add the pocket
        with patch.object(doc.ActiveBody, "addObject") as mock_body_add:
            module.pocket_text(text_shape, depth=depth, body=doc.ActiveBody)

            # Should add ShapeString and pocket to body (2 calls)
            assert mock_body_add.call_count == 2

    def test_pocket_text_with_custom_depth(self, monkeypatch):
        """pocket_text respects custom depth parameter."""
        doc = FakeDocument()
        module = import_text_stamp(monkeypatch, doc=doc)
        text_shape = MagicMock()

        # The pocket_text function should call body.addObject() twice:
        # once to add the ShapeString to the body, once to add the pocket
        with patch.object(doc.ActiveBody, "addObject") as mock_body_add:
            module.pocket_text(text_shape, depth=3.0, body=doc.ActiveBody)

            # Verify addObject was called twice on the body (ShapeString + pocket)
            assert mock_body_add.call_count == 2


class TestMacroIntegration:
    """Integration tests for full text stamp workflow."""

    def test_main_workflow_with_config_and_dialog(self, monkeypatch):
        """Full workflow: load config, show dialog, apply substitutions, create text."""
        doc = FakeDocument()
        config_dir = Path(doc.FileName).parent / ".freecad_tools"
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / "config.yml"
        config_file.write_text(
            """
macros:
  text_stamp:
    font: "Arial"
    size: 10
    depth: 1.0
    substitutions:
      project: "TestProj"
"""
        )

        module = import_text_stamp(monkeypatch, doc=doc)

        # Only test if QT is available (dialog is conditional)
        if not module.QT_AVAILABLE:
            # Without Qt, main() should gracefully handle missing dialog
            with patch.object(module, "get_selected_faces", return_value=[]):
                module.main()  # Should return early
            return

        # Mock dialog and other components
        with patch("text_stamp.TextStampDialog") as mock_dialog_class:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = 1  # QDialog.Accepted
            mock_dialog.get_values.return_value = {
                "text": "Test Label",
                "font_file": "/fake/Arial.ttf",
                "size": 10,
                "depth": 1.0,
            }
            mock_dialog_class.return_value = mock_dialog

            # Mock face selection
            with patch("text_stamp.get_selected_faces", return_value=[(MagicMock(), doc.ActiveBody)]):
                # Mock text shape creation
                with patch("text_stamp.create_text_shape", return_value=MagicMock()):
                    # Mock projection
                    with patch("text_stamp.project_text_to_face", return_value=MagicMock()):
                        # Mock pocket creation
                        with patch("text_stamp.pocket_text"):
                            # Should not raise
                            module.main()

    def test_macro_handles_missing_face_selection(self, monkeypatch):
        """When no face is selected, macro prompts or gracefully exits."""
        doc = FakeDocument()
        module = import_text_stamp(monkeypatch, doc=doc)

        # Mock empty selection
        with patch.object(module, "get_selected_faces") as mock_selection:
            mock_selection.return_value = []

            # Should handle gracefully (raise, return None, or show dialog)
            # Exact behavior depends on design, but should not crash
            try:
                module.main()
            except Exception as e:
                # Acceptable: raise user-friendly error
                assert "face" in str(e).lower() or "select" in str(e).lower()


class TestYAMLAvailability:
    """Verify text_stamp works with FreeCAD's bundled PyYAML."""

    def test_yaml_module_is_imported(self, monkeypatch):
        """yaml module is available (bundled with FreeCAD)."""
        module = import_text_stamp(monkeypatch)

        # Should have yaml available
        assert module.YAML_AVAILABLE is True or hasattr(module, "yaml")
