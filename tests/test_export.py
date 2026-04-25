#!/usr/bin/env python3
import sys

print("=== TEST SCRIPT ===", file=sys.stderr)

try:
    import FreeCAD

    print("FreeCAD imported successfully", file=sys.stderr)

    doc = FreeCAD.open("Moxon_OE1EBG.FCStd")
    print(f"Opened document: {doc.Name}", file=sys.stderr)

    objects = [obj.Name for obj in doc.Objects]
    print(f"Number of objects: {len(objects)}", file=sys.stderr)
    print(f"First 10 objects: {objects[:10]}", file=sys.stderr)

    # Check for specific objects
    target_objects = ["Body001", "Assembly"]
    for obj_name in target_objects:
        obj = doc.getObject(obj_name)
        if obj:
            print(f"Found object '{obj_name}'", file=sys.stderr)
            if hasattr(obj, "Shape"):
                print(f"  Object has Shape: {obj.Shape is not None}", file=sys.stderr)
            else:
                print("  Object does not have Shape attribute", file=sys.stderr)
        else:
            print(f"Object '{obj_name}' NOT FOUND", file=sys.stderr)

    FreeCAD.closeDocument(doc.Name)
    print("Document closed", file=sys.stderr)

except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("=== TEST COMPLETE ===", file=sys.stderr)
