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


def _axis_angle_to_matrix(axis, angle_deg, position=None):
    """
    Create a 3MF transformation matrix from axis+angle rotation and position.

    Args:
        axis: List of [X, Y, Z] axis vector (will be normalized)
        angle_deg: Rotation angle in degrees
        position: List of [X, Y, Z] position offsets in mm (optional)

    Returns:
        lib3mf.Transform object with combined rotation and translation

    Notes:
        - Uses Rodrigues' rotation formula for axis+angle conversion
        - Axis is normalized before calculation
        - Angle is in degrees and converted to radians internally
    """
    # Normalize axis
    axis_length = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
    if axis_length == 0:
        # Zero axis is invalid, use identity
        logger.warning(f"Zero-length rotation axis: {axis}")
        axis = [0, 0, 1]  # Default to Z-axis
        axis_length = 1
    else:
        axis = [axis[i] / axis_length for i in range(3)]

    # Convert angle to radians
    rad_theta = math.radians(angle_deg)

    # Rodrigues' rotation formula: R = I + sin(theta)*K + (1-cos(theta))*K^2
    # where K is the cross-product matrix of the unit axis vector
    theta = rad_theta
    c = math.cos(theta)
    s = math.sin(theta)
    t = 1 - c

    # Cross-product matrix elements for normalized axis [ux, uy, uz]
    ux, uy, uz = axis[0], axis[1], axis[2]

    # Rotation matrix (3x3)
    # R[0][0] = t*ux*ux + c
    # R[0][1] = t*ux*uy - s*uz
    # R[0][2] = t*ux*uz + s*uy
    # R[1][0] = t*uy*ux + s*uz
    # R[1][1] = t*uy*uy + c
    # R[1][2] = t*uy*uz - s*ux
    # R[2][0] = t*uz*ux - s*uy
    # R[2][1] = t*uz*uy + s*ux
    # R[2][2] = t*uz*uz + c

    transform = lib3mf.Transform()

    # Row 0 (X-axis output)
    transform.Fields[0][0] = t * ux * ux + c
    transform.Fields[0][1] = t * ux * uy - s * uz
    transform.Fields[0][2] = t * ux * uz + s * uy
    transform.Fields[0][3] = position[0] if position else 0

    # Row 1 (Y-axis output)
    transform.Fields[1][0] = t * uy * ux + s * uz
    transform.Fields[1][1] = t * uy * uy + c
    transform.Fields[1][2] = t * uy * uz - s * ux
    transform.Fields[1][3] = position[1] if position else 0

    # Row 2 (Z-axis output)
    transform.Fields[2][0] = t * uz * ux - s * uy
    transform.Fields[2][1] = t * uz * uy + s * ux
    transform.Fields[2][2] = t * uz * uz + c
    transform.Fields[2][3] = position[2] if position else 0

    return transform


def create_euler_transform(
    rotation_deg: list[float] | dict | None = None, position: list[float] | None = None
) -> "lib3mf.Transform":
    """
    Create a 3MF transformation matrix from rotation and position.

    Supports two rotation formats for backward compatibility:
    - Euler angles: [x_deg, y_deg, z_deg] (list of 3 numbers, existing format)
    - Axis+Angle: {"axis": [x, y, z], "angle": deg} (dict format, matches FreeCAD GUI)

    Args:
        rotation_deg: Rotation specification (optional). Can be:
                     - List of [X, Y, Z] Euler angles in degrees (intrinsic XYZ order)
                     - Dict with {"axis": [x, y, z], "angle": deg} for axis+angle rotation
        position: List of [X, Y, Z] position offsets in mm (optional)

    Returns:
        lib3mf.Transform object with combined rotation and translation

    Notes:
        - Euler rotation: intrinsic (body-relative) XYZ order
        - Axis+Angle: Uses Rodrigues' rotation formula, matches FreeCAD rotation display
        - Angles are in degrees and will be converted to radians internally
        - Identity transform is used if no rotation/position specified
    """
    if position is None:
        position = [0, 0, 0]

    # Detect rotation format
    if rotation_deg is None:
        # No rotation - return identity with position
        transform = lib3mf.Transform()
        transform.Fields[0][0] = 1
        transform.Fields[0][1] = 0
        transform.Fields[0][2] = 0
        transform.Fields[0][3] = position[0]
        transform.Fields[1][0] = 0
        transform.Fields[1][1] = 1
        transform.Fields[1][2] = 0
        transform.Fields[1][3] = position[1]
        transform.Fields[2][0] = 0
        transform.Fields[2][1] = 0
        transform.Fields[2][2] = 1
        transform.Fields[2][3] = position[2]
        return transform

    if isinstance(rotation_deg, dict):
        # Axis+Angle format: {"axis": [x, y, z], "angle": deg}
        axis = rotation_deg.get("axis", [0, 0, 1])
        angle = rotation_deg.get("angle", 0)
        return _axis_angle_to_matrix(axis, angle, position)

    # Euler angle format: [x, y, z] list
    if not isinstance(rotation_deg, (list, tuple)) or len(rotation_deg) != 3:
        logger.warning(f"Invalid Euler rotation format (expected 3-element list): {rotation_deg}")
        # Fall back to identity
        transform = lib3mf.Transform()
        transform.Fields[0][0] = 1
        transform.Fields[0][1] = 0
        transform.Fields[0][2] = 0
        transform.Fields[0][3] = position[0]
        transform.Fields[1][0] = 0
        transform.Fields[1][1] = 1
        transform.Fields[1][2] = 0
        transform.Fields[1][3] = position[1]
        transform.Fields[2][0] = 0
        transform.Fields[2][1] = 0
        transform.Fields[2][2] = 1
        transform.Fields[2][3] = position[2]
        return transform

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


def convert_stl_to_lib3mf_mesh(stl_file_path: str, mesh_object) -> dict:
    """
    Parse a binary STL file and add its mesh data to a lib3mf mesh object.

    Args:
        stl_file_path: Path to binary STL file
        mesh_object: lib3mf mesh object to populate with vertices and triangles

    Returns:
        Dictionary with quality metrics:
        - vertex_count: Number of unique vertices
        - triangle_count: Number of triangles
        - file_size: Size of STL file in bytes

    Raises:
        FileNotFoundError: If STL file doesn't exist
        struct.error: If STL format is invalid
    """
    stl_path = Path(stl_file_path)
    if not stl_path.exists():
        raise FileNotFoundError(f"STL file not found: {stl_file_path}")

    # Get file size for metrics
    file_size = stl_path.stat().st_size

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

            # Return quality metrics
            return {
                "vertex_count": vertex_count,
                "triangle_count": len(triangle_data),
                "file_size": file_size,
            }

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
) -> tuple[bool, dict]:
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
        Tuple of (success: bool, quality_metrics: dict) where quality_metrics contains:
        - total_vertex_count: Sum of all vertices across all meshes
        - total_triangle_count: Sum of all triangles across all meshes
        - total_stl_size: Sum of all STL file sizes
        - per_body: Dict with per-body metrics (body_label -> {vertex_count, triangle_count, file_size})
        - output_file_size: Size of generated 3MF file in bytes
    """
    try:
        logger.info(f"Creating 3MF with {len(stl_files)} meshes")

        # Track quality metrics
        total_vertex_count = 0
        total_triangle_count = 0
        total_stl_size = 0
        per_body_metrics = {}

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

            # Convert STL to mesh with vertex/triangle data and get metrics
            metrics = convert_stl_to_lib3mf_mesh(stl_file_path, mesh_obj)
            total_vertex_count += metrics["vertex_count"]
            total_triangle_count += metrics["triangle_count"]
            total_stl_size += metrics["file_size"]
            per_body_metrics[body_label] = {
                "vertex_count": metrics["vertex_count"],
                "triangle_count": metrics["triangle_count"],
                "file_size": metrics["file_size"],
            }

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

        # Get output file size
        output_file_size = Path(output_path).stat().st_size

        # Build quality metrics report
        quality_metrics = {
            "total_vertex_count": total_vertex_count,
            "total_triangle_count": total_triangle_count,
            "total_stl_size": total_stl_size,
            "output_file_size": output_file_size,
            "per_body": per_body_metrics,
        }

        logger.info(f"Successfully created 3MF file: {output_path}")
        logger.info(
            f"Quality Metrics: {total_vertex_count} vertices, "
            f"{total_triangle_count} triangles, "
            f"{total_stl_size} bytes STL input, "
            f"{output_file_size} bytes 3MF output"
        )
        return True, quality_metrics

    except Exception as e:
        logger.error(f"Failed to create 3MF: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return False, {}


def create_from_json_config(config_path: str) -> tuple[bool, dict]:
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
        Tuple of (success: bool, quality_metrics: dict)
        quality_metrics contains vertex/triangle counts, file sizes, per-body metrics
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
            return False, {}

        if not stl_files_config:
            logger.error("No stl_files specified in config")
            return False, {}

        # Convert config to list of tuples
        stl_files = [(item["label"], item["path"]) for item in stl_files_config]

        logger.info(f"Loading config from {config_path}")
        return create_3mf_from_stls(stl_files, output_path, template_path, metadata, transforms)

    except FileNotFoundError:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {config_path}: {e}")
        return False, {}
    except Exception as e:
        logger.error(f"Failed to process config {config_path}: {e}")
        return False, {}


def validate_3mf_file(three_mf_path: str) -> dict:
    """
    Validate a 3MF file structure and extract basic info.

    3MF files are ZIP archives containing XML and optionally resources.

    Args:
        three_mf_path: Path to the 3MF file

    Returns:
        Dictionary with validation results:
        - is_valid: bool (True if file is a valid ZIP archive with 3MF structure)
        - has_model: bool (True if 3dmodel.model file exists)
        - has_metadata: bool (True if model has metadata)
        - file_size: int (size of 3MF file in bytes)
        - error: str (error message if validation failed)
        - mesh_count: int (number of mesh objects if valid)
    """
    import zipfile

    result = {
        "is_valid": False,
        "has_model": False,
        "has_metadata": False,
        "file_size": 0,
        "error": None,
        "mesh_count": 0,
    }

    try:
        path = Path(three_mf_path)
        result["file_size"] = path.stat().st_size

        # Check it's a valid ZIP file
        with zipfile.ZipFile(three_mf_path, "r") as zf:
            # Check for required files
            file_list = zf.namelist()

            # 3MF requires 3dmodel.model - can be in root or in 3D/ directory
            has_model = (
                "3dmodel.model" in file_list or "3D/3dmodel.model" in file_list or "3d/3dmodel.model" in file_list
            )
            if not has_model:
                result["error"] = "Missing required file: 3dmodel.model (in root or 3D/ directory)"
                return result

            result["has_model"] = True

            # Check for metadata file (optional)
            if any(f.startswith("metadata/") or f.startswith("Metadata/") for f in file_list):
                result["has_metadata"] = True

            # Count mesh files (optional, but useful for quality checks)
            mesh_files = [f for f in file_list if (f.startswith("3D/") or f.startswith("3d/") or "mesh" in f.lower())]
            result["mesh_count"] = len(mesh_files)

            result["is_valid"] = True

    except zipfile.BadZipFile as e:
        result["error"] = f"Invalid ZIP/3MF file: {e}"
    except Exception as e:
        result["error"] = f"Validation error: {e}"

    return result


def format_quality_report(quality_metrics: dict) -> str:
    """
    Format quality metrics as a human-readable report.

    Args:
        quality_metrics: Dictionary from create_3mf_from_stls or create_from_json_config

    Returns:
        Formatted string report
    """
    if not quality_metrics:
        return "No quality metrics available (export may have failed)."

    lines = []
    lines.append("=" * 60)
    lines.append("3MF Export Quality Report")
    lines.append("=" * 60)
    lines.append("")

    # Overall totals
    lines.append("SUMMARY")
    lines.append("-" * 40)

    total_vertices = quality_metrics.get("total_vertex_count", 0)
    total_triangles = quality_metrics.get("total_triangle_count", 0)
    total_stl_size = quality_metrics.get("total_stl_size", 0)
    output_size = quality_metrics.get("output_file_size", 0)

    lines.append(f"Total Vertices:     {total_vertices:,}")
    lines.append(f"Total Triangles:    {total_triangles:,}")
    lines.append(f"Input STL Size:     {_format_bytes(total_stl_size)}")
    lines.append(f"Output 3MF Size:    {_format_bytes(output_size)}")

    if output_size > 0 and total_stl_size > 0:
        ratio = output_size / total_stl_size
        lines.append(f"Compression Ratio:  {ratio:.2f}x")

    lines.append("")

    # Per-body breakdown
    per_body = quality_metrics.get("per_body", {})
    if per_body:
        lines.append("PER-BODY BREAKDOWN")
        lines.append("-" * 40)
        for body_name, body_metrics in sorted(per_body.items()):
            v_count = body_metrics.get("vertex_count", 0)
            t_count = body_metrics.get("triangle_count", 0)
            f_size = body_metrics.get("file_size", 0)
            lines.append(f"  {body_name}: {v_count:,} vertices, {t_count:,} triangles, {_format_bytes(f_size)}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def _format_bytes(num_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


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

        success, metrics = create_3mf_from_stls(stl_files, output_path, template_path)
        if success and metrics:
            print(
                f"Quality Metrics: {metrics['total_vertex_count']} vertices, "
                f"{metrics['total_triangle_count']} triangles, "
                f"{metrics['output_file_size']} bytes"
            )
        sys.exit(0 if success else 1)

    elif command == "create-from-json":
        if len(sys.argv) < 3:
            print("Usage: python3 lib3mf_utils.py create-from-json <config.json>")
            sys.exit(1)

        config_path = sys.argv[2]
        success, metrics = create_from_json_config(config_path)
        if success and metrics:
            print(
                f"Quality Metrics: {metrics['total_vertex_count']} vertices, "
                f"{metrics['total_triangle_count']} triangles, "
                f"{metrics['output_file_size']} bytes"
            )
        sys.exit(0 if success else 1)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
