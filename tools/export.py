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

import logging
import os
import subprocess
import sys
from pathlib import Path

# Configure basic logging
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Determine the script directory
SCRIPT_DIR = Path(__file__).parent.absolute()

# Find and run fc_export.py (which handles FreeCAD integration)
FC_EXPORT_SCRIPT = SCRIPT_DIR / "fc_export.py"

if not FC_EXPORT_SCRIPT.exists():
    print(f"Error: fc_export.py not found at {FC_EXPORT_SCRIPT}", file=sys.stderr)
    sys.exit(1)

# Determine config file to use
CONFIG_FILE = None
PROJECT_ROOT = Path.cwd()  # Capture project root BEFORE any directory changes

# Check command-line argument first
if len(sys.argv) > 1:
    CONFIG_FILE = Path(sys.argv[1]).resolve()  # Convert to absolute path
    if not CONFIG_FILE.exists():
        print(f"Error: Config file not found: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)
    # For absolute config paths, capture the project root from the config's parent
    # (in case export.py was run from a different directory)
    PROJECT_ROOT = CONFIG_FILE.parent

# If no config argument, look in current directory
elif os.path.exists("export_config.yml"):
    CONFIG_FILE = Path("export_config.yml").resolve()  # Also make absolute
    # Config is in current directory, PROJECT_ROOT is already set

logger.info(f"PROJECT_ROOT: {PROJECT_ROOT}")
logger.info(f"CONFIG_FILE: {CONFIG_FILE}")

# Build arguments for fc_export.py
fc_args = [sys.executable, str(FC_EXPORT_SCRIPT)]
if CONFIG_FILE:
    fc_args.append(str(CONFIG_FILE))

# Pass PROJECT_ROOT and CONFIG_FILE via environment variables for subprocess
env = os.environ.copy()
env["FREECAD_TOOLS_PROJECT_ROOT"] = str(PROJECT_ROOT)
env["FREECAD_TOOLS_LIB3MF_PYTHON"] = sys.executable  # Pass original Python with lib3mf
if CONFIG_FILE:
    env["FREECAD_TOOLS_CONFIG"] = str(CONFIG_FILE)

# Run fc_export.py with the same Python interpreter
result = subprocess.run(fc_args, env=env, text=True)
sys.exit(result.returncode)
