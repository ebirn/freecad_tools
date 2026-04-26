#!/usr/bin/env python3
import json
import logging
import os
import subprocess
import sys
import tempfile

import yaml

# Import git utilities
try:
    # Try to import from same directory
    import git_utils
except ImportError:
    # Try from parent directory
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        import git_utils
    except ImportError:
        git_utils = None

# Configure logging to both console and file
# Allow overriding log level via environment variable
log_level_name = os.environ.get("FREECAD_TOOLS_LOG_LEVEL", "INFO")
try:
    log_level = getattr(logging, log_level_name.upper())
except AttributeError:
    log_level = logging.INFO

log_file = "fc_export.log"
logging.basicConfig(
    level=log_level,
    format="%(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.debug("Script starting")
logger.debug(f"Python version: {sys.version}")
logger.debug(f"Current directory: {os.getcwd()}")

# Default config file - can be overridden by command-line argument or auto-discovery
CONFIG_FILE = None
PROJECT_ROOT = None

# Check if PROJECT_ROOT and CONFIG_FILE were passed via environment variables from parent process
if "FREECAD_TOOLS_PROJECT_ROOT" in os.environ:
    PROJECT_ROOT = os.environ["FREECAD_TOOLS_PROJECT_ROOT"]
    logger.info(f"PROJECT_ROOT restored from environment: {PROJECT_ROOT}")

if "FREECAD_TOOLS_CONFIG" in os.environ:
    CONFIG_FILE = os.environ["FREECAD_TOOLS_CONFIG"]
    logger.info(f"CONFIG_FILE restored from environment: {CONFIG_FILE}")
# Otherwise, try to set CONFIG_FILE via command-line or auto-discovery
elif len(sys.argv) > 1:
    CONFIG_FILE = sys.argv[1]
    logger.debug(f"CONFIG_FILE from command-line argument: {CONFIG_FILE}")
else:
    # Auto-discover config file
    project_config = ".freecad_tools/export.yml"
    legacy_config = "export_config.yml"

    if os.path.exists(project_config):
        CONFIG_FILE = project_config
        logger.info(f"Auto-discovered per-project config: {CONFIG_FILE}")
    elif os.path.exists(legacy_config):
        CONFIG_FILE = legacy_config
        logger.info(f"Auto-discovered legacy config: {CONFIG_FILE}")
    else:
        logger.warning("Config not found. Will try to auto-discover in subprocess.")

freecad_found = False
try:
    import FreeCAD
    import Mesh
    import Part

    freecad_found = True

except ImportError as e:
    logger.warning(f"FreeCAD not found in current Python: {e}")
    logger.info("Attempting to find FreeCAD interpreter...")

    # Try to find FreeCAD Python interpreter
    freecad_interpreter = None

    # Common FreeCAD Python interpreter locations
    interpreter_paths = [
        "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
        "/usr/bin/freecadcmd",
        "/opt/freecad/bin/freecadcmd",
        "/usr/local/bin/freecadcmd",
    ]

    for path in interpreter_paths:
        logger.debug(f"Checking for FreeCAD interpreter at: {path}")
        if os.path.exists(path):
            freecad_interpreter = path
            logger.info(f"Found FreeCAD interpreter: {freecad_interpreter}")
            break

    if freecad_interpreter:
        logger.info(f"Re-executing script with FreeCAD interpreter: {freecad_interpreter}")

        # Pass CONFIG_FILE and PROJECT_ROOT to subprocess via environment variables
        env = os.environ.copy()
        if CONFIG_FILE:
            env["FREECAD_TOOLS_CONFIG"] = CONFIG_FILE
            logger.debug(f"Passing CONFIG_FILE via environment: {CONFIG_FILE}")
        if PROJECT_ROOT:
            env["FREECAD_TOOLS_PROJECT_ROOT"] = PROJECT_ROOT
            logger.debug(f"Passing PROJECT_ROOT via environment: {PROJECT_ROOT}")

        # Run the script with the found interpreter
        result = subprocess.run([freecad_interpreter, __file__], env=env, capture_output=True, text=True)
        logger.info(f"Subprocess returned exit code: {result.returncode}")
        if result.stdout:
            logger.info(f"Subprocess STDOUT:\n{result.stdout}")
        if result.stderr:
            logger.info(f"Subprocess STDERR:\n{result.stderr}")
        # Exit with the subprocess result code
        sys.exit(result.returncode)
    else:
        logger.error("FreeCAD interpreter not found. Checked paths:")
        for path in interpreter_paths:
            logger.error(f"  - {path}")
        logger.error("Please install FreeCAD or adjust interpreter paths in this script")
        sys.exit(1)

# If we reach here, FreeCAD was found in the current Python environment
if not freecad_found:
    logger.error("FreeCAD import failed but no exception was raised - this should not happen")
    sys.exit(1)

logger.debug("FreeCAD modules successfully available, proceeding with main()")


def resolve_template_path(template_name):
    """
    Resolve template 3MF file path.
    Try locations in order:
    1. If template_name is None, use default template from examples/
    2. Check if template_name is absolute path that exists
    3. Check in current directory
    4. Check in project's .freecad_tools/ directory
    5. Fallback to examples/default.3mf if available

    Args:
        template_name: Name or path of template file, or None to use default

    Returns:
        Absolute path to template if found, None otherwise
    """
    # Try to find freecad_tools default template (examples/default.3mf)
    script_dir = os.path.dirname(os.path.abspath(__file__))  # tools/
    tools_root = os.path.dirname(script_dir)  # freecad_tools/
    default_template = os.path.join(tools_root, "examples", "default.3mf")

    # If no template specified, use default
    if not template_name:
        if os.path.exists(default_template):
            logger.debug(f"Using default template: {default_template}")
            return default_template
        else:
            logger.debug("No template specified and no default available")
            return None

    # Try as absolute path first
    if os.path.isabs(template_name) and os.path.exists(template_name):
        logger.debug(f"Found template at absolute path: {template_name}")
        return template_name

    # Try in current directory
    if os.path.exists(template_name):
        abs_path = os.path.abspath(template_name)
        logger.debug(f"Found template in current directory: {abs_path}")
        return abs_path

    # Try in .freecad_tools/ directory
    project_template = os.path.join(".freecad_tools", template_name)
    if os.path.exists(project_template):
        abs_path = os.path.abspath(project_template)
        logger.debug(f"Found template in .freecad_tools/: {abs_path}")
        return abs_path

    # Fallback to default template
    if os.path.exists(default_template):
        logger.info(f"Template '{template_name}' not found, using default: {default_template}")
        return default_template

    logger.warning(f"Template '{template_name}' not found and no default available")
    return None


def resolve_object_identifier(doc, identifier):
    """
    Resolve a FreeCAD object by Name or Label.
    User can specify either the internal Name (e.g., 'Body') or friendly Label (e.g., 'Feed').

    Args:
        doc: FreeCAD document
        identifier: Object Name or Label to find

    Returns:
        Tuple (obj, resolved_name, resolved_label) or (None, None, None) if not found
    """
    # First try exact Name match
    obj = doc.getObject(identifier)
    if obj is not None:
        label = obj.Label if hasattr(obj, "Label") else identifier
        logger.debug(f"Resolved '{identifier}' as Name → {obj.Name} (Label: {label})")
        return obj, obj.Name, label

    # Then try Label match (case-insensitive for user-friendliness)
    for obj in doc.Objects:
        if hasattr(obj, "Label") and obj.Label == identifier:
            logger.debug(f"Resolved '{identifier}' as Label → {obj.Name} (Label: {obj.Label})")
            return obj, obj.Name, obj.Label

    logger.warning(f"Could not resolve object '{identifier}' by Name or Label")
    return None, None, None


def parse_body_specs(bodies_config):
    """
    Parse body specifications from config, handling both simple and complex formats.

    Body specs can be:
    - String: Simple body identifier (Name or Label)
    - Dict: Object with 'body' field and optional 'rotation' and 'position' transforms

    Args:
        bodies_config: List of body specifications (strings or dicts)

    Returns:
        List of tuples: (body_identifier, rotation_deg, position_mm)
        where rotation_deg and position_mm are None if not specified
    """
    parsed = []

    for body_spec in bodies_config:
        if isinstance(body_spec, str):
            # Simple string format: just the body identifier
            parsed.append((body_spec, None, None))
        elif isinstance(body_spec, dict):
            # Complex format with optional transforms
            body_id = body_spec.get("body")
            if not body_id:
                logger.warning(f"Body spec missing 'body' field: {body_spec}")
                continue

            rotation = body_spec.get("rotation")
            position = body_spec.get("position")

            # Validate rotation/position if provided
            if rotation and len(rotation) != 3:
                logger.warning(f"Invalid rotation (expected 3 values): {rotation}")
                rotation = None
            if position and len(position) != 3:
                logger.warning(f"Invalid position (expected 3 values): {position}")
                position = None

            parsed.append((body_id, rotation, position))
        else:
            logger.warning(f"Unexpected body spec format: {body_spec}")

    return parsed


def resolve_relative_path(path, base_dir):
    """
    Resolve a path relative to a base directory.
    If path is already absolute, return as-is. If relative, join with base_dir.

    Args:
        path: The path to resolve (can be None, absolute, or relative)
        base_dir: The base directory for resolving relative paths

    Returns:
        Resolved absolute path, or None if path is None
    """
    if not path:
        return None
    if os.path.isabs(path):
        return path
    return os.path.join(base_dir, path)


def get_export_metadata(config_item, base_dir):
    """
    Extract metadata from config item and environment.

    Args:
        config_item: Export configuration item dict
        base_dir: Base directory for resolving relative paths

    Returns:
        Dictionary of metadata key-value pairs
    """
    metadata = {}

    # Add explicitly specified metadata from config
    export_metadata = config_item.get("metadata", {})
    if export_metadata:
        metadata.update(export_metadata)

    # Add git metadata if available and not already specified
    if git_utils and git_utils.is_git_repo(base_dir):
        try:
            git_meta = git_utils.get_git_metadata(cwd=base_dir)

            # Add git metadata with defaults
            if "GitCommit" not in metadata and git_meta.get("commit_short"):
                metadata["GitCommit"] = git_meta["commit_short"]
            if "GitCommitFull" not in metadata and git_meta.get("commit_hash"):
                metadata["GitCommitFull"] = git_meta["commit_hash"]
            if "GitBranch" not in metadata and git_meta.get("branch"):
                metadata["GitBranch"] = git_meta["branch"]
            if "GitTags" not in metadata and git_meta.get("tags"):
                metadata["GitTags"] = git_meta["tags"]
            if "GitRemote" not in metadata and git_meta.get("remote_url"):
                metadata["GitRemote"] = git_meta["remote_url"]

            logger.info(f"Added git metadata: {list(git_meta.keys())}")
        except Exception as e:
            logger.debug(f"Failed to get git metadata: {e}")
    else:
        logger.debug("Not in a git repository or git_utils not available")

    return metadata


def load_config():
    global CONFIG_FILE, PROJECT_ROOT

    # If CONFIG_FILE not set by command-line, determine default
    if not CONFIG_FILE:
        # Try .freecad_tools/export.yml first (per-project config)
        project_config = ".freecad_tools/export.yml"
        if os.path.exists(project_config):
            CONFIG_FILE = project_config
            logger.info(f"Using per-project config: {CONFIG_FILE}")
        # Fall back to export_config.yml in current directory
        elif os.path.exists("export_config.yml"):
            CONFIG_FILE = "export_config.yml"
            logger.info(f"Using legacy config: {CONFIG_FILE}")
        else:
            logger.error("Config file not found. Tried '.freecad_tools/export.yml' and 'export_config.yml'")
            sys.exit(1)

    logger.debug(f"Loading config from: {CONFIG_FILE}")
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"Config file '{CONFIG_FILE}' not found.")
        sys.exit(1)

    # Get the project root directory for path resolution
    # Use PROJECT_ROOT from environment if available (passed by export.py)
    # Otherwise, detect it from config file location
    if PROJECT_ROOT:
        base_dir = PROJECT_ROOT
        logger.info(f"Using PROJECT_ROOT from environment: {base_dir}")
    else:
        # Detect project root based on config file location
        # If config is in .freecad_tools/, resolve paths relative to parent (project root)
        # If config is in root (legacy), resolve relative to current directory
        config_path = os.path.abspath(CONFIG_FILE)
        config_dir = os.path.dirname(config_path)
        if os.path.basename(config_dir) == ".freecad_tools":
            # Config is in .freecad_tools/, use parent directory as base
            base_dir = os.path.dirname(config_dir)
        else:
            # Config is in project root (legacy), use its directory as base
            base_dir = config_dir
        logger.info(f"Detected project root from config location: {base_dir}")

    logger.debug(f"Base directory for path resolution: {base_dir}")

    with open(CONFIG_FILE) as f:
        content = f.read()
        logger.debug(f"Config file content:\n{content}")
        config = yaml.safe_load(content)
    logger.debug(f"Loaded config: {config}")
    if config is None:
        logger.error("Config file is empty or invalid YAML")
        sys.exit(1)
    result = config.get("export", [])
    logger.debug(f"Export list type: {type(result)}, length: {len(result) if isinstance(result, list) else 'N/A'}")
    logger.debug(f"Export list: {result}")

    # Resolve relative paths in config items relative to project root
    for item in result:
        # List of path fields to resolve
        path_fields = ["source", "output", "template", "stl_output_dir"]
        for field in path_fields:
            if field in item and item[field]:
                resolved = resolve_relative_path(item[field], base_dir)
                if resolved != item[field]:
                    logger.debug(f"Resolved {field} '{item[field]}' to: {resolved}")
                item[field] = resolved

    return result


def export_bodies(doc, bodies, output_path):
    logger.debug(f"Available objects in document: {[obj.Name for obj in doc.Objects]}")
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    exported_any = False
    for body_name in bodies:
        obj = doc.getObject(body_name)
        if obj is None:
            logger.warning(f"Object '{body_name}' not found in document. Skipping.")
            continue
        if hasattr(obj, "Shape") and obj.Shape:
            # Get the label (user-friendly name) of the body
            body_label = obj.Label if hasattr(obj, "Label") else body_name
            logger.debug(f"Exporting shape from '{body_name}' (Label: {body_label})")
            try:
                # Calculate tessellation tolerance based on object size
                # For small parts, we need finer tolerance for better quality
                bbox = obj.Shape.BoundBox
                max_dimension = max(bbox.XLength, bbox.YLength, bbox.ZLength)
                # Use 0.1% of the largest dimension as tolerance (minimum 0.001mm)
                tessellation_tolerance = max(0.001, max_dimension * 0.001)
                logger.debug(
                    f"Object size: {max_dimension:.2f}mm, using tessellation tolerance: {tessellation_tolerance:.4f}mm"
                )

                # Generate filename with body label
                output_base = str(output_path)
                if output_base.endswith((".stl", ".3mf")):
                    output_base = output_base.rsplit(".", 1)[0]
                # Sanitize label for filename
                safe_label = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in body_label)
                output_file = f"{output_base}-{safe_label}.stl"

                logger.debug(
                    f"Creating mesh from '{body_name}' with tessellation tolerance {tessellation_tolerance:.4f}mm"
                )
                mesh = Mesh.Mesh(obj.Shape.tessellate(tessellation_tolerance))
                logger.info(f"Mesh created with {len(mesh.Facets)} facets")

                # Write mesh to file
                mesh.write(output_file)
                logger.info(f"Exported '{body_label}' ({body_name}) to '{output_file}'")
                exported_any = True
            except Exception as e:
                logger.error(f"Failed to export '{body_name}': {e}")
        else:
            logger.warning(f"Object '{body_name}' has no Shape. Skipping.")
    if not exported_any:
        logger.error(f"No objects exported from '{output_path}'.")
        return False
    return True


def export_full_doc(doc, output_path):
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    logger.debug(f"Exporting full document to {output_path}")
    doc.save()

    # For FreeCAD documents, we need to use the document's built-in export
    # Try using Part Design workbench export if available
    try:
        doc.export3MF(output_path)
    except AttributeError:
        # Fallback: try using Part workbench export
        logger.warning("Document export3MF not available, trying Part.exportShape")
        # Export the active body or first body
        bodies = [obj for obj in doc.Objects if hasattr(obj, "Shape") and obj.Shape]
        if bodies:
            Part.export(bodies[0].Shape, output_path)
        else:
            logger.error("No exportable shapes found in document")
            return False
    logger.info(f"Exported full document to '{output_path}'")
    return True


def export_bodies_to_3mf_with_template(
    doc,
    bodies,
    output_path,
    template_path=None,
    keep_stl=False,
    stl_output_dir=None,
    export_name="",
    metadata=None,
):
    """
    Export bodies to 3MF format using lib3mf (via subprocess).
    Optionally uses a template 3MF file for metadata/settings preservation.

    Args:
        doc: FreeCAD document
        bodies: List of body identifiers or specs. Can be:
                - Strings: body Name or Label
                - Dicts: {"body": "name", "rotation": [x,y,z], "position": [x,y,z]}
        output_path: Output 3MF file path
        template_path: Optional path to a template 3MF file
        keep_stl: If True, keep generated STL files in stl_output_dir
        stl_output_dir: Directory to place STL files (defaults to temp if keep_stl=False)
        export_name: Export item name (used to prefix STL files)
        metadata: Optional dictionary of metadata to embed in the 3MF file
    """
    logger.debug(f"Exporting bodies to 3MF with template: {template_path}")

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Determine where to put STL files
    if keep_stl and stl_output_dir:
        os.makedirs(stl_output_dir, exist_ok=True)
        stl_dir = stl_output_dir
        temp_dir = None
    else:
        temp_dir = tempfile.TemporaryDirectory()
        stl_dir = temp_dir.name

    try:
        # Parse body specifications (can include transforms)
        parsed_bodies = parse_body_specs(bodies)
        logger.debug(f"Parsed {len(parsed_bodies)} body specifications")

        # Export bodies to STL files
        stl_files = []
        transforms = []  # Parallel list of transforms
        body_count = {}  # Track duplicate body exports

        for body_id, rotation, position in parsed_bodies:
            # Resolve object by Name or Label
            obj, obj_name, obj_label = resolve_object_identifier(doc, body_id)

            if obj is None:
                logger.warning(f"Object '{body_id}' not found. Skipping.")
                continue

            if not (hasattr(obj, "Shape") and obj.Shape):
                logger.warning(f"Object '{obj_name}' has no Shape. Skipping.")
                continue

            try:
                # Calculate tessellation tolerance based on object size
                bbox = obj.Shape.BoundBox
                max_dimension = max(bbox.XLength, bbox.YLength, bbox.ZLength)
                tessellation_tolerance = max(0.001, max_dimension * 0.001)

                # Track duplicate bodies (e.g., exporting same body twice)
                body_key = obj_name
                if body_key not in body_count:
                    body_count[body_key] = 0
                body_count[body_key] += 1

                # Generate STL filename with export name prefix and body label
                # If exporting same body multiple times, append count suffix
                stl_filename = f"{export_name}_{obj_label}"
                if body_count[body_key] > 1:
                    stl_filename = f"{export_name}_{obj_label}_{body_count[body_key]}"

                # Sanitize filename
                stl_filename = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in stl_filename)
                stl_file = os.path.join(stl_dir, f"{stl_filename}.stl")

                # Export STL
                mesh = Mesh.Mesh(obj.Shape.tessellate(tessellation_tolerance))
                mesh.write(stl_file)
                logger.info(f"Created STL for '{obj_label}': {len(mesh.Facets)} facets → {stl_filename}.stl")

                # Use export_name_body_label for the 3MF mesh object label
                mesh_label = f"{export_name}_{obj_label}"
                if body_count[body_key] > 1:
                    mesh_label = f"{export_name}_{obj_label}_{body_count[body_key]}"

                stl_files.append((mesh_label, stl_file))

                # Collect transform for this body
                transform_dict = {}
                if rotation:
                    transform_dict["rotation"] = rotation
                if position:
                    transform_dict["position"] = position

                transforms.append(transform_dict if transform_dict else None)
                logger.debug(f"Body '{obj_label}': rotation={rotation}, position={position}")

            except Exception as e:
                logger.error(f"Failed to create STL for '{obj_name}': {e}")

        if not stl_files:
            logger.error("No valid bodies to export to 3MF")
            return False

        # Ensure output_path is absolute before passing to subprocess
        abs_output_path = os.path.abspath(output_path)
        logger.debug(f"Output path (absolute): {abs_output_path}")

        # Call lib3mf via subprocess to create 3MF
        logger.info(f"Creating 3MF with {len(stl_files)} embedded meshes via lib3mf")

        # Build config for lib3mf subprocess
        lib3mf_config = {
            "output_path": abs_output_path,
            "stl_files": [{"label": label, "path": path} for label, path in stl_files],
        }

        # Add transforms if any are specified
        if any(transforms):
            lib3mf_config["transforms"] = [
                {"rotation": t.get("rotation"), "position": t.get("position")} if t else None for t in transforms
            ]
            logger.debug(f"Added {len([t for t in transforms if t])} body transforms to lib3mf config")

        if template_path and os.path.exists(template_path):
            lib3mf_config["template_path"] = template_path

        # Add metadata if provided
        if metadata:
            lib3mf_config["metadata"] = metadata
            logger.debug(f"Added metadata to lib3mf config: {list(metadata.keys())}")

        # Write config to temp JSON file
        config_file = os.path.join(stl_dir, "_lib3mf_config.json")
        with open(config_file, "w") as f:
            json.dump(lib3mf_config, f)

        # Call lib3mf_utils.py via subprocess using a Python with lib3mf installed
        # First check if lib3mf Python was passed via environment (original Python before FreeCAD takeover)
        script_dir = os.path.dirname(__file__)
        lib3mf_script = os.path.join(script_dir, "lib3mf_utils.py")

        # Try to use the lib3mf Python passed from export.py (original Python with lib3mf)
        lib3mf_python = os.environ.get("FREECAD_TOOLS_LIB3MF_PYTHON")
        if lib3mf_python:
            python_executable = lib3mf_python
            logger.debug(f"Using lib3mf Python from environment: {python_executable}")
        else:
            # Fallback: try venv or sys.executable
            venv_python = os.path.join(os.path.dirname(script_dir), ".venv", "bin", "python3")
            venv_python = os.path.abspath(venv_python)
            python_executable = venv_python if os.path.exists(venv_python) else sys.executable
            logger.debug(f"Using fallback Python: {python_executable}")

        logger.debug(f"Calling lib3mf: {python_executable} {lib3mf_script} create-from-json {config_file}")

        result = subprocess.run(
            [python_executable, lib3mf_script, "create-from-json", config_file],
            capture_output=True,
            text=True,
        )

        # Log subprocess output
        if result.stdout:
            logger.debug(f"lib3mf STDOUT:\n{result.stdout}")
        if result.stderr:
            logger.debug(f"lib3mf STDERR:\n{result.stderr}")

        if result.returncode != 0:
            logger.error(f"lib3mf subprocess failed with exit code {result.returncode}")
            return False

        # Verify the 3MF file was actually created
        if not os.path.exists(abs_output_path):
            logger.error(f"3MF file was not created at {abs_output_path}")
            logger.error("lib3mf reported success but file does not exist - this is a critical issue")
            return False

        # Get file stats for logging
        file_size = os.path.getsize(abs_output_path)
        logger.info(f"Successfully created 3MF: {abs_output_path} ({file_size} bytes)")
        return True

    except Exception as e:
        logger.error(f"Failed to export to 3MF: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return False

    finally:
        # Clean up temp directory if we created one
        if temp_dir:
            temp_dir.cleanup()


def export_techdraw_pages(doc, pages_to_export, output_dir):
    """
    Export TechDraw pages from a document to SVG files.

    Attempts to extract TechDraw pages by rendering them to SVG.
    Note: TechDraw SVG export requires GUI rendering, which is not available
    in headless mode (freecadcmd). This function serves as a placeholder for
    future enhancement when FreeCAD provides headless rendering support.

    For now, TechDraw pages can be exported manually from the FreeCAD GUI:
    - TechDraw > Export Page as SVG

    Args:
        doc: FreeCAD document
        pages_to_export: List of page names/labels (empty = all pages)
        output_dir: Directory to save SVG files

    Returns:
        List of (page_label, svg_file_path) tuples (empty in headless mode)
    """
    result = []

    try:
        import TechDraw  # noqa: F401 - needed for TechDraw objects

        # Find all TechDraw DrawPage objects in document
        techdraw_pages = [obj for obj in doc.Objects if hasattr(obj, "TypeId") and obj.TypeId == "TechDraw::DrawPage"]

        if not techdraw_pages:
            logger.info("No TechDraw pages found in document")
            return result

        logger.info(f"Found {len(techdraw_pages)} TechDraw page(s)")

        # Determine which pages to export
        if pages_to_export:
            # Export specific pages
            pages_to_process = []
            for page_spec in pages_to_export:
                # Try Name first, then Label
                found = None
                for page in techdraw_pages:
                    if page.Name == page_spec or (hasattr(page, "Label") and page.Label == page_spec):
                        found = page
                        break
                if found:
                    pages_to_process.append(found)
                else:
                    logger.warning(f"TechDraw page '{page_spec}' not found")
        else:
            # Export all pages
            pages_to_process = techdraw_pages

        logger.info(f"TechDraw pages available: {len(pages_to_process)}")
        logger.debug("Note: TechDraw SVG export requires GUI rendering (not available in headless mode)")
        logger.info("To export TechDraw pages manually:")
        logger.info("  1. Open the document in FreeCAD GUI")
        logger.info("  2. Right-click TechDraw page → Export Page as SVG")
        logger.info("  3. Save to output directory")

        for page in pages_to_process:
            page_label = page.Label if hasattr(page, "Label") else page.Name
            logger.debug(f"Identified TechDraw page: {page_label} ({page.Name})")

        # Return empty list since SVG export requires GUI
        # Future: when FreeCAD provides headless rendering, this will generate SVGs
        logger.warning("TechDraw SVG export skipped (requires FreeCAD GUI, not available in headless mode)")

    except ImportError:
        logger.warning("TechDraw module not available")
    except Exception as e:
        logger.exception(f"Error processing TechDraw pages: {e}")

    return result


def extract_bom_from_assembly(doc, custom_fields=None):
    """
    Extract Bill of Materials from FreeCAD Assembly workbench (native, FreeCAD 1.0+).

    Walks the Assembly object tree recursively to build a BOM with part counts.

    Args:
        doc: FreeCAD document
        custom_fields: List of custom property names to extract (e.g., ["URL", "Price", "Material"])

    Returns:
        List of BOM dicts: [{"label": "", "quantity": 1, "material": "", ...}, ...]
    """
    bom = []
    part_count = {}  # Track part counts by linked object

    if custom_fields is None:
        custom_fields = []

    try:
        # Find Assembly objects (native workbench: FreeCAD 1.0+)
        assembly_objects = [
            obj
            for obj in doc.Objects
            if hasattr(obj, "TypeId") and obj.TypeId in ["Assembly::AssemblyObject", "Assembly::AssemblyLink"]
        ]

        if not assembly_objects:
            logger.info("No native Assembly found in document")
            return bom

        logger.info(f"Found {len(assembly_objects)} Assembly object(s)")

        # Recursively walk assembly tree
        def walk_assembly(obj, depth=0):
            indent = "  " * depth
            logger.debug(f"{indent}Walking {obj.Name} (TypeId: {obj.TypeId})")

            # Get subobjects (child parts/assemblies)
            try:
                subobjects = obj.getSubObjects()
                for subobj_name in subobjects:
                    try:
                        subobj = obj.getSubObject(subobj_name, retType=1)
                        if subobj is None:
                            continue

                        # For App::Link objects, get the linked object
                        # This handles duplicates (Bearing001, Bearing002) as same part
                        linked_obj = subobj
                        if hasattr(subobj, "LinkedObject"):
                            linked_obj = subobj.LinkedObject

                        # Use linked object's ID for counting duplicates
                        obj_id = linked_obj.FullName if hasattr(linked_obj, "FullName") else linked_obj.Name

                        # Increment count for this part
                        part_count[obj_id] = part_count.get(obj_id, 0) + 1

                        logger.debug(
                            f"{indent}  Part: {subobj.Label} → {linked_obj.Label} (count: {part_count[obj_id]})"
                        )

                        # Recurse if this is a container
                        if hasattr(subobj, "getSubObjects"):
                            walk_assembly(subobj, depth + 1)
                    except Exception as e:
                        logger.debug(f"{indent}  Error processing subobject: {e}")
            except Exception as e:
                logger.debug(f"{indent}  Error getting subobjects: {e}")

        # Walk each assembly
        for asm_obj in assembly_objects:
            walk_assembly(asm_obj)

        # Build BOM from part counts
        for obj_id, qty in part_count.items():
            # Parse FullName to get object name
            if "#" in obj_id:
                doc_name, obj_name = obj_id.split("#", 1)
                obj = doc.getObject(obj_name)
            else:
                obj = doc.getObject(obj_id)

            if obj is None:
                logger.warning(f"Could not find object: {obj_id}")
                continue

            bom_item = {
                "label": obj.Label if hasattr(obj, "Label") else obj.Name,
                "quantity": qty,
            }

            # Extract custom properties if present
            for field in custom_fields:
                try:
                    value = getattr(obj, field, "")
                    if value:
                        bom_item[field.lower()] = str(value)
                except Exception:
                    pass

            bom.append(bom_item)

        logger.info(f"Extracted {len(bom)} unique parts from Assembly")

    except Exception as e:
        logger.exception(f"Error extracting Assembly BOM: {e}")

    return bom


def extract_bom_from_spreadsheet(doc, spreadsheet_name=None, custom_fields=None):
    """
    Extract Bill of Materials from a FreeCAD Spreadsheet.

    Reads cells from a spreadsheet object to build BOM.

    Args:
        doc: FreeCAD document
        spreadsheet_name: Name/Label of spreadsheet to read (default: "BOM")
        custom_fields: List of custom property names to extract

    Returns:
        List of BOM dicts
    """
    bom = []

    if spreadsheet_name is None:
        spreadsheet_name = "BOM"

    if custom_fields is None:
        custom_fields = []

    try:
        # Find spreadsheet object
        sheet_obj = None
        for obj in doc.Objects:
            if hasattr(obj, "TypeId") and obj.TypeId == "Spreadsheet::Sheet":
                if obj.Name == spreadsheet_name or (hasattr(obj, "Label") and obj.Label == spreadsheet_name):
                    sheet_obj = obj
                    break

        if sheet_obj is None:
            logger.warning(f"Spreadsheet '{spreadsheet_name}' not found")
            return bom

        logger.info(f"Reading BOM from spreadsheet: {spreadsheet_name}")

        # Get non-empty cells range
        try:
            # Try getUsedRange() if available (newer FreeCAD)
            if hasattr(sheet_obj, "getUsedRange"):
                start_cell, end_cell = sheet_obj.getUsedRange()
                logger.debug(f"Used range: {start_cell} to {end_cell}")
            else:
                # Fallback: assume data starts at A1
                start_cell = "A1"
                end_cell = None
        except Exception as e:
            logger.debug(f"Could not determine cell range: {e}")
            # Assume standard BOM format with header in row 1
            start_cell = "A1"

        # Read spreadsheet cells (simplified: assumes standard BOM table format)
        # Expected format: Column A = Label, Column B = Quantity, etc.
        try:
            # Get all non-empty cells
            if hasattr(sheet_obj, "getNonEmptyCells"):
                cells = sheet_obj.getNonEmptyCells()
                logger.debug(f"Found {len(cells)} non-empty cells")

                # Group by row and build BOM items
                rows = {}
                for cell_addr in cells:
                    # Parse cell address (e.g., "A1" → (1, 'A'))
                    # Extract row number
                    row_num = int("".join(c for c in cell_addr if c.isdigit()))
                    col_letter = "".join(c for c in cell_addr if c.isalpha())

                    if row_num not in rows:
                        rows[row_num] = {}
                    try:
                        cell_value = sheet_obj.getContents(cell_addr)
                        rows[row_num][col_letter] = cell_value
                    except Exception:
                        pass

                # Skip header row (row 1), build BOM from data rows
                for row_num in sorted(rows.keys()):
                    if row_num == 1:  # Skip header
                        continue

                    row = rows[row_num]
                    # Assume: A=Label, B=Quantity, C+=custom fields
                    if "A" in row:
                        bom_item = {
                            "label": str(row.get("A", "")),
                            "quantity": int(row.get("B", "1")),
                        }

                        # Map remaining columns to custom fields
                        col_letters = ["C", "D", "E", "F", "G", "H", "I", "J"]
                        for i, field_name in enumerate(custom_fields):
                            if i < len(col_letters) and col_letters[i] in row:
                                bom_item[field_name.lower()] = str(row[col_letters[i]])

                        bom.append(bom_item)

        except Exception as e:
            logger.warning(f"Error reading spreadsheet cells: {e}")

        logger.info(f"Extracted {len(bom)} items from spreadsheet")

    except Exception as e:
        logger.exception(f"Error extracting Spreadsheet BOM: {e}")

    return bom


def extract_bom_from_parts(doc, custom_fields=None):
    """
    Extract Bill of Materials by inspecting Part and Body objects directly.

    Fallback BOM generation when Assembly/Spreadsheet not available.

    Args:
        doc: FreeCAD document
        custom_fields: List of custom property names to extract

    Returns:
        List of BOM dicts
    """
    bom = []

    if custom_fields is None:
        custom_fields = []

    try:
        # Find all Part and Body objects
        part_bodies = [
            obj
            for obj in doc.Objects
            if hasattr(obj, "TypeId") and obj.TypeId in ["PartDesign::Body", "Part::Feature", "Part::FeaturePython"]
        ]

        logger.info(f"Found {len(part_bodies)} Part/Body object(s)")

        for obj in part_bodies:
            bom_item = {
                "label": obj.Label if hasattr(obj, "Label") else obj.Name,
                "quantity": 1,
            }

            # Extract custom properties if present
            for field in custom_fields:
                try:
                    value = getattr(obj, field, "")
                    if value:
                        bom_item[field.lower()] = str(value)
                except Exception:
                    pass

            bom.append(bom_item)

        logger.info(f"Extracted {len(bom)} parts from document")

    except Exception as e:
        logger.exception(f"Error extracting Parts BOM: {e}")

    return bom


def main():
    logger.info("=" * 60)
    logger.debug(f"Current working directory: {os.getcwd()}")
    logger.debug(f"PROJECT_ROOT: {PROJECT_ROOT}")
    logger.debug(f"CONFIG_FILE: {CONFIG_FILE}")
    logger.debug("Starting main()")
    exports = load_config()
    logger.debug(f"Loaded {len(exports)} exports")
    if not exports:
        logger.warning("No exports defined in config - exports list is empty or None")
        sys.exit(0)
    logger.info(f"Beginning processing of {len(exports)} export(s)")
    for i, item in enumerate(exports):
        logger.info(f"=== Processing item {i} ===")
        logger.debug(f"Item content: {item}")

        source = item.get("source")
        output = item.get("output")
        bodies = item.get("bodies", [])
        template = item.get("template")  # Optional template 3MF file
        keep_stl = item.get("keep_stl", False)  # Keep STL files?
        stl_output_dir = item.get("stl_output_dir")  # Where to place STL files
        export_name = item.get("name", "export")  # Export item name (used for file prefixing)
        techdraw_config = item.get("techdraw")  # Optional TechDraw export config
        bom_config = item.get("bom")  # Optional BOM generation config

        logger.debug(
            f"Item {i}: name={export_name}, source={source}, output={output}, bodies={bodies}, "
            f"template={template}, keep_stl={keep_stl}, stl_output_dir={stl_output_dir}, "
            f"techdraw={techdraw_config}, bom={bom_config}"
        )

        if not source:
            logger.error("Missing 'source' in config item.")
            sys.exit(1)

        # Generate default output filename if not specified
        if not output:
            output = f"prints/{export_name}.3mf"
            logger.info(f"No output specified, using default: {output}")

        if not os.path.exists(source):
            logger.error(f"Source file '{source}' not found.")
            sys.exit(1)

        logger.debug(f"Opening document {source}")
        try:
            doc = FreeCAD.open(source)
            doc_name = doc.Name  # Save the name before closing
            logger.debug(f"Opened document {doc_name}")
            logger.debug(
                f"Document objects: {[(obj.Name, obj.Label if hasattr(obj, 'Label') else 'N/A') for obj in doc.Objects]}"
            )
            FreeCAD.setActiveDocument(doc_name)

            if bodies:
                logger.info(f"Exporting bodies {bodies} with export name '{export_name}'")
                # Try to resolve template path (uses config value or falls back to default)
                resolved_template = resolve_template_path(template)

                # Extract metadata from config item and environment
                export_metadata = get_export_metadata(item, PROJECT_ROOT or os.getcwd())

                # Use template-based export if template is available
                if resolved_template:
                    logger.info(f"Using template: {resolved_template}")
                    success = export_bodies_to_3mf_with_template(
                        doc,
                        bodies,
                        output,
                        resolved_template,
                        keep_stl,
                        stl_output_dir,
                        export_name,
                        metadata=export_metadata,
                    )
                else:
                    # Fallback to STL export if no template available
                    logger.info("No template specified or available, exporting bodies to 3MF without template")
                    success = export_bodies(doc, bodies, output)
            else:
                logger.info("Exporting full document")
                success = export_full_doc(doc, output)

            logger.debug(f"Export success: {success}")
            if not success:
                FreeCAD.closeDocument(doc_name)
                sys.exit(1)

            # Final validation: ensure output file exists
            output_abs = os.path.abspath(output)
            if not os.path.exists(output_abs):
                logger.error(f"Export reported success but output file does not exist: {output_abs}")
                logger.error("This is a critical issue - the export process completed but produced no file")
                FreeCAD.closeDocument(doc_name)
                sys.exit(1)

            file_size = os.path.getsize(output_abs)
            logger.info(f"Output file verified: {output_abs} ({file_size} bytes)")

            # Process TechDraw pages if configured
            if techdraw_config:
                logger.info("Processing TechDraw export")
                pages_to_export = techdraw_config.get("pages", [])
                techdraw_output_dir = techdraw_config.get("output_dir", "docs")
                techdraw_format = techdraw_config.get("format", "svg")  # Currently only SVG supported

                if techdraw_format != "svg":
                    logger.warning(f"TechDraw format '{techdraw_format}' not yet supported, skipping")
                else:
                    try:
                        logger.debug(f"Exporting TechDraw pages: {pages_to_export or 'all'} to {techdraw_output_dir}")
                        techdraw_results = export_techdraw_pages(doc, pages_to_export, techdraw_output_dir)
                        if techdraw_results:
                            logger.info(f"Exported {len(techdraw_results)} TechDraw page(s)")
                            for page_label, svg_path in techdraw_results:
                                logger.info(f"  → {page_label}: {svg_path}")
                        else:
                            logger.warning("No TechDraw pages exported")
                    except Exception as e:
                        logger.exception(f"Error exporting TechDraw pages: {e}")

            # Process BOM generation if configured
            if bom_config:
                logger.info("Processing BOM generation")
                bom_source = bom_config.get("source", "auto")  # auto/assembly/spreadsheet/parts
                bom_output = bom_config.get("output", f"docs/{export_name}_bom.csv")
                bom_fields = bom_config.get("fields", [])  # Custom fields like material, url, price

                try:
                    # Generate default BOM output path if not specified
                    if not os.path.isabs(bom_output):
                        bom_output = os.path.join(os.getcwd(), bom_output)

                    # Extract BOM based on source priority (auto/assembly/spreadsheet/parts)
                    bom_data = []
                    if bom_source in ("auto", "assembly"):
                        logger.debug("Attempting to extract BOM from Assembly")
                        bom_data = extract_bom_from_assembly(doc, custom_fields=bom_fields)
                        if bom_data:
                            logger.info(f"Successfully extracted BOM from Assembly ({len(bom_data)} items)")

                    if not bom_data and bom_source in ("auto", "spreadsheet"):
                        spreadsheet_name = bom_config.get("spreadsheet_name", "BOM")
                        logger.debug(f"Attempting to extract BOM from Spreadsheet '{spreadsheet_name}'")
                        bom_data = extract_bom_from_spreadsheet(
                            doc, spreadsheet_name=spreadsheet_name, custom_fields=bom_fields
                        )
                        if bom_data:
                            logger.info(f"Successfully extracted BOM from Spreadsheet ({len(bom_data)} items)")

                    if not bom_data and bom_source in ("auto", "parts"):
                        logger.debug("Attempting to extract BOM from Parts")
                        bom_data = extract_bom_from_parts(doc, custom_fields=bom_fields)
                        if bom_data:
                            logger.info(f"Successfully extracted BOM from Parts ({len(bom_data)} items)")

                    if bom_data:
                        # Write BOM CSV via subprocess (lib3mf_utils pattern)
                        os.makedirs(os.path.dirname(bom_output) or ".", exist_ok=True)

                        # For now, write BOM directly (no subprocess needed for CSV)
                        # In future, can use subprocess pattern if we need XML/Excel formats
                        import csv

                        # Determine fields to write
                        csv_fields = ["label", "quantity"]
                        if bom_fields:
                            csv_fields.extend(bom_fields)
                        else:
                            # Infer fields from BOM data
                            seen_fields = set()
                            for item in bom_data:
                                for key in item.keys():
                                    if key not in csv_fields and key not in seen_fields:
                                        csv_fields.append(key)
                                        seen_fields.add(key)

                        with open(bom_output, "w", newline="", encoding="utf-8") as csvfile:
                            writer = csv.DictWriter(csvfile, fieldnames=csv_fields, restval="")
                            writer.writeheader()
                            for item in bom_data:
                                row = {field: item.get(field, "") for field in csv_fields}
                                writer.writerow(row)

                        logger.info(f"Wrote BOM to {bom_output} ({len(bom_data)} items, {len(csv_fields)} fields)")
                    else:
                        logger.warning("No BOM data extracted from document")

                except Exception as e:
                    logger.exception(f"Error generating BOM: {e}")

            FreeCAD.closeDocument(doc_name)
            logger.debug(f"Closed document {doc_name}")
        except Exception as e:
            logger.exception(f"Exception during processing: {e}")
            sys.exit(1)

    logger.info("Export completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(f"Exception in main: {e}")
        sys.exit(1)
else:
    # When run via freecadcmd, __name__ is not '__main__', but we still want to run main()
    try:
        main()
    except Exception as e:
        logger.exception(f"Exception in main: {e}")
        sys.exit(1)
