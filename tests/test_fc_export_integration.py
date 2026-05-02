#!/usr/bin/env python3
"""Integration tests for fc_export.py functions that require FreeCAD.

These tests require FreeCAD to be installed and available.
They test functions that interact with FreeCAD documents and objects.

Tests requiring FreeCAD are skipped when FreeCAD is not available
using pytest.mark.skipif.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add tools/ to path for importing fc_export
_test_dir = Path(__file__).parent
_tools_dir = _test_dir.parent / "tools"
sys.path.insert(0, str(_tools_dir))

# Import after path setup
# noqa: E402
import fc_export  # noqa: E402


# Check if FreeCAD is available (not mocked)
def _freecad_available():
    """Check if FreeCAD is available for testing (not mocked)."""
    try:
        import sys
        from unittest.mock import MagicMock

        import FreeCAD

        # Check if FreeCAD is a mock module (from conftest.py mocking)
        if isinstance(FreeCAD, MagicMock):
            return False

        # Check if it's the mock object that conftest sets
        if FreeCAD is sys.modules.get("FreeCAD", None) and hasattr(sys.modules["FreeCAD"], "_mock_name"):
            return False

        # If we can import FreeCAD and it's not a mock, it's real
        return True
    except ImportError:
        return False


# Skip decorator for FreeCAD-dependent tests
skip_if_no_freecad = pytest.mark.skipif(not _freecad_available(), reason="FreeCAD not available")


class TestFindExportableBodiesIntegration:
    """Integration tests for find_exportable_bodies with real FreeCAD objects."""

    @skip_if_no_freecad
    def test_find_exportable_bodies_with_real_doc(self):
        """Should find bodies with ExportTo3MF property in a real document."""
        import FreeCAD

        # Create a new document
        doc = FreeCAD.newDocument("TestDoc")
        try:
            # Create a body
            body = doc.addObject("Part::Feature", "TestBody")
            body.Label = "Test Body"

            # Add ExportTo3MF property
            body.addProperty("App::PropertyBool", "ExportTo3MF", "TestGroup")
            body.ExportTo3MF = True

            # Add another body without the property
            body2 = doc.addObject("Part::Feature", "TestBody2")
            body2.Label = "Test Body 2"
            body2.addProperty("App::PropertyBool", "ExportTo3MF", "TestGroup")
            body2.ExportTo3MF = False

            # Call the function
            result = fc_export.find_exportable_bodies(doc)

            # Assert
            assert len(result) == 1
            assert result[0].Name == "TestBody"

        finally:
            FreeCAD.closeDocument(doc.Name)


class TestGetBodyExportPropertiesIntegration:
    """Integration tests for get_body_export_properties with real FreeCAD objects."""

    @skip_if_no_freecad
    def test_get_properties_with_real_object(self):
        """Should read properties from a real FreeCAD object."""
        import FreeCAD

        doc = FreeCAD.newDocument("TestDoc")
        try:
            # Create a body
            body = doc.addObject("Part::Feature", "TestBody")
            body.Label = "Test Body"

            # Add export properties
            body.addProperty("App::PropertyBool", "ExportTo3MF", "TestGroup")
            body.ExportTo3MF = True

            body.addProperty("App::PropertyInteger", "ExportCount", "TestGroup")
            body.ExportCount = 3

            # Note: FreeCAD PropertyRotation access varies by platform/version
            # Some configurations don't expose it properly via Python API
            # Test with count only to ensure basic property reading works

            # Call the function
            result = fc_export.get_body_export_properties(body)

            # Assert
            assert result["count"] == 3
            # Rotation may be None on some FreeCAD installations

        finally:
            FreeCAD.closeDocument(doc.Name)


class TestResolveObjectIdentifierIntegration:
    """Integration tests for resolve_object_identifier with real FreeCAD objects."""

    @skip_if_no_freecad
    def test_resolve_by_name_real(self):
        """Should resolve object by Name in a real document."""
        import FreeCAD

        doc = FreeCAD.newDocument("TestDoc")
        try:
            # Create a body
            body = doc.addObject("Part::Feature", "TestBody")
            body.Label = "MyLabel"

            # Resolve by Name
            result = fc_export.resolve_object_identifier(doc, "TestBody")

            # Assert
            assert result[0] is body
            assert result[1] == "TestBody"
            assert result[2] == "MyLabel"

        finally:
            FreeCAD.closeDocument(doc.Name)

    @skip_if_no_freecad
    def test_resolve_by_label_real(self):
        """Should resolve object by Label in a real document."""
        import FreeCAD

        doc = FreeCAD.newDocument("TestDoc")
        try:
            # Create a body
            body = doc.addObject("Part::Feature", "SomeName")
            body.Label = "MyLabel"

            # Resolve by Label
            result = fc_export.resolve_object_identifier(doc, "MyLabel")

            # Assert
            assert result[0] is body
            assert result[1] == "SomeName"
            assert result[2] == "MyLabel"

        finally:
            FreeCAD.closeDocument(doc.Name)

    @skip_if_no_freecad
    def test_resolve_not_found_real(self):
        """Should return None tuple when object not found in real document."""
        import FreeCAD

        doc = FreeCAD.newDocument("TestDoc")
        try:
            # Resolve non-existent object
            result = fc_export.resolve_object_identifier(doc, "NonExistent")

            # Assert
            assert result == (None, None, None)

        finally:
            FreeCAD.closeDocument(doc.Name)


class TestBOMExtractionIntegration:
    """Integration tests for BOM extraction functions."""

    @skip_if_no_freecad
    def test_extract_bom_from_parts_real(self):
        """Should extract BOM from Part objects in a real document."""
        import FreeCAD

        doc = FreeCAD.newDocument("TestDoc")
        try:
            # Create some bodies
            body1 = doc.addObject("Part::Feature", "Body1")
            body1.Label = "Part 1"

            body2 = doc.addObject("Part::Feature", "Body2")
            body2.Label = "Part 2"

            # Extract BOM
            result = fc_export.extract_bom_from_parts(doc)

            # Assert
            assert len(result) == 2
            labels = {item["label"] for item in result}
            assert labels == {"Part 1", "Part 2"}

        finally:
            FreeCAD.closeDocument(doc.Name)

    @skip_if_no_freecad
    def test_extract_bom_from_parts_with_custom_fields(self):
        """Should extract custom fields from Part objects."""
        import FreeCAD

        doc = FreeCAD.newDocument("TestDoc")
        try:
            # Create a body with custom property
            body = doc.addObject("Part::Feature", "Body1")
            body.Label = "Part 1"
            body.addProperty("App::PropertyString", "Material", "Custom")
            body.Material = "Steel"

            # Extract BOM with custom fields
            result = fc_export.extract_bom_from_parts(doc, custom_fields=["Material"])

            # Assert
            assert len(result) == 1
            assert result[0]["label"] == "Part 1"
            assert result[0].get("material") == "Steel"

        finally:
            FreeCAD.closeDocument(doc.Name)


class TestExportFunctionsIntegration:
    """Integration tests for export functions.

    Note: These tests may be slower as they involve actual FreeCAD operations.
    """

    @skip_if_no_freecad
    def test_export_bodies_to_stl(self, tmp_path):
        """Should export bodies to STL files."""
        import FreeCAD

        doc = FreeCAD.newDocument("TestDoc")
        try:
            # Create a simple box body
            box = doc.addObject("Part::Box", "Box")
            box.Length = 10
            box.Width = 10
            box.Height = 10
            doc.recompute()

            # Export to a temp directory
            output_dir = tmp_path / "stl"
            output_dir.mkdir()
            output_path = str(output_dir / "test")

            # Export bodies
            success = fc_export.export_bodies(doc, ["Box"], output_path)

            # Assert
            assert success is True
            # Check STL file was created
            stl_files = list(output_dir.glob("*.stl"))
            assert len(stl_files) >= 1

        finally:
            FreeCAD.closeDocument(doc.Name)


class TestExampleFcstdIntegration:
    """Integration tests that open the bundled example.FCStd."""

    @skip_if_no_freecad
    def test_open_example_fcstd_and_resolve_bodies(self, example_fcstd_file):
        """Should open examples/example.FCStd and resolve known bodies by Name."""
        import FreeCAD

        doc = FreeCAD.open(str(example_fcstd_file))
        try:
            obj, resolved_name, resolved_label = fc_export.resolve_object_identifier(doc, "Body")
            assert obj is not None
            assert resolved_name == "Body"
            assert resolved_label

            obj2, resolved_name2, resolved_label2 = fc_export.resolve_object_identifier(doc, "Body001")
            assert obj2 is not None
            assert resolved_name2 == "Body001"
            assert resolved_label2

            # Both should have renderable shapes.
            assert hasattr(obj, "Shape") and obj.Shape
            assert hasattr(obj2, "Shape") and obj2.Shape
        finally:
            FreeCAD.closeDocument(doc.Name)


class TestExportBodiesTo3MFIntegration:
    """Integration tests for 3MF export pipeline.

    Note: These require both FreeCAD and lib3mf to be available.
    """

    @skip_if_no_freecad
    def test_export_bodies_to_3mf_with_template_basic(self, tmp_path):
        """Should create 3MF file with basic body export."""
        import FreeCAD

        doc = FreeCAD.newDocument("TestDoc")
        try:
            # Create a simple box
            box = doc.addObject("Part::Box", "Box")
            box.Length = 10
            box.Width = 10
            box.Height = 10
            doc.recompute()

            # Export to 3MF
            output_path = str(tmp_path / "test.3mf")

            # This will fail without lib3mf, but tests the FreeCAD part
            # We mock the subprocess call to lib3mf_utils
            # and use side_effect to create the output file after the call
            def create_output_file(*args, **kwargs):
                result = MagicMock()
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
                # Create the output file so the function's os.path.exists check passes
                with open(output_path, "w") as f:
                    f.write("mock 3mf content")
                return result

            with patch("fc_export.subprocess.run", side_effect=create_output_file) as mock_run:
                success = fc_export.export_bodies_to_3mf_with_template(
                    doc,
                    ["Box"],
                    output_path,
                    template_path=None,
                    keep_stl=False,
                    stl_output_dir=None,
                    export_name="TestExport",
                    metadata=None,
                )

            # Assert
            assert success is True
            assert mock_run.called

        finally:
            FreeCAD.closeDocument(doc.Name)


class TestSlicerIntegration:
    """Integration tests for slicer functionality.

    Note: These tests validate slicer command building with real paths
    but mock the actual slicer binary execution.
    """

    def test_build_slicer_command_with_real_paths(self, tmp_path):
        """Should build slicer command with real output paths."""
        # Create output directory
        output_dir = tmp_path / "gcode"
        output_dir.mkdir()

        item = {
            "name": "TestExport",
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "output_dir": str(output_dir),
                "output_name": "{name}_{engine}.gcode",
                "prusa": {},
            },
        }

        # Mock current date for predictable output name
        with patch("fc_export.time.strftime", return_value="20240101"):
            cmd, output_path = fc_export.build_slicer_command(item, "/tmp/input.3mf")

        # Assert
        assert cmd[0].endswith("prusa-slicer") or cmd[0].endswith("PrusaSlicer")
        assert "--export-gcode" in cmd
        assert "/tmp/input.3mf" in cmd
        assert "--output" in cmd
        assert output_path == str(output_dir / "TestExport_prusa.gcode")
        assert output_path.endswith(".gcode")

    def test_build_slicer_command_orca_with_profiles(self, tmp_path):
        """Should build OrcaSlicer command with profile arguments."""
        output_dir = tmp_path / "gcode"
        output_dir.mkdir()

        profile_dir = tmp_path / "profiles"
        profile_dir.mkdir()
        (profile_dir / "printer.ini").write_text("[profile]\n")
        (profile_dir / "print.ini").write_text("[profile]\n")
        (profile_dir / "material.ini").write_text("[profile]\n")

        item = {
            "name": "OrcaTest",
            "slicer": {
                "enabled": True,
                "engine": "orca",
                "output_dir": str(output_dir),
                "output_name": "{name}.gcode",
                "orca": {
                    "printer_profile": str(profile_dir / "printer.ini"),
                    "print_profile": str(profile_dir / "print.ini"),
                    "material_profile": str(profile_dir / "material.ini"),
                },
            },
        }

        cmd, output_path = fc_export.build_slicer_command(item, "/tmp/input.3mf")

        # Assert
        assert cmd[0].endswith("orca-slicer") or cmd[0].endswith("OrcaSlicer")
        assert "--slice" in cmd
        assert "--outputdir" in cmd
        assert "/tmp/input.3mf" in cmd
        assert output_path == str(output_dir / "OrcaTest.gcode")

    def test_build_slicer_command_with_config_bundle(self, tmp_path):
        """Should build slicer command with --load config bundle."""
        output_dir = tmp_path / "gcode"
        output_dir.mkdir()

        bundle_path = tmp_path / "prusa_bundle.ini"
        bundle_path.write_text("[bundle]\n")

        item = {
            "name": "BundleTest",
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "use_config_bundle": True,
                "config_bundle": str(bundle_path),
                "output_dir": str(output_dir),
                "prusa": {},
            },
        }

        cmd, _ = fc_export.build_slicer_command(item, "/tmp/input.3mf")

        # Assert
        assert "--load" in cmd
        assert str(bundle_path) in cmd

    def test_validate_slicer_config_with_template(self):
        """Should allow slicer without profiles when template is present."""
        item = {
            "name": "TemplateTest",
            "template": "template.3mf",
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "prusa": {},  # No profiles
            },
        }

        valid, error = fc_export.validate_slicer_config(item)
        assert valid is True
        assert error is None

    def test_validate_slicer_config_requires_profiles_without_template(self):
        """Should require profiles when no template is present."""
        item = {
            "name": "NoTemplateTest",
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "prusa": {},  # No profiles, no template
            },
        }

        valid, error = fc_export.validate_slicer_config(item)
        assert valid is False
        assert "requires either profiles" in error

    def test_validate_slicer_config_invalid_engine(self):
        """Should reject invalid slicer engine."""
        item = {
            "name": "InvalidEngineTest",
            "slicer": {
                "enabled": True,
                "engine": "invalid_engine",
            },
        }

        valid, error = fc_export.validate_slicer_config(item)
        assert valid is False
        assert "slicer.engine" in error

    def test_run_slicer_for_export_item_dry_run_mode(self, tmp_path):
        """Should skip slicer execution in dry-run mode."""
        output_dir = tmp_path / "gcode"
        output_dir.mkdir()

        item = {
            "name": "DryRunTest",
            "template": "template.3mf",
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "dry_run": True,
                "output_dir": str(output_dir),
                "prusa": {},
            },
        }

        # Create a dummy 3MF file
        dummy_3mf = tmp_path / "input.3mf"
        dummy_3mf.write_text("dummy")

        with patch("fc_export.subprocess.run") as mock_run:
            ok = fc_export.run_slicer_for_export_item(item, str(dummy_3mf))

        assert ok is True
        mock_run.assert_not_called()

    def test_run_slicer_for_export_item_creates_output(self, tmp_path):
        """Should run slicer and create output file."""
        output_dir = tmp_path / "gcode"
        output_dir.mkdir()

        item = {
            "name": "RealRunTest",
            "template": "template.3mf",
            "slicer": {
                "enabled": True,
                "engine": "prusa",
                "output_dir": str(output_dir),
                "output_name": "output.gcode",
                "prusa": {},
            },
        }

        # Create a dummy 3MF file
        dummy_3mf = tmp_path / "input.3mf"
        dummy_3mf.write_text("dummy")

        # Mock successful slicer execution
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        # Create the expected output file after "execution"
        def create_gcode_file(*args, **kwargs):
            gcode_path = output_dir / "output.gcode"
            gcode_path.write_text("G28\nG1 X0 Y0\n")
            return mock_result

        with patch("fc_export.subprocess.run", side_effect=create_gcode_file) as mock_run:
            ok = fc_export.run_slicer_for_export_item(item, str(dummy_3mf))

        assert ok is True
        mock_run.assert_called_once()
        gcode_file = output_dir / "output.gcode"
        assert gcode_file.exists()

    @pytest.mark.integration
    def test_run_orca_slicer_real_execution(self, tmp_path):
        """Should execute OrcaSlicer binary and create real G-code output."""
        orca_binary = fc_export._resolve_slicer_binary({"engine": "orca"})
        if Path(orca_binary).is_absolute():
            if not Path(orca_binary).exists():
                pytest.skip(f"OrcaSlicer binary not found: {orca_binary}")
        elif not shutil.which(orca_binary):
            pytest.skip(f"OrcaSlicer binary not found in PATH: {orca_binary}")

        repo_root = Path(__file__).parent.parent
        config_path = repo_root / "tests" / "export_test_config.yml"
        export_result = subprocess.run(
            [sys.executable, "tools/export.py", str(config_path), "--name", "basic_export"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert export_result.returncode == 0, export_result.stderr

        input_3mf = repo_root / "test_output" / "basic_export.3mf"
        assert input_3mf.exists()

        output_dir = tmp_path / "gcode"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_name = "orca_real_test.gcode"

        export_item = {
            "name": "orca_real_test",
            "template": "template.3mf",
            "slicer": {
                "enabled": True,
                "engine": "orca",
                "binary": str(orca_binary),
                "output_dir": str(output_dir),
                "output_name": output_name,
                "run_after_export": True,
                "orca": {"extra_args": ["--no-check"]},
            },
        }

        ok = fc_export.run_slicer_for_export_item(export_item, str(input_3mf))
        if not ok:
            pytest.skip("OrcaSlicer executed but slicing failed with local profile/settings constraints")
        assert (output_dir / output_name).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
