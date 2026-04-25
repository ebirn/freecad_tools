#!/usr/bin/env python3
"""Unit tests for lib3mf_utils.py."""
import pytest
import struct
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

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
            lib3mf_utils.convert_stl_to_lib3mf_mesh(str(stl_path), mock_mesh)

            # Then
            # Should have 3 unique vertices for the triangle
            assert mock_mesh.AddVertex.call_count >= 3

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
            lib3mf_utils.convert_stl_to_lib3mf_mesh(str(stl_path), mock_mesh)

            # Then - vertices should be deduplicated to 1
            assert mock_mesh.AddVertex.call_count == 1


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
        import lib3mf_utils
        from unittest.mock import MagicMock

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

        # Mock STL conversion to avoid actual lib3mf calls
        with patch.object(lib3mf_utils, "convert_stl_to_lib3mf_mesh"):
            # When
            result = lib3mf_utils.create_3mf_from_stls(stl_files, str(output_file))

            # Then
            assert result is True
            mock_model.AddMeshObject.assert_called_once()
            mock_writer.WriteToFile.assert_called_once_with(str(output_file))

    @patch("lib3mf_utils.get_wrapper")
    def test_handles_template(self, mock_get_wrapper, tmp_path):
        """Should handle optional template file."""
        # Given
        import lib3mf_utils
        from unittest.mock import MagicMock

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

        # When - template path is passed
        with patch.object(lib3mf_utils, "convert_stl_to_lib3mf_mesh"):
            result = lib3mf_utils.create_3mf_from_stls(
                stl_files, str(output_file), template_path=str(template_file)
            )

        # Then - template parameter is accepted
        assert result is True


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
        import json

        config_file = tmp_path / "no_output.json"
        config_file.write_text('{"stl_files": []}')

        # When/Then
        result = lib3mf_utils.create_from_json_config(str(config_file))
        assert result is False

    def test_rejects_empty_stl_files(self, tmp_path):
        """Should reject config without stl_files."""
        # Given
        import lib3mf_utils

        config_file = tmp_path / "no_stl.json"
        config_file.write_text('{"output_path": "output.3mf"}')

        # When/Then
        result = lib3mf_utils.create_from_json_config(str(config_file))
        assert result is False

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
        result = lib3mf_utils.create_from_json_config(str(config_file))
        assert result is False  # Fails because STL doesn't exist, but JSON was valid


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
                normal = struct.unpack("<fff", f.read(12))
                for _ in range(3):
                    vertex = struct.unpack("<fff", f.read(12))
                attr = struct.unpack("<H", f.read(2))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])