#!/usr/bin/env python3
"""
body_screenshot.py - Screenshot generation for FreeCAD bodies.

Runs inside FreeCAD GUI binary to capture publication-ready screenshots
of bodies for Thingiverse, Printables.com, and similar platforms.

Usage:
    FreeCAD body_screenshot.py <config.json>

Config JSON format:
    {
        "source": "/path/to/document.FCStd",
        "bodies": ["Body1", "Body2"],
        "output_dir": "/path/to/output/",
        "result_file": "/path/to/result.json",
        "views": ["isometric", "front", "top"],
        "resolution": [1920, 1080],
        "background": [255, 255, 255, 255],
        "format": "png",
        "composite": true
    }

Result JSON written to result_file:
    {
        "success": true,
        "images": [
            {"body": "Body1", "view": "isometric", "path": "/output/Body1_isometric.png"},
            ...
        ],
        "error": null
    }
"""

import json
import os
import sys
import threading

try:
    import yaml
except Exception:  # pragma: no cover
    # PyYAML is expected to be available in FreeCAD's Python in our environment,
    # but keep an explicit error message if it isn't.
    yaml = None

# Default screenshot configuration
DEFAULT_SCREENSHOT_CONFIG = {
    "enabled": False,
    "output_dir": "prints/images/",
    "views": ["isometric"],
    "resolution": [1920, 1080],
    "background": [255, 255, 255, 255],
    "format": "png",
    "composite": True,
}

# Valid view names and their corresponding FreeCAD view methods
VIEW_ORIENTATIONS = {
    "isometric": "viewAxonometric",
    "front": "viewFront",
    "top": "viewTop",
    "right": "viewRight",
    "back": "viewBack",
    "bottom": "viewBottom",
    "left": "viewLeft",
}

VALID_VIEWS = set(VIEW_ORIENTATIONS.keys())
VALID_FORMATS = {"png", "jpg"}


def get_screenshot_config(export_item):
    """
    Extract screenshot configuration from an export item and merge with defaults.

    Args:
        export_item: Dictionary containing export configuration, may have
                    'screenshots' key with boolean or dict value

    Returns:
        Dictionary with merged screenshot configuration
    """
    raw = export_item.get("screenshots", {})

    if isinstance(raw, bool):
        return {**DEFAULT_SCREENSHOT_CONFIG, "enabled": raw}
    elif isinstance(raw, dict):
        return {**DEFAULT_SCREENSHOT_CONFIG, **raw}
    else:
        return {**DEFAULT_SCREENSHOT_CONFIG, "enabled": False}


def validate_screenshot_config(config):
    """
    Validate screenshot configuration dictionary.

    Args:
        config: Dictionary with screenshot configuration

    Raises:
        ValueError: If any configuration value is invalid
    """
    if "views" in config:
        views = config["views"]
        if not isinstance(views, list):
            raise ValueError("Views must be a list")
        for view in views:
            if view not in VALID_VIEWS:
                raise ValueError(f"Invalid view '{view}'. Valid views: {sorted(VALID_VIEWS)}")

    if "resolution" in config:
        res = config["resolution"]
        if not isinstance(res, list) or len(res) != 2:
            raise ValueError("Resolution must be a list of exactly 2 integers [width, height]")
        if not all(isinstance(x, int) and x > 0 for x in res):
            raise ValueError("Resolution values must be positive integers")

    if "background" in config:
        bg = config["background"]
        if not isinstance(bg, list) or len(bg) != 4:
            raise ValueError("Background must be RGBA list of 4 integers [R, G, B, A]")
        if not all(isinstance(x, int) and 0 <= x <= 255 for x in bg):
            raise ValueError("Background values must be integers 0-255")

    if "format" in config:
        fmt = config["format"].lower()
        if fmt not in VALID_FORMATS:
            raise ValueError(f"Format must be one of {VALID_FORMATS}, got '{fmt}'")


def build_screenshot_config(export_item, screenshot_cfg):
    """
    Build a complete screenshot configuration from export item and parsed config.

    Args:
        export_item: The export configuration dictionary
        screenshot_cfg: The parsed screenshot configuration

    Returns:
        Dictionary with all fields needed for screenshot generation
    """
    result = {}
    result["source"] = export_item.get("source", "")
    result["bodies"] = export_item.get("bodies", [])
    result["output_dir"] = os.path.abspath(screenshot_cfg.get("output_dir", "prints/images/"))
    result["views"] = screenshot_cfg.get("views", DEFAULT_SCREENSHOT_CONFIG["views"])
    result["resolution"] = screenshot_cfg.get("resolution", DEFAULT_SCREENSHOT_CONFIG["resolution"])
    result["background"] = screenshot_cfg.get("background", DEFAULT_SCREENSHOT_CONFIG["background"])
    result["format"] = screenshot_cfg.get("format", DEFAULT_SCREENSHOT_CONFIG["format"])
    result["composite"] = screenshot_cfg.get("composite", DEFAULT_SCREENSHOT_CONFIG["composite"])
    return result


def main():
    """
    Main entry point for screenshot generation.

    Runs inside FreeCAD GUI binary, captures screenshots of specified bodies
    from specified view angles.

    Config can be:
    1. Loaded from the project YAML export config (preferred):
       - FREECAD_TOOLS_CONFIG: path to export.yml/export_config.yml
       - FREECAD_TOOLS_PROJECT_ROOT: base dir for relative paths
       - FREECAD_TOOLS_NAME: export item name to select
       - FREECAD_TOOLS_SCREENSHOT_RESULT: optional path for result JSON
    2. Passed as JSON file via first command-line argument
    3. Found at __screenshot_config in current directory (legacy fallback)
    """
    config = None
    result_file_env = os.environ.get("FREECAD_TOOLS_SCREENSHOT_RESULT")

    # If something deadlocks inside FreeCAD/Qt, kill the process so the caller doesn't hang forever.
    # We write a result file first if we can.
    _current_step = {"name": "startup"}

    def _watchdog_fire() -> None:  # pragma: no cover
        payload = {
            "success": False,
            "images": [],
            "error": f"Timeout/hang in screenshot subprocess (step={_current_step['name']})",
        }
        if result_file_env:
            try:
                os.makedirs(os.path.dirname(result_file_env), exist_ok=True)
                with open(result_file_env, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            except Exception:
                pass
        # Hard-exit: FreeCAD GUI can keep threads/event loop alive.
        os._exit(124)  # noqa: S606

    watchdog_seconds = int(os.environ.get("FREECAD_TOOLS_SCREENSHOT_WATCHDOG_SECONDS", "180"))
    watchdog = threading.Timer(watchdog_seconds, _watchdog_fire)
    watchdog.daemon = True
    watchdog.start()

    def _write_result_and_exit(payload: dict, exit_code: int) -> None:
        """Best-effort result writer for subprocess IPC."""
        if result_file_env:
            try:
                os.makedirs(os.path.dirname(result_file_env), exist_ok=True)
                with open(result_file_env, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            except Exception:
                # If result file can't be written, fall back to stdout.
                pass
        try:
            print(json.dumps(payload))
        except Exception:
            pass
        sys.exit(exit_code)

    # Preferred: load from YAML export config (read directly in the FreeCAD GUI process).
    yaml_path = os.environ.get("FREECAD_TOOLS_CONFIG")
    if yaml_path and os.path.exists(yaml_path):
        try:
            if yaml is None:
                raise ImportError("PyYAML is not available in this FreeCAD Python environment")

            with open(yaml_path, encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f)

            exports = (yaml_config or {}).get("export", [])
            if not isinstance(exports, list):
                raise ValueError("YAML config must have 'export' as a list")

            name_filter = os.environ.get("FREECAD_TOOLS_NAME")
            if name_filter:
                export_item = next(
                    (it for it in exports if isinstance(it, dict) and it.get("name") == name_filter), None
                )
            else:
                # If no name is provided, only accept a single export item to avoid ambiguity.
                export_item = exports[0] if len(exports) == 1 and isinstance(exports[0], dict) else None

            if not export_item:
                raise ValueError(
                    "Unable to select export item. Set FREECAD_TOOLS_NAME to an item 'name' from the YAML config."
                )

            screenshot_cfg = get_screenshot_config(export_item)
            if not screenshot_cfg.get("enabled", False):
                # Treat as successful no-op; write result if a target path exists.
                output_dir = os.path.abspath(screenshot_cfg.get("output_dir", DEFAULT_SCREENSHOT_CONFIG["output_dir"]))
                os.makedirs(output_dir, exist_ok=True)
                result_file = result_file_env or os.path.join(output_dir, "result.json")
                with open(result_file, "w", encoding="utf-8") as f:
                    json.dump({"success": True, "images": [], "error": None, "skipped": True}, f, indent=2)
                sys.exit(0)

            validate_screenshot_config(screenshot_cfg)

            # Resolve paths relative to the project root if provided.
            base_dir = os.environ.get("FREECAD_TOOLS_PROJECT_ROOT")
            if base_dir:
                base_dir = os.path.abspath(base_dir)
            else:
                base_dir = os.path.dirname(os.path.abspath(yaml_path))
                if os.path.basename(base_dir) == ".freecad_tools":
                    base_dir = os.path.dirname(base_dir)

            source = export_item.get("source", "")
            if source and not os.path.isabs(source):
                source = os.path.abspath(os.path.join(base_dir, source))

            output_dir = screenshot_cfg.get("output_dir", DEFAULT_SCREENSHOT_CONFIG["output_dir"])
            if output_dir and not os.path.isabs(output_dir):
                output_dir = os.path.abspath(os.path.join(base_dir, output_dir))
            else:
                output_dir = os.path.abspath(output_dir)

            os.makedirs(output_dir, exist_ok=True)
            result_file = result_file_env or os.path.join(output_dir, "result.json")

            config = {
                "source": source,
                "bodies": export_item.get("bodies", []),
                "output_dir": output_dir,
                "result_file": result_file,
                "views": screenshot_cfg.get("views", DEFAULT_SCREENSHOT_CONFIG["views"]),
                "resolution": screenshot_cfg.get("resolution", DEFAULT_SCREENSHOT_CONFIG["resolution"]),
                "background": screenshot_cfg.get("background", DEFAULT_SCREENSHOT_CONFIG["background"]),
                "format": screenshot_cfg.get("format", DEFAULT_SCREENSHOT_CONFIG["format"]),
                "composite": screenshot_cfg.get("composite", DEFAULT_SCREENSHOT_CONFIG["composite"]),
            }

        except Exception as e:
            # Fall through to legacy config loading below, but preserve a useful error if nothing else works.
            config = {"_yaml_error": str(e)}

    # Legacy: JSON passed on argv or __screenshot_config in cwd.
    if not config or config.get("_yaml_error"):
        json_config = None
        config_path = None
        if len(sys.argv) > 1:
            config_path = sys.argv[1]
        if not config_path or not os.path.exists(config_path):
            config_path = "__screenshot_config"

        if os.path.exists(config_path):
            try:
                with open(config_path, encoding="utf-8") as f:
                    json_config = json.load(f)
            except Exception:
                json_config = None

        if json_config:
            config = json_config
        else:
            error_msg = f"No usable config found. yaml_error={config.get('_yaml_error') if config else None}"
            _write_result_and_exit({"success": False, "images": [], "error": error_msg}, 1)

    # Validate config
    try:
        validate_screenshot_config(config)
    except ValueError as e:
        _write_result_and_exit({"success": False, "images": [], "error": f"Invalid config: {e}"}, 1)

    # Determine output directory and result file path
    output_dir = config.get("output_dir", "prints/images/")
    os.makedirs(output_dir, exist_ok=True)
    result_file = config.get("result_file") or result_file_env or os.path.join(output_dir, "result.json")

    try:
        import FreeCAD
        import FreeCADGui
    except ImportError as e:
        result = {"success": False, "images": [], "error": f"FreeCAD GUI import failed: {e}"}
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f)
        sys.exit(1)

    try:
        # Open the document
        source = config.get("source", "")
        print(f"DEBUG: Attempting to open source: {source}", file=sys.stderr)
        print(f"DEBUG: Source exists: {os.path.exists(source)}", file=sys.stderr)

        if not os.path.exists(source):
            result = {"success": False, "images": [], "error": f"Source file not found: {source}"}
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result, f)
            sys.exit(1)

        _current_step["name"] = "open_document"
        print("DEBUG: Starting FreeCAD open()", file=sys.stderr)
        try:
            sys.stderr.flush()
        except Exception:
            pass

            # Some FreeCAD builds expose FreeCADGui.showMainWindow(), others don't.
            # Avoid nested event loops here (they can deadlock); just pump events briefly.
            try:
                from PySide6 import QtWidgets  # noqa: N812
            except ImportError:  # pragma: no cover
                try:
                    from PySide2 import QtWidgets  # noqa: N812
                except ImportError:
                    QtWidgets = None  # noqa: N806

        def _pump_events(iterations: int = 50) -> None:
            if not QtWidgets:
                return
            app = QtWidgets.QApplication.instance()
            if not app:
                return
            for _ in range(iterations):
                try:
                    app.processEvents()
                except Exception:
                    break

        if hasattr(FreeCADGui, "showMainWindow"):
            try:
                FreeCADGui.showMainWindow()
            except Exception:
                pass

        _pump_events()

        doc = FreeCAD.open(source)

        # recompute() can be expensive and, in some FreeCAD builds, may block indefinitely.
        # For screenshots we usually don't need a full recompute of the model.
        do_recompute = os.environ.get("FREECAD_TOOLS_SCREENSHOT_RECOMPUTE", "false").lower() in ("1", "true", "yes")
        if do_recompute:
            _current_step["name"] = "recompute"
            print("DEBUG: Document opened, starting recompute()", file=sys.stderr)
            try:
                sys.stderr.flush()
            except Exception:
                pass
            try:
                doc.recompute()
            except Exception as e:
                print(f"DEBUG: recompute() failed: {e}", file=sys.stderr)
        else:
            print("DEBUG: Skipping recompute() (FREECAD_TOOLS_SCREENSHOT_RECOMPUTE not enabled)", file=sys.stderr)

        # Set the document as active
        FreeCAD.setActiveDocument(doc.Name)

        # Ensure the GUI layer also considers this document active.
        if hasattr(FreeCADGui, "activateDocument"):
            try:
                FreeCADGui.activateDocument(doc.Name)
            except Exception:
                pass

        _pump_events()

        # Get the GUI document
        gui_doc = None
        if hasattr(FreeCADGui, "getDocument"):
            try:
                gui_doc = FreeCADGui.getDocument(doc.Name)
            except Exception:
                gui_doc = None
        if hasattr(FreeCADGui, "activeDocument"):
            try:
                gui_doc = FreeCADGui.activeDocument()
            except Exception:
                gui_doc = None
        if not gui_doc and hasattr(FreeCADGui, "ActiveDocument"):
            gui_doc = FreeCADGui.ActiveDocument
        if not gui_doc:
            gui_doc = FreeCAD.ActiveDocument
        if not gui_doc and hasattr(doc, "GuiDocument"):
            gui_doc = doc.GuiDocument

        if not gui_doc:
            result = {"success": False, "images": [], "error": "Cannot access GUI document"}
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result, f)
            sys.exit(1)

        # Get the active 3D view.
        # Note: In some automation modes (e.g. FreeCAD GUI binary invoked with -c),
        # the GUI is available but no 3D MDI view exists yet.

        def _get_active_3d_view():
            if hasattr(gui_doc, "activeView"):
                try:
                    v = gui_doc.activeView()
                    if v and hasattr(v, "saveImage"):
                        return v
                except Exception:
                    return None
            if hasattr(gui_doc, "ActiveView") and gui_doc.ActiveView:
                v = gui_doc.ActiveView
                if hasattr(v, "saveImage"):
                    return v
                if hasattr(v, "View") and v.View and hasattr(v.View, "saveImage"):
                    return v.View
            return None

        def _ensure_3d_view() -> None:
            """Best-effort attempt to ensure a 3D view exists.

            FreeCAD GUI scripting is inconsistent across builds.
            We try a few known commands and main window hooks, then re-check activeView().
            """
            if _get_active_3d_view() is not None:
                return

            # Attempt common GUI commands that may open/activate a 3D view.
            cmd_candidates = [
                "Std_NewView",
                "Std_ViewCreate",
                "Std_NewWindow",
                "Std_Refresh",
                "Std_ViewIsometric",
                "Std_ViewFitAll",
            ]
            if hasattr(FreeCADGui, "runCommand"):
                for cmd in cmd_candidates:
                    try:
                        FreeCADGui.runCommand(cmd, 0)
                        _pump_events()
                        if _get_active_3d_view() is not None:
                            return
                    except Exception:
                        continue

            # Try main window based activation.
            if hasattr(FreeCADGui, "getMainWindow"):
                try:
                    mw = FreeCADGui.getMainWindow()
                    try:
                        mw.show()
                    except Exception:
                        pass
                    _pump_events()
                except Exception:
                    pass

        _current_step["name"] = "ensure_3d_view"
        _ensure_3d_view()
        view = _get_active_3d_view()

        # Last resort: try to extract a view from the active MDI child without walking all QObjects.
        if not view and hasattr(FreeCADGui, "getMainWindow"):
            try:
                mw = FreeCADGui.getMainWindow()
                child = mw.activeMdiChild() if hasattr(mw, "activeMdiChild") else None
                if child:
                    for attr in ("View", "getView", "centralWidget", "getCentralWidget"):
                        if hasattr(child, attr):
                            try:
                                v = getattr(child, attr)() if callable(getattr(child, attr)) else getattr(child, attr)
                                if v and hasattr(v, "saveImage"):
                                    view = v
                                    break
                            except Exception:
                                pass
            except Exception:
                pass

        if not view:
            result = {"success": False, "images": [], "error": "Cannot access ActiveView from GUI document"}
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result, f)
            os._exit(1)  # noqa: S606

        # Verify view has saveImage
        if not hasattr(view, "saveImage"):
            print(f"DEBUG: view has no saveImage method! Type: {type(view)}", file=sys.stderr)
            print(f"DEBUG: view methods: {[m for m in dir(view) if not m.startswith('_')]}", file=sys.stderr)
            result = {"success": False, "images": [], "error": f"View has no saveImage method. Type: {type(view)}"}
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result, f)
            sys.exit(1)

        print(f"DEBUG: view.saveImage found: {hasattr(view, 'saveImage')}", file=sys.stderr)

        # Let FreeCAD process pending GUI events without starting nested event loops.
        _pump_events()

        # Get all body objects
        all_objects = doc.Objects
        body_objects = [
            obj
            for obj in all_objects
            if hasattr(obj, "Shape") and obj.Shape and (obj.TypeId.startswith("Part::") or "Body" in obj.Name)
        ]

        # Resolve target bodies
        target_bodies = []
        bodies_config = config.get("bodies", [])
        for body_spec in bodies_config:
            obj = doc.getObject(body_spec)
            if obj:
                target_bodies.append(obj)
                continue
            for obj in all_objects:
                if hasattr(obj, "Label") and obj.Label == body_spec:
                    target_bodies.append(obj)
                    break

        if not target_bodies:
            result = {"success": False, "images": [], "error": "No target bodies found"}
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result, f)
            sys.exit(1)

        views = config.get("views", ["isometric"])
        resolution = config.get("resolution", [1920, 1080])
        fmt = config.get("format", "png")
        composite = config.get("composite", True)

        images = []

        def _set_visible(obj, visible: bool) -> None:
            """Set object visibility in a way the 3D view respects."""
            try:
                if hasattr(obj, "ViewObject") and obj.ViewObject is not None and hasattr(obj.ViewObject, "Visibility"):
                    obj.ViewObject.Visibility = bool(visible)
                    return
            except Exception:
                pass

        def _collect_renderables_for(obj):
            """Return objects that need to be visible for obj to render.

            For PartDesign::Body, the body container alone isn't sufficient if its
            features were previously hidden. Include Tip/Group so the view has
            actual shapes to draw.
            """
            renderables = [obj]
            try:
                if hasattr(obj, "TypeId") and obj.TypeId == "PartDesign::Body":
                    tip = getattr(obj, "Tip", None)
                    if tip:
                        renderables.append(tip)
                    group = getattr(obj, "Group", None)
                    if group:
                        renderables.extend(list(group))
            except Exception:
                pass
            return renderables

        def _refresh_view() -> None:
            if hasattr(view, "fitAll"):
                try:
                    view.fitAll()
                except Exception:
                    pass
            if hasattr(FreeCADGui, "updateGui"):
                try:
                    FreeCADGui.updateGui()
                except Exception:
                    pass
            if hasattr(view, "redraw"):
                try:
                    view.redraw()
                except Exception:
                    pass
            _pump_events(200)

        if composite:
            # Show all target bodies, hide others.
            # Important: if we hide everything (including a PartDesign body's features),
            # making the body container visible again may still render nothing.
            keep = set()
            for body in target_bodies:
                for r in _collect_renderables_for(body):
                    keep.add(r)

            for obj in all_objects:
                _set_visible(obj, obj in keep)
            _refresh_view()

            for view_name in views:
                _current_step["name"] = f"orient_{view_name}"
                view_method = getattr(view, VIEW_ORIENTATIONS[view_name], None)
                if view_method:
                    view_method()
                FreeCADGui.SendMsgToActiveView("ViewFit")
                _refresh_view()

                safe_names = [
                    "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in obj.Label)
                    if hasattr(obj, "Label") and obj.Label
                    else obj.Name
                    for obj in target_bodies
                ]
                name_part = "_and_".join(safe_names) if len(target_bodies) > 1 else safe_names[0]
                filename = f"{name_part}_{view_name}.{fmt}"
                filepath = os.path.join(output_dir, filename)

                alpha = fmt.lower() == "png"
                # Some FreeCAD builds expect the 4th arg as a string (e.g. "true"/"false").
                alpha_arg = "true" if alpha else "false"
                _current_step["name"] = f"saveImage_{view_name}"
                ok = view.saveImage(filepath, resolution[0], resolution[1], alpha_arg)
                print(f"DEBUG: saveImage returned {ok}", file=sys.stderr)
                _refresh_view()
                images.append({"body": name_part, "view": view_name, "path": filepath})
        else:
            for obj in target_bodies:
                for o in all_objects:
                    _set_visible(o, False)
                _set_visible(obj, True)
                _refresh_view()

                for view_name in views:
                    _current_step["name"] = f"orient_{view_name}"
                    view_method = getattr(view, VIEW_ORIENTATIONS[view_name], None)
                    if view_method:
                        view_method()
                    FreeCADGui.SendMsgToActiveView("ViewFit")
                    _refresh_view()

                    name = obj.Label if hasattr(obj, "Label") and obj.Label else obj.Name
                    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
                    filename = f"{safe_name}_{view_name}.{fmt}"
                    filepath = os.path.join(output_dir, filename)

                    alpha = fmt.lower() == "png"
                    alpha_arg = "true" if alpha else "false"
                    _current_step["name"] = f"saveImage_{view_name}"
                    ok = view.saveImage(filepath, resolution[0], resolution[1], alpha_arg)
                    print(f"DEBUG: saveImage returned {ok}", file=sys.stderr)
                    _refresh_view()
                    images.append({"body": safe_name, "view": view_name, "path": filepath})

        result = {"success": True, "images": images, "error": None}

    except Exception as e:
        import traceback

        result = {"success": False, "images": [], "error": f"{e}\n{traceback.format_exc()}"}

    # Save result
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Close document
    if "doc" in locals():
        FreeCAD.closeDocument(doc.Name)

    try:
        watchdog.cancel()
    except Exception:
        pass

    # Exit FreeCAD when invoked as a subprocess for automation.
    # Use os._exit to avoid the GUI keeping the process alive.
    os._exit(0 if result.get("success") else 1)  # noqa: S606


# FreeCAD GUI runs the script at import time, not via __main__
# But prevent main() from running when imported as a module
# Guard: skip if running under pytest or if explicitly guard by fc_export.py
_skip_main = hasattr(sys, "_body_screenshot_skip_main") or "pytest" in sys.modules

if __name__ == "__main__" or not _skip_main:
    main()
