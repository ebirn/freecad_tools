#!/usr/bin/env python3
"""Run multiple GUI export jobs in a single FreeCAD session."""

import json
import os
import sys

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


def _ensure_view(gui_doc):
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
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    result_file = cfg["result_file"]
    jobs = cfg.get("jobs", [])
    out = {"success": True, "results": {}}

    try:
        import FreeCAD  # pylint: disable=import-error
        import FreeCADGui  # pylint: disable=import-error
        import TechDrawGui  # pylint: disable=import-error

        for job in jobs:
            name = job.get("name", "unnamed")
            source = job["source"]
            doc = FreeCAD.open(source)
            FreeCAD.setActiveDocument(doc.Name)
            if hasattr(FreeCADGui, "activateDocument"):
                FreeCADGui.activateDocument(doc.Name)

            job_result = {
                "screenshots": {"success": True, "images": [], "error": None, "skipped": True},
                "techdraw": {"success": True, "pages": [], "error": None},
            }

            # TechDraw pages to PDFs
            td = job.get("techdraw") or {}
            if td.get("enabled"):
                temp_dir = td["temp_dir"]
                os.makedirs(temp_dir, exist_ok=True)
                pages_filter = td.get("pages") or []
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
                    pdf_path = os.path.join(temp_dir, f"{page.Name}.pdf")
                    try:
                        TechDrawGui.exportPageAsPdf(page, pdf_path)
                        job_result["techdraw"]["pages"].append({"name": page.Name, "pdf_path": pdf_path})
                    except Exception as e:
                        job_result["techdraw"]["pages"].append({"name": page.Name, "pdf_path": None, "error": str(e)})
                job_result["techdraw"]["success"] = all(p.get("pdf_path") for p in job_result["techdraw"]["pages"])

            # Screenshots
            sc = job.get("screenshots") or {}
            if sc.get("enabled"):
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

                view = _ensure_view(gui_doc) if gui_doc else None
                if not view:
                    job_result["screenshots"] = {
                        "success": False,
                        "images": [],
                        "error": "Cannot access GUI view",
                        "skipped": False,
                    }
                else:
                    all_objects = doc.Objects
                    targets = _resolve_bodies(doc, body_specs)
                    if not targets:
                        job_result["screenshots"] = {
                            "success": False,
                            "images": [],
                            "error": "No target bodies found",
                            "skipped": False,
                        }
                    else:
                        job_result["screenshots"]["skipped"] = False
                        for obj in all_objects:
                            try:
                                if hasattr(obj, "ViewObject") and obj.ViewObject is not None:
                                    obj.ViewObject.Visibility = composite and (obj in targets)
                            except Exception:
                                pass

                        images = []
                        if composite:
                            base_name = "_and_".join(
                                _safe_name(getattr(obj, "Label", "") or obj.Name) for obj in targets
                            )
                            for view_name in views:
                                method = getattr(view, VIEW_ORIENTATIONS.get(view_name, ""), None)
                                if method:
                                    method()
                                FreeCADGui.SendMsgToActiveView("ViewFit")
                                filename = f"{base_name}_{view_name}.{fmt}"
                                filepath = os.path.join(output_dir, filename)
                                alpha_arg = "true" if fmt.lower() == "png" else "false"
                                view.saveImage(filepath, resolution[0], resolution[1], alpha_arg)
                                images.append({"body": base_name, "view": view_name, "path": filepath})
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
                                    images.append({"body": body_name, "view": view_name, "path": filepath})

                        job_result["screenshots"]["images"] = images
                        job_result["screenshots"]["success"] = True

            FreeCAD.closeDocument(doc.Name)
            out["results"][name] = job_result

    except Exception as e:
        out["success"] = False
        out["error"] = str(e)

    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    sys.exit(0 if out.get("success") else 1)


main()
