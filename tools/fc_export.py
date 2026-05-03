#!/usr/bin/env python3
import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from unittest.mock import MagicMock

import yaml

# Import git utilities
try:
    # Try to import from same directory
    import git_utils
except ImportError:
    # Try from parent directory
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        import git_utils
    except ImportError:
        git_utils = None


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="python3 fc_export.py",
        description="Export FreeCAD documents to 3MF format (FreeCAD-internal script)",
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
    parser.add_argument(
        "--slicer-dry-run",
        action="store_true",
        help="Build slicer commands but do not execute slicers",
    )
    parser.add_argument(
        "--name",
        "-n",
        type=str,
        default=None,
        help="Export only the item with this name (from multi-item config)",
    )
    parser.add_argument(
        "--list-exports",
        action="store_true",
        help="List export item names from config and exit",
    )
    parser.add_argument(
        "--gui-only",
        action="store_true",
        help="Run only GUI-dependent tasks (TechDraw/screenshots), skip 3MF export",
    )
    parser.add_argument(
        "--screenshots-only",
        action="store_true",
        help="Run only screenshot GUI tasks, skip 3MF export and TechDraw",
    )
    parser.add_argument(
        "--gui-session",
        choices=["item", "run"],
        default="item",
        help="GUI session scope: per-item (default) or single session per run",
    )
    return parser.parse_args()


def configure_logging(verbose=False, log_level_env=None):
    """Configure logging with optional verbose override."""
    if verbose:
        log_level = logging.DEBUG
    elif log_level_env:
        try:
            log_level = getattr(logging, log_level_env.upper())
        except AttributeError:
            log_level = logging.INFO
    else:
        log_level = logging.INFO

    log_file = "fc_export.log"
    # Clean console format: LEVEL - message (no module name)
    console_format = "%(levelname)s - %(message)s"
    file_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=log_level,
        format=console_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr),
        ],
    )
    # Set file handler to use more detailed format
    for handler in logging.root.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.setFormatter(logging.Formatter(file_format))
    return logging.getLogger(__name__)


# Parse command-line arguments early so we can respect --verbose before imports
args = parse_args()

# Check for verbose flag from CLI or environment
verbose_cli = args.verbose
dry_run_mode = args.dry_run
slicer_dry_run_mode = args.slicer_dry_run
name_filter = args.name
list_exports_mode = args.list_exports
gui_only_mode = args.gui_only
screenshots_only_mode = args.screenshots_only
gui_session_mode = args.gui_session

# Check environment for verbose/log level (set by export.py)
log_level_env = os.environ.get("FREECAD_TOOLS_LOG_LEVEL")
if os.environ.get("FREECAD_TOOLS_DRY_RUN", "").lower() == "true":
    dry_run_mode = True
if os.environ.get("FREECAD_TOOLS_SLICER_DRY_RUN", "").lower() == "true":
    slicer_dry_run_mode = True
if os.environ.get("FREECAD_TOOLS_NAME") and not name_filter:
    name_filter = os.environ.get("FREECAD_TOOLS_NAME")
if os.environ.get("FREECAD_TOOLS_LIST_EXPORTS", "").lower() == "true":
    list_exports_mode = True
if os.environ.get("FREECAD_TOOLS_GUI_ONLY", "").lower() == "true":
    gui_only_mode = True
if os.environ.get("FREECAD_TOOLS_SCREENSHOTS_ONLY", "").lower() == "true":
    screenshots_only_mode = True
if os.environ.get("FREECAD_TOOLS_GUI_SESSION") in ("item", "run"):
    gui_session_mode = os.environ.get("FREECAD_TOOLS_GUI_SESSION")

# Configure logging (respects --verbose or env var)
logger = configure_logging(verbose=verbose_cli, log_level_env=log_level_env)


# --- Logging Helper Functions for Cleaner Console Output ---
def log_section(title: str) -> None:
    """Log a section header with visual separators."""
    separator = "=" * 60
    logger.info(separator)
    logger.info(f"  {title}")
    logger.info(separator)


def log_subsection(title: str) -> None:
    """Log a subsection header."""
    logger.info(f"\n--- {title} ---")


def log_action(message: str) -> None:
    """Log an action/step with arrow symbol."""
    logger.info(f"→ {message}")


def log_success(message: str) -> None:
    """Log a success with checkmark symbol."""
    logger.info(f"✓ {message}")


def log_failure(message: str) -> None:
    """Log a failure with X symbol."""
    logger.error(f"✗ {message}")


def log_warning_msg(message: str) -> None:
    """Log a warning with exclamation symbol."""
    logger.warning(f"⚠ {message}")


def _format_bytes(num_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def get_export_names(exports):
    """Return display-safe export names from config entries."""
    names = []
    for idx, item in enumerate(exports):
        name = item.get("name") if isinstance(item, dict) else None
        names.append(name or f"unnamed_{idx}")
    return names


def filter_exports_by_name(exports, selected_name):
    """Filter exports by exact name match."""
    return [item for item in exports if item.get("name") == selected_name]


def should_run_3mf_export(gui_only=False, screenshots_only=False):
    """Return True when the core 3MF export pipeline should run."""
    return not (gui_only or screenshots_only)


def should_run_techdraw(techdraw_config, screenshots_only=False):
    """Return True when TechDraw tasks should run."""
    return bool(techdraw_config) and not screenshots_only


def has_gui_tasks(export_item):
    """Return True when an export item has screenshot or TechDraw work configured."""
    return bool(export_item.get("screenshots") or export_item.get("techdraw"))


def build_gui_task_summary(export_item, screenshots_only=False):
    """Build a concise summary of GUI tasks for logging/reporting."""
    screenshot_cfg = export_item.get("screenshots")
    techdraw_cfg = export_item.get("techdraw")
    return {
        "screenshots": bool(screenshot_cfg),
        "techdraw": should_run_techdraw(techdraw_cfg, screenshots_only=screenshots_only),
    }


def plan_gui_tasks(export_item, screenshots_only=False):
    """Return the GUI task plan for an export item."""
    summary = build_gui_task_summary(export_item, screenshots_only=screenshots_only)
    return {
        "run_screenshots": summary["screenshots"],
        "run_techdraw": summary["techdraw"],
    }


def body_specs_to_identifiers(bodies):
    """Convert mixed body specs into plain body identifiers."""
    identifiers = []
    for spec in bodies or []:
        if isinstance(spec, str):
            identifiers.append(spec)
        elif isinstance(spec, dict) and spec.get("body"):
            identifiers.append(spec["body"])
    return identifiers


def resolve_screenshot_bodies(item, resolved_bodies):
    """Resolve screenshot body identifiers using screenshot_source selector."""
    source = item.get("screenshot_source", SCREENSHOT_SOURCE_EXPORT)
    if source == SCREENSHOT_SOURCE_EXPORT:
        return body_specs_to_identifiers(resolved_bodies)
    return (item.get("screenshots") or {}).get("bodies", [])


def resolve_techdraw_pages(item):
    """Resolve TechDraw pages using techdraw_source selector."""
    source = item.get("techdraw_source", TECHDRAW_SOURCE_ALL)
    if source == TECHDRAW_SOURCE_ALL:
        return []
    return (item.get("techdraw") or {}).get("pages", [])


def _compute_image_stddev(image_path):
    """Return average RGB stddev for an image, or None if unavailable."""
    try:
        from PIL import Image, ImageStat  # pylint: disable=import-error

        with Image.open(image_path) as img:
            rgb = img.convert("RGB")
            stat = ImageStat.Stat(rgb)
            if not stat.stddev:
                return 0.0
            return sum(stat.stddev) / len(stat.stddev)
    except Exception:
        return None


def warn_on_near_uniform_images(images, stddev_threshold=1.5):
    """Warn when generated screenshots appear near-uniform/blank."""
    for image in images:
        image_path = image.get("path")
        if not image_path or not os.path.exists(image_path):
            continue
        stddev = _compute_image_stddev(image_path)
        if stddev is None:
            continue
        if stddev <= stddev_threshold:
            log_warning_msg(
                f"Screenshot may be blank/near-uniform: {image_path} (stddev={stddev:.2f}, threshold={stddev_threshold:.2f})"
            )


def summarize_subprocess_stderr(stderr_text, limit=240):
    """Return a compact single-line stderr summary for operator output."""
    if not stderr_text:
        return ""
    compact = " ".join(line.strip() for line in stderr_text.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def validate_slicer_config(export_item):
    """Validate slicer config and return normalized warning/error state."""
    slicer = export_item.get("slicer")
    if not slicer:
        return True, None
    if not isinstance(slicer, dict):
        return False, "slicer must be a mapping"

    enabled = slicer.get("enabled", False)
    if not enabled:
        return True, None

    engine = slicer.get("engine")
    if engine not in ("prusa", "orca"):
        return False, "slicer.engine must be one of: prusa, orca"

    engine_cfg = slicer.get(engine, {})
    if engine_cfg is None:
        engine_cfg = {}
    if not isinstance(engine_cfg, dict):
        return False, f"slicer.{engine} must be a mapping"

    output_name = slicer.get("output_name")
    if output_name is not None and not isinstance(output_name, str):
        return False, "slicer.output_name must be a string"

    extra_args = engine_cfg.get("extra_args", [])
    if extra_args and (not isinstance(extra_args, list) or not all(isinstance(arg, str) for arg in extra_args)):
        return False, f"slicer.{engine}.extra_args must be a list of strings"

    has_template = bool(export_item.get("template"))
    use_config_bundle = bool(slicer.get("use_config_bundle", False))
    config_bundle = slicer.get("config_bundle")
    profile_keys = ["printer_profile", "print_profile", "material_profile"]
    has_profiles = all(bool(engine_cfg.get(key)) for key in profile_keys)

    if use_config_bundle and not config_bundle:
        return False, "slicer.config_bundle is required when slicer.use_config_bundle=true"

    if not has_template and not has_profiles and not use_config_bundle:
        return (
            False,
            "slicer requires either profiles (printer_profile/print_profile/material_profile) "
            "or use_config_bundle=true when no export template is configured",
        )

    return True, None


def _resolve_slicer_binary(slicer_config):
    """Resolve slicer executable name/path for selected engine."""
    engine = slicer_config.get("engine")
    binary_override = slicer_config.get("binary")
    if binary_override:
        return binary_override

    if engine == "prusa":
        candidates = [
            "prusa-slicer",
            "PrusaSlicer",
            "/Applications/Original Prusa Drivers/PrusaSlicer.app/Contents/MacOS/PrusaSlicer",
            "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer",
        ]
    else:
        candidates = [
            "orca-slicer",
            "OrcaSlicer",
            "/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",
        ]

    for candidate in candidates:
        if os.path.isabs(candidate):
            if os.path.exists(candidate):
                return candidate
            continue

        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    return candidates[0]


def _format_slicer_output_name(template, export_name, engine):
    """Format output_name template for slicer gcode outputs."""
    date_token = time.strftime("%Y%m%d")
    value = template.format(name=export_name, engine=engine, date=date_token)
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in value)


def _strip_profile_value(raw_value):
    """Normalize profile value parsed from slicer config text."""
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1]
    return value.strip() or None


def _extract_prusa_profiles_from_template(template_path):
    """Extract default profile names from template 3MF Prusa config metadata."""
    if not template_path or not os.path.exists(template_path):
        return {}

    try:
        with zipfile.ZipFile(template_path) as archive:
            if "Metadata/Slic3r_PE.config" not in archive.namelist():
                return {}
            config_text = archive.read("Metadata/Slic3r_PE.config").decode("utf-8", errors="ignore")
    except Exception as exc:
        logger.debug(f"Failed to read template slicer config metadata: {exc}")
        return {}

    profile_map = {
        "printer_settings_id": "printer_profile",
        "print_settings_id": "print_profile",
        "filament_settings_id": "material_profile",
        "default_print_profile": "print_profile",
        "default_filament_profile": "material_profile",
    }
    extracted = {}

    for raw_line in config_text.splitlines():
        line = raw_line.strip()
        if not line.startswith(";"):
            continue
        line = line[1:].strip()
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        normalized_key = profile_map.get(key)
        if not normalized_key:
            continue
        cleaned = _strip_profile_value(value)
        if cleaned and normalized_key not in extracted:
            extracted[normalized_key] = cleaned

    return extracted


def _extract_template_slic3r_config_to_temp(template_path):
    """Extract Metadata/Slic3r_PE.config from a 3MF template into a temp file."""
    if not template_path or not os.path.exists(template_path):
        return None

    try:
        with zipfile.ZipFile(template_path) as archive:
            if "Metadata/Slic3r_PE.config" not in archive.namelist():
                return None
            config_text = archive.read("Metadata/Slic3r_PE.config").decode("utf-8", errors="ignore")
    except Exception as exc:
        logger.debug(f"Failed to extract Slic3r config from template: {exc}")
        return None

    temp_file = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".ini", delete=False)
    temp_file.write(config_text)
    temp_file.flush()
    temp_file.close()
    return temp_file.name


def build_slicer_command(export_item, output_3mf_path):
    """Build slicer CLI command for a generated 3MF output."""
    slicer = export_item.get("slicer", {})
    if not slicer.get("enabled", False):
        return None, None, None

    engine = slicer["engine"]
    raw_engine_cfg = dict(slicer.get(engine, {}) or {})
    engine_cfg = dict(raw_engine_cfg)
    explicit_profile_overrides = any(
        raw_engine_cfg.get(key) for key in ("printer_profile", "print_profile", "material_profile")
    )

    if engine == "prusa":
        template_profiles = _extract_prusa_profiles_from_template(export_item.get("template"))
        for key in ("printer_profile", "print_profile", "material_profile"):
            if not engine_cfg.get(key) and template_profiles.get(key):
                engine_cfg[key] = template_profiles[key]
        if template_profiles:
            logger.debug(f"Template-derived Prusa profiles: {template_profiles}")

    binary = _resolve_slicer_binary(slicer)

    output_dir = slicer.get("output_dir") or os.path.dirname(output_3mf_path)
    os.makedirs(output_dir, exist_ok=True)
    output_name_template = slicer.get("output_name", "{name}_{engine}_{date}.gcode")
    output_name = _format_slicer_output_name(output_name_template, export_item.get("name", "export"), engine)
    output_path = os.path.join(output_dir, output_name)
    temp_bundle_path = None

    if engine == "prusa":
        cmd = [binary, "--export-gcode", output_3mf_path, "--output", output_path]

        if slicer.get("use_config_bundle", False) and slicer.get("config_bundle"):
            cmd.extend(["--load", slicer["config_bundle"]])
        elif not explicit_profile_overrides:
            temp_bundle_path = _extract_template_slic3r_config_to_temp(export_item.get("template"))
            if temp_bundle_path:
                cmd.extend(["--load", temp_bundle_path])

        profile_map = {
            "printer_profile": "--printer-profile",
            "print_profile": "--print-profile",
            "material_profile": "--material-profile",
        }
        if explicit_profile_overrides:
            for key, flag in profile_map.items():
                value = engine_cfg.get(key)
                if value:
                    cmd.extend([flag, value])
    else:
        cmd = [binary, "--slice", "0", "--outputdir", output_dir]
        if slicer.get("use_config_bundle", False) and slicer.get("config_bundle"):
            cmd.extend(["--load-settings", slicer["config_bundle"]])
        elif export_item.get("template"):
            temp_bundle_path = _extract_template_slic3r_config_to_temp(export_item.get("template"))
            if temp_bundle_path:
                cmd.extend(["--load-settings", temp_bundle_path])
        cmd.append(output_3mf_path)

    cmd.extend(engine_cfg.get("extra_args", []))
    return cmd, output_path, temp_bundle_path


def run_slicer_for_export_item(export_item, output_3mf_path):
    """Run optional slicer stage after 3MF export."""
    cmd, output_path, temp_bundle_path = build_slicer_command(export_item, output_3mf_path)
    if not cmd:
        return True

    cmd_display = " ".join(cmd)
    log_action(f"Slicer command: {cmd_display}")

    slicer = export_item.get("slicer", {})
    slicer_dry_run = bool(slicer.get("dry_run", False) or slicer_dry_run_mode or dry_run_mode)
    if slicer_dry_run:
        log_action("Skipping slicer execution in dry-run mode")
        return True

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except Exception as exc:
        log_failure(f"Slicer execution failed: {exc}")
        if temp_bundle_path and os.path.exists(temp_bundle_path):
            os.unlink(temp_bundle_path)
        return False

    if result.returncode != 0:
        stderr_summary = summarize_subprocess_stderr(result.stderr)
        log_failure(f"Slicer failed (exit {result.returncode}): {stderr_summary}")
        if temp_bundle_path and os.path.exists(temp_bundle_path):
            os.unlink(temp_bundle_path)
        return False

    slicer = export_item.get("slicer", {})
    if slicer.get("engine") == "orca":
        output_dir = slicer.get("output_dir") or os.path.dirname(output_3mf_path)
        if not os.path.exists(output_path):
            gcode_files = [
                os.path.join(output_dir, entry)
                for entry in os.listdir(output_dir)
                if entry.lower().endswith(".gcode") and os.path.isfile(os.path.join(output_dir, entry))
            ]
            if gcode_files:
                latest_gcode = max(gcode_files, key=os.path.getmtime)
                if latest_gcode != output_path:
                    try:
                        os.replace(latest_gcode, output_path)
                    except OSError:
                        output_path = latest_gcode
                else:
                    output_path = latest_gcode

    if output_path and os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        log_success(f"Slicer output generated: {os.path.basename(output_path)} ({_format_bytes(file_size)})")
    else:
        log_warning_msg("Slicer completed but output file was not found at expected path")

    if temp_bundle_path and os.path.exists(temp_bundle_path):
        os.unlink(temp_bundle_path)

    return True


def build_gui_batch_config(item, source_path, project_root, temp_dir, resolved_bodies):
    """Build JSON-serializable config payload for batched GUI subprocess."""
    screenshot_cfg = item.get("screenshots") if isinstance(item.get("screenshots"), dict) else {}
    screenshot_output_dir = screenshot_cfg.get("output_dir", "prints/images/")
    if not os.path.isabs(screenshot_output_dir):
        screenshot_output_dir = os.path.abspath(os.path.join(project_root, screenshot_output_dir))

    return {
        "source": source_path,
        "run_screenshots": True,
        "run_techdraw": True,
        "screenshots": {
            "bodies": resolve_screenshot_bodies(item, resolved_bodies),
            "output_dir": screenshot_output_dir,
            "views": screenshot_cfg.get("views", ["isometric"]),
            "resolution": screenshot_cfg.get("resolution", [1920, 1080]),
            "format": screenshot_cfg.get("format", "png"),
            "composite": screenshot_cfg.get("composite", True),
        },
        "techdraw": {
            "pages": resolve_techdraw_pages(item),
            "output_dir": temp_dir,
        },
    }


def merge_techdraw_pdfs(page_pdfs, output_path, temp_dir):
    """Merge per-page PDFs into final output path via techdraw_pdf.py."""
    merge_config = {
        "page_pdfs": page_pdfs,
        "output_path": os.path.abspath(output_path),
    }
    merge_config_path = os.path.join(temp_dir, "merge_config.json")
    with open(merge_config_path, "w", encoding="utf-8") as f:
        json.dump(merge_config, f, indent=2)

    merge_cmd = [
        _find_venv_python(),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "techdraw_pdf.py"),
        merge_config_path,
    ]
    merge_result = subprocess.run(merge_cmd, capture_output=True, text=True, timeout=120)
    if merge_result.stderr:
        logger.debug(f"PDF merge stderr: {merge_result.stderr[:1000]}")
        logger.info(f"PDF merge stderr summary: {summarize_subprocess_stderr(merge_result.stderr)}")

    return merge_result.returncode == 0 and os.path.exists(merge_config["output_path"])


def normalize_gui_batch_result(batch_result):
    """Normalize batched GUI result into stable dict shape."""
    screenshots = batch_result.get("screenshots") if isinstance(batch_result, dict) else None
    techdraw = batch_result.get("techdraw") if isinstance(batch_result, dict) else None
    artifacts = batch_result.get("artifacts") if isinstance(batch_result, dict) else None
    timing = batch_result.get("timing") if isinstance(batch_result, dict) else None

    if not isinstance(screenshots, dict):
        screenshots = {"success": False, "images": [], "error": "Missing screenshots result", "skipped": False}
    screenshots.setdefault("success", False)
    screenshots.setdefault("images", [])
    screenshots.setdefault("error", None)
    screenshots.setdefault("skipped", False)

    if not isinstance(techdraw, dict):
        techdraw = {"success": False, "pages": [], "error": "Missing techdraw result"}
    techdraw.setdefault("success", False)
    techdraw.setdefault("pages", [])
    techdraw.setdefault("error", None)

    if not isinstance(artifacts, dict):
        artifacts = {"pdf_pages": [], "images": []}
    artifacts.setdefault("pdf_pages", [])
    artifacts.setdefault("images", [])

    if not isinstance(timing, dict):
        timing = {"total_seconds": 0.0, "techdraw_seconds": 0.0, "screenshots_seconds": 0.0}
    timing.setdefault("total_seconds", 0.0)
    timing.setdefault("techdraw_seconds", 0.0)
    timing.setdefault("screenshots_seconds", 0.0)

    return {
        "success": bool(batch_result.get("success", False)) if isinstance(batch_result, dict) else False,
        "screenshots": screenshots,
        "techdraw": techdraw,
        "artifacts": artifacts,
        "timing": timing,
        "error": (batch_result.get("error") if isinstance(batch_result, dict) else "Invalid batch result"),
    }


def summarize_gui_batch_result(batch_result):
    """Build concise human-readable summary line for batched GUI results."""
    normalized = normalize_gui_batch_result(batch_result)
    screenshots_ok = normalized["screenshots"].get("success")
    techdraw_ok = normalized["techdraw"].get("success")
    image_count = len(normalized["artifacts"].get("images", []))
    page_count = len(normalized["artifacts"].get("pdf_pages", []))
    total_seconds = normalized["timing"].get("total_seconds", 0.0)
    return (
        "GUI batch result: "
        f"success={normalized['success']} "
        f"screenshots={screenshots_ok}({image_count} images) "
        f"techdraw={techdraw_ok}({page_count} pages) "
        f"time={total_seconds:.3f}s"
    )


def summarize_export_timing(export_name, timing_data):
    """Return a concise per-export timing summary line."""
    open_seconds = timing_data.get("open_seconds", 0.0)
    export_seconds = timing_data.get("export_seconds", 0.0)
    gui_seconds = timing_data.get("gui_seconds", 0.0)
    total_seconds = timing_data.get("total_seconds", 0.0)
    return (
        f"Export timing [{export_name}]: "
        f"open={open_seconds:.3f}s "
        f"export={export_seconds:.3f}s "
        f"gui={gui_seconds:.3f}s "
        f"total={total_seconds:.3f}s"
    )


def log_export_timing(export_name, timing_data):
    """Emit per-export timing summary to logs."""
    logger.info(summarize_export_timing(export_name, timing_data))


def summarize_run_stats(run_stats):
    """Return concise overall timing/stats summary for full export run."""
    return (
        "Run totals: "
        f"items={run_stats.get('item_count', 0)} "
        f"open={run_stats.get('open_seconds', 0.0):.3f}s "
        f"export={run_stats.get('export_seconds', 0.0):.3f}s "
        f"gui={run_stats.get('gui_seconds', 0.0):.3f}s "
        f"shared_gui={run_stats.get('shared_gui_seconds', 0.0):.3f}s "
        f"total={run_stats.get('total_seconds', 0.0):.3f}s"
    )


def run_gui_tasks_for_item(doc, item, export_name, source_path, project_root, resolved_bodies, screenshots_only=False):
    """Run GUI-dependent tasks for one export item and return task results."""
    results = {
        "screenshot": None,
        "techdraw": None,
        "last_bom_csv": None,
    }

    task_plan = plan_gui_tasks(item, screenshots_only=screenshots_only)
    logger.debug(f"GUI task plan: {task_plan}")

    if task_plan["run_screenshots"] and task_plan["run_techdraw"]:
        batched_results = run_gui_tasks_batched(doc, item, export_name, source_path, project_root, resolved_bodies)
        if batched_results.get("screenshot") is not None or batched_results.get("techdraw") is not None:
            return batched_results
        log_warning_msg("Batched GUI path unavailable, falling back to sequential GUI steps")

    if task_plan["run_screenshots"]:
        log_action("Generating screenshots")
        screenshot_item = dict(item)
        screenshot_cfg = dict(item.get("screenshots") or {})
        screenshot_cfg["bodies"] = resolve_screenshot_bodies(item, resolved_bodies)
        screenshot_item["screenshots"] = screenshot_cfg
        screenshot_success, screenshot_result = run_screenshot_generation(screenshot_item, project_root)
        results["screenshot"] = {
            "success": screenshot_success,
            "result": screenshot_result,
        }

        if screenshot_result.get("success"):
            images = screenshot_result.get("images", [])
            if images:
                log_success(f"Generated {len(images)} screenshots")
                for img in images:
                    logger.debug(f"  - {img.get('path', 'unknown')}")
                warn_on_near_uniform_images(images)
            elif screenshot_result.get("skipped"):
                logger.debug("Screenshots skipped (not enabled)")
        else:
            error = screenshot_result.get("error", "Unknown error")
            log_warning_msg(f"Screenshot generation failed (non-fatal): {error}")

    techdraw_config = item.get("techdraw")
    if task_plan["run_techdraw"]:
        log_action("Processing TechDraw export")
        pages_to_export = resolve_techdraw_pages(item)
        techdraw_output_dir = techdraw_config.get("output_dir", "docs")
        techdraw_format = techdraw_config.get("format", "pdf")

        if not os.path.isabs(techdraw_output_dir):
            techdraw_output_dir = os.path.join(project_root, techdraw_output_dir)
        os.makedirs(techdraw_output_dir, exist_ok=True)

        if techdraw_format == "pdf":
            pdf_output = os.path.join(techdraw_output_dir, f"{export_name}.pdf")
            techdraw_pdf_pending = {
                "pages": pages_to_export,
                "output": pdf_output,
                "instructions": techdraw_config.get("instructions"),
            }
            logger.debug(f"TechDraw PDF generation pending: {pdf_output}")
        else:
            log_warning_msg(f"TechDraw format '{techdraw_format}' not yet supported, skipping")
            techdraw_pdf_pending = None
    else:
        techdraw_pdf_pending = None

    bom_config = item.get("bom")
    if bom_config and task_plan["run_techdraw"]:
        bom_configs = [bom_config] if isinstance(bom_config, dict) else bom_config

        for i, single_bom_config in enumerate(bom_configs):
            log_action(f"Processing BOM generation #{i}")
            bom_source = single_bom_config.get("source", "auto")
            bom_output = single_bom_config.get("output", f"docs/{export_name}_bom.csv")
            bom_fields = single_bom_config.get("fields", [])
            bom_assembly = single_bom_config.get("assembly")

            try:
                if not os.path.isabs(bom_output):
                    bom_output = os.path.join(project_root, bom_output)

                bom_data = []
                if bom_source in ("auto", "assembly"):
                    logger.debug("Attempting to extract BOM from Assembly")
                    bom_data = extract_bom_from_assembly(doc, custom_fields=bom_fields, assembly_name=bom_assembly)
                    if bom_data:
                        log_success(f"Extracted BOM from Assembly ({len(bom_data)} items)")

                if not bom_data and bom_source in ("auto", "spreadsheet"):
                    spreadsheet_name = single_bom_config.get("spreadsheet_name", "BOM")
                    logger.debug(f"Attempting to extract BOM from Spreadsheet '{spreadsheet_name}'")
                    bom_data = extract_bom_from_spreadsheet(
                        doc, spreadsheet_name=spreadsheet_name, custom_fields=bom_fields
                    )
                    if bom_data:
                        log_success(f"Extracted BOM from Spreadsheet ({len(bom_data)} items)")

                if not bom_data and bom_source in ("auto", "parts"):
                    logger.debug("Attempting to extract BOM from Parts")
                    bom_data = extract_bom_from_parts(doc, custom_fields=bom_fields)
                    if bom_data:
                        log_success(f"Extracted BOM from Parts ({len(bom_data)} items)")

                os.makedirs(os.path.dirname(bom_output) or ".", exist_ok=True)

                from bom_utils import write_bom_csv  # pylint: disable=import-error

                fields = ["label", "quantity"] + bom_fields if bom_fields else None
                write_bom_csv(bom_data, bom_output, fields=fields)
                if bom_data:
                    log_success(f"BOM written to: {bom_output} ({len(bom_data)} items)")
                else:
                    log_warning_msg(f"BOM written to: {bom_output} (no items found)")
                results["last_bom_csv"] = bom_output

            except Exception as e:
                logger.exception(f"Error generating BOM #{i}: {e}")

    if techdraw_pdf_pending:
        try:
            pdf_output = techdraw_pdf_pending["output"]
            pages = techdraw_pdf_pending["pages"]
            instructions_path = techdraw_pdf_pending.get("instructions")

            if instructions_path and not os.path.isabs(instructions_path):
                instructions_path = os.path.join(project_root, instructions_path)

            last_bom_csv = results["last_bom_csv"]
            bom_csv_for_pdf = last_bom_csv if (last_bom_csv and os.path.exists(last_bom_csv)) else None

            pdf_metadata = get_export_metadata(item, project_root)
            pdf_metadata["title"] = export_name
            pdf_metadata["source"] = os.path.basename(source_path)

            log_action(f"Generating TechDraw PDF: {os.path.basename(pdf_output)}")
            pdf_success = export_techdraw_to_pdf(
                doc,
                pages,
                pdf_output,
                bom_csv_path=bom_csv_for_pdf,
                instructions_path=instructions_path,
                metadata=pdf_metadata,
            )
            results["techdraw"] = {
                "success": pdf_success,
                "output": pdf_output,
            }

            if pdf_success:
                log_success(f"TechDraw PDF generated: {os.path.basename(pdf_output)}")
            else:
                log_warning_msg("TechDraw PDF generation failed")
        except Exception as e:
            logger.exception(f"Error generating TechDraw PDF: {e}")
            results["techdraw"] = {
                "success": False,
                "error": str(e),
            }

    return results


def run_gui_tasks_batched(doc, item, export_name, source_path, project_root, resolved_bodies):
    """Run screenshots and TechDraw in a single GUI subprocess."""
    results = {"screenshot": None, "techdraw": None, "last_bom_csv": None}
    freecad_gui = _find_freecad_gui_binary()
    if not freecad_gui:
        log_warning_msg("FreeCAD GUI binary not found; cannot run batched GUI tasks")
        return results

    with tempfile.TemporaryDirectory(prefix="gui_batch_") as temp_dir:
        result_file = os.path.join(temp_dir, "result.json")
        config_path = os.path.join(temp_dir, "batch_config.json")
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_batch_export.py")

        batch_cfg = build_gui_batch_config(item, source_path, project_root, temp_dir, resolved_bodies)
        batch_cfg["result_file"] = result_file

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(batch_cfg, f, indent=2)

        cmd = [freecad_gui, script_path, config_path]
        gui_result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if gui_result.stderr:
            logger.debug(f"Batched GUI stderr: {gui_result.stderr[:1000]}")
            logger.info(f"Batched GUI stderr summary: {summarize_subprocess_stderr(gui_result.stderr)}")

        if not os.path.exists(result_file):
            log_warning_msg("Batched GUI run produced no result file")
            return results

        with open(result_file, encoding="utf-8") as f:
            batch_result = normalize_gui_batch_result(json.load(f))
        logger.info(summarize_gui_batch_result(batch_result))

        screenshot_result = batch_result["screenshots"]
        results["screenshot"] = {
            "success": bool(screenshot_result.get("success")),
            "result": screenshot_result,
        }
        if screenshot_result.get("success"):
            warn_on_near_uniform_images(screenshot_result.get("images", []))

        page_pdfs = [p.get("pdf_path") for p in batch_result["techdraw"]["pages"] if p.get("pdf_path")]
        if page_pdfs:
            final_pdf = os.path.abspath(os.path.join(project_root, "docs", f"{export_name}.pdf"))
            techdraw_success = merge_techdraw_pdfs(page_pdfs, final_pdf, temp_dir)
            results["techdraw"] = {"success": techdraw_success, "output": final_pdf}
            if techdraw_success:
                log_success(f"TechDraw PDF generated: {os.path.basename(final_pdf)}")
            else:
                log_warning_msg("TechDraw PDF generation failed in batched mode")

    return results


def run_gui_tasks_shared_session(gui_jobs, project_root):
    """Run GUI tasks for multiple export jobs in one GUI process."""
    if not gui_jobs:
        return {}
    freecad_gui = _find_freecad_gui_binary()
    if not freecad_gui:
        log_warning_msg("FreeCAD GUI binary not found; cannot run shared GUI session")
        return {}

    tools_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(tools_dir, "gui_batch_run.py")
    with tempfile.TemporaryDirectory(prefix="gui_run_") as temp_dir:
        result_file = os.path.join(temp_dir, "result.json")
        cfg_path = os.path.join(temp_dir, "run_config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"jobs": gui_jobs, "result_file": result_file}, f, indent=2)

        cmd = [freecad_gui, script_path, cfg_path]
        gui_result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if gui_result.stderr:
            logger.info(f"Shared GUI stderr summary: {summarize_subprocess_stderr(gui_result.stderr)}")
        if not os.path.exists(result_file):
            log_warning_msg("Shared GUI run produced no result file")
            return {}
        with open(result_file, encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("results", {})


def build_shared_gui_job(item, export_name, source, project_root, resolved_bodies, screenshots_only=False):
    """Build one shared-session GUI job payload from export item."""
    techdraw_cfg = item.get("techdraw") or {}
    screenshots_cfg = item.get("screenshots")

    techdraw_enabled = should_run_techdraw(techdraw_cfg, screenshots_only=screenshots_only)
    screenshot_enabled = bool(screenshots_cfg)

    screenshot_output_dir = None
    if screenshot_enabled:
        screenshot_output_dir = screenshots_cfg.get("output_dir")
        if screenshot_output_dir:
            if not os.path.isabs(screenshot_output_dir):
                screenshot_output_dir = os.path.abspath(os.path.join(project_root, screenshot_output_dir))
        else:
            screenshot_output_dir = os.path.abspath(os.path.join(project_root, "prints", "images"))

    return {
        "name": export_name,
        "source": source,
        "techdraw": {
            "enabled": techdraw_enabled,
            "pages": resolve_techdraw_pages(item),
            "temp_dir": os.path.join(project_root, "test_output", "_gui_pages", export_name),
            "output_dir": techdraw_cfg.get("output_dir", "docs"),
        },
        "screenshots": {
            "enabled": screenshot_enabled,
            "output_dir": screenshot_output_dir,
            "views": (screenshots_cfg or {}).get("views", ["isometric"]),
            "resolution": (screenshots_cfg or {}).get("resolution", [1920, 1080]),
            "format": (screenshots_cfg or {}).get("format", "png"),
            "composite": (screenshots_cfg or {}).get("composite", True),
            "bodies": resolve_screenshot_bodies(item, resolved_bodies),
        },
    }


logger.info("=" * 60)
logger.debug("Script starting")
logger.debug(f"Python version: {sys.version}")
logger.debug(f"Current directory: {os.getcwd()}")

# Default config file - can be overridden by command-line argument or auto-discovery
CONFIG_FILE = None
PROJECT_ROOT = None

# Determine config file priority: env var > CLI --config > CLI positional > auto-discovery
# Environment variables take precedence because export.py passes config via env vars,
# and CLI args may contain freecadcmd-specific paths that should be ignored.

# Always check for PROJECT_ROOT and CONFIG_FILE from environment first (set by export.py)
if "FREECAD_TOOLS_PROJECT_ROOT" in os.environ:
    PROJECT_ROOT = os.environ["FREECAD_TOOLS_PROJECT_ROOT"]
    logger.info(f"PROJECT_ROOT restored from environment: {PROJECT_ROOT}")

if "FREECAD_TOOLS_CONFIG" in os.environ:
    # Config passed via environment variable (from export.py) - takes highest priority
    CONFIG_FILE = os.environ["FREECAD_TOOLS_CONFIG"]
    logger.info(f"CONFIG_FILE restored from environment: {CONFIG_FILE}")

# If not set from environment, try CLI arguments
config_from_cli = args.config if args.config else args.config_file
if not CONFIG_FILE and config_from_cli:
    # Config explicitly provided via command line
    CONFIG_FILE = config_from_cli
    logger.debug(f"CONFIG_FILE from CLI: {CONFIG_FILE}")
    # Also set PROJECT_ROOT from config file directory if not already set
    if not PROJECT_ROOT:
        PROJECT_ROOT = os.path.dirname(os.path.abspath(CONFIG_FILE))
        logger.debug(f"Derived PROJECT_ROOT from config file: {PROJECT_ROOT}")

# If still no config, try command-line argument (legacy support) or auto-discovery
if not CONFIG_FILE:
    if len(sys.argv) > 1 and not config_from_cli:
        # Legacy: sys.argv[1] might be config file (when not using argparse)
        CONFIG_FILE = sys.argv[1]
        logger.debug(f"CONFIG_FILE from legacy command-line argument: {CONFIG_FILE}")
    else:
        # Auto-discover config file
        project_config = ".freecad_tools/export.yml"
        legacy_config = "export_config.yml"

        if os.path.exists(project_config):
            CONFIG_FILE = project_config
            logger.info(f"Auto-discovered per-project config: {CONFIG_FILE}")
        elif os.path.exists(legacy_config):
            CONFIG_FILE = legacy_config
            logger.info(f"Auto-discovered legacy config: {CONFIG_FILE}")
        else:
            logger.warning("Config not found. Will try to auto-discover in subprocess.")

# Check for test mode - skip FreeCAD detection and subprocess re-execution
_test_mode = os.environ.get("FREECAD_TOOLS_TEST_MODE", "").lower() in ("1", "true", "yes")
if _test_mode:
    logger.debug("Test mode enabled - skipping FreeCAD detection")
    # Define mock exit function

    def mock_exit(code=0):
        """Mock sys.exit for testing."""
        pass

    # Mock FreeCAD for testing purposes
    if "FreeCAD" not in sys.modules:
        sys.modules["FreeCAD"] = MagicMock()
    if "FreeCADGui" not in sys.modules:
        sys.modules["FreeCADGui"] = MagicMock()
    if "Mesh" not in sys.modules:
        sys.modules["Mesh"] = MagicMock()
    if "Part" not in sys.modules:
        sys.modules["Part"] = MagicMock()
    # Replace sys.exit if not already mocked
    if getattr(sys.exit, "__code__", None) is not mock_exit.__code__:
        sys.exit = mock_exit

freecad_found = False
try:
    import FreeCAD
    import Mesh
    import Part

    freecad_found = True

except ImportError as e:
    logger.warning(f"FreeCAD not found in current Python: {e}")
    logger.info("Attempting to find FreeCAD interpreter...")

    # Try to find FreeCAD Python interpreter
    freecad_interpreter = None

    # Common FreeCAD Python interpreter locations
    interpreter_paths = [
        "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
        "/opt/freecad/usr/bin/freecadcmd",
        "/opt/freecad/bin/freecadcmd",
        "/usr/bin/freecadcmd",
        "/usr/local/bin/freecadcmd",
    ]

    # PATH fallback for Linux/container installations
    path_freecadcmd = shutil.which("freecadcmd")
    if path_freecadcmd and path_freecadcmd not in interpreter_paths:
        interpreter_paths.append(path_freecadcmd)

    for path in interpreter_paths:
        logger.debug(f"Checking for FreeCAD interpreter at: {path}")
        if os.path.exists(path):
            freecad_interpreter = path
            logger.info(f"Found FreeCAD interpreter: {freecad_interpreter}")
            break

    if freecad_interpreter:
        logger.info(f"Re-executing script with FreeCAD interpreter: {freecad_interpreter}")

        # Pass CONFIG_FILE, PROJECT_ROOT, and mode flags to subprocess via environment variables
        env = os.environ.copy()
        if CONFIG_FILE:
            env["FREECAD_TOOLS_CONFIG"] = CONFIG_FILE
            logger.debug(f"Passing CONFIG_FILE via environment: {CONFIG_FILE}")
        if PROJECT_ROOT:
            env["FREECAD_TOOLS_PROJECT_ROOT"] = PROJECT_ROOT
            logger.debug(f"Passing PROJECT_ROOT via environment: {PROJECT_ROOT}")
        # Pass dry-run and verbose flags to subprocess
        if dry_run_mode:
            env["FREECAD_TOOLS_DRY_RUN"] = "true"
            logger.debug("Passing FREECAD_TOOLS_DRY_RUN=true to subprocess")
        if list_exports_mode:
            env["FREECAD_TOOLS_LIST_EXPORTS"] = "true"
            logger.debug("Passing FREECAD_TOOLS_LIST_EXPORTS=true to subprocess")
        if gui_only_mode:
            env["FREECAD_TOOLS_GUI_ONLY"] = "true"
            logger.debug("Passing FREECAD_TOOLS_GUI_ONLY=true to subprocess")
        if screenshots_only_mode:
            env["FREECAD_TOOLS_SCREENSHOTS_ONLY"] = "true"
            logger.debug("Passing FREECAD_TOOLS_SCREENSHOTS_ONLY=true to subprocess")
        if gui_session_mode:
            env["FREECAD_TOOLS_GUI_SESSION"] = gui_session_mode
            logger.debug(f"Passing FREECAD_TOOLS_GUI_SESSION={gui_session_mode} to subprocess")
        if verbose_cli or log_level_env:
            log_level_pass = "DEBUG" if verbose_cli else log_level_env
            env["FREECAD_TOOLS_LOG_LEVEL"] = log_level_pass
            logger.debug(f"Passing FREECAD_TOOLS_LOG_LEVEL={log_level_pass} to subprocess")

        # Run the script with the found interpreter
        # Note: Do NOT pass command-line arguments, as freecadcmd will try to parse them
        # and fail on unrecognized options like --dry-run.
        # Instead, all necessary information is passed via environment variables.
        result = subprocess.run([freecad_interpreter, __file__], env=env, capture_output=True, text=True)
        logger.info(f"Subprocess returned exit code: {result.returncode}")
        if result.stdout:
            logger.info(f"Subprocess STDOUT:\n{result.stdout}")
        if result.stderr:
            logger.info(f"Subprocess STDERR:\n{result.stderr}")
        # Exit with the subprocess result code
        sys.exit(result.returncode)
    else:
        logger.error("FreeCAD interpreter not found. Checked paths:")
        for path in interpreter_paths:
            logger.error(f"  - {path}")
        logger.error("Please install FreeCAD or adjust interpreter paths in this script")
        sys.exit(1)

# If we reach here, FreeCAD was found in the current Python environment
if not freecad_found:
    logger.error("FreeCAD import failed but no exception was raised - this should not happen")
    sys.exit(1)

logger.debug("FreeCAD modules successfully available, proceeding with main()")


def resolve_template_path(template_name):
    """
    Resolve template 3MF file path.
    Try locations in order:
    1. If template_name is None, use default template from examples/
    2. Check if template_name is absolute path that exists
    3. Check in current directory
    4. Check in project's .freecad_tools/ directory
    5. Fallback to examples/default.3mf if available

    Args:
        template_name: Name or path of template file, or None to use default

    Returns:
        Absolute path to template if found, None otherwise
    """
    # Try to find freecad_tools default template (examples/default.3mf)
    script_dir = os.path.dirname(os.path.abspath(__file__))  # tools/
    tools_root = os.path.dirname(script_dir)  # freecad_tools/
    default_template = os.path.join(tools_root, "examples", "default.3mf")

    # If no template specified, use default
    if not template_name:
        if os.path.exists(default_template):
            logger.debug(f"Using default template: {default_template}")
            return default_template
        else:
            logger.debug("No template specified and no default available")
            return None

    # Try as absolute path first
    if os.path.isabs(template_name) and os.path.exists(template_name):
        logger.debug(f"Found template at absolute path: {template_name}")
        return template_name

    # Try in current directory
    if os.path.exists(template_name):
        abs_path = os.path.abspath(template_name)
        logger.debug(f"Found template in current directory: {abs_path}")
        return abs_path

    # Try in .freecad_tools/ directory
    project_template = os.path.join(".freecad_tools", template_name)
    if os.path.exists(project_template):
        abs_path = os.path.abspath(project_template)
        logger.debug(f"Found template in .freecad_tools/: {abs_path}")
        return abs_path

    # Fallback to default template
    if os.path.exists(default_template):
        logger.info(f"Template '{template_name}' not found, using default: {default_template}")
        return default_template

    logger.warning(f"Template '{template_name}' not found and no default available")
    return None


# Body source mode options
BODY_SOURCE_CONFIG = "config"  # Bodies specified explicitly in config
BODY_SOURCE_PROPERTIES = "properties"  # Bodies selected via FreeCAD properties
BODY_SOURCE_OPTIONS = (BODY_SOURCE_CONFIG, BODY_SOURCE_PROPERTIES)

TECHDRAW_SOURCE_ALL = "all"
TECHDRAW_SOURCE_CONFIG = "config"
TECHDRAW_SOURCE_OPTIONS = (TECHDRAW_SOURCE_ALL, TECHDRAW_SOURCE_CONFIG)

SCREENSHOT_SOURCE_EXPORT = "export"
SCREENSHOT_SOURCE_CONFIG = "config"
SCREENSHOT_SOURCE_OPTIONS = (SCREENSHOT_SOURCE_EXPORT, SCREENSHOT_SOURCE_CONFIG)


def resolve_object_identifier(doc, identifier):
    """
    Resolve a FreeCAD object by Name or Label.
    User can specify either the internal Name (e.g., 'Body') or friendly Label (e.g., 'Feed').

    Args:
        doc: FreeCAD document
        identifier: Object Name or Label to find

    Returns:
        Tuple (obj, resolved_name, resolved_label) or (None, None, None) if not found
    """
    # First try exact Name match
    obj = doc.getObject(identifier)
    if obj is not None:
        label = obj.Label if hasattr(obj, "Label") else identifier
        logger.debug(f"Resolved '{identifier}' as Name → {obj.Name} (Label: {label})")
        return obj, obj.Name, label

    # Then try Label match (case-insensitive for user-friendliness)
    for obj in doc.Objects:
        if hasattr(obj, "Label") and obj.Label == identifier:
            logger.debug(f"Resolved '{identifier}' as Label → {obj.Name} (Label: {obj.Label})")
            return obj, obj.Name, obj.Label

    logger.warning(f"Could not resolve object '{identifier}' by Name or Label")
    return None, None, None


def find_exportable_bodies(doc):
    """
    Find all bodies in a FreeCAD document that have ExportTo3MF property set to True.

    This function scans all objects in the document and returns those that have
    the custom 'ExportTo3MF' property (App::PropertyBool) set to True.

    These bodies are used when body_source: properties is specified in the config.

    Args:
        doc: FreeCAD document

    Returns:
        List of FreeCAD objects that should be exported (have ExportTo3MF=True)
    """
    exportable = []
    try:
        for obj in doc.Objects:
            # Check for ExportTo3MF property
            if hasattr(obj, "ExportTo3MF"):
                export_flag = obj.ExportTo3MF
                if export_flag:
                    logger.debug(f"Found exportable body: {obj.Name} (Label: {getattr(obj, 'Label', 'N/A')})")
                    exportable.append(obj)
            # Also check with getattr for cases where property might not be directly accessible
            elif hasattr(obj, "getPropertyByName"):
                try:
                    export_flag = obj.getPropertyByName("ExportTo3MF")
                    if export_flag:
                        logger.debug(f"Found exportable body (via getPropertyByName): {obj.Name}")
                        exportable.append(obj)
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Error scanning for exportable bodies: {e}")

    logger.info(f"Found {len(exportable)} bodies with ExportTo3MF=True")
    return exportable


def get_body_export_properties(obj):
    """
    Read export-related properties from a FreeCAD body object.

    Reads the following custom properties:
    - ExportTo3MF (App::PropertyBool): Whether to export this body
    - ExportCount (App::PropertyInteger): Number of copies to export (default: 1)
    - ExportRotation (App::PropertyRotation): Orientation for export (FreeCAD.Rotation)

    Args:
        obj: FreeCAD object (typically a Part or Body)

    Returns:
        Dictionary with keys:
        - count: int (number of copies, default 1)
        - rotation: dict with {axis: [x, y, z], angle: deg} or None
        - position: list [x, y, z] or None (not yet implemented for properties)
    """
    props = {
        "count": 1,
        "rotation": None,
        "position": None,
    }

    try:
        # Read ExportCount
        if hasattr(obj, "ExportCount"):
            count = obj.ExportCount
            if isinstance(count, (int, float)) and count > 0:
                props["count"] = int(count)
                logger.debug(f"Body {obj.Name}: ExportCount = {props['count']}")
        elif hasattr(obj, "getPropertyByName"):
            try:
                count = obj.getPropertyByName("ExportCount")
                if isinstance(count, (int, float)) and count > 0:
                    props["count"] = int(count)
                    logger.debug(f"Body {obj.Name}: ExportCount (via getPropertyByName) = {props['count']}")
            except Exception:
                pass

        # Read ExportRotation (FreeCAD.Rotation object)
        if hasattr(obj, "ExportRotation"):
            rotation_obj = obj.ExportRotation
            if rotation_obj is not None:
                # FreeCAD.Rotation has .Axis (Vector) and .Angle (degrees)
                try:
                    axis = rotation_obj.Axis
                    angle_deg = rotation_obj.Angle
                    # Convert FreeCAD Vector to list
                    axis_list = [axis.x, axis.y, axis.z]
                    props["rotation"] = {
                        "axis": axis_list,
                        "angle": float(angle_deg),
                    }
                    logger.debug(f"Body {obj.Name}: ExportRotation = axis={axis_list}, angle={angle_deg}°")
                except Exception as e:
                    logger.warning(f"Failed to read ExportRotation from {obj.Name}: {e}")
        elif hasattr(obj, "getPropertyByName"):
            try:
                rotation_obj = obj.getPropertyByName("ExportRotation")
                if rotation_obj is not None:
                    axis = rotation_obj.Axis
                    angle_deg = rotation_obj.Angle
                    axis_list = [axis.x, axis.y, axis.z]
                    props["rotation"] = {
                        "axis": axis_list,
                        "angle": float(angle_deg),
                    }
                    logger.debug(
                        f"Body {obj.Name}: ExportRotation (via getPropertyByName) = axis={axis_list}, angle={angle_deg}°"
                    )
            except Exception:
                pass

    except Exception as e:
        logger.warning(f"Error reading export properties from {obj.Name}: {e}")

    return props


def validate_body_source_config(item):
    """
    Validate body_source configuration for an export item.

    Checks:
    - body_source is one of the valid options (config, properties)
    - If body_source is 'config', bodies list should be present
    - If body_source is 'properties', bodies list should be absent or empty
    - Issues deprecation warning if body_source is omitted

    Args:
        item: Export configuration item dict

    Returns:
        Tuple (is_valid: bool, body_source: str, warning_message: str or None)
    """
    body_source = item.get("body_source")
    bodies = item.get("bodies", [])

    if body_source is not None:
        # Validate body_source value
        if body_source not in BODY_SOURCE_OPTIONS:
            return False, body_source, f"Invalid body_source '{body_source}'. Must be one of: {BODY_SOURCE_OPTIONS}"

        # Check for conflicts
        if body_source == BODY_SOURCE_CONFIG and not bodies:
            return False, body_source, "body_source is 'config' but no bodies list provided"

        if body_source == BODY_SOURCE_PROPERTIES and bodies:
            return (
                False,
                body_source,
                "body_source is 'properties' but bodies list is also provided. "
                "Remove bodies list when using properties mode.",
            )

        return True, body_source, None

    # body_source not specified - backward compatibility
    # Infer from bodies presence
    if bodies:
        inferred_source = BODY_SOURCE_CONFIG
        warning = (
            "body_source not specified, inferring 'config' from bodies list. "
            "Explicitly set body_source: 'config' or body_source: 'properties' "
            "to avoid this warning."
        )
        return True, inferred_source, warning

    # No body_source and no bodies - use properties mode
    inferred_source = BODY_SOURCE_PROPERTIES
    warning = (
        "body_source not specified and no bodies list provided, "
        "defaulting to 'properties' mode. Bodies with ExportTo3MF=True will be exported. "
        "Explicitly set body_source: 'config' or body_source: 'properties' "
        "to avoid this warning."
    )
    return True, inferred_source, warning


def validate_gui_source_config(item):
    """Validate source selector fields for TechDraw and screenshot tasks."""
    name = item.get("name", "unnamed")

    techdraw_cfg = item.get("techdraw")
    if isinstance(techdraw_cfg, dict):
        techdraw_source = item.get("techdraw_source")
        if techdraw_source not in TECHDRAW_SOURCE_OPTIONS:
            return (
                False,
                f"Export item '{name}': techdraw_source must be one of {TECHDRAW_SOURCE_OPTIONS} when techdraw is set.",
            )
        pages = techdraw_cfg.get("pages", [])
        if techdraw_source == TECHDRAW_SOURCE_CONFIG and (not isinstance(pages, list) or not pages):
            return False, f"Export item '{name}': techdraw_source 'config' requires non-empty techdraw.pages"

    screenshot_cfg = item.get("screenshots")
    if isinstance(screenshot_cfg, dict):
        screenshot_source = item.get("screenshot_source")
        if screenshot_source not in SCREENSHOT_SOURCE_OPTIONS:
            return (
                False,
                f"Export item '{name}': screenshot_source must be one of {SCREENSHOT_SOURCE_OPTIONS} when screenshots is set.",
            )
        bodies = screenshot_cfg.get("bodies", [])
        if screenshot_source == SCREENSHOT_SOURCE_CONFIG and (not isinstance(bodies, list) or not bodies):
            return False, f"Export item '{name}': screenshot_source 'config' requires non-empty screenshots.bodies"

    return True, None


def parse_body_specs(bodies_config):
    """
    Parse body specifications from config, handling both simple and complex formats.

    Body specs can be:
    - String: Simple body identifier (Name or Label)
    - Dict: Object with 'body' field and optional 'rotation' and 'position' transforms

    Rotation can be specified in two formats:
    - Euler angles: [x_deg, y_deg, z_deg] (list of 3 numbers, existing format)
    - Axis+Angle: {"axis": [x, y, z], "angle": deg} (dict format, matches FreeCAD GUI)

    Args:
        bodies_config: List of body specifications (strings or dicts)

    Returns:
        List of tuples: (body_identifier, rotation_deg_or_dict, position_mm)
        where rotation can be:
        - None if not specified
        - [x, y, z] list for Euler angles (degrees)
        - {"axis": [x, y, z], "angle": deg} dict for axis+angle
        position is always a [x, y, z] list or None
    """
    parsed = []

    for body_spec in bodies_config:
        if isinstance(body_spec, str):
            # Simple string format: just the body identifier
            parsed.append((body_spec, None, None))
        elif isinstance(body_spec, dict):
            # Complex format with optional transforms
            body_id = body_spec.get("body")
            if not body_id:
                logger.warning(f"Body spec missing 'body' field: {body_spec}")
                continue

            rotation = body_spec.get("rotation")
            position = body_spec.get("position")

            # Validate rotation if provided
            if rotation is not None:
                if isinstance(rotation, dict):
                    # Axis+Angle format: {"axis": [x, y, z], "angle": deg}
                    if "axis" in rotation and "angle" in rotation:
                        axis = rotation.get("axis")
                        angle = rotation.get("angle")
                        if isinstance(axis, (list, tuple)) and len(axis) == 3:
                            if isinstance(angle, (int, float)):
                                # Valid axis+angle format, keep as-is
                                pass
                            else:
                                logger.warning(f"Invalid rotation angle (expected number): {angle}")
                                rotation = None
                        else:
                            logger.warning(f"Invalid rotation axis (expected 3-element list): {axis}")
                            rotation = None
                    else:
                        logger.warning(f"Invalid rotation dict (expected 'axis' and 'angle' keys): {rotation}")
                        rotation = None
                elif isinstance(rotation, (list, tuple)):
                    # Euler angle format: [x, y, z]
                    if len(rotation) != 3:
                        logger.warning(f"Invalid rotation (expected 3 values): {rotation}")
                        rotation = None
                    # Validate all are numbers
                    else:
                        try:
                            _ = [float(v) for v in rotation]
                        except (TypeError, ValueError):
                            logger.warning(f"Invalid rotation values (expected numbers): {rotation}")
                            rotation = None
                else:
                    logger.warning(f"Invalid rotation type (expected list or dict): {type(rotation)}")
                    rotation = None

            # Validate position if provided
            if position is not None:
                if isinstance(position, (list, tuple)) and len(position) == 3:
                    try:
                        _ = [float(v) for v in position]
                    except (TypeError, ValueError):
                        logger.warning(f"Invalid position values (expected numbers): {position}")
                        position = None
                else:
                    logger.warning(f"Invalid position (expected 3-element list): {position}")
                    position = None

            parsed.append((body_id, rotation, position))
        else:
            logger.warning(f"Unexpected body spec format: {body_spec}")

    return parsed


def resolve_relative_path(path, base_dir):
    """
    Resolve a path relative to a base directory.
    If path is already absolute, return as-is. If relative, join with base_dir.

    Args:
        path: The path to resolve (can be None, absolute, or relative)
        base_dir: The base directory for resolving relative paths

    Returns:
        Resolved absolute path, or None if path is None
    """
    if not path:
        return None
    if os.path.isabs(path):
        return path
    return os.path.join(base_dir, path)


def get_export_metadata(config_item, base_dir):
    """
    Extract metadata from config item and environment.

    Args:
        config_item: Export configuration item dict
        base_dir: Base directory for resolving relative paths

    Returns:
        Dictionary of metadata key-value pairs
    """
    metadata = {}

    # Add explicitly specified metadata from config
    export_metadata = config_item.get("metadata", {})
    if export_metadata:
        metadata.update(export_metadata)

    # Add git metadata if available and not already specified
    if git_utils and git_utils.is_git_repo(base_dir):
        try:
            git_meta = git_utils.get_git_metadata(cwd=base_dir)

            # Add git metadata with defaults
            if "GitCommit" not in metadata and git_meta.get("commit_short"):
                metadata["GitCommit"] = git_meta["commit_short"]
            if "GitCommitFull" not in metadata and git_meta.get("commit_hash"):
                metadata["GitCommitFull"] = git_meta["commit_hash"]
            if "GitBranch" not in metadata and git_meta.get("branch"):
                metadata["GitBranch"] = git_meta["branch"]
            if "GitTags" not in metadata and git_meta.get("tags"):
                metadata["GitTags"] = git_meta["tags"]
            if "GitRemote" not in metadata and git_meta.get("remote_url"):
                metadata["GitRemote"] = git_meta["remote_url"]

            logger.info(f"Added git metadata: {list(git_meta.keys())}")
        except Exception as e:
            logger.debug(f"Failed to get git metadata: {e}")
    else:
        logger.debug("Not in a git repository or git_utils not available")

    return metadata


def load_config():
    global CONFIG_FILE, PROJECT_ROOT

    # If CONFIG_FILE not set by command-line, determine default
    if not CONFIG_FILE:
        # Try .freecad_tools/export.yml first (per-project config)
        project_config = ".freecad_tools/export.yml"
        if os.path.exists(project_config):
            CONFIG_FILE = project_config
            logger.info(f"Using per-project config: {CONFIG_FILE}")
        # Fall back to export_config.yml in current directory
        elif os.path.exists("export_config.yml"):
            CONFIG_FILE = "export_config.yml"
            logger.info(f"Using legacy config: {CONFIG_FILE}")
        else:
            logger.error("Config file not found. Tried '.freecad_tools/export.yml' and 'export_config.yml'")
            sys.exit(1)

    logger.debug(f"Loading config from: {CONFIG_FILE}")
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"Config file '{CONFIG_FILE}' not found.")
        sys.exit(1)

    # Get the project root directory for path resolution
    # Use PROJECT_ROOT from environment if available (passed by export.py)
    # Otherwise, detect it from config file location
    if PROJECT_ROOT:
        base_dir = PROJECT_ROOT
        logger.info(f"Using PROJECT_ROOT from environment: {base_dir}")
    else:
        # Detect project root based on config file location
        # If config is in .freecad_tools/, resolve paths relative to parent (project root)
        # If config is in root (legacy), resolve relative to current directory
        config_path = os.path.abspath(CONFIG_FILE)
        config_dir = os.path.dirname(config_path)
        if os.path.basename(config_dir) == ".freecad_tools":
            # Config is in .freecad_tools/, use parent directory as base
            base_dir = os.path.dirname(config_dir)
        else:
            # Config is in project root (legacy), use its directory as base
            base_dir = config_dir
        logger.info(f"Detected project root from config location: {base_dir}")

    logger.debug(f"Base directory for path resolution: {base_dir}")
    logger.info(f"Loading YAML config from: {CONFIG_FILE}")

    with open(CONFIG_FILE) as f:
        content = f.read()
        logger.debug(f"Config file content:\n{content}")
        logger.info(f"Config file has {len(content)} characters")
        config = yaml.safe_load(content)
    logger.debug(f"Loaded config: {config}")
    if config is None:
        logger.error("Config file is empty or invalid YAML")
        sys.exit(1)
    result = config.get("export", [])
    logger.debug(f"Export list type: {type(result)}, length: {len(result) if isinstance(result, list) else 'N/A'}")
    logger.debug(f"Export list: {result}")

    # Resolve relative paths in config items relative to project root
    for item in result:
        # List of path fields to resolve
        path_fields = ["source", "output", "template", "stl_output_dir"]
        for field in path_fields:
            if field in item and item[field]:
                resolved = resolve_relative_path(item[field], base_dir)
                if resolved != item[field]:
                    logger.debug(f"Resolved {field} '{item[field]}' to: {resolved}")
                item[field] = resolved

        # Resolve nested paths in techdraw section
        if "techdraw" in item and isinstance(item["techdraw"], dict):
            td = item["techdraw"]
            if "output_dir" in td and td["output_dir"]:
                resolved = resolve_relative_path(td["output_dir"], base_dir)
                if resolved != td["output_dir"]:
                    logger.debug(f"Resolved techdraw.output_dir '{td['output_dir']}' to: {resolved}")
                td["output_dir"] = resolved

        # Resolve nested paths in bom section
        if "bom" in item and isinstance(item["bom"], dict):
            bom = item["bom"]
            if "output" in bom and bom["output"]:
                resolved = resolve_relative_path(bom["output"], base_dir)
                if resolved != bom["output"]:
                    logger.debug(f"Resolved bom.output '{bom['output']}' to: {resolved}")
                bom["output"] = resolved

        # Resolve nested paths in screenshots section
        screenshot_cfg = item.get("screenshots")
        if screenshot_cfg and isinstance(screenshot_cfg, dict):
            if "output_dir" in screenshot_cfg and screenshot_cfg["output_dir"]:
                resolved = resolve_relative_path(screenshot_cfg["output_dir"], base_dir)
                if resolved != screenshot_cfg["output_dir"]:
                    logger.debug(f"Resolved screenshots.output_dir '{screenshot_cfg['output_dir']}' to: {resolved}")
                screenshot_cfg["output_dir"] = resolved

        # Resolve nested paths in slicer section
        slicer_cfg = item.get("slicer")
        if slicer_cfg and isinstance(slicer_cfg, dict):
            for nested_path in ["output_dir", "config_bundle", "binary"]:
                if nested_path in slicer_cfg and slicer_cfg[nested_path]:
                    # Only resolve binary as a path if caller provided path-like content
                    if nested_path == "binary" and os.path.sep not in str(slicer_cfg[nested_path]):
                        continue
                    resolved = resolve_relative_path(slicer_cfg[nested_path], base_dir)
                    if resolved != slicer_cfg[nested_path]:
                        logger.debug(f"Resolved slicer.{nested_path} '{slicer_cfg[nested_path]}' to: {resolved}")
                    slicer_cfg[nested_path] = resolved

        # Validate body_source configuration
        is_valid, body_source_resolved, warning_msg = validate_body_source_config(item)
        if warning_msg:
            logger.warning(f"Export item '{item.get('name', 'unnamed')}': {warning_msg}")
        if not is_valid:
            logger.error(f"Export item '{item.get('name', 'unnamed')}': {warning_msg}")
            sys.exit(1)
        # Store resolved body_source in item for later use
        item["_body_source"] = body_source_resolved

        # Validate optional slicer configuration
        slicer_valid, slicer_error = validate_slicer_config(item)
        if not slicer_valid:
            logger.error(f"Export item '{item.get('name', 'unnamed')}': {slicer_error}")
            sys.exit(1)

        gui_valid, gui_error = validate_gui_source_config(item)
        if not gui_valid:
            logger.error(gui_error)
            sys.exit(1)

    return result


def export_bodies(doc, bodies, output_path):
    logger.debug(f"Available objects in document: {[obj.Name for obj in doc.Objects]}")
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    exported_any = False
    for body_name in bodies:
        obj = doc.getObject(body_name)
        if obj is None:
            logger.warning(f"Object '{body_name}' not found in document. Skipping.")
            continue
        if hasattr(obj, "Shape") and obj.Shape:
            # Get the label (user-friendly name) of the body
            body_label = obj.Label if hasattr(obj, "Label") else body_name
            logger.debug(f"Exporting shape from '{body_name}' (Label: {body_label})")
            try:
                # Calculate tessellation tolerance based on object size
                # For small parts, we need finer tolerance for better quality
                bbox = obj.Shape.BoundBox
                max_dimension = max(bbox.XLength, bbox.YLength, bbox.ZLength)
                # Use 0.1% of the largest dimension as tolerance (minimum 0.001mm)
                tessellation_tolerance = max(0.001, max_dimension * 0.001)
                logger.debug(
                    f"Object size: {max_dimension:.2f}mm, using tessellation tolerance: {tessellation_tolerance:.4f}mm"
                )

                # Generate filename with body label
                output_base = str(output_path)
                if output_base.endswith((".stl", ".3mf")):
                    output_base = output_base.rsplit(".", 1)[0]
                # Sanitize label for filename
                safe_label = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in body_label)
                output_file = f"{output_base}-{safe_label}.stl"

                logger.debug(
                    f"Creating mesh from '{body_name}' with tessellation tolerance {tessellation_tolerance:.4f}mm"
                )
                mesh = Mesh.Mesh(obj.Shape.tessellate(tessellation_tolerance))
                logger.info(f"Mesh created with {len(mesh.Facets)} facets")

                # Write mesh to file
                mesh.write(output_file)
                logger.info(f"Exported '{body_label}' ({body_name}) to '{output_file}'")
                exported_any = True
            except Exception as e:
                logger.error(f"Failed to export '{body_name}': {e}")
        else:
            logger.warning(f"Object '{body_name}' has no Shape. Skipping.")
    if not exported_any:
        logger.error(f"No objects exported from '{output_path}'.")
        return False
    return True


def export_full_doc(doc, output_path):
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    logger.debug(f"Exporting full document to {output_path}")
    doc.save()

    # For FreeCAD documents, we need to use the document's built-in export
    # Try using Part Design workbench export if available
    try:
        doc.export3MF(output_path)
    except AttributeError:
        # Fallback: try using Part workbench export
        logger.warning("Document export3MF not available, trying Part.exportShape")
        # Export the active body or first body
        bodies = [obj for obj in doc.Objects if hasattr(obj, "Shape") and obj.Shape]
        if bodies:
            Part.export(bodies[0].Shape, output_path)
        else:
            logger.error("No exportable shapes found in document")
            return False
    logger.info(f"Exported full document to '{output_path}'")
    return True


def export_bodies_to_3mf_with_template(
    doc,
    bodies,
    output_path,
    template_path=None,
    keep_stl=False,
    stl_output_dir=None,
    export_name="",
    metadata=None,
):
    """
    Export bodies to 3MF format using lib3mf (via subprocess).
    Optionally uses a template 3MF file for metadata/settings preservation.

    Args:
        doc: FreeCAD document
        bodies: List of body identifiers or specs. Can be:
                - Strings: body Name or Label
                - Dicts: {"body": "name", "rotation": [x,y,z], "position": [x,y,z]}
        output_path: Output 3MF file path
        template_path: Optional path to a template 3MF file
        keep_stl: If True, keep generated STL files in stl_output_dir
        stl_output_dir: Directory to place STL files (defaults to temp if keep_stl=False)
        export_name: Export item name (used to prefix STL files)
        metadata: Optional dictionary of metadata to embed in the 3MF file
    """
    logger.debug(f"Exporting bodies to 3MF with template: {template_path}")

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Determine where to put STL files
    if keep_stl and stl_output_dir:
        os.makedirs(stl_output_dir, exist_ok=True)
        stl_dir = stl_output_dir
        temp_dir = None
    else:
        temp_dir = tempfile.TemporaryDirectory()
        stl_dir = temp_dir.name

    try:
        # Parse body specifications (can include transforms)
        parsed_bodies = parse_body_specs(bodies)
        logger.debug(f"Parsed {len(parsed_bodies)} body specifications")

        # Export bodies to STL files
        stl_files = []
        transforms = []  # Parallel list of transforms
        body_count = {}  # Track duplicate body exports

        for body_id, rotation, position in parsed_bodies:
            # Resolve object by Name or Label
            obj, obj_name, obj_label = resolve_object_identifier(doc, body_id)

            if obj is None:
                logger.warning(f"Object '{body_id}' not found. Skipping.")
                continue

            if not (hasattr(obj, "Shape") and obj.Shape):
                logger.warning(f"Object '{obj_name}' has no Shape. Skipping.")
                continue

            try:
                # Calculate tessellation tolerance based on object size
                bbox = obj.Shape.BoundBox
                max_dimension = max(bbox.XLength, bbox.YLength, bbox.ZLength)
                tessellation_tolerance = max(0.001, max_dimension * 0.001)

                # Track duplicate bodies (e.g., exporting same body twice)
                body_key = obj_name
                if body_key not in body_count:
                    body_count[body_key] = 0
                body_count[body_key] += 1

                # Generate STL filename with export name prefix and body label
                # If exporting same body multiple times, append count suffix
                stl_filename = f"{export_name}_{obj_label}"
                if body_count[body_key] > 1:
                    stl_filename = f"{export_name}_{obj_label}_{body_count[body_key]}"

                # Sanitize filename
                stl_filename = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in stl_filename)
                stl_file = os.path.join(stl_dir, f"{stl_filename}.stl")

                # Export STL
                mesh = Mesh.Mesh(obj.Shape.tessellate(tessellation_tolerance))
                mesh.write(stl_file)
                logger.info(f"Created STL for '{obj_label}': {len(mesh.Facets)} facets → {stl_filename}.stl")

                # Use export_name_body_label for the 3MF mesh object label
                mesh_label = f"{export_name}_{obj_label}"
                if body_count[body_key] > 1:
                    mesh_label = f"{export_name}_{obj_label}_{body_count[body_key]}"

                stl_files.append((mesh_label, stl_file))

                # Collect transform for this body
                transform_dict = {}
                if rotation:
                    transform_dict["rotation"] = rotation
                if position:
                    transform_dict["position"] = position

                transforms.append(transform_dict if transform_dict else None)
                logger.debug(f"Body '{obj_label}': rotation={rotation}, position={position}")

            except Exception as e:
                logger.error(f"Failed to create STL for '{obj_name}': {e}")

        if not stl_files:
            logger.error("No valid bodies to export to 3MF")
            return False

        # Ensure output_path is absolute before passing to subprocess
        abs_output_path = os.path.abspath(output_path)
        logger.debug(f"Output path (absolute): {abs_output_path}")

        # Call lib3mf via subprocess to create 3MF
        logger.info(f"Creating 3MF with {len(stl_files)} embedded meshes via lib3mf")

        # Build config for lib3mf subprocess
        lib3mf_config = {
            "output_path": abs_output_path,
            "stl_files": [{"label": label, "path": path} for label, path in stl_files],
        }

        # Add transforms if any are specified
        if any(transforms):
            lib3mf_config["transforms"] = [
                {"rotation": t.get("rotation"), "position": t.get("position")} if t else None for t in transforms
            ]
            logger.debug(f"Added {len([t for t in transforms if t])} body transforms to lib3mf config")

        if template_path and os.path.exists(template_path):
            lib3mf_config["template_path"] = template_path

        # Add metadata if provided
        if metadata:
            lib3mf_config["metadata"] = metadata
            logger.debug(f"Added metadata to lib3mf config: {list(metadata.keys())}")

        # Write config to temp JSON file
        config_file = os.path.join(stl_dir, "_lib3mf_config.json")
        with open(config_file, "w") as f:
            json.dump(lib3mf_config, f)

        # Call lib3mf_utils.py via subprocess using a Python with lib3mf installed
        # First check if lib3mf Python was passed via environment (original Python before FreeCAD takeover)
        script_dir = os.path.dirname(__file__)
        lib3mf_script = os.path.join(script_dir, "lib3mf_utils.py")

        # Try to use the lib3mf Python passed from export.py (original Python with lib3mf)
        lib3mf_python = os.environ.get("FREECAD_TOOLS_LIB3MF_PYTHON")
        if lib3mf_python:
            python_executable = lib3mf_python
            logger.debug(f"Using lib3mf Python from environment: {python_executable}")
        else:
            # Fallback: try venv or sys.executable
            venv_python = os.path.join(os.path.dirname(script_dir), ".venv", "bin", "python3")
            venv_python = os.path.abspath(venv_python)
            python_executable = venv_python if os.path.exists(venv_python) else sys.executable
            logger.debug(f"Using fallback Python: {python_executable}")

        logger.debug(f"Calling lib3mf: {python_executable} {lib3mf_script} create-from-json {config_file}")

        result = subprocess.run(
            [python_executable, lib3mf_script, "create-from-json", config_file],
            capture_output=True,
            text=True,
        )

        # Log subprocess output
        if result.stdout:
            logger.info(f"lib3mf: {result.stdout.strip()}")
        if result.stderr:
            logger.debug(f"lib3mf STDERR:\n{result.stderr}")

        if result.returncode != 0:
            logger.error(f"lib3mf subprocess failed with exit code {result.returncode}")
            return False

        # Verify the 3MF file was actually created
        if not os.path.exists(abs_output_path):
            logger.error(f"3MF file was not created at {abs_output_path}")
            logger.error("lib3mf reported success but file does not exist - this is a critical issue")
            return False

        # Get file stats for logging
        file_size = os.path.getsize(abs_output_path)
        logger.info(f"Successfully created 3MF: {abs_output_path} ({file_size} bytes)")
        return True

    except Exception as e:
        logger.error(f"Failed to export to 3MF: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return False

    finally:
        # Clean up temp directory if we created one
        if temp_dir:
            temp_dir.cleanup()


def _find_venv_python():
    """Find the venv Python executable for subprocess calls."""
    lib3mf_python = os.environ.get("FREECAD_TOOLS_LIB3MF_PYTHON")
    if lib3mf_python:
        return lib3mf_python
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(os.path.dirname(script_dir), ".venv", "bin", "python3")
    venv_python = os.path.abspath(venv_python)
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable


def _find_freecad_gui_binary():
    """
    Find the FreeCAD GUI binary for TechDraw PDF export and screenshot generation.

    TechDrawGui.exportPageAsPdf() and body screenshot generation require
    the GUI binary (not freecadcmd).
    As of FreeCAD 1.1, there is no offline/headless API for pixel-perfect
    TechDraw PDF export — check future FreeCAD releases for improvements.

    Returns:
        Path to FreeCAD GUI binary, or None if not found
    """
    gui_paths = [
        # macOS
        "/Applications/FreeCAD.app/Contents/MacOS/FreeCAD",
        # Linux common locations
        "/usr/bin/freecad",
        "/usr/local/bin/freecad",
        "/opt/freecad/bin/freecad",
        # Snap/Flatpak
        "/snap/freecad/current/bin/freecad",
    ]

    # Also check env var override
    env_path = os.environ.get("FREECAD_GUI_BINARY")
    if env_path and os.path.exists(env_path):
        return env_path

    for path in gui_paths:
        if os.path.exists(path):
            return path

    return None


def export_techdraw_to_pdf(doc, pages_to_export, output_path, bom_csv_path=None, instructions_path=None, metadata=None):
    """
    Export TechDraw pages to a multi-page PDF.

    Two-step pipeline:
    1. Export individual page PDFs via FreeCAD GUI binary (TechDrawGui.exportPageAsPdf)
    2. Merge page PDFs + BOM table + instructions via venv subprocess (techdraw_pdf.py)

    Args:
        doc: FreeCAD document (used to get source path and page names)
        pages_to_export: List of page names/labels (empty = all pages)
        output_path: Path for the output PDF file
        bom_csv_path: Optional path to BOM CSV to include in PDF
        instructions_path: Optional path to instructions markdown to include in PDF
        metadata: Optional dict with document metadata for cover page

    Returns:
        True on success, False on failure
    """
    try:
        # Step 1: Export individual page PDFs via FreeCAD GUI binary
        freecad_gui = _find_freecad_gui_binary()
        if not freecad_gui:
            logger.error(
                "FreeCAD GUI binary not found. TechDraw PDF export requires the GUI binary. "
                "Set FREECAD_GUI_BINARY environment variable or install FreeCAD in a standard location."
            )
            return False

        # Get the source document path
        source_path = doc.FileName
        if not source_path:
            logger.error("Document has no file path — save it first")
            return False

        # Create temp directory for individual page PDFs (cleaned up automatically)
        with tempfile.TemporaryDirectory(prefix="techdraw_") as temp_dir:
            return _run_techdraw_pipeline(
                doc,
                pages_to_export,
                output_path,
                temp_dir,
                bom_csv_path=bom_csv_path,
                instructions_path=instructions_path,
                metadata=metadata,
                freecad_gui=freecad_gui,
            )

    except Exception as e:
        logger.exception(f"Error exporting TechDraw to PDF: {e}")
        return False


def _run_techdraw_pipeline(
    doc,
    pages_to_export,
    output_path,
    temp_dir,
    bom_csv_path=None,
    instructions_path=None,
    metadata=None,
    freecad_gui=None,
):
    """Inner pipeline for TechDraw PDF export, runs inside a TemporaryDirectory context."""
    result_file = os.path.join(temp_dir, "result.json")

    # Build config for techdraw_export.py
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    export_script = os.path.join(tools_dir, "techdraw_export.py")

    source_path = doc.FileName

    export_config = {
        "source": source_path,
        "pages": pages_to_export if pages_to_export else None,
        "output_dir": temp_dir,
        "result_file": result_file,
    }

    config_path = os.path.join(temp_dir, "export_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(export_config, f, indent=2)

    cmd = [freecad_gui, export_script, config_path]
    logger.info(f"Exporting TechDraw pages via GUI: {freecad_gui}")
    logger.debug(f"Running: {' '.join(cmd)}")

    gui_result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if gui_result.stdout:
        logger.debug(f"GUI export stdout: {gui_result.stdout[:500]}")
    if gui_result.stderr:
        logger.debug(f"GUI export stderr: {gui_result.stderr[:500]}")

    # Read result
    if not os.path.exists(result_file):
        logger.error(f"GUI export produced no result file. Exit code: {gui_result.returncode}")
        return False

    with open(result_file, encoding="utf-8") as f:
        export_result = json.load(f)

    if not export_result.get("success"):
        logger.error(f"GUI export failed: {export_result.get('error', 'unknown error')}")
        return False

    page_pdfs = [p["pdf_path"] for p in export_result["pages"] if p.get("pdf_path")]
    if not page_pdfs and not bom_csv_path and not instructions_path:
        logger.warning("No TechDraw pages exported and no BOM/instructions to include")
        return False

    logger.info(f"Exported {len(page_pdfs)} TechDraw page PDF(s)")

    # Step 2: Merge page PDFs + BOM + instructions via venv subprocess
    pdf_script = os.path.join(tools_dir, "techdraw_pdf.py")
    venv_python = _find_venv_python()

    merge_config = {
        "page_pdfs": page_pdfs,
        "output_path": os.path.abspath(output_path),
    }
    if bom_csv_path:
        merge_config["bom_csv_path"] = os.path.abspath(bom_csv_path)
    if instructions_path:
        merge_config["instructions_path"] = os.path.abspath(instructions_path)
    if metadata:
        merge_config["metadata"] = metadata

    merge_config_path = os.path.join(temp_dir, "merge_config.json")
    with open(merge_config_path, "w", encoding="utf-8") as f:
        json.dump(merge_config, f, indent=2)

    merge_cmd = [venv_python, pdf_script, merge_config_path]
    logger.info(f"Merging PDF: {output_path}")
    logger.debug(f"Running: {' '.join(merge_cmd)}")

    merge_result = subprocess.run(merge_cmd, capture_output=True, text=True, timeout=120)

    if merge_result.stdout:
        logger.debug(f"PDF merger stdout: {merge_result.stdout[:500]}")
    if merge_result.stderr:
        logger.debug(f"PDF merger stderr: {merge_result.stderr[:500]}")

    if merge_result.returncode != 0:
        logger.error(f"PDF merge failed (exit code {merge_result.returncode})")
        return False

    if os.path.exists(output_path):
        logger.info(f"PDF generated: {output_path} ({os.path.getsize(output_path)} bytes)")
        return True

    logger.error(f"PDF merge completed but file not found: {output_path}")
    return False


def run_screenshot_generation(export_item, project_root):
    """
    Run screenshot generation for an export item.

    This function runs body_screenshot.py via FreeCAD GUI binary
    to generate screenshots of the exported bodies.

    Args:
        export_item: The export configuration dictionary
        project_root: The project root directory

    Returns:
        Tuple (success: bool, result: dict) where result contains 'images' on success
    """
    logger.info(f"run_screenshot_generation called with export_item name: {export_item.get('name')}")

    # Load the helper module from tools/ explicitly so pylint/CI doesn't depend on PYTHONPATH.
    # Also set a guard so importing the file does not execute main().
    import importlib.util
    import sys as _sys

    _sys._body_screenshot_skip_main = True  # noqa: SLF001
    try:
        tools_dir = os.path.dirname(os.path.abspath(__file__))
        body_screenshot_py = os.path.join(tools_dir, "body_screenshot.py")
        spec = importlib.util.spec_from_file_location("body_screenshot", body_screenshot_py)
        if not spec or not spec.loader:
            raise ImportError("Unable to load body_screenshot module spec")
        body_screenshot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(body_screenshot)
        logger.info("Successfully loaded body_screenshot module")
    except Exception as e:
        logger.error(f"Failed to load body_screenshot module: {e}")
        return False, {"success": False, "images": [], "error": f"Import error: {e}"}
    finally:
        if hasattr(_sys, "_body_screenshot_skip_main"):
            del _sys._body_screenshot_skip_main

    # Get screenshot config from export item
    raw_screenshot_cfg = body_screenshot.get_screenshot_config(export_item)
    logger.info(f"Raw screenshot config from export item: {raw_screenshot_cfg}")

    if not raw_screenshot_cfg.get("enabled", False):
        logger.info("Screenshots not enabled for this export item (skipping)")
        return True, {"success": True, "images": [], "error": None, "skipped": True}

    logger.info("Screenshots enabled - proceeding with generation")

    # Validate config
    try:
        body_screenshot.validate_screenshot_config(raw_screenshot_cfg)
    except ValueError as e:
        logger.warning(f"Invalid screenshot config: {e}")
        return False, {"success": False, "images": [], "error": str(e)}

    # Build full screenshot config (preflight only; GUI process reads YAML directly)
    body_screenshot.build_screenshot_config(export_item, raw_screenshot_cfg)

    # Find FreeCAD GUI binary
    freecad_gui = _find_freecad_gui_binary()
    logger.info(f"Screenshot GUI binary path: {freecad_gui}")
    if freecad_gui:
        logger.info(f"GUI binary exists: {os.path.exists(freecad_gui)}")
    if not freecad_gui:
        logger.warning(
            "FreeCAD GUI binary not found. Screenshot generation requires the GUI binary. "
            "Set FREECAD_GUI_BINARY environment variable or install FreeCAD in a standard location."
        )
        return (
            False,
            {
                "success": False,
                "images": [],
                "error": "FreeCAD GUI binary not found. Screenshot generation requires GUI binary.",
            },
        )

    # Ensure source file exists (resolved earlier in load_config)
    source_path = export_item.get("source", "")
    if not os.path.exists(source_path):
        logger.warning(f"Screenshot source file not found: {source_path}")
        return False, {"success": False, "images": [], "error": f"Source file not found: {source_path}"}

    # Create temp directory for result exchange only; screenshot script reads YAML config directly.
    with tempfile.TemporaryDirectory(prefix="screenshot_") as tmpdir:
        result_path = os.path.join(tmpdir, "result.json")

        tools_dir = os.path.dirname(os.path.abspath(__file__))
        body_screenshot_path = os.path.join(tools_dir, "body_screenshot.py")

        # IMPORTANT: invoking the GUI binary with a script path can leave the full app open
        # and/or depend on the Qt main loop. For automation we run in console mode (-c)
        # and exec() the script, then rely on the script's sys.exit().
        cmd = [
            freecad_gui,
            "-c",
            (
                "import os,sys; "
                f"os.chdir({tmpdir!r}); "
                f"sys.path.insert(0,{tools_dir!r}); "
                f"exec(open({body_screenshot_path!r}).read())"
            ),
        ]

        env = os.environ.copy()
        # Pass selection to the GUI process; body_screenshot.py will read YAML itself.
        if os.environ.get("FREECAD_TOOLS_CONFIG"):
            env["FREECAD_TOOLS_CONFIG"] = os.environ["FREECAD_TOOLS_CONFIG"]
        elif CONFIG_FILE:
            env["FREECAD_TOOLS_CONFIG"] = str(CONFIG_FILE)
        if project_root:
            env["FREECAD_TOOLS_PROJECT_ROOT"] = str(project_root)
        if export_item.get("name"):
            env["FREECAD_TOOLS_NAME"] = export_item.get("name")
        env["FREECAD_TOOLS_SCREENSHOT_RESULT"] = result_path
        # Avoid GUI hangs on some FreeCAD builds.
        env.setdefault("FREECAD_TOOLS_SCREENSHOT_RECOMPUTE", "false")

        logger.info(f"Generating screenshots via GUI: {freecad_gui}")
        logger.debug(f"Command: {' '.join(cmd)}")
        logger.debug(f"Working directory: {project_root or os.getcwd()}")

        gui_result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=(project_root or os.getcwd()),
        )

        logger.debug(f"Screenshot GUI exit code: {gui_result.returncode}")

        if gui_result.stdout:
            stdout_str = gui_result.stdout
            # Print full stdout if not too long, otherwise truncate
            if len(stdout_str) > 2000:
                logger.info(f"Screenshot stdout (first 1000 chars): {stdout_str[:1000]}")
                logger.info(f"Screenshot stdout (last 1000 chars): {stdout_str[-1000:]}")
            else:
                logger.info(f"Screenshot stdout: {stdout_str}")
        if gui_result.stderr:
            stderr_str = gui_result.stderr
            if len(stderr_str) > 2000:
                logger.warning(f"Screenshot stderr (first 1000 chars): {stderr_str[:1000]}")
                logger.warning(f"Screenshot stderr (last 1000 chars): {stderr_str[-1000:]}")
            else:
                logger.warning(f"Screenshot stderr: {stderr_str}")

        # Read result
        if os.path.exists(result_path):
            with open(result_path, encoding="utf-8") as f:
                result = json.load(f)
            return gui_result.returncode == 0, result

        # No result file
        error_msg = f"Screenshot GUI produced no result file. Exit code: {gui_result.returncode}"
        logger.error(error_msg)
        return (
            False,
            {"success": False, "images": [], "error": error_msg, "exit_code": gui_result.returncode},
        )


def _col_index_to_letter(col_idx):
    """Convert a 1-based column index to Excel-style letter(s).

    Examples: 1→A, 26→Z, 27→AA, 52→AZ, 53→BA, 702→ZZ
    """
    result = []
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result.append(chr(65 + remainder))
    return "".join(reversed(result))


def extract_bom_from_assembly(doc, custom_fields=None, assembly_name=None):
    """
    Extract Bill of Materials directly from Assembly::BomObject.

    Reads the embedded spreadsheet in the Assembly::BomObject (native FreeCAD 1.0+).
    This respects what the user explicitly configured in the BOM, rather than walking the tree.

    Args:
        doc: FreeCAD document
        custom_fields: List of custom property names to extract (e.g., ["URL", "Price", "Material"])
                      Note: These are inferred from BomObject columns if present.
        assembly_name: Optional name or label of the assembly to extract BOM from.
                       If None, uses the first BomObject found.

    Returns:
        List of BOM row dicts with all columns from BomObject as keys
        E.g., [{"Index": "1", "Name": "Sphere", "Description": "", "File Name": "...", "Quantity": "1"}, ...]
    """
    bom = []

    if custom_fields is None:
        custom_fields = []

    try:
        # Find Assembly::BomObject
        bom_obj = None
        for obj in doc.Objects:
            if hasattr(obj, "TypeId") and "BomObject" in obj.TypeId:
                # If assembly_name is specified, match against Name or Label
                if assembly_name:
                    obj_name = obj.Name
                    obj_label = obj.Label if hasattr(obj, "Label") else None
                    # Try to find the parent assembly of this BomObject
                    # BomObject is typically a child of an Assembly object
                    if hasattr(obj, "Parent"):
                        parent_obj = obj.Parent
                        parent_name = parent_obj.Name if hasattr(parent_obj, "Name") else None
                        parent_label = parent_obj.Label if hasattr(parent_obj, "Label") else None
                        # Match against parent assembly name or label
                        if parent_name == assembly_name or parent_label == assembly_name:
                            bom_obj = obj
                            break
                        # Also check if the BomObject itself matches
                        elif obj_name == assembly_name or obj_label == assembly_name:
                            bom_obj = obj
                            break
                else:
                    # No specific assembly requested, use first found (backward compatible)
                    bom_obj = obj
                    break

        if bom_obj is None:
            if assembly_name:
                logger.info(f"No Assembly::BomObject found for assembly '{assembly_name}' in document")
            else:
                logger.info("No Assembly::BomObject found in document")
            return bom

        logger.info(f"Found Assembly::BomObject: {bom_obj.Name} (Label: {bom_obj.Label})")
        if assembly_name:
            logger.info(f"  (matched assembly: {assembly_name})")

        # Access the embedded spreadsheet via cells property
        cells = bom_obj.cells
        if cells is None:
            logger.warning("BomObject has no cells/spreadsheet")
            return bom

        # Extract column headers from row 1
        headers = []
        col_idx = 1
        while True:
            # Convert column index to letter: 1=A, 2=B, ..., 27=AA, etc.
            col_letter = _col_index_to_letter(col_idx)

            cell_addr = col_letter + "1"
            try:
                header = cells[cell_addr]
                if header is None or header == "":
                    break
                # Remove leading apostrophe used by FreeCAD for text formatting
                header = header.strip("'")
                headers.append(header)
                col_idx += 1
            except Exception as e:
                logger.debug(f"Error reading header {cell_addr}: {e}")
                break

        logger.info(f"Found {len(headers)} BOM columns: {headers}")

        if not headers:
            logger.warning("BomObject has no column headers")
            return bom

        # Map BomObject column names to standard BOM field names for consistency
        # Common BomObject columns: Index, Name, Description, File Name, Quantity, etc.
        # Standard BOM fields: label, quantity, description, file_name, index, name, etc.
        column_mapping = {
            "Name": "label",
            "Index": "index",
            "Quantity": "quantity",
            "Description": "description",
            "File Name": "file_name",
            "Part Number": "part_number",
            "Material": "material",
        }

        # Extract data rows
        row_idx = 2
        while True:
            row_data = {}
            row_empty = True

            for col_idx, header in enumerate(headers, start=1):
                # Convert column index to letter
                col_letter = _col_index_to_letter(col_idx)

                cell_addr = col_letter + str(row_idx)
                try:
                    val = cells[cell_addr]
                    if val is not None and val != "":
                        row_empty = False
                    # Convert to string first (cells may return int), then strip apostrophe
                    val_str = str(val) if val is not None else ""
                    val_str = val_str.strip("'").strip()

                    # Map header to standard field name
                    mapped_header = column_mapping.get(header, header)
                    row_data[mapped_header] = val_str
                except Exception as e:
                    logger.debug(f"Error reading cell {cell_addr}: {e}")
                    mapped_header = column_mapping.get(header, header)
                    row_data[mapped_header] = ""

            if row_empty:
                # End of data rows
                break

            bom.append(row_data)
            logger.debug(f"Row {row_idx}: {row_data}")
            row_idx += 1

        logger.info(f"Extracted {len(bom)} rows from BomObject")

    except Exception as e:
        logger.exception(f"Error extracting BomObject: {e}")

    return bom


def extract_bom_from_spreadsheet(doc, spreadsheet_name=None, custom_fields=None):
    """
    Extract Bill of Materials from a FreeCAD Spreadsheet.

    Reads cells from a spreadsheet object to build BOM.

    Args:
        doc: FreeCAD document
        spreadsheet_name: Name/Label of spreadsheet to read (default: "BOM")
        custom_fields: List of custom property names to extract

    Returns:
        List of BOM dicts
    """
    bom = []

    if spreadsheet_name is None:
        spreadsheet_name = "BOM"

    if custom_fields is None:
        custom_fields = []

    try:
        # Find spreadsheet object
        sheet_obj = None
        for obj in doc.Objects:
            if hasattr(obj, "TypeId") and obj.TypeId == "Spreadsheet::Sheet":
                if obj.Name == spreadsheet_name or (hasattr(obj, "Label") and obj.Label == spreadsheet_name):
                    sheet_obj = obj
                    break

        if sheet_obj is None:
            logger.warning(f"Spreadsheet '{spreadsheet_name}' not found")
            return bom

        logger.info(f"Reading BOM from spreadsheet: {spreadsheet_name}")

        # Get non-empty cells range
        try:
            # Try getUsedRange() if available (newer FreeCAD)
            if hasattr(sheet_obj, "getUsedRange"):
                start_cell, end_cell = sheet_obj.getUsedRange()
                logger.debug(f"Used range: {start_cell} to {end_cell}")
            else:
                # Fallback: assume data starts at A1
                start_cell = "A1"
                end_cell = None
        except Exception as e:
            logger.debug(f"Could not determine cell range: {e}")
            # Assume standard BOM format with header in row 1
            start_cell = "A1"

        # Read spreadsheet cells (simplified: assumes standard BOM table format)
        # Expected format: Column A = Label, Column B = Quantity, etc.
        try:
            # Get all non-empty cells
            if hasattr(sheet_obj, "getNonEmptyCells"):
                cells = sheet_obj.getNonEmptyCells()
                logger.debug(f"Found {len(cells)} non-empty cells")

                # Group by row and build BOM items
                rows = {}
                for cell_addr in cells:
                    # Parse cell address (e.g., "A1" → (1, 'A'))
                    # Extract row number
                    row_num = int("".join(c for c in cell_addr if c.isdigit()))
                    col_letter = "".join(c for c in cell_addr if c.isalpha())

                    if row_num not in rows:
                        rows[row_num] = {}
                    try:
                        cell_value = sheet_obj.getContents(cell_addr)
                        rows[row_num][col_letter] = cell_value
                    except Exception:
                        pass

                # Skip header row (row 1), build BOM from data rows
                for row_num in sorted(rows.keys()):
                    if row_num == 1:  # Skip header
                        continue

                    row = rows[row_num]
                    # Assume: A=Label, B=Quantity, C+=custom fields
                    if "A" in row:
                        bom_item = {
                            "label": str(row.get("A", "")),
                            "quantity": int(row.get("B", "1")),
                        }

                        # Map remaining columns to custom fields
                        col_letters = ["C", "D", "E", "F", "G", "H", "I", "J"]
                        for i, field_name in enumerate(custom_fields):
                            if i < len(col_letters) and col_letters[i] in row:
                                bom_item[field_name.lower()] = str(row[col_letters[i]])

                        bom.append(bom_item)

        except Exception as e:
            logger.warning(f"Error reading spreadsheet cells: {e}")

        logger.info(f"Extracted {len(bom)} items from spreadsheet")

    except Exception as e:
        logger.exception(f"Error extracting Spreadsheet BOM: {e}")

    return bom


def extract_bom_from_parts(doc, custom_fields=None):
    """
    Extract Bill of Materials by inspecting Part and Body objects directly.

    Fallback BOM generation when Assembly/Spreadsheet not available.

    Args:
        doc: FreeCAD document
        custom_fields: List of custom property names to extract

    Returns:
        List of BOM dicts
    """
    bom = []

    if custom_fields is None:
        custom_fields = []

    try:
        # Find all Part and Body objects
        part_bodies = [
            obj
            for obj in doc.Objects
            if hasattr(obj, "TypeId") and obj.TypeId in ["PartDesign::Body", "Part::Feature", "Part::FeaturePython"]
        ]

        logger.info(f"Found {len(part_bodies)} Part/Body object(s)")

        for obj in part_bodies:
            bom_item = {
                "label": obj.Label if hasattr(obj, "Label") else obj.Name,
                "quantity": 1,
            }

            # Extract custom properties if present
            for field in custom_fields:
                try:
                    value = getattr(obj, field, "")
                    if value:
                        bom_item[field.lower()] = str(value)
                except Exception:
                    pass

            bom.append(bom_item)

        logger.info(f"Extracted {len(bom)} parts from document")

    except Exception as e:
        logger.exception(f"Error extracting Parts BOM: {e}")

    return bom


def main():
    logger.info("=" * 60)
    logger.debug(f"Current working directory: {os.getcwd()}")
    logger.debug(f"PROJECT_ROOT: {PROJECT_ROOT}")
    logger.debug(f"CONFIG_FILE: {CONFIG_FILE}")
    logger.debug("Starting main()")

    if screenshots_only_mode:
        logger.info("Screenshots-only mode enabled")
    if gui_only_mode:
        logger.info("GUI-only mode enabled")

    # Handle dry-run mode: validate config and exit without exporting
    if dry_run_mode:
        logger.info("DRY-RUN MODE: Validating config without performing export")
        try:
            exports = load_config()

            # Filter exports by name if --name flag was provided (for consistency)
            if name_filter:
                exports = filter_exports_by_name(exports, name_filter)

            if not exports:
                if name_filter:
                    logger.warning(f"No export item found with name '{name_filter}'")
                else:
                    logger.warning("No exports defined in config - exports list is empty or None")
                sys.exit(0)

            logger.info(f"Found {len(exports)} export(s) in config:")
            for i, item in enumerate(exports):
                source = item.get("source")
                output = item.get("output")
                bodies = item.get("bodies", [])
                export_name = item.get("name", "export")

                logger.info(f"  Export #{i}: {export_name}")
                logger.info(f"    Source: {source}")
                if source and not os.path.exists(source):
                    logger.error(f"    ERROR: Source file does not exist: {source}")
                    sys.exit(1)
                logger.info(f"    Output: {output or f'prints/{export_name}.3mf (default)'}")
                logger.info(f"    Bodies: {bodies if bodies else '(all)'}")

                # Validate bodies if specified
                if bodies:
                    for body in bodies:
                        logger.info(f"      - {body}")

            logger.info("\nConfig validation passed. Run without --dry-run to perform export.")
            sys.exit(0)

        except Exception as e:
            logger.error(f"Config validation failed: {e}")
            sys.exit(1)

    exports = load_config()
    logger.debug(f"Loaded {len(exports)} exports")

    if list_exports_mode:
        for export_name in get_export_names(exports):
            logger.info(export_name)
        sys.exit(0)

    # Filter exports by name if --name flag was provided
    if name_filter:
        filtered_exports = filter_exports_by_name(exports, name_filter)
        if not filtered_exports:
            logger.warning(f"No export item found with name '{name_filter}'")
            logger.info(f"Available export names: {get_export_names(exports)}")
            sys.exit(1)
        exports = filtered_exports
        logger.info(f"Filtered to 1 export item: {name_filter}")

    if not exports:
        log_warning_msg("No exports defined in config - exports list is empty or None")
        sys.exit(0)

    run_start = time.time()
    run_stats = {
        "item_count": len(exports),
        "open_seconds": 0.0,
        "export_seconds": 0.0,
        "gui_seconds": 0.0,
        "shared_gui_seconds": 0.0,
        "total_seconds": 0.0,
    }

    log_section(f"Starting Export - {len(exports)} item(s) to process")
    queued_gui_jobs = []

    for i, item in enumerate(exports):
        export_name = item.get("name", "export")
        item_start = time.time()
        timing_data = {"open_seconds": 0.0, "export_seconds": 0.0, "gui_seconds": 0.0, "total_seconds": 0.0}
        log_subsection(f"Export Item {i}: {export_name}")
        logger.debug(f"Item content: {item}")

        source = item.get("source")
        output = item.get("output")
        bodies = item.get("bodies", [])
        template = item.get("template")  # Optional template 3MF file
        keep_stl = item.get("keep_stl", False)  # Keep STL files?
        stl_output_dir = item.get("stl_output_dir")  # Where to place STL files
        techdraw_config = item.get("techdraw")  # Optional TechDraw export config
        bom_config = item.get("bom")  # Optional BOM generation config

        logger.debug(
            f"Item {i}: name={export_name}, source={source}, output={output}, bodies={bodies}, "
            f"template={template}, keep_stl={keep_stl}, stl_output_dir={stl_output_dir}, "
            f"techdraw={techdraw_config}, bom={bom_config}"
        )

        if not source:
            log_failure("Missing 'source' in config item")
            sys.exit(1)

        # Generate default output filename if not specified
        if not output:
            output = f"prints/{export_name}.3mf"
            log_action(f"Using default output: {output}")

        if not os.path.exists(source):
            log_failure(f"Source file not found: {source}")
            sys.exit(1)

        log_action(f"Opening document: {source}")
        try:
            open_start = time.time()
            doc = FreeCAD.open(source)
            doc_name = doc.Name  # Save the name before closing
            logger.debug(f"Opened document {doc_name}")
            logger.debug(
                f"Document objects: {[(obj.Name, obj.Label if hasattr(obj, 'Label') else 'N/A') for obj in doc.Objects]}"
            )
            FreeCAD.setActiveDocument(doc_name)
            log_success(f"Document opened: {doc_name}")
            timing_data["open_seconds"] = time.time() - open_start

            # Determine bodies to export based on body_source mode
            body_source = item.get("_body_source", BODY_SOURCE_CONFIG)

            if body_source == BODY_SOURCE_PROPERTIES:
                # Find bodies with ExportTo3MF property set to True
                exportable_bodies = find_exportable_bodies(doc)
                if not exportable_bodies:
                    logger.warning("No bodies with ExportTo3MF=True found in document. Nothing to export.")
                    bodies = []
                else:
                    # Build body specs from properties, including count and rotation
                    bodies = []
                    for body_obj in exportable_bodies:
                        body_name = body_obj.Name
                        props = get_body_export_properties(body_obj)

                        # If count > 1, add multiple entries
                        for copy_idx in range(props["count"]):
                            body_spec = {
                                "body": body_name,
                            }
                            if props["rotation"]:
                                body_spec["rotation"] = props["rotation"]
                            if props["position"]:
                                body_spec["position"] = props["position"]
                            # Add copy suffix if count > 1
                            if props["count"] > 1:
                                body_spec["_copy"] = copy_idx + 1
                            bodies.append(body_spec)

                log_action(f"Exporting {len(bodies)} bodies from properties (name: {export_name})")

            if should_run_3mf_export(gui_only=gui_only_mode, screenshots_only=screenshots_only_mode):
                export_start = time.time()
                if bodies:
                    log_action(f"Exporting {len(bodies)} bodies")
                    # Try to resolve template path (uses config value or falls back to default)
                    resolved_template = resolve_template_path(template)

                    # Extract metadata from config item and environment
                    export_metadata = get_export_metadata(item, PROJECT_ROOT or os.getcwd())

                    # Use template-based export if template is available
                    if resolved_template:
                        log_action(f"Using template: {os.path.basename(resolved_template)}")
                        success = export_bodies_to_3mf_with_template(
                            doc,
                            bodies,
                            output,
                            resolved_template,
                            keep_stl,
                            stl_output_dir,
                            export_name,
                            metadata=export_metadata,
                        )
                    else:
                        # Fallback to STL export if no template available
                        log_warning_msg("No template - exporting without template")
                        success = export_bodies(doc, bodies, output)
                else:
                    log_action("Exporting full document")
                    success = export_full_doc(doc, output)
                timing_data["export_seconds"] = time.time() - export_start
            else:
                log_action("Skipping 3MF export in GUI-only mode")
                success = True

            logger.debug(f"Export success: {success}")
            if not success:
                FreeCAD.closeDocument(doc_name)
                sys.exit(1)

            # Final validation: ensure output file exists when 3MF export ran
            if should_run_3mf_export(gui_only=gui_only_mode, screenshots_only=screenshots_only_mode):
                output_abs = os.path.abspath(output)
                if not os.path.exists(output_abs):
                    logger.error(f"Export reported success but output file does not exist: {output_abs}")
                    logger.error("This is a critical issue - the export process completed but produced no file")
                    FreeCAD.closeDocument(doc_name)
                    sys.exit(1)

                file_size = os.path.getsize(output_abs)
                log_success(f"Output verified: {os.path.basename(output_abs)} ({_format_bytes(file_size)})")

                slicer_cfg = item.get("slicer") or {}
                if slicer_cfg.get("enabled", False) and slicer_cfg.get("run_after_export", True):
                    if not run_slicer_for_export_item(item, output_abs):
                        FreeCAD.closeDocument(doc_name)
                        sys.exit(1)

            gui_start = time.time()
            if gui_session_mode == "run" and has_gui_tasks(item) and not item.get("bom"):
                queued_gui_jobs.append(
                    build_shared_gui_job(
                        item,
                        export_name,
                        source,
                        PROJECT_ROOT or os.getcwd(),
                        bodies,
                        screenshots_only=screenshots_only_mode,
                    )
                )
            else:
                run_gui_tasks_for_item(
                    doc,
                    item,
                    export_name,
                    source,
                    PROJECT_ROOT or os.getcwd(),
                    bodies,
                    screenshots_only=screenshots_only_mode,
                )
            timing_data["gui_seconds"] = time.time() - gui_start
            timing_data["total_seconds"] = time.time() - item_start
            log_export_timing(export_name, timing_data)
            run_stats["open_seconds"] += timing_data["open_seconds"]
            run_stats["export_seconds"] += timing_data["export_seconds"]
            run_stats["gui_seconds"] += timing_data["gui_seconds"]

            FreeCAD.closeDocument(doc_name)
            logger.debug(f"Closed document {doc_name}")
        except Exception as e:
            logger.exception(f"Exception during processing: {e}")
            sys.exit(1)

    log_section("Export Completed Successfully")

    if gui_session_mode == "run" and queued_gui_jobs:
        log_action(f"Running shared GUI session for {len(queued_gui_jobs)} job(s)")
        shared_start = time.time()
        shared_results = run_gui_tasks_shared_session(queued_gui_jobs, PROJECT_ROOT or os.getcwd())
        run_stats["shared_gui_seconds"] = time.time() - shared_start
        for job in queued_gui_jobs:
            name = job["name"]
            res = (shared_results or {}).get(name, {})

            screenshot_res = res.get("screenshots", {})
            if screenshot_res.get("success"):
                warn_on_near_uniform_images(screenshot_res.get("images", []))
            elif job.get("screenshots", {}).get("enabled"):
                err = screenshot_res.get("error") or "unknown screenshot error"
                log_warning_msg(f"Screenshot generation failed for {name}: {err}")

            td = res.get("techdraw", {})
            page_pdfs = [p.get("pdf_path") for p in td.get("pages", []) if p.get("pdf_path")]
            if page_pdfs:
                out_dir = job["techdraw"].get("output_dir", "docs")
                if not os.path.isabs(out_dir):
                    out_dir = os.path.abspath(os.path.join(PROJECT_ROOT or os.getcwd(), out_dir))
                os.makedirs(out_dir, exist_ok=True)
                final_pdf = os.path.join(out_dir, f"{name}.pdf")
                ok = merge_techdraw_pdfs(page_pdfs, final_pdf, os.path.dirname(page_pdfs[0]))
                if ok:
                    log_success(f"TechDraw PDF generated: {os.path.basename(final_pdf)}")
                else:
                    log_warning_msg(f"TechDraw PDF merge failed for {name}")

    run_stats["total_seconds"] = time.time() - run_start
    log_section("Run Statistics")
    logger.info(summarize_run_stats(run_stats))
    sys.exit(0)


# Only run main() if not in test mode
_run_main_on_import = os.environ.get("FREECAD_TOOLS_TEST_MODE", "").lower() not in ("1", "true", "yes")

if __name__ == "__main__" or (_run_main_on_import and __name__ != "__main__"):
    try:
        main()
    except Exception as e:
        logger.exception(f"Exception in main: {e}")
        sys.exit(1)
