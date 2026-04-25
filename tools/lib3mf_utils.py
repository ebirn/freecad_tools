#!/usr/bin/env python3
"""
lib3mf_utils.py - Standalone utility for creating 3MF files with embedded meshes.

This module is designed to run outside FreeCAD's Python environment using the venv.
It converts STL files to 3MF format with embedded mesh data.

Usage:
    python3 lib3mf_utils.py create <output.3mf> <stl1> [<stl2> ...] [--template <template.3mf>]
    python3 lib3mf_utils.py create-from-json <config.json>
"""

import json
import logging
import struct
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import lib3mf
from lib3mf import get_wrapper

# Configure logging
logging.basicConfig(level=logging.INFO, format="lib3mf_utils - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def convert_stl_to_lib3mf_mesh(stl_file_path: str, mesh_object) -> None:
    """
    Parse a binary STL file and add its mesh data to a lib3mf mesh object.

    Args:
        stl_file_path: Path to binary STL file
        mesh_object: lib3mf mesh object to populate with vertices and triangles

    Raises:
        FileNotFoundError: If STL file doesn't exist
        struct.error: If STL format is invalid
    """
    stl_path = Path(stl_file_path)
    if not stl_path.exists():
        raise FileNotFoundError(f"STL file not found: {stl_file_path}")

    try:
        with open(stl_path, "rb") as f:
            # Skip header (80 bytes)
            f.read(80)

            # Read triangle count (4 bytes, little-endian unsigned int)
            tri_count_bytes = f.read(4)
            tri_count = struct.unpack("<I", tri_count_bytes)[0]
            logger.info(f"Processing {stl_path.name}: {tri_count} triangles")

            # Maps (x, y, z) to vertex index for deduplication
            vertex_map = {}
            vertex_count = 0
            triangle_data = []

            # Parse all triangles
            for tri_idx in range(tri_count):
                # Skip normal vector (12 bytes, we don't use it)
                f.read(12)

                # Read 3 vertices (12 bytes each)
                vertex_indices = []
                for _ in range(3):
                    vertex_bytes = f.read(12)
                    x, y, z = struct.unpack("<fff", vertex_bytes)

                    # Round to 4 decimals to deduplicate nearly-identical vertices
                    v_key = (round(x, 4), round(y, 4), round(z, 4))

                    if v_key not in vertex_map:
                        # Add new vertex to mesh
                        pos = lib3mf.Position()
                        pos.Coordinates[0] = float(x)
                        pos.Coordinates[1] = float(y)
                        pos.Coordinates[2] = float(z)
                        mesh_object.AddVertex(pos)
                        vertex_map[v_key] = vertex_count
                        vertex_count += 1

                    vertex_indices.append(vertex_map[v_key])

                # Skip attribute byte count (2 bytes)
                f.read(2)

                # Store triangle indices
                triangle_data.append(tuple(vertex_indices))

                if (tri_idx + 1) % 50000 == 0:
                    logger.debug(f"  Processed {tri_idx + 1}/{tri_count} triangles")

            # Add all triangles to mesh
            logger.info(f"Adding {len(triangle_data)} triangles to mesh")
            for v0, v1, v2 in triangle_data:
                tri = lib3mf.Triangle()
                tri.Indices[0] = v0
                tri.Indices[1] = v1
                tri.Indices[2] = v2
                mesh_object.AddTriangle(tri)

            logger.info(f"STL conversion complete: {vertex_count} vertices, {len(triangle_data)} triangles")

    except struct.error as e:
        logger.error(f"Invalid STL format in {stl_file_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to convert STL {stl_file_path}: {e}")
        raise


def create_3mf_from_stls(
    stl_files: List[Tuple[str, str]], output_path: str, template_path: Optional[str] = None
) -> bool:
    """
    Create a 3MF file with embedded meshes from STL files using lib3mf.

    Args:
        stl_files: List of (body_label, stl_file_path) tuples
        output_path: Output 3MF file path
        template_path: Optional template 3MF file to copy metadata from

    Returns:
        True on success, False on failure
    """
    try:
        logger.info(f"Creating 3MF with {len(stl_files)} meshes")

        # Create a new 3MF model
        wrapper = get_wrapper()
        model = wrapper.CreateModel()

        # Add each STL as a mesh object
        for body_label, stl_file_path in stl_files:
            logger.info(f"Adding mesh object: {body_label}")

            # Create mesh object and set name
            mesh_obj = model.AddMeshObject()
            mesh_obj.SetName(body_label)

            # Convert STL to mesh with vertex/triangle data
            convert_stl_to_lib3mf_mesh(stl_file_path, mesh_obj)

            # Add to build (place on print bed with identity transform)
            model.AddBuildItem(mesh_obj, wrapper.GetIdentityTransform())

        # Write to file
        logger.info(f"Writing 3MF to {output_path}")
        writer = model.QueryWriter("3mf")
        writer.WriteToFile(output_path)

        logger.info(f"Successfully created 3MF file: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create 3MF: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return False


def create_from_json_config(config_path: str) -> bool:
    """
    Create 3MF from a JSON configuration file.

    JSON format:
    {
        "output_path": "path/to/output.3mf",
        "stl_files": [
            {"label": "Body1", "path": "path/to/body1.stl"},
            {"label": "Body2", "path": "path/to/body2.stl"}
        ],
        "template_path": "path/to/template.3mf" (optional)
    }

    Args:
        config_path: Path to JSON configuration file

    Returns:
        True on success, False on failure
    """
    try:
        with open(config_path) as f:
            config = json.load(f)

        output_path = config.get("output_path")
        stl_files_config = config.get("stl_files", [])
        template_path = config.get("template_path")

        if not output_path:
            logger.error("output_path not specified in config")
            return False

        if not stl_files_config:
            logger.error("No stl_files specified in config")
            return False

        # Convert config to list of tuples
        stl_files = [(item["label"], item["path"]) for item in stl_files_config]

        logger.info(f"Loading config from {config_path}")
        return create_3mf_from_stls(stl_files, output_path, template_path)

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {config_path}: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to process config {config_path}: {e}")
        return False


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "create":
        if len(sys.argv) < 4:
            print("Usage: python3 lib3mf_utils.py create <output.3mf> <stl1> [<stl2> ...]")
            sys.exit(1)

        output_path = sys.argv[2]
        stl_files = []

        # Parse STL files with auto-generated labels
        for _i, stl_path in enumerate(sys.argv[3:]):
            if stl_path.startswith("--"):
                break
            label = Path(stl_path).stem
            stl_files.append((label, stl_path))

        # Check for template flag
        template_path = None
        try:
            template_idx = sys.argv.index("--template")
            template_path = sys.argv[template_idx + 1]
        except (ValueError, IndexError):
            pass

        success = create_3mf_from_stls(stl_files, output_path, template_path)
        sys.exit(0 if success else 1)

    elif command == "create-from-json":
        if len(sys.argv) < 3:
            print("Usage: python3 lib3mf_utils.py create-from-json <config.json>")
            sys.exit(1)

        config_path = sys.argv[2]
        success = create_from_json_config(config_path)
        sys.exit(0 if success else 1)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
