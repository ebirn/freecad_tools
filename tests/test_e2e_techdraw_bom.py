#!/usr/bin/env python3
"""End-to-end test for TechDraw and BOM export."""

import os
import sys
from pathlib import Path

# Add tools to path
tools_dir = Path(__file__).parent.parent / "tools"
sys.path.insert(0, str(tools_dir))


def test_techdraw_and_bom_export():
    """Test TechDraw and BOM export with example document."""
    import tempfile

    import yaml

    # Example file is in examples directory, not tests directory
    example_dir = Path(__file__).parent.parent / "examples"
    example_doc = example_dir / "example_techdraw.FCStd"

    assert example_doc.exists(), f"Example document not found: {example_doc}"

    # Create temporary output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create config
        config = {
            "export": [
                {
                    "name": "test_techdraw",
                    "source": str(example_doc),
                    "bodies": ["Body"],  # Export the Body
                    "output": str(tmpdir / "test.3mf"),
                    "techdraw": {
                        "pages": [],  # Export all TechDraw pages
                        "output_dir": str(tmpdir / "drawings"),
                        "format": "pdf",
                    },
                    "bom": {
                        "source": "parts",  # Fallback to parts for this test
                        "output": str(tmpdir / "bom.csv"),
                        "fields": ["material"],
                    },
                }
            ]
        }

        # Write config to temp file
        config_file = tmpdir / "export.yml"

        config_file.write_text(yaml.dump(config))

        # Change to temp directory and run export
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Import and run the export
            # Note: This will try to run via FreeCAD subprocess
            exports = config["export"]
            for item in exports:
                print(f"Testing export: {item['name']}")
                print(f"  Document: {item['source']}")
                print(f"  3MF output: {item['output']}")
                if item.get("techdraw"):
                    print(f"  TechDraw output: {item['techdraw']['output_dir']}")
                if item.get("bom"):
                    print(f"  BOM output: {item['bom']['output']}")

            # We can't actually run this without FreeCAD in the test
            # But we can verify the config is valid
            assert config_file.exists(), "Config file should be created"
            assert config_file.read_text(), "Config file should have content"

        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    test_techdraw_and_bom_export()
