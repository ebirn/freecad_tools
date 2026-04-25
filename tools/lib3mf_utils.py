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
import math
import struct
import sys
from pathlib import Path

import lib3mf
from lib3mf import get_wrapper

# Configure logging
logging.basicConfig(level=logging.INFO, format="lib3mf_utils - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_euler_transform(
    rotation_deg: list[float] | None = None, position: list[float] | None = None
) -> "lib3mf.Transform":
    """
    Create a 3MF transformation matrix from Euler angles and position.

    Args:
        rotation_deg: List of [X, Y, Z] rotation angles in degrees (optional).
                     Applied in intrinsic order: X -> Y -> Z
        position: List of [X, Y, Z] position offsets in mm (optional)

    Returns:
        lib3mf.Transform object with combined rotation and translation

    Notes:
        - Rotation uses intrinsic (body-relative) XYZ order
        - Angles are in degrees and will be converted to radians internally
        - Identity transform is used if no rotation/position specified
    """
    # Default to zeros if not provided
    if rotation_deg is None:
        rotation_deg = [0, 0, 0]
    if position is None:
        position = [0, 0, 0]

    # Convert degrees to radians
    rad_x = math.radians(rotation_deg[0])
    rad_y = math.radians(rotation_deg[1])
    rad_z = math.radians(rotation_deg[2])

    # Pre-calculate sines and cosines
    cx = math.cos(rad_x)
    sx = math.sin(rad_x)
    cy = math.cos(rad_y)
    sy = math.sin(rad_y)
    cz = math.cos(rad_z)
    sz = math.sin(rad_z)

    # Create transformation matrix with combined XYZ rotation
    # Using intrinsic rotation order: Rz(Ry(Rx))
    transform = lib3mf.Transform()

    # Row 0 (X-axis output)
    transform.Fields[0][0] = cy * cz
    transform.Fields[0][1] = sx * sy * cz - cx * sz
    transform.Fields[0][2] = cx * sy * cz + sx * sz
    transform.Fields[0][3] = position[0]

    # Row 1 (Y-axis output)
    transform.Fields[1][0] = cy * sz
    transform.Fields[1][1] = sx * sy * sz + cx * cz
    transform.Fields[1][2] = cx * sy * sz - sx * cz
    transform.Fields[1][3] = position[1]

    # Row 2 (Z-axis output)
    transform.Fields[2][0] = -sy
    transform.Fields[2][1] = sx * cy
    transform.Fields[2][2] = cx * cy
    transform.Fields[2][3] = position[2]

    return transform


def read_metadata_from_3mf(template_path: str) -> dict | None:
    """
    Read metadata from an existing 3MF template file.

    Args:
        template_path: Path to the template 3MF file

    Returns:
        Dictionary of metadata key-value pairs, or None if file doesn't exist or has no metadata

    Notes:
        - Returns only the metadata entries (name and value pairs)
        - Ignores namespace and type information
        - Returns empty dict if file exists but has no metadata
    """
    if not template_path or not Path(template_path).exists():
        logger.warning(f"Template file not found: {template_path}")
        return None

    try:
        wrapper = get_wrapper()
        model = wrapper.CreateModel()

        # Read template 3MF file
        reader = model.QueryReader("3mf")
        reader.SetStrictModeActive(False)
        reader.ReadFromFile(template_path)

        # Extract metadata
        metadata_dict = {}
        metadata_group = model.GetMetaDataGroup()
        metadata_count = metadata_group.GetMetaDataCount()

        logger.debug(f"Reading {metadata_count} metadata entries from template: {template_path}")

        for i in range(metadata_count):
            meta = metadata_group.GetMetaData(i)
            name = meta.GetName()
            value = meta.GetValue()
            metadata_dict[name] = value
            logger.debug(f"  Template metadata: {name} = {value}")

        if metadata_count == 0:
            logger.info(f"Template file has no metadata: {template_path}")
            return {}

        logger.info(f"Extracted {len(metadata_dict)} metadata entries from template")
        return metadata_dict

    except Exception as e:
        logger.error(f"Failed to read metadata from template: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return None


def merge_metadata(template_metadata: dict | None, export_metadata: dict | None, precedence: str = "export") -> dict:
    """
    Merge template and export metadata with precedence rules.

    Args:
        template_metadata: Metadata from template 3MF file (lower priority)
        export_metadata: Metadata from export config (higher priority by default)
        precedence: Which metadata takes precedence:
                   - "export" (default): Export metadata overrides template
                   - "template": Template metadata overrides export
                   - "merge": Combine without overrides (all keys preserved)

    Returns:
        Merged metadata dictionary

    Notes:
        - "export" mode: Start with template, add/override with export metadata
        - "template" mode: Start with export, add/override with template metadata
        - "merge" mode: Combine all, with export taking precedence
    """
    result = {}

    if not template_metadata:
        template_metadata = {}
    if not export_metadata:
        export_metadata = {}

    if precedence == "template":
        # Template takes precedence: start with export, override with template
        result.update(export_metadata)
        result.update(template_metadata)
        logger.debug("Merge precedence: template > export")

    elif precedence == "merge":
        # Merge all keys, with export taking precedence
        result.update(template_metadata)
        result.update(export_metadata)
        logger.debug("Merge precedence: export > template (merge mode)")

    else:  # "export" (default)
        # Export takes precedence: start with template, override with export
        result.update(template_metadata)
        result.update(export_metadata)
        logger.debug("Merge precedence: export > template (default)")

    logger.debug(f"Final merged metadata: {len(result)} keys")
    return result


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


def add_metadata_to_model(model, metadata: dict | None = None) -> None:
    """
    Add metadata to a 3MF model.

    Args:
        model: lib3mf model object
        metadata: Dictionary of metadata key-value pairs
    """
    if not metadata:
        return

    try:
        metadata_group = model.GetMetaDataGroup()
        for key, value in metadata.items():
            if value is not None:
                logger.debug(f"Adding metadata: {key} = {value}")
                metadata_group.AddMetaData(key, str(value))
    except Exception as e:
        logger.warning(f"Failed to add metadata to model: {e}")


def create_3mf_from_stls(
    stl_files: list[tuple[str, str]],
    output_path: str,
    template_path: str | None = None,
    metadata: dict | None = None,
    transforms: list[dict] | None = None,
) -> bool:
    """
    Create a 3MF file with embedded meshes from STL files using lib3mf.

    Args:
        stl_files: List of (body_label, stl_file_path) tuples
        output_path: Output 3MF file path
        template_path: Optional template 3MF file to copy metadata from
        metadata: Optional metadata dictionary to embed in the 3MF file
                 (keys like "Project", "Author", "Version", "GitCommit", "GitBranch", etc.)
        transforms: Optional list of transform dictionaries matching stl_files order.
                   Each transform dict can have:
                   - "rotation": [x_deg, y_deg, z_deg] (degrees, optional)
                   - "position": [x_mm, y_mm, z_mm] (millimeters, optional)

    Returns:
        True on success, False on failure
    """
    try:
        logger.info(f"Creating 3MF with {len(stl_files)} meshes")

        # Read template metadata BEFORE creating the main model
        # This avoids potential conflicts with lib3mf's wrapper state
        template_metadata = None
        if template_path:
            template_metadata = read_metadata_from_3mf(template_path)
            if template_metadata:
                logger.info(f"Loaded {len(template_metadata)} metadata entries from template")

        # Create a new 3MF model
        wrapper = get_wrapper()
        model = wrapper.CreateModel()

        # Add each STL as a mesh object
        for i, (body_label, stl_file_path) in enumerate(stl_files):
            logger.info(f"Adding mesh object: {body_label}")

            # Create mesh object and set name
            mesh_obj = model.AddMeshObject()
            mesh_obj.SetName(body_label)

            # Convert STL to mesh with vertex/triangle data
            convert_stl_to_lib3mf_mesh(stl_file_path, mesh_obj)

            # Get transform for this body (or use identity if not provided)
            if transforms and i < len(transforms) and transforms[i]:
                transform_data = transforms[i]
                rotation = transform_data.get("rotation")
                position = transform_data.get("position")
                transform = create_euler_transform(rotation, position)
                logger.info(f"Applied transform to {body_label}: rotation={rotation}, position={position}")
            else:
                transform = wrapper.GetIdentityTransform()

            # Add to build with the specified transform
            model.AddBuildItem(mesh_obj, transform)

        # Add metadata if provided
        if metadata or template_metadata:
            # Merge template and export metadata
            merged_metadata = merge_metadata(template_metadata, metadata, precedence="export")
            if merged_metadata:
                logger.debug(f"Final metadata: {list(merged_metadata.keys())}")
                add_metadata_to_model(model, merged_metadata)
            else:
                logger.debug("No metadata to add")

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
        "template_path": "path/to/template.3mf" (optional),
        "transforms": [
            {"rotation": [45, 0, 0], "position": [10, 0, 0]} (optional per body),
            null (no transform)
        ] (optional),
        "metadata": {
            "Project": "MyProject",
            "Author": "John Doe",
            "Version": "1.0",
            "GitCommit": "abc1234",
            "GitBranch": "main"
        } (optional)
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
        metadata = config.get("metadata")
        transforms = config.get("transforms")

        if not output_path:
            logger.error("output_path not specified in config")
            return False

        if not stl_files_config:
            logger.error("No stl_files specified in config")
            return False

        # Convert config to list of tuples
        stl_files = [(item["label"], item["path"]) for item in stl_files_config]

        logger.info(f"Loading config from {config_path}")
        return create_3mf_from_stls(stl_files, output_path, template_path, metadata, transforms)

    except FileNotFoundError:
        raise
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
