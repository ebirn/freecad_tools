#!/usr/bin/env python3
"""
export.py - Unified entry point for FreeCAD 3MF export workflow.

This script provides a single command to export FreeCAD documents to 3MF format
with optional printer settings preservation and STL file generation.

Usage:
    python3 export.py                    # Run with export_config.yml
    python3 export.py <config_file>      # Run with custom config file

The config file should be YAML format with the following structure:
    export:
      - source: model.FCStd
        output: output.3mf
        bodies: [Body, Body002]
        template: template.3mf (optional)
        keep_stl: true (optional, default false)
        stl_output_dir: stl/ (optional)
"""

import sys
import os
from pathlib import Path

# Determine the script directory
SCRIPT_DIR = Path(__file__).parent.absolute()

# Find and run fc_export.py (which handles FreeCAD integration)
FC_EXPORT_SCRIPT = SCRIPT_DIR / "fc_export.py"

if not FC_EXPORT_SCRIPT.exists():
    print(f"Error: fc_export.py not found at {FC_EXPORT_SCRIPT}", file=sys.stderr)
    sys.exit(1)

# Change to caller's directory so relative paths in config work correctly
# (config file should be in the project directory, not the tools directory)
# Only change if we're running the export tools directly
if os.path.exists('export_config.yml'):
    # Config is in current directory, keep it
    pass
elif os.path.exists(os.path.join(SCRIPT_DIR, 'export_config.yml.example')):
    # Config template is in tools directory, but user should copy to project dir
    pass
# Don't change directory - let fc_export.py handle paths relative to caller

# Run fc_export.py with the same Python interpreter
# (it will re-invoke itself with FreeCAD if needed)
import subprocess

result = subprocess.run([sys.executable, str(FC_EXPORT_SCRIPT)], text=True)
sys.exit(result.returncode)
