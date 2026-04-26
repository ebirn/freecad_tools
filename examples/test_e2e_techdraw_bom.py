#!/usr/bin/env python3
"""End-to-end test for TechDraw and BOM export with example_techdraw.FCStd"""

import os
import shutil
import sys
from pathlib import Path


def test_techdraw_bom_export():
    """Test TechDraw and BOM export using the example document."""
    examples_dir = Path(__file__).parent
    tools_dir = examples_dir.parent / "tools"
    test_output = examples_dir / "test_output"

    # Clean up any previous test output
    if test_output.exists():
        shutil.rmtree(test_output)
    test_output.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("End-to-End Test: TechDraw and BOM Export")
    print("=" * 60)

    # Create .freecad_tools directory with config
    fc_tools_dir = examples_dir / ".freecad_tools"
    fc_tools_dir.mkdir(exist_ok=True)

    config_file = fc_tools_dir / "export.yml"
    config_file.write_text("""
export:
  - name: techdraw_assembly_test
    source: example_techdraw.FCStd
    bodies:
      - Body
      - Body001
      - Box

    output: test_output/assembly_test.3mf

    techdraw:
      pages: []
      output_dir: test_output/drawings
      format: svg

    bom:
      source: assembly
      output: test_output/bom.csv
      fields:
        - material
""")

    print(f"\n✓ Config file created: {config_file}")
    print(f"✓ Output directory: {test_output}")

    # Change to examples directory and run export
    original_cwd = os.getcwd()
    try:
        os.chdir(examples_dir)
        print(f"\nRunning export from: {examples_dir}")
        print("Document: example_techdraw.FCStd")

        # Run the export via subprocess
        export_script = tools_dir / "export.py"
        result = os.system(f"python3 {export_script}")

        if result == 0:
            print("\n✓ Export script completed successfully")

            # Check output files
            files_to_check = [
                ("3MF file", test_output / "assembly_test.3mf"),
                ("BOM CSV", test_output / "bom.csv"),
            ]

            all_good = True
            for name, filepath in files_to_check:
                if filepath.exists():
                    size = filepath.stat().st_size
                    print(f"✓ {name}: {filepath.name} ({size} bytes)")
                else:
                    print(f"✗ {name} NOT FOUND: {filepath}")
                    all_good = False

            # Check TechDraw SVG files
            drawings_dir = test_output / "drawings"
            if drawings_dir.exists():
                svg_files = list(drawings_dir.glob("*.svg"))
                if svg_files:
                    print(f"✓ TechDraw SVGs: {len(svg_files)} page(s)")
                    for svg in svg_files:
                        print(f"  - {svg.name}")
                else:
                    print("✗ No SVG files found in drawings directory")
                    all_good = False
            else:
                print("✗ Drawings directory not created")
                all_good = False

            # Show BOM content if it exists
            bom_file = test_output / "bom.csv"
            if bom_file.exists():
                print(f"\nBOM Content ({bom_file.name}):")
                with open(bom_file) as f:
                    content = f.read()
                    for line in content.split("\n")[:10]:  # Show first 10 lines
                        if line:
                            print(f"  {line}")

            print("\n" + "=" * 60)
            if all_good:
                print("✓ End-to-end test PASSED")
                return True
            else:
                print("✗ Some files missing, but export completed")
                return False

        else:
            print(f"\n✗ Export script failed with code {result}")
            # Check log file
            log_file = examples_dir / "fc_export.log"
            if log_file.exists():
                print(f"\nLog file ({log_file}):")
                with open(log_file) as f:
                    lines = f.readlines()[-20:]  # Last 20 lines
                    for line in lines:
                        print(f"  {line.rstrip()}")
            return False

    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    success = test_techdraw_bom_export()
    sys.exit(0 if success else 1)
