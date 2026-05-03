#!/usr/bin/env python3
"""Run TechDraw and screenshot GUI tasks in one FreeCAD launch."""

import json
import os
import sys
import time

VIEW_ORIENTATIONS = {
    "isometric": "viewAxonometric",
    "front": "viewFront",
    "top": "viewTop",
    "right": "viewRight",
    "back": "viewBack",
    "bottom": "viewBottom",
    "left": "viewLeft",
}


def _safe_name(value):
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in value)


def _resolve_bodies(doc, body_specs):
    resolved = []
    for body_spec in body_specs:
        obj = doc.getObject(body_spec)
        if obj:
            resolved.append(obj)
            continue
        for obj in doc.Objects:
            if hasattr(obj, "Label") and obj.Label == body_spec:
                resolved.append(obj)
                break
    return resolved


def _ensure_view(_freecad_gui, gui_doc):
    if hasattr(gui_doc, "activeView"):
        view = gui_doc.activeView()
        if view and hasattr(view, "saveImage"):
            return view
    if hasattr(gui_doc, "ActiveView") and gui_doc.ActiveView:
        view = gui_doc.ActiveView
        if hasattr(view, "saveImage"):
            return view
        if hasattr(view, "View") and view.View and hasattr(view.View, "saveImage"):
            return view.View
    return None


def main():
    config_path = None
    for arg in sys.argv[1:]:
        if arg.endswith(".json") and os.path.exists(arg):
            config_path = arg
            break

    if not config_path:
        print(json.dumps({"success": False, "error": "No config JSON provided"}))
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    result_file = cfg["result_file"]
    result = {
        "success": False,
        "techdraw": {"success": True, "pages": [], "error": None},
        "screenshots": {"success": True, "images": [], "error": None, "skipped": True},
        "artifacts": {"pdf_pages": [], "images": []},
        "timing": {"total_seconds": 0.0, "techdraw_seconds": 0.0, "screenshots_seconds": 0.0},
        "error": None,
    }
    start_time = time.time()

    try:
        import FreeCAD  # pylint: disable=import-error
        import FreeCADGui  # pylint: disable=import-error
        import TechDrawGui  # pylint: disable=import-error

        source = cfg["source"]
        doc = FreeCAD.open(source)
        FreeCAD.setActiveDocument(doc.Name)
        if hasattr(FreeCADGui, "activateDocument"):
            FreeCADGui.activateDocument(doc.Name)

        run_techdraw = bool(cfg.get("run_techdraw"))
        run_screenshots = bool(cfg.get("run_screenshots"))

        if run_techdraw:
            techdraw_start = time.time()
            td = cfg.get("techdraw", {})
            pages_filter = td.get("pages")
            output_dir = td.get("output_dir")
            os.makedirs(output_dir, exist_ok=True)
            td_pages = [obj for obj in doc.Objects if getattr(obj, "TypeId", "") == "TechDraw::DrawPage"]
            if pages_filter:
                filtered = []
                for spec in pages_filter:
                    for page in td_pages:
                        if page.Name == spec or (hasattr(page, "Label") and page.Label == spec):
                            filtered.append(page)
                            break
                td_pages = filtered

            for page in td_pages:
                name = page.Name
                pdf_path = os.path.join(output_dir, f"{name}.pdf")
                try:
                    TechDrawGui.exportPageAsPdf(page, pdf_path)
                    if os.path.exists(pdf_path):
                        result["techdraw"]["pages"].append({"name": name, "pdf_path": pdf_path})
                        result["artifacts"]["pdf_pages"].append(pdf_path)
                    else:
                        result["techdraw"]["pages"].append(
                            {"name": name, "pdf_path": None, "error": "No file produced"}
                        )
                except Exception as e:
                    result["techdraw"]["pages"].append({"name": name, "pdf_path": None, "error": str(e)})

            result["techdraw"]["success"] = bool(result["techdraw"]["pages"]) and all(
                p.get("pdf_path") for p in result["techdraw"]["pages"]
            )
            result["timing"]["techdraw_seconds"] = round(time.time() - techdraw_start, 3)

        if run_screenshots:
            screenshots_start = time.time()
            sc = cfg.get("screenshots", {})
            output_dir = sc.get("output_dir")
            os.makedirs(output_dir, exist_ok=True)
            views = sc.get("views", ["isometric"])
            resolution = sc.get("resolution", [1920, 1080])
            fmt = sc.get("format", "png")
            composite = sc.get("composite", True)
            body_specs = sc.get("bodies", [])

            gui_doc = None
            if hasattr(FreeCADGui, "getDocument"):
                gui_doc = FreeCADGui.getDocument(doc.Name)
            if not gui_doc and hasattr(FreeCADGui, "activeDocument"):
                gui_doc = FreeCADGui.activeDocument()

            view = _ensure_view(FreeCADGui, gui_doc) if gui_doc else None
            if not view:
                result["screenshots"] = {
                    "success": False,
                    "images": [],
                    "error": "Cannot access GUI view",
                    "skipped": False,
                }
            else:
                all_objects = doc.Objects
                targets = _resolve_bodies(doc, body_specs)
                if not targets:
                    result["screenshots"] = {
                        "success": False,
                        "images": [],
                        "error": "No target bodies found",
                        "skipped": False,
                    }
                else:
                    result["screenshots"]["skipped"] = False
                    for obj in all_objects:
                        try:
                            if hasattr(obj, "ViewObject") and obj.ViewObject is not None:
                                obj.ViewObject.Visibility = composite and (obj in targets)
                        except Exception:
                            pass

                    image_rows = []
                    if composite:
                        base_name = "_and_".join(_safe_name(getattr(obj, "Label", "") or obj.Name) for obj in targets)
                        for view_name in views:
                            method = getattr(view, VIEW_ORIENTATIONS.get(view_name, ""), None)
                            if method:
                                method()
                            FreeCADGui.SendMsgToActiveView("ViewFit")
                            filename = f"{base_name}_{view_name}.{fmt}"
                            filepath = os.path.join(output_dir, filename)
                            alpha_arg = "true" if fmt.lower() == "png" else "false"
                            view.saveImage(filepath, resolution[0], resolution[1], alpha_arg)
                            image_rows.append({"body": base_name, "view": view_name, "path": filepath})
                    else:
                        for body in targets:
                            for obj in all_objects:
                                try:
                                    if hasattr(obj, "ViewObject") and obj.ViewObject is not None:
                                        obj.ViewObject.Visibility = obj == body
                                except Exception:
                                    pass
                            body_name = _safe_name(getattr(body, "Label", "") or body.Name)
                            for view_name in views:
                                method = getattr(view, VIEW_ORIENTATIONS.get(view_name, ""), None)
                                if method:
                                    method()
                                FreeCADGui.SendMsgToActiveView("ViewFit")
                                filename = f"{body_name}_{view_name}.{fmt}"
                                filepath = os.path.join(output_dir, filename)
                                alpha_arg = "true" if fmt.lower() == "png" else "false"
                                view.saveImage(filepath, resolution[0], resolution[1], alpha_arg)
                                image_rows.append({"body": body_name, "view": view_name, "path": filepath})

                    existing_images = [
                        row["path"] for row in image_rows if row.get("path") and os.path.exists(row["path"])
                    ]
                    result["screenshots"]["images"] = image_rows
                    result["artifacts"]["images"] = existing_images
                    result["screenshots"]["success"] = bool(existing_images)
            result["timing"]["screenshots_seconds"] = round(time.time() - screenshots_start, 3)

        result["success"] = bool(result["techdraw"]["success"] and result["screenshots"]["success"])
        FreeCAD.closeDocument(doc.Name)

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    with open(result_file, "w", encoding="utf-8") as f:
        result["timing"]["total_seconds"] = round(time.time() - start_time, 3)
        json.dump(result, f, indent=2)

    sys.exit(0 if result.get("success") else 1)


main()
