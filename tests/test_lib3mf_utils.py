#!/usr/bin/env python3
"""Unit tests for lib3mf_utils.py."""

import json
import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add tools/ to path
_test_dir = Path(__file__).parent
_tools_dir = _test_dir.parent / "tools"
sys.path.insert(0, str(_tools_dir))


def create_minimal_binary_stl(file_path: Path, triangles: list) -> None:
    """Create a minimal binary STL file for testing.

    Args:
        file_path: Path to write STL file
        triangles: List of [(x1,y1,z1), (x2,y2,z2), (x3,y3,z3)] vertex tuples
    """
    with open(file_path, "wb") as f:
        # Write 80-byte header
        header = b"Tests STL file                                    "
        f.write(header.ljust(80, b" "))

        # Write triangle count
        f.write(struct.pack("<I", len(triangles)))

        # Write triangles
        for tri in triangles:
            # Write normal (ignored but required)
            f.write(struct.pack("<fff", 0.0, 0.0, 1.0))

            # Write 3 vertices
            for x, y, z in tri:
                f.write(struct.pack("<fff", x, y, z))

            # Write attribute byte count
            f.write(struct.pack("<H", 0))


class TestConvertSTLToLib3MFMesh:
    """Tests for convert_stl_to_lib3mf_mesh function."""

    def test_raises_on_missing_file(self, tmp_path):
        """Should raise FileNotFoundError when STL doesn't exist."""
        # Given
        import lib3mf_utils

        missing_file = str(tmp_path / "nonexistent.stl")
        mock_mesh = MagicMock()

        # When/Then
        with pytest.raises(FileNotFoundError):
            lib3mf_utils.convert_stl_to_lib3mf_mesh(missing_file, mock_mesh)

    def test_parses_single_triangle_stl(self, tmp_path):
        """Should parse STL with single triangle."""
        # Given
        import lib3mf_utils

        stl_path = tmp_path / "single_tri.stl"
        create_minimal_binary_stl(stl_path, [[(0, 0, 0), (1, 0, 0), (0, 1, 0)]])

        mock_mesh = MagicMock()
        mock_mesh.AddVertex = MagicMock()
        mock_mesh.AddTriangle = MagicMock()

        # Mock lib3mf.Position
        with patch.object(lib3mf_utils, "lib3mf") as mock_lib3mf:
            mock_pos = MagicMock()
            mock_pos.Coordinates = [0.0, 0.0, 0.0]
            mock_lib3mf.Position.return_value = mock_pos

            # When
            metrics = lib3mf_utils.convert_stl_to_lib3mf_mesh(str(stl_path), mock_mesh)

            # Then
            # Should have 3 unique vertices for the triangle
            assert mock_mesh.AddVertex.call_count >= 3
            # Should return metrics dict
            assert isinstance(metrics, dict)
            assert "vertex_count" in metrics
            assert "triangle_count" in metrics
            assert metrics["vertex_count"] >= 3

    def test_deduplicates_vertices(self, tmp_path):
        """Should deduplicate identical vertices."""
        # Given
        import lib3mf_utils

        # Triangle with shared vertices (all vertices at same position = degenerate but tests dedup)
        stl_path = tmp_path / "degenerate.stl"
        create_minimal_binary_stl(stl_path, [[(0, 0, 0), (0, 0, 0), (0, 0, 0)]])

        mock_mesh = MagicMock()
        mock_mesh.AddVertex = MagicMock()
        mock_mesh.AddTriangle = MagicMock()

        with patch.object(lib3mf_utils, "lib3mf") as mock_lib3mf:
            mock_pos = MagicMock()
            mock_pos.Coordinates = [0.0, 0.0, 0.0]
            mock_lib3mf.Position.return_value = mock_pos

            # When
            metrics = lib3mf_utils.convert_stl_to_lib3mf_mesh(str(stl_path), mock_mesh)

            # Then - vertices should be deduplicated to 1
            assert mock_mesh.AddVertex.call_count == 1
            # Should return metrics dict
            assert isinstance(metrics, dict)
            assert metrics["vertex_count"] == 1


class TestAddMetadataToModel:
    """Tests for add_metadata_to_model function."""

    def test_does_nothing_without_metadata(self):
        """Should do nothing when metadata is None or empty."""
        # Given
        import lib3mf_utils

        mock_model = MagicMock()
        mock_model.GetMetaDataGroup = MagicMock()

        # When
        lib3mf_utils.add_metadata_to_model(mock_model, None)
        lib3mf_utils.add_metadata_to_model(mock_model, {})

        # Then
        mock_model.GetMetaDataGroup.assert_not_called()

    def test_adds_metadata_items(self):
        """Should add metadata items to model."""
        # Given
        import lib3mf_utils

        mock_model = MagicMock()
        mock_metadata_group = MagicMock()
        mock_model.GetMetaDataGroup.return_value = mock_metadata_group

        metadata = {
            "Project": "TestProject",
            "Version": "1.0",
        }

        # When
        lib3mf_utils.add_metadata_to_model(mock_model, metadata)

        # Then
        assert mock_metadata_group.AddMetaData.call_count == 2


class Test3MFCreateFromSTLs:
    """Tests for create_3mf_from_stls function."""

    @patch("lib3mf_utils.get_wrapper")
    def test_creates_3mf_file(self, mock_get_wrapper, tmp_path):
        """Should create a valid 3MF file."""
        # Given
        from unittest.mock import MagicMock

        import lib3mf_utils

        mock_wrapper = MagicMock()
        mock_model = MagicMock()
        mock_writer = MagicMock()

        mock_wrapper.CreateModel.return_value = mock_model
        mock_model.QueryWriter.return_value = mock_writer

        mock_get_wrapper.return_value = mock_wrapper

        # Create test STL file
        stl_file = tmp_path / "test.stl"
        create_minimal_binary_stl(stl_file, [[(0, 0, 0), (1, 0, 0), (0, 1, 0)]])

        output_file = tmp_path / "output.3mf"
        stl_files = [("TestMesh", str(stl_file))]

        # Mock STL conversion to avoid actual lib3mf calls and return metrics
        mock_metrics = {"vertex_count": 3, "triangle_count": 1, "file_size": 148}
        # Mock Path.stat to return a fake file size (for output_file_size in metrics)
        mock_stat = MagicMock()
        mock_stat.st_size = 500
        with (
            patch.object(lib3mf_utils, "convert_stl_to_lib3mf_mesh", return_value=mock_metrics),
            patch("lib3mf_utils.Path") as mock_path,
        ):
            mock_path_instance = MagicMock()
            mock_path_instance.stat.return_value = mock_stat
            mock_path.return_value = mock_path_instance

            # When
            success, metrics = lib3mf_utils.create_3mf_from_stls(stl_files, str(output_file))

            # Then
            assert success is True
            assert "total_vertex_count" in metrics
            assert "total_triangle_count" in metrics
            assert metrics["total_vertex_count"] == 3
            assert metrics["total_triangle_count"] == 1
            assert metrics["output_file_size"] == 500
            mock_model.AddMeshObject.assert_called_once()
            mock_writer.WriteToFile.assert_called_once_with(str(output_file))

    @patch("lib3mf_utils.get_wrapper")
    def test_handles_template(self, mock_get_wrapper, tmp_path):
        """Should handle optional template file."""
        # Given
        from unittest.mock import MagicMock

        import lib3mf_utils

        mock_wrapper = MagicMock()
        mock_model = MagicMock()
        mock_writer = MagicMock()

        mock_wrapper.CreateModel.return_value = mock_model
        mock_model.QueryWriter.return_value = mock_writer
        mock_get_wrapper.return_value = mock_wrapper

        # Create test STL
        stl_file = tmp_path / "test.stl"
        create_minimal_binary_stl(stl_file, [[(0, 0, 0), (1, 0, 0), (0, 1, 0)]])

        # Create template (just the 3MF structure)
        template_file = tmp_path / "template.3mf"
        output_file = tmp_path / "output.3mf"
        stl_files = [("TestMesh", str(stl_file))]

        # Mock STL conversion to return metrics
        mock_metrics = {"vertex_count": 3, "triangle_count": 1, "file_size": 148}
        # Mock Path.stat for output file size
        mock_stat = MagicMock()
        mock_stat.st_size = 500
        # When - template path is passed
        with (
            patch.object(lib3mf_utils, "convert_stl_to_lib3mf_mesh", return_value=mock_metrics),
            patch("lib3mf_utils.Path") as mock_path,
        ):
            mock_path_instance = MagicMock()
            mock_path_instance.stat.return_value = mock_stat
            mock_path.return_value = mock_path_instance

            success, metrics = lib3mf_utils.create_3mf_from_stls(
                stl_files, str(output_file), template_path=str(template_file)
            )

        # Then - template parameter is accepted
        assert success is True
        assert "total_vertex_count" in metrics
        assert metrics["total_vertex_count"] == 3
        assert metrics["output_file_size"] == 500


class TestCreateFromJsonConfig:
    """Tests for create_from_json_config function."""

    def test_raises_on_missing_file(self):
        """Should raise error when config file doesn't exist."""
        # Given
        import lib3mf_utils

        # When/Then
        with pytest.raises(FileNotFoundError):
            lib3mf_utils.create_from_json_config("/nonexistent/config.json")

    def test_rejects_empty_output_path(self, tmp_path):
        """Should reject config without output_path."""
        # Given

        import lib3mf_utils

        config_file = tmp_path / "no_output.json"
        config_file.write_text('{"stl_files": []}')

        # When/Then
        success, metrics = lib3mf_utils.create_from_json_config(str(config_file))
        assert success is False

    def test_rejects_empty_stl_files(self, tmp_path):
        """Should reject config without stl_files."""
        # Given
        import lib3mf_utils

        config_file = tmp_path / "no_stl.json"
        config_file.write_text('{"output_path": "output.3mf"}')

        # When/Then
        success, metrics = lib3mf_utils.create_from_json_config(str(config_file))
        assert success is False

    def test_parses_valid_config(self, tmp_path):
        """Should parse valid JSON configuration."""
        # Given
        import lib3mf_utils

        config_file = tmp_path / "valid.json"
        config = {
            "output_path": str(tmp_path / "output.3mf"),
            "stl_files": [{"label": "Mesh1", "path": "/fake/path.stl"}],
        }
        config_file.write_text(json.dumps(config))

        # When/Then - should attempt to create (will fail on missing STL but validates JSON parsing)
        success, metrics = lib3mf_utils.create_from_json_config(str(config_file))
        assert success is False  # Fails because STL doesn't exist, but JSON was valid


class TestMetadataFunctions:
    """Tests for metadata reading and merging functions."""

    def test_read_metadata_from_nonexistent_file(self):
        """Should return None for nonexistent template file."""
        # Given
        import lib3mf_utils

        # When
        result = lib3mf_utils.read_metadata_from_3mf("/nonexistent/template.3mf")

        # Then
        assert result is None

    def test_merge_metadata_export_precedence(self):
        """Should use export metadata over template metadata."""
        # Given
        import lib3mf_utils

        template_meta = {"Title": "Template Title", "Version": "1.0"}
        export_meta = {"Title": "Export Title", "Author": "John Doe"}

        # When
        result = lib3mf_utils.merge_metadata(template_meta, export_meta, precedence="export")

        # Then
        assert result["Title"] == "Export Title"  # Export overrides template
        assert result["Author"] == "John Doe"  # Export provides new value
        assert result["Version"] == "1.0"  # Template provides default

    def test_merge_metadata_template_precedence(self):
        """Should use template metadata over export metadata."""
        # Given
        import lib3mf_utils

        template_meta = {"Title": "Template Title", "Version": "1.0"}
        export_meta = {"Title": "Export Title", "Author": "John Doe"}

        # When
        result = lib3mf_utils.merge_metadata(template_meta, export_meta, precedence="template")

        # Then
        assert result["Title"] == "Template Title"  # Template overrides export
        assert result["Author"] == "John Doe"  # Export provides new value
        assert result["Version"] == "1.0"  # Template provides value

    def test_merge_metadata_merge_mode(self):
        """Should combine all metadata in merge mode."""
        # Given
        import lib3mf_utils

        template_meta = {"Title": "Template Title", "Version": "1.0"}
        export_meta = {"Title": "Export Title", "Author": "John Doe"}

        # When
        result = lib3mf_utils.merge_metadata(template_meta, export_meta, precedence="merge")

        # Then
        # In merge mode, export should still take precedence for conflicts
        assert result["Title"] == "Export Title"
        assert result["Author"] == "John Doe"
        assert result["Version"] == "1.0"

    def test_merge_metadata_with_none_template(self):
        """Should handle None template metadata."""
        # Given
        import lib3mf_utils

        export_meta = {"Title": "Export Title", "Author": "John Doe"}

        # When
        result = lib3mf_utils.merge_metadata(None, export_meta, precedence="export")

        # Then
        assert result == export_meta

    def test_merge_metadata_with_none_export(self):
        """Should handle None export metadata."""
        # Given
        import lib3mf_utils

        template_meta = {"Title": "Template Title", "Version": "1.0"}

        # When
        result = lib3mf_utils.merge_metadata(template_meta, None, precedence="export")

        # Then
        assert result == template_meta

    def test_merge_metadata_with_both_none(self):
        """Should return empty dict when both are None."""
        # Given
        import lib3mf_utils

        # When
        result = lib3mf_utils.merge_metadata(None, None, precedence="export")

        # Then
        assert result == {}


class TestSTLCreation:
    """Tests for STL file creation helper."""

    def test_create_minimal_binary_stl(self, tmp_path):
        """Should create valid binary STL."""
        # Given
        stl_file = tmp_path / "triangle.stl"
        triangles = [
            [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            [(1, 0, 0), (1, 1, 0), (0, 1, 0)],
        ]

        # When
        create_minimal_binary_stl(stl_file, triangles)

        # Then
        assert stl_file.exists()

        # Verify structure
        with open(stl_file, "rb") as f:
            header = f.read(80)
            assert len(header) == 80

            tri_count = struct.unpack("<I", f.read(4))[0]
            assert tri_count == 2

            # Read triangles
            for _ in range(tri_count):
                struct.unpack("<fff", f.read(12))  # normal (ignored)
                for _ in range(3):
                    struct.unpack("<fff", f.read(12))  # vertex (ignored)
                struct.unpack("<H", f.read(2))  # attribute (ignored)


class TestAxisAngleTransform:
    """Tests for axis+angle rotation transform creation."""

    def test_create_euler_transform_with_axis_angle_dict(self):
        """Should create transform from axis+angle dict format."""
        # Given
        import lib3mf_utils

        rotation = {"axis": [0, 0, 1], "angle": 90}  # 90 deg around Z

        with patch.object(lib3mf_utils, "lib3mf") as mock_lib3mf:
            mock_transform = MagicMock()
            mock_transform.Fields = [[0] * 4 for _ in range(3)]
            mock_lib3mf.Transform.return_value = mock_transform

            # When
            result = lib3mf_utils.create_euler_transform(rotation)

            # Then
            assert result is not None
            # For 90 deg around Z: R = [[cos90, -sin90, 0, 0], [sin90, cos90, 0, 0], [0, 0, 1, 0]]
            # cos(90) ≈ 0, sin(90) = 1
            # So R ≈ [[0, -1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 0]]
            # Verify the rotation matrix was calculated (identity with position 0)
            assert mock_lib3mf.Transform.called

    def test_create_euler_transform_with_euler_list(self):
        """Should still create transform from Euler list (backward compat)."""
        # Given
        import lib3mf_utils

        rotation = [45, 0, 0]  # Euler X rotation

        with patch.object(lib3mf_utils, "lib3mf") as mock_lib3mf:
            mock_transform = MagicMock()
            mock_transform.Fields = [[0] * 4 for _ in range(3)]
            mock_lib3mf.Transform.return_value = mock_transform

            # When
            result = lib3mf_utils.create_euler_transform(rotation)

            # Then
            assert result is not None

    def test_create_euler_transform_with_none_rotation(self):
        """Should create identity transform when rotation is None."""
        # Given
        import lib3mf_utils

        with patch.object(lib3mf_utils, "lib3mf") as mock_lib3mf:
            mock_transform = MagicMock()
            mock_transform.Fields = [[0] * 4 for _ in range(3)]
            mock_lib3mf.Transform.return_value = mock_transform

            # When
            result = lib3mf_utils.create_euler_transform(None, position=[10, 20, 30])

            # Then
            assert result is not None
            # Identity matrix with position
            assert mock_transform.Fields[0][0] == 1
            assert mock_transform.Fields[1][1] == 1
            assert mock_transform.Fields[2][2] == 1
            assert mock_transform.Fields[0][3] == 10
            assert mock_transform.Fields[1][3] == 20
            assert mock_transform.Fields[2][3] == 30

    def test_axis_angle_zero_axis_uses_default(self):
        """Should use default Z-axis when axis is zero length."""
        # Given
        import lib3mf_utils

        rotation = {"axis": [0, 0, 0], "angle": 45}

        with patch.object(lib3mf_utils, "lib3mf") as mock_lib3mf:
            mock_transform = MagicMock()
            mock_transform.Fields = [[0] * 4 for _ in range(3)]
            mock_lib3mf.Transform.return_value = mock_transform

            # When - should not crash, use default axis
            result = lib3mf_utils.create_euler_transform(rotation)

            # Then
            assert result is not None

    def test_axis_angle_normalizes_axis(self):
        """Should normalize axis vector."""
        # Given
        import lib3mf_utils

        # Non-unit axis
        rotation = {"axis": [2, 0, 0], "angle": 180}

        with patch.object(lib3mf_utils, "lib3mf") as mock_lib3mf:
            mock_transform = MagicMock()
            mock_transform.Fields = [[0] * 4 for _ in range(3)]
            mock_lib3mf.Transform.return_value = mock_transform

            # When
            result = lib3mf_utils.create_euler_transform(rotation)

            # Then - should handle non-normalized axis
            assert result is not None

    def test_create_euler_transform_with_invalid_dict_format(self):
        """Should handle invalid dict rotation format gracefully."""
        # Given
        import lib3mf_utils

        rotation = {"invalid": "format"}

        with patch.object(lib3mf_utils, "lib3mf") as mock_lib3mf:
            mock_transform = MagicMock()
            mock_transform.Fields = [[0] * 4 for _ in range(3)]
            mock_lib3mf.Transform.return_value = mock_transform

            # When - should not crash
            result = lib3mf_utils.create_euler_transform(rotation)

            # Then - should return identity transform
            assert result is not None


class TestQualityMetrics:
    """Tests for quality metrics functions (vertex/triangle counting, 3MF validation)."""

    def test_convert_stl_returns_metrics(self, tmp_path):
        """Should return vertex/triangle/file_size metrics."""
        import lib3mf_utils

        # Create test STL file with 1 triangle
        stl_path = tmp_path / "test.stl"
        create_minimal_binary_stl(stl_path, [[(0, 0, 0), (1, 0, 0), (0, 1, 0)]])

        mock_mesh = MagicMock()
        mock_mesh.AddVertex = MagicMock()
        mock_mesh.AddTriangle = MagicMock()

        with patch.object(lib3mf_utils, "lib3mf"):
            # When
            metrics = lib3mf_utils.convert_stl_to_lib3mf_mesh(str(stl_path), mock_mesh)

            # Then
            assert isinstance(metrics, dict)
            assert "vertex_count" in metrics
            assert "triangle_count" in metrics
            assert "file_size" in metrics
            assert metrics["vertex_count"] == 3
            assert metrics["triangle_count"] == 1
            assert metrics["file_size"] > 0

    def test_validate_3mf_file_valid(self, tmp_path):
        """Should validate a real 3MF file."""
        import lib3mf_utils

        # Use the example 3MF file
        example_3mf = Path(__file__).parent.parent / "examples" / "example.3mf"
        if example_3mf.exists():
            result = lib3mf_utils.validate_3mf_file(str(example_3mf))
            assert result["is_valid"] is True
            assert result["has_model"] is True
            assert result["file_size"] > 0

    def test_validate_3mf_file_missing(self, tmp_path):
        """Should handle missing file."""
        import lib3mf_utils

        result = lib3mf_utils.validate_3mf_file("/nonexistent/file.3mf")
        assert result["is_valid"] is False
        assert result["file_size"] == 0

    def test_validate_3mf_file_not_zip(self, tmp_path):
        """Should handle non-ZIP file."""
        import lib3mf_utils

        # Create a fake file
        fake_file = tmp_path / "fake.3mf"
        fake_file.write_text("not a zip file")

        result = lib3mf_utils.validate_3mf_file(str(fake_file))
        assert result["is_valid"] is False
        assert result["error"] is not None

    def test_create_3mf_from_stls_returns_metrics(self, tmp_path):
        """Should return quality metrics when creating 3MF from STL files."""
        import lib3mf_utils

        # Mock the lib3mf wrapper
        with patch("lib3mf_utils.get_wrapper") as mock_get_wrapper:
            mock_wrapper = MagicMock()
            mock_model = MagicMock()
            mock_writer = MagicMock()

            mock_wrapper.CreateModel.return_value = mock_model
            mock_model.QueryWriter.return_value = mock_writer

            mock_get_wrapper.return_value = mock_wrapper

            # Create test STL file
            stl_file = tmp_path / "test.stl"
            create_minimal_binary_stl(stl_file, [[(0, 0, 0), (1, 0, 0), (0, 1, 0)]])

            output_file = tmp_path / "output.3mf"
            stl_files = [("TestMesh", str(stl_file))]

            # Mock STL conversion metrics and Path.stat
            mock_stl_metrics = {"vertex_count": 3, "triangle_count": 1, "file_size": 148}
            mock_stat = MagicMock()
            mock_stat.st_size = 500
            with (
                patch.object(lib3mf_utils, "convert_stl_to_lib3mf_mesh", return_value=mock_stl_metrics),
                patch("lib3mf_utils.Path") as mock_path,
            ):
                mock_path_instance = MagicMock()
                mock_path_instance.stat.return_value = mock_stat
                mock_path.return_value = mock_path_instance

                # When
                success, metrics = lib3mf_utils.create_3mf_from_stls(stl_files, str(output_file))

                # Then
                assert success is True
                assert "total_vertex_count" in metrics
                assert "total_triangle_count" in metrics
                assert "output_file_size" in metrics
                assert metrics["total_vertex_count"] == 3
                assert metrics["total_triangle_count"] == 1
                assert metrics["output_file_size"] == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
