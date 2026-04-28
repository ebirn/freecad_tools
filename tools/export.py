#!/usr/bin/env python3
"""
export.py - Unified entry point for FreeCAD 3MF export workflow.

This script provides a single command to export FreeCAD documents to 3MF format
with optional printer settings preservation and STL file generation.

Usage:
    python3 export.py                    # Run with auto-discovered config
    python3 export.py <config_file>      # Run with custom config file
    python3 export.py --config exports.yml  # Run with config flag

The config file should be YAML format. See README.md for full configuration options.
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="python3 export.py",
        description="Export FreeCAD documents to 3MF format with embedded mesh data",
    )
    parser.add_argument(
        "config_file",
        nargs="?",
        default=None,
        help="Path to YAML export config file (default: auto-discover)",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to YAML export config file",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config without performing export",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Configure basic logging
    # Priority: CLI --verbose flag > environment variable > default INFO
    if args.verbose:
        log_level = logging.DEBUG
    else:
        log_level_name = os.environ.get("FREECAD_TOOLS_LOG_LEVEL", "INFO")
        try:
            log_level = getattr(logging, log_level_name.upper())
        except AttributeError:
            log_level = logging.INFO

    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)

    # Determine the script directory
    SCRIPT_DIR = Path(__file__).parent.absolute()  # noqa: N806

    # Find fc_export.py
    FC_EXPORT_SCRIPT = SCRIPT_DIR / "fc_export.py"  # noqa: N806

    if not FC_EXPORT_SCRIPT.exists():
        print(f"Error: fc_export.py not found at {FC_EXPORT_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    # Determine config file to use
    CONFIG_FILE = None  # noqa: N806
    PROJECT_ROOT = Path.cwd()  # noqa: N806

    # Priority: --config flag > positional argument > auto-discovery
    config_from_flag = args.config if args.config else args.config_file

    if config_from_flag:
        CONFIG_FILE = Path(config_from_flag).resolve()  # noqa: N806
        if not CONFIG_FILE.exists():
            print(f"Error: Config file not found: {CONFIG_FILE}", file=sys.stderr)
            print("Use --help for usage information", file=sys.stderr)
            sys.exit(1)
        PROJECT_ROOT = CONFIG_FILE.parent  # noqa: N806

    elif os.path.exists("export_config.yml"):
        CONFIG_FILE = Path("export_config.yml").resolve()  # noqa: N806

    logger.debug(f"PROJECT_ROOT: {PROJECT_ROOT}")
    logger.debug(f"CONFIG_FILE: {CONFIG_FILE}")

    # Handle dry-run mode
    if args.dry_run:
        env = os.environ.copy()
        env["FREECAD_TOOLS_DRY_RUN"] = "true"
        if args.verbose:
            env["FREECAD_TOOLS_LOG_LEVEL"] = "DEBUG"

        # Pass environment for config discovery
        env["FREECAD_TOOLS_PROJECT_ROOT"] = str(PROJECT_ROOT)
        env["FREECAD_TOOLS_LIB3MF_PYTHON"] = sys.executable
        if CONFIG_FILE:
            env["FREECAD_TOOLS_CONFIG"] = str(CONFIG_FILE)

        # Build arguments for fc_export.py - config first, then flags
        fc_args = [sys.executable, str(FC_EXPORT_SCRIPT)]
        if CONFIG_FILE:
            fc_args.append(str(CONFIG_FILE))
        fc_args.append("--dry-run")

        result = subprocess.run(fc_args, env=env, text=True)
        sys.exit(result.returncode)

    # Normal execution mode
    fc_args = [sys.executable, str(FC_EXPORT_SCRIPT)]
    if CONFIG_FILE:
        fc_args.append(str(CONFIG_FILE))

    # Pass PROJECT_ROOT and CONFIG_FILE via environment variables for subprocess
    env = os.environ.copy()
    env["FREECAD_TOOLS_PROJECT_ROOT"] = str(PROJECT_ROOT)
    env["FREECAD_TOOLS_LIB3MF_PYTHON"] = sys.executable  # Pass original Python with lib3mf
    if CONFIG_FILE:
        env["FREECAD_TOOLS_CONFIG"] = str(CONFIG_FILE)
    if args.verbose:
        env["FREECAD_TOOLS_LOG_LEVEL"] = "DEBUG"

    # Run fc_export.py with the same Python interpreter
    result = subprocess.run(fc_args, env=env, text=True)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
