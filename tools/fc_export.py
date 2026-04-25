#!/usr/bin/env python3
import json
import logging
import os
import subprocess
import sys
import tempfile

import yaml

# Configure logging to both console and file
log_file = "fc_export.log"
logging.basicConfig(
    level=logging.INFO,
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

# Check if CONFIG_FILE was passed via environment variable from parent process
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

        # Pass CONFIG_FILE to subprocess via environment variable
        env = os.environ.copy()
        if CONFIG_FILE:
            env["FREECAD_TOOLS_CONFIG"] = CONFIG_FILE
            logger.debug(f"Passing CONFIG_FILE via environment: {CONFIG_FILE}")

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


def load_config():
    global CONFIG_FILE

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

    # Get the directory where the config file is located for path resolution
    config_dir = os.path.dirname(os.path.abspath(CONFIG_FILE))
    logger.debug(f"Config directory: {config_dir}")

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

    # Resolve relative paths in config items relative to config file directory
    for item in result:
        # Resolve source path
        if "source" in item and item["source"]:
            source = item["source"]
            if not os.path.isabs(source):
                item["source"] = os.path.join(config_dir, source)
                logger.debug(f"Resolved source to: {item['source']}")

        # Resolve output path
        if "output" in item and item["output"]:
            output = item["output"]
            if not os.path.isabs(output):
                item["output"] = os.path.join(config_dir, output)
                logger.debug(f"Resolved output to: {item['output']}")

        # Resolve template path
        if "template" in item and item["template"]:
            template = item["template"]
            if not os.path.isabs(template):
                item["template"] = os.path.join(config_dir, template)
                logger.debug(f"Resolved template to: {item['template']}")

        # Resolve stl_output_dir path
        if "stl_output_dir" in item and item["stl_output_dir"]:
            stl_dir = item["stl_output_dir"]
            if not os.path.isabs(stl_dir):
                item["stl_output_dir"] = os.path.join(config_dir, stl_dir)
                logger.debug(f"Resolved stl_output_dir to: {item['stl_output_dir']}")

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
    doc, bodies, output_path, template_path=None, keep_stl=False, stl_output_dir=None, export_name=""
):
    """
    Export bodies to 3MF format using lib3mf (via subprocess).
    Optionally uses a template 3MF file for metadata/settings preservation.

    Args:
        doc: FreeCAD document
        bodies: List of body identifiers (Name or Label) to export
        output_path: Output 3MF file path
        template_path: Optional path to a template 3MF file
        keep_stl: If True, keep generated STL files in stl_output_dir
        stl_output_dir: Directory to place STL files (defaults to temp if keep_stl=False)
        export_name: Export item name (used to prefix STL files)
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
        # Export bodies to STL files
        stl_files = []
        body_count = {}  # Track duplicate body exports

        for body_id in bodies:
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
            except Exception as e:
                logger.error(f"Failed to create STL for '{obj_name}': {e}")

        if not stl_files:
            logger.error("No valid bodies to export to 3MF")
            return False

        # Call lib3mf via subprocess to create 3MF
        logger.info(f"Creating 3MF with {len(stl_files)} embedded meshes via lib3mf")

        # Build config for lib3mf subprocess
        lib3mf_config = {
            "output_path": output_path,
            "stl_files": [{"label": label, "path": path} for label, path in stl_files],
        }

        if template_path and os.path.exists(template_path):
            lib3mf_config["template_path"] = template_path

        # Write config to temp JSON file
        config_file = os.path.join(stl_dir, "_lib3mf_config.json")
        with open(config_file, "w") as f:
            json.dump(lib3mf_config, f)

        # Call lib3mf_utils.py via subprocess using the current Python interpreter
        # (when run via pre-commit hook, use the hook's Python; otherwise use venv Python if available)
        script_dir = os.path.dirname(__file__)
        lib3mf_script = os.path.join(script_dir, "lib3mf_utils.py")

        # Try to use venv Python first, fall back to sys.executable
        venv_python = os.path.join(os.path.dirname(script_dir), ".venv", "bin", "python3")
        python_executable = venv_python if os.path.exists(venv_python) else sys.executable

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

        logger.info(f"Successfully created 3MF: {output_path}")
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


def main():
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

        logger.debug(
            f"Item {i}: name={export_name}, source={source}, output={output}, bodies={bodies}, "
            f"template={template}, keep_stl={keep_stl}, stl_output_dir={stl_output_dir}"
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

                # Use template-based export if template is available
                if resolved_template:
                    success = export_bodies_to_3mf_with_template(
                        doc, bodies, output, resolved_template, keep_stl, stl_output_dir, export_name
                    )
                else:
                    # Fallback to STL export if no template available
                    success = export_bodies(doc, bodies, output)
            else:
                logger.info("Exporting full document")
                success = export_full_doc(doc, output)

            logger.debug(f"Export success: {success}")
            FreeCAD.closeDocument(doc_name)
            logger.debug(f"Closed document {doc_name}")
            if not success:
                sys.exit(1)
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
