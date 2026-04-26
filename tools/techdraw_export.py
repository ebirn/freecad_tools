#!/usr/bin/env python3
"""
TechDraw page exporter — runs inside FreeCAD GUI binary.

Exports TechDraw pages from a FreeCAD document as individual PDF files
using TechDrawGui.exportPageAsPdf() for pixel-perfect output.

Usage:
    FreeCAD techdraw_export.py <config.json>

Config JSON format:
    {
        "source": "/path/to/document.FCStd",
        "pages": ["Page", "Page001"],      // optional, null = all pages
        "output_dir": "/path/to/temp_dir",
        "result_file": "/path/to/result.json"
    }

Result JSON format:
    {
        "success": true,
        "pages": [
            {"name": "Page", "label": "...", "pdf_path": "/path/to/Page.pdf",
             "width": 297.0, "height": 210.0},
            ...
        ],
        "error": null
    }

NOTE: Requires FreeCAD GUI binary (not freecadcmd).
      TechDrawGui module is only available in the GUI environment.
      As of FreeCAD 1.1, there is no offline/headless API for pixel-perfect
      TechDraw PDF export. Check future FreeCAD releases for improvements.
"""

import json
import os
import sys


def main():
    """Export TechDraw pages as individual PDFs."""
    # Find config file from command-line args
    config_path = None
    for arg in sys.argv[1:]:
        if arg.endswith(".json") and os.path.exists(arg):
            config_path = arg
            break

    if not config_path:
        print(json.dumps({"success": False, "pages": [], "error": "No config JSON provided"}))
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    source = config["source"]
    pages_filter = config.get("pages")  # None = all pages
    output_dir = config["output_dir"]
    result_file = config["result_file"]

    result = {"success": False, "pages": [], "error": None}

    try:
        import FreeCAD
        import TechDrawGui

        try:
            from PySide6 import QtCore
        except ImportError:
            from PySide2 import QtCore

        doc = FreeCAD.open(source)

        # Recompute to ensure all views (geometry, dimensions, balloons) are up-to-date
        doc.recompute()

        # Wait for TechDraw's hidden-line-removal threads to finish.
        # doc.recompute() triggers HLR in background threads; exportPageAsPdf
        # will produce blank geometry if called before those threads complete.
        # See: https://github.com/FreeCAD/FreeCAD/issues/19603
        loop = QtCore.QEventLoop()
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(3000)  # 3 second delay for HLR completion
        loop.exec_()

        # Find TechDraw pages
        td_pages = [obj for obj in doc.Objects if obj.TypeId == "TechDraw::DrawPage"]

        if pages_filter:
            filtered = []
            for spec in pages_filter:
                for page in td_pages:
                    if page.Name == spec or (hasattr(page, "Label") and page.Label == spec):
                        filtered.append(page)
                        break
            td_pages = filtered

        os.makedirs(output_dir, exist_ok=True)

        for page in td_pages:
            name = page.Name
            label = page.Label if hasattr(page, "Label") else name
            pdf_path = os.path.join(output_dir, f"{name}.pdf")

            try:
                TechDrawGui.exportPageAsPdf(page, pdf_path)
                if os.path.exists(pdf_path):
                    result["pages"].append(
                        {
                            "name": name,
                            "label": label,
                            "pdf_path": pdf_path,
                            "width": page.PageWidth,
                            "height": page.PageHeight,
                        }
                    )
                else:
                    result["pages"].append(
                        {
                            "name": name,
                            "label": label,
                            "pdf_path": None,
                            "error": "Export produced no file",
                        }
                    )
            except Exception as e:
                result["pages"].append(
                    {
                        "name": name,
                        "label": label,
                        "pdf_path": None,
                        "error": str(e),
                    }
                )

        FreeCAD.closeDocument(doc.Name)
        result["success"] = len(result["pages"]) > 0 and all(p.get("pdf_path") for p in result["pages"])

    except ImportError as e:
        result["error"] = f"Import error (need FreeCAD GUI binary, not freecadcmd): {e}"
    except Exception as e:
        result["error"] = str(e)

    # Write result
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    sys.exit(0 if result["success"] else 1)


# FreeCAD runs scripts at import time, not via __main__
main()
