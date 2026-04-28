#!/usr/bin/env python3
"""
set_export_properties.py - FreeCAD Macro

Set export properties on selected bodies for use with freecad_tools body_source: properties mode.

This macro adds custom properties to selected Part/Body objects:
- ExportTo3MF (App::PropertyBool): Mark body for export
- ExportCount (App::PropertyInteger): Number of copies to export (default: 1)
- ExportRotation (App::PropertyRotation): Orientation for export

These properties are grouped under the 'freecad_tools' category in the Properties panel.

Usage:
    1. Select one or more bodies in the FreeCAD 3D view
    2. Run this macro from Macro menu
    3. Properties dialog will appear for each selected object
    4. Set ExportTo3MF=True to enable exporting that body
    5. Set ExportCount to duplicate the body in export
    6. Set ExportRotation to apply orientation transform

CLI Usage (headless mode):
    python3 set_export_properties.py <document.FCStd> <object_name> [options]

    Options:
        --export / --no-export     Set ExportTo3MF (default: True)
        --count N                  Set ExportCount (default: 1)
        --rotation-axis X Y Z      Set rotation axis (default: 0 0 1)
        --rotation-angle DEG       Set rotation angle in degrees (default: 0)
        --list                     List all objects in document
        --verbose / -v             Verbose output

Examples:
    # Set properties on Body in MyDocument.FCStd
    python3 set_export_properties.py MyDocument.FCStd Body --count 3 --rotation-angle 45

    # Disable export for all objects
    python3 set_export_properties.py MyDocument.FCStd --export false

    # List all objects
    python3 set_export_properties.py MyDocument.FCStd --list
"""

import argparse
import sys


def get_selected_objects():
    """Get currently selected objects from FreeCAD GUI."""
    try:
        import FreeCADGui

        sel = FreeCADGui.Selection.getSelection()
        return sel
    except Exception:
        return []


def add_custom_properties(obj):
    """
    Add custom export properties to a FreeCAD object.

    Properties added:
    - ExportTo3MF (App::PropertyBool): Mark for export
    - ExportCount (App::PropertyInteger): Copy count
    - ExportRotation (App::PropertyRotation): Orientation

    Args:
        obj: FreeCAD object to add properties to
    """
    try:
        import FreeCAD
    except ImportError:
        print("Error: FreeCAD not available")
        return False

    # Check if properties already exist
    props_added = []

    # Add ExportTo3MF property
    if not hasattr(obj, "ExportTo3MF"):
        obj.addProperty("App::PropertyBool", "ExportTo3MF", "freecad_tools", "Mark body for 3MF export")
        obj.ExportTo3MF = True
        props_added.append("ExportTo3MF")

    # Add ExportCount property
    if not hasattr(obj, "ExportCount"):
        obj.addProperty("App::PropertyInteger", "ExportCount", "freecad_tools", "Number of copies to export")
        obj.ExportCount = 1
        props_added.append("ExportCount")

    # Add ExportRotation property
    if not hasattr(obj, "ExportRotation"):
        obj.addProperty("App::PropertyRotation", "ExportRotation", "freecad_tools", "Orientation for export")
        # Set to identity rotation (0 degrees around Z-axis)
        import FreeCAD

        obj.ExportRotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 0)
        props_added.append("ExportRotation")

    return props_added


def set_export_properties_gui():
    """Interactive GUI mode - set properties on selected objects."""
    try:
        import FreeCAD
    except ImportError:
        print("Error: FreeCAD GUI not available. Use CLI mode or run from FreeCAD.")
        return False

    doc = FreeCAD.ActiveDocument
    if doc is None:
        print("Error: No active FreeCAD document. Open or create a document first.")
        return False

    # Get selected objects
    selected = get_selected_objects()
    if not selected:
        print("No objects selected. Please select one or more bodies in the 3D view.")
        return False

    print(f"Setting export properties on {len(selected)} selected object(s):")

    for obj in selected:
        obj_name = obj.Name
        obj_label = obj.Label if hasattr(obj, "Label") else obj_name
        print(f"  Processing: {obj_name} (Label: {obj_label})")

        # Add properties if they don't exist
        props_added = add_custom_properties(obj)
        if props_added:
            print(f"    Added properties: {', '.join(props_added)}")
        else:
            print("    All export properties already exist")

        # Mark for export by default
        obj.ExportTo3MF = True

    print("\nProperties set successfully!")
    print("Open the Properties panel and expand 'freecad_tools' to view/edit settings.")
    return True


def set_properties_cli(doc, obj_name, export=True, count=1, rotation_axis=None, rotation_angle=0, list_objects=False):
    """
    CLI mode - set properties on specified object.

    Args:
        doc: FreeCAD document
        obj_name: Name of object to modify
        export: True/False for ExportTo3MF
        count: ExportCount value
        rotation_axis: [x, y, z] axis for rotation
        rotation_angle: Angle in degrees
        list_objects: If True, just list objects and exit
    """
    try:
        import FreeCAD
    except ImportError:
        print("Error: FreeCAD not available")
        return False

    if list_objects:
        print(f"Objects in document: {doc.Name}")
        for obj in doc.Objects:
            name = obj.Name
            label = obj.Label if hasattr(obj, "Label") else name
            export_flag = getattr(obj, "ExportTo3MF", "not set")
            export_count = getattr(obj, "ExportCount", "not set")
            export_rot = getattr(obj, "ExportRotation", "not set")
            print(f"  {name} (Label: {label})")
            print(f"    ExportTo3MF: {export_flag}")
            print(f"    ExportCount: {export_count}")
            print(f"    ExportRotation: {export_rot}")
        return True

    # Find object by name or label
    obj = doc.getObject(obj_name)
    if obj is None:
        # Try by label
        for candidate in doc.Objects:
            if hasattr(candidate, "Label") and candidate.Label == obj_name:
                obj = candidate
                break

    if obj is None:
        print(f"Error: Object '{obj_name}' not found in document")
        return False

    obj_name_actual = obj.Name
    print(f"Setting properties on: {obj_name_actual}")

    # Add properties if needed
    add_custom_properties(obj)

    # Set values
    obj.ExportTo3MF = export
    obj.ExportCount = count

    # Set rotation
    if rotation_axis is not None:
        import FreeCAD

        axis_vec = FreeCAD.Vector(rotation_axis[0], rotation_axis[1], rotation_axis[2])
        obj.ExportRotation = FreeCAD.Rotation(axis_vec, rotation_angle)

    print(f"  ExportTo3MF = {obj.ExportTo3MF}")
    print(f"  ExportCount = {obj.ExportCount}")
    print(f"  ExportRotation = axis:{list(obj.ExportRotation.Axis)} angle:{obj.ExportRotation.Angle}°")

    return True


def main():
    """Main entry point."""
    # Check if running in CLI mode (with arguments) or GUI mode (no arguments)
    if len(sys.argv) > 1:
        # CLI mode
        parser = argparse.ArgumentParser(description="Set export properties on FreeCAD objects for freecad_tools")
        parser.add_argument("document", nargs="?", help="FreeCAD document file (.FCStd)")
        parser.add_argument("object", nargs="?", help="Object name or label to modify")
        parser.add_argument("--export", action="store_true", default=None, help="Enable export (default)")
        parser.add_argument("--no-export", action="store_true", help="Disable export")
        parser.add_argument("--count", type=int, default=1, help="Number of copies (default: 1)")
        parser.add_argument(
            "--rotation-axis", type=float, nargs=3, default=None, metavar=("X", "Y", "Z"), help="Rotation axis vector"
        )
        parser.add_argument("--rotation-angle", type=float, default=0, help="Rotation angle in degrees (default: 0)")
        parser.add_argument("--list", "-l", action="store_true", help="List all objects in document")
        parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

        args = parser.parse_args()

        # Determine export flag
        export = True
        if args.no_export:
            export = False
        elif args.export is None and not args.no_export:
            export = True

        if args.verbose:
            print(f"Settings: export={export}, count={args.count}, rotation_angle={args.rotation_angle}")
            if args.rotation_axis:
                print(f"  rotation_axis={args.rotation_axis}")

        # Open document
        try:
            import FreeCAD
        except ImportError as e:
            print(
                "Error: Cannot import FreeCAD. Make sure FreeCAD is installed and this script runs in a FreeCAD context."
            )
            print(f"  Original error: {e}")
            print("\nFor headless usage, run via:")
            print(
                "  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd macros/set_export_properties.py <document> <object>"
            )
            sys.exit(1)

        if args.document:
            # Open specified document
            doc = FreeCAD.open(args.document)
            if doc is None:
                print(f"Error: Could not open document {args.document}")
                sys.exit(1)
        else:
            doc = FreeCAD.ActiveDocument
            if doc is None:
                print("Error: No document specified and no active document")
                sys.exit(1)

        # Process object
        if args.list:
            success = set_properties_cli(doc, None, list_objects=True)
            sys.exit(0 if success else 1)

        if args.object is None:
            print("Error: Must specify object name or use --list")
            print("Run with --help for usage information")
            sys.exit(1)

        success = set_properties_cli(
            doc,
            args.object,
            export=export,
            count=args.count,
            rotation_axis=args.rotation_axis,
            rotation_angle=args.rotation_angle,
        )
        sys.exit(0 if success else 1)

    else:
        # GUI mode - run interactively
        try:
            import FreeCAD

            success = set_export_properties_gui()
            sys.exit(0 if success else 1)
        except ImportError:
            print("FreeCAD not available or not running in GUI mode")
            print("For CLI usage run with arguments, or run from FreeCAD Macro menu")
            sys.exit(1)


if __name__ == "__main__":
    main()
