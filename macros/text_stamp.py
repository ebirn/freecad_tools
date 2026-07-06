#!/usr/bin/env python3
"""
text_stamp.py - FreeCAD Macro for Text Engraving

Allows users to engrave text on selected faces of FreeCAD bodies with:
- Variable substitution (built-in: {date}, {timestamp}, {git_branch}, {git_commit})
- Config-driven parameters (font, size, depth)
- Custom substitutions from .freecad_tools/config.yml
- Interactive dialog for text input and customization
- Automatic pocket/engrave operation

Usage: Run from FreeCAD Macro menu after selecting a body and face.

FreeCAD Macro Metadata:
- Version: 1.0.0
- Author: OpenCode Agent
- License: LGPL 2.0
"""

import logging
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

import FreeCAD  # type: ignore[import-not-found]

try:
    from PySide6 import QtWidgets as _QtWidgets
except ImportError:
    try:
        from PySide2 import QtWidgets as _QtWidgets  # noqa: F401
    except ImportError:
        _QtWidgets = None

try:
    import Part  # type: ignore[import-not-found]
except ImportError:
    Part = None

# Check if yaml is available (it is in FreeCAD bundled Python)
try:
    import yaml  # noqa: F401

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Add macro helper module to path (must come after imports)
macros_dir = Path(__file__).parent
if str(macros_dir) not in sys.path:
    sys.path.insert(0, str(macros_dir))

from macro_helper import (  # noqa: E402
    QT_AVAILABLE,
    MacroConfigDialog,
    get_macro_config_candidates,
    load_macro_config,
)

# Configure logging with file output
log_file = Path.home() / "Documents" / "FreeCAD" / "freecad_tools" / "test_output" / "text_stamp_macro.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Do NOT propagate to root logger — FreeCAD captures root and shows every
# message (including DEBUG) in a popup dialog.  All output goes to the file
# handler only; user-visible messages use warnings.warn() or FreeCAD.Console.
logger.propagate = False

file_handler = logging.FileHandler(str(log_file), mode="w")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s  %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

UNIFIED_CONFIG_RELATIVE_PATH = Path(".freecad_tools") / "config.yml"


def get_substitutions_help(config: dict[str, Any]) -> str:
    """Build help text describing available substitutions.

    Args:
        config: Configuration dict containing substitutions

    Returns:
        Formatted help text describing available variables
    """
    help_text = "Variables: {date}, {timestamp}, {git_branch}, {git_commit}"

    custom_subs = config.get("substitutions", {})
    if custom_subs:
        custom_vars = ", ".join([f"{{{k}}}" for k in custom_subs.keys()])
        help_text += f" | Custom: {custom_vars}"

    return help_text


def load_text_stamp_config(doc=None) -> dict[str, Any]:
    """Load text_stamp configuration from .freecad_tools/config.yml.

    Returns default config if file not found.
    """
    defaults = {
        "font": "Arial",
        "size": 10,
        "depth": 1.0,
        "substitutions": {},
    }

    candidates = get_macro_config_candidates(doc=doc)
    for candidate_path in candidates:
        if not candidate_path.exists():
            continue

        try:
            # Try to load the macros.text_stamp section from config
            config = load_macro_config(str(candidate_path), section="macros.text_stamp")
            if config:
                logger.debug(f"Loaded text_stamp config from {candidate_path}")
                # Merge with defaults (config takes precedence)
                result = defaults.copy()
                result.update(config)
                return result
        except Exception as e:
            logger.warning(f"Failed to load config from {candidate_path}: {e}")
            continue

    logger.debug("Using default text_stamp configuration")
    return defaults


def apply_substitutions(text: str, substitutions: dict[str, Any]) -> str:
    """Apply variable substitutions to text.

    Supports:
    - Built-in variables: {date}, {timestamp}, {git_branch}, {git_commit}
    - Custom variables from config substitutions dict

    Args:
        text: Template text with {variable} placeholders
        substitutions: Dict of custom variable values

    Returns:
        Text with variables replaced
    """
    import re

    result = text

    # Built-in substitutions
    builtin_subs = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
    }

    # Try to get git info if available
    try:
        import subprocess

        git_branch = (
            subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
        builtin_subs["git_branch"] = git_branch
    except Exception:
        builtin_subs["git_branch"] = "unknown"

    try:
        git_commit = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        )
        builtin_subs["git_commit"] = git_commit
    except Exception:
        builtin_subs["git_commit"] = "unknown"

    # Merge custom and built-in substitutions (custom takes precedence)
    all_subs = {**builtin_subs, **substitutions}

    # Replace all {variable} placeholders
    def replace_var(match: Any) -> str:
        var_name = match.group(1)
        return str(all_subs.get(var_name, match.group(0)))

    result = re.sub(r"\{([^}]+)\}", replace_var, result)
    return result


def create_text_shape(text: str, font_path: str = "", size: float = 10.0) -> Any:
    """Create a text shape using Draft.makeShapeString.

    Args:
        text: Text to engrave
        font_path: Full path to a .ttf or .otf font file.
                   Falls back to system font discovery if empty or file not found.
        size: Font size in mm

    Returns:
        FreeCAD Draft ShapeString object
    """
    try:
        import Draft  # type: ignore[import-not-found]

        # Resolve font path — fall back to system discovery if not given or missing.
        if not font_path or not Path(font_path).exists():
            logger.warning(f"Font file not found: '{font_path}', falling back to system font discovery")
            font_path = get_font_path_for_name("Arial")
        logger.debug(f"Using font file: {font_path}")

        # Create text shape using Draft.makeShapeString with full font path
        # This creates a ShapeString object in the active document
        shape_string = Draft.makeShapeString(text, font_path, size)
        logger.debug(f"Created text shape: {text} (font_path={font_path}, size={size})")

        # Disable MakeFace so it's just a 2D wire outline for pocketing
        if hasattr(shape_string, "MakeFace"):
            shape_string.MakeFace = False
            logger.debug("Disabled MakeFace - using wire outline only")

        return shape_string
    except ImportError:
        logger.error("Draft module not available")
        raise
    except Exception as e:
        logger.error(f"Failed to create text shape: {e}")
        raise


def get_selected_faces() -> list[tuple[Any, Any]]:
    """Get currently selected faces in FreeCAD with their source bodies.

    Returns:
        List of tuples (face, source_body) where source_body is the PartDesign::Body
        that contains the face
    """
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return []

    faces_with_bodies = []
    try:
        from FreeCADGui import Selection  # type: ignore[import-not-found]

        sel_ex = Selection.getSelectionEx()

        for obj in sel_ex:
            if obj.HasSubObjects:
                # obj.Object is the selected object (could be a feature like AdditiveSphere)
                selected_obj = obj.Object
                logger.debug(f"Selected object: {selected_obj.Name}, TypeId: {selected_obj.TypeId}")

                source_body = None

                # Strategy 1: Check if the object itself is a Body
                if "PartDesign::Body" in str(selected_obj.TypeId):
                    source_body = selected_obj
                    logger.debug(f"Selected object is a Body: {selected_obj.Name}")

                # Strategy 2: Try the Body property
                if source_body is None and hasattr(selected_obj, "Body") and selected_obj.Body is not None:
                    source_body = selected_obj.Body
                    logger.debug(f"Found body via Body property: {source_body.Name}")

                # Strategy 3: Search document for body containing this feature
                if source_body is None:
                    logger.debug(f"Searching for body containing {selected_obj.Name}...")
                    for candidate in doc.Objects:
                        if "PartDesign::Body" not in str(candidate.TypeId):
                            continue

                        # Check if selected_obj is in this body's feature tree
                        if hasattr(candidate, "Tip"):
                            current = candidate.Tip
                            while current is not None:
                                if current == selected_obj:
                                    source_body = candidate
                                    logger.debug(f"Found body via feature tree: {source_body.Name}")
                                    break
                                # Move to previous feature
                                if hasattr(current, "PreviousFeature"):
                                    current = current.PreviousFeature
                                else:
                                    break

                        if source_body:
                            break

                # Final validation
                if source_body is None:
                    logger.warning(f"Could not find PartDesign::Body parent of {selected_obj.Name}")
                    continue

                if "PartDesign::Body" not in str(source_body.TypeId):
                    logger.warning(f"Found object {source_body.Name} is not a PartDesign::Body, skipping")
                    continue

                # Extract faces from selection
                for sub in obj.SubObjects:
                    if hasattr(sub, "Area"):  # Face has Area attribute
                        faces_with_bodies.append((sub, source_body))
                        logger.debug(f"Found face from body: {source_body.Name}")
    except Exception as e:
        logger.warning(f"Failed to get selected faces: {e}")

    return faces_with_bodies


def get_available_fonts() -> dict[str, str]:
    """Discover available TrueType fonts on the system.

    Returns a dictionary mapping font names to full font file paths.
    Searches common system font directories.

    Returns:
        Dict of {font_name: full_path_to_ttf_file}
    """
    fonts: dict[str, str] = {}

    # Common font directories by platform
    font_dirs: list[Path] = []

    if sys.platform == "darwin":
        # macOS
        font_dirs = [
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path.home() / "Library/Fonts",
        ]
    elif sys.platform.startswith("linux"):
        # Linux
        font_dirs = [
            Path("/usr/share/fonts/truetype"),
            Path("/usr/share/fonts"),
            Path.home() / ".fonts",
        ]
    elif sys.platform.startswith("win"):
        # Windows
        font_dirs = [
            Path("C:/Windows/Fonts"),
            Path("C:/winnt/Fonts"),
        ]

    # Search for TTF fonts
    for font_dir in font_dirs:
        if not font_dir.exists():
            continue
        try:
            for ttf_file in font_dir.rglob("*.ttf"):
                # Use filename without extension as the font name
                font_name = ttf_file.stem
                if font_name not in fonts:
                    fonts[font_name] = str(ttf_file)
        except Exception as e:
            logger.debug(f"Failed to search font directory {font_dir}: {e}")

    logger.debug(f"Found {len(fonts)} available fonts")
    return fonts


def get_font_path_for_name(font_name: str, default_font: str = "Arial") -> str:
    """Get the full path to a font file by name.

    Args:
        font_name: Name of the font (e.g., "Arial", "DejaVuSans")
        default_font: Fallback font name if specified font not found

    Returns:
        Full path to the font TTF file
    """
    available_fonts = get_available_fonts()

    # Try the requested font first
    if font_name in available_fonts:
        return available_fonts[font_name]

    # Try default if different
    if default_font in available_fonts:
        logger.warning(f"Font '{font_name}' not found, using '{default_font}'")
        return available_fonts[default_font]

    # If no fonts found at all, return a generic path (may fail later)
    # but at least provide something
    if available_fonts:
        first_font = next(iter(available_fonts.values()))
        logger.warning(f"Font '{font_name}' not found, using first available: {Path(first_font).stem}")
        return first_font

    logger.error("No fonts found on system")
    raise RuntimeError("No TrueType fonts found on system")


def project_text_to_face(text_shape_obj: Any, face: Any, body: Any = None) -> Any:
    """Position and align text shape to the selected face.

    Transforms the ShapeString to lie flat on the selected face surface,
    oriented so text is readable from outside the face.

    Uses world-aligned "up" direction: picks the global axis most parallel to the face,
    ensuring intuitive text orientation for part designers.

    *** GEOMETRY CRITICAL — read before modifying ***
    The coordinate system here was carefully validated against both flat faces (cube with
    non-identity body Placement) and curved faces (sphere). Key invariants:

    1. BODY-LOCAL COORDINATES: face.Surface.value() and face.normalAt() return points in
       body-local space (body.Placement is NOT yet applied). Do NOT apply body.Placement
       here. PartDesign::Pocket receives this body-local placement and the body's own
       Placement transform brings it to the correct world position automatically (because
       the ShapeString is added to the body via body.addObject() in pocket_text()).

    2. Surface.value(u, v) NOT CenterOfMass: for curved faces (e.g. sphere) CenterOfMass
       is the geometric centre of the enclosed volume — inside the body, not on the surface.
       Surface.value(u_mid, v_mid) gives the actual surface point.

    3. Gram-Schmidt projection for "up": the Y-axis is the world "up" vector projected
       onto the face plane. This keeps text orientation intuitive regardless of body
       rotation. Do not replace with an arbitrary fixed axis.

    4. Column-major rotation matrix: FreeCAD's Rotation(xx,yx,zx, xy,yy,zy, xz,yz,zz)
       constructor takes columns [X-axis | Y-axis | Z-axis]. Transposing the arguments
       would silently produce the wrong orientation.

    Args:
        text_shape_obj: ShapeString object from Draft.makeShapeString
        face: Target face from FreeCAD body (a Face object with geometry info)
        body: The PartDesign::Body containing the face (for coordinate transformation)

    Returns:
        The ShapeString DocumentObject positioned flat on the face, readable from outside
    """
    try:
        from FreeCAD import Placement, Rotation, Vector  # type: ignore[import-not-found]

        # Get face geometry information
        if not hasattr(face, "CenterOfMass"):
            logger.warning("Face has no CenterOfMass, positioning at origin")
            return text_shape_obj

        # --- GEOMETRY CRITICAL: parametric midpoint ---
        # Use the parametric centre of the face to sample normal and surface position.
        # Sampling at (u_mid, v_mid) is stable for all surface types (planar, cylindrical,
        # spherical, toroidal). Do not use face.CenterOfMass as the position source —
        # see invariant 2 above.
        face_u_min, face_u_max, face_v_min, face_v_max = face.ParameterRange
        face_u_param = (face_u_min + face_u_max) / 2
        face_v_param = (face_v_min + face_v_max) / 2

        # Surface.value() returns a point ON the surface in body-local coordinates.
        # Fall back to CenterOfMass only if the surface evaluation fails (degenerate face).
        try:
            face_center = face.Surface.value(face_u_param, face_v_param)
        except Exception:
            face_center = face.CenterOfMass

        # Z-axis of the ShapeString frame = outward face normal (body-local).
        z_axis = face.normalAt(face_u_param, face_v_param).normalize()
        logger.debug(f"Face center (body-local): {face_center}, normal: {z_axis}")

        # --- GEOMETRY CRITICAL: world-aligned "up" selection ---
        # Pick the global axis that is most perpendicular to the face normal (i.e. most
        # parallel to the face plane) as the candidate "up" direction for text.
        # This keeps text upright and readable for axis-aligned faces without requiring
        # any manual rotation hint from the user.
        normal_x = abs(z_axis.x)
        normal_y = abs(z_axis.y)
        normal_z = abs(z_axis.z)
        logger.debug(f"Normal components: X={normal_x:.3f}, Y={normal_y:.3f}, Z={normal_z:.3f}")

        if normal_z > normal_x and normal_z > normal_y:
            # Face is XY-parallel (normal is ~Z) — use world Y as "up"
            logger.debug("Face is XY-parallel, using Y as 'up'")
            world_up = Vector(0, 1, 0)
        elif normal_x > normal_y and normal_x > normal_z:
            # Face is YZ-parallel (normal is ~X) — use world Z as "up"
            logger.debug("Face is YZ-parallel, using Z as 'up'")
            world_up = Vector(0, 0, 1)
        elif normal_y > normal_x and normal_y > normal_z:
            # Face is XZ-parallel (normal is ~Y) — use world Z as "up"
            logger.debug("Face is XZ-parallel, using Z as 'up'")
            world_up = Vector(0, 0, 1)
        else:
            # Non-axis-aligned face — fall back to world Z
            logger.debug("Face is non-axis-aligned, using Z as default 'up'")
            world_up = Vector(0, 0, 1)

        # --- GEOMETRY CRITICAL: Gram-Schmidt projection ---
        # Project the world "up" vector onto the face plane to obtain the Y-axis of
        # the ShapeString frame. Formula: y = (up - (up·n)*n).normalize()
        # This removes the component of "up" that is parallel to the normal, leaving
        # a vector that lies flat on the face and points "upward" for the reader.
        dot_with_normal = world_up.dot(z_axis)
        y_axis = (world_up - (z_axis * dot_with_normal)).normalize()
        logger.debug(f"Projected world 'up' to face: {y_axis}")

        # X-axis completes the right-handed coordinate frame (reading direction →).
        x_axis = y_axis.cross(z_axis).normalize()
        logger.debug(f"Computed X-axis (reading direction): {x_axis}")

        # Ensure the frame is right-handed: (x × y) must point in the same direction as z.
        cross_check = x_axis.cross(y_axis)
        if cross_check.dot(z_axis) < 0:
            logger.debug("Flipping coordinate system for right-handed convention")
            x_axis = x_axis * -1

        # Log final axes
        logger.debug(f"Final X-axis (text reads →): ({x_axis.x:.3f}, {x_axis.y:.3f}, {x_axis.z:.3f})")
        logger.debug(f"Final Y-axis (text reads ↑): ({y_axis.x:.3f}, {y_axis.y:.3f}, {y_axis.z:.3f})")
        logger.debug(f"Final Z-axis (faces out ⊙): ({z_axis.x:.3f}, {z_axis.y:.3f}, {z_axis.z:.3f})")

        # --- GEOMETRY CRITICAL: column-major rotation constructor ---
        # FreeCAD Rotation(xx,yx,zx, xy,yy,zy, xz,yz,zz) takes the three basis vectors
        # as COLUMNS: first column = X-axis, second = Y-axis, third = Z-axis.
        # Swapping rows/columns here would silently rotate the text by 90° or flip it.
        rotation = Rotation(x_axis.x, y_axis.x, z_axis.x, x_axis.y, y_axis.y, z_axis.y, x_axis.z, y_axis.z, z_axis.z)

        # Place the ShapeString at the body-local face centre with the computed rotation.
        # body.addObject() in pocket_text() ensures PartDesign applies body.Placement
        # so the visual position and the pocket position both land at the correct world coords.
        text_shape_obj.Placement = Placement(face_center, rotation)
        logger.debug(f"ShapeString placed at body-local {face_center}")

        return text_shape_obj
    except Exception as e:
        logger.error(f"Failed to position text on face: {e}")
        logger.warning("Continuing with ShapeString at origin")
        return text_shape_obj


def get_active_body(doc: Any) -> Any:
    """Get the active body in the document.

    FreeCAD doesn't have a direct ActiveBody property, so we search for
    the active body by checking the Body objects in the document.

    Args:
        doc: FreeCAD document

    Returns:
        Active PartDesign::Body object, or None if not found
    """
    try:
        # Search for Body objects in the document
        bodies = doc.findObjects("PartDesign::Body")
        if not bodies:
            logger.warning("No PartDesign::Body found in document")
            return None

        # Return the first body (typically the active one in simple documents)
        # For complex documents, we might need to check Tip property
        if bodies:
            return bodies[0]
    except Exception as e:
        logger.error(f"Failed to find active body: {e}")
    return None


def pocket_text(text_shape_obj: Any, depth: float = 1.0, body: Any = None) -> None:
    """Create a pocket feature from the ShapeString.

    The ShapeString object is used directly as the Pocket's Profile.
    FreeCAD's Pocket feature will handle the actual pocketing operation.

    *** GEOMETRY CRITICAL — read before modifying ***

    1. ADD SHAPETRING TO BODY FIRST: body.addObject(text_shape_obj) must be called before
       creating the Pocket. This makes PartDesign apply the body's world Placement to the
       ShapeString for display, so the ShapeString renders at the correct world position
       (aligned with the pocket) even when the body has a non-identity Placement.
       Without this, the ShapeString appears offset by the body's translation in the viewport.

    2. Pocket.Type = "Length": do NOT change to "UpToFirst". "UpToFirst" cuts through to
       the next surface it encounters, which for thin bodies or boxes cuts all the way
       through and can delete the solid entirely. "Length" cuts to an explicit depth.

    Args:
        text_shape_obj: ShapeString DocumentObject from project_text_to_face
        depth: Pocket depth in mm
        body: Target body (defaults to active body)
    """
    doc = FreeCAD.ActiveDocument
    if doc is None:
        raise RuntimeError("No active document")

    if body is None:
        body = get_active_body(doc)
        if body is None:
            raise RuntimeError("No PartDesign::Body found in document")

    # Log what we're working with
    logger.debug(f"pocket_text: body.Name={getattr(body, 'Name', '?')}, TypeId={getattr(body, 'TypeId', '?')}")

    try:
        # Add the ShapeString to the body first so PartDesign applies the body's world
        # Placement to it for display — body-local Placement values will render at the
        # correct world position, keeping the ShapeString visually aligned with the pocket.
        body.addObject(text_shape_obj)

        # Create a Pocket feature in the document
        pocket = doc.addObject("PartDesign::Pocket", "TextPocket")
        logger.debug(f"Created Pocket feature with depth={depth}mm")

        # Set the profile (the ShapeString is the sketch/profile for the pocket)
        pocket.Profile = (text_shape_obj, [])

        # Use "Length" mode: pocket to a specific depth
        # Valid types: "Length", "ThroughAll", "UpToFirst", "UpToFace", "?TwoLengths", "UpToShape"
        pocket.Type = "Length"
        pocket.Length = depth

        # Add the pocket to the body
        body.addObject(pocket)

        # Enable compound if needed (workaround for BOPcheck issue)
        if hasattr(body, "AllowCompound"):
            body.AllowCompound = True

        doc.recompute()
        logger.debug("Document recomputed successfully")
    except Exception as e:
        logger.error(f"Failed to create pocket: {e}")
        raise


# TextStampDialog is defined conditionally below based on QT_AVAILABLE
TextStampDialog: Any = None  # type: ignore[assignment]

if QT_AVAILABLE:

    class TextStampDialog(MacroConfigDialog):
        """Dialog for text stamp configuration."""

        def __init__(self, parent=None, config: dict[str, Any] | None = None, default_font_path: str = ""):
            self.config = config or {}

            fields = [
                {
                    "name": "text",
                    "label": "Text to Engrave",
                    "type": "text",
                    "default": "",
                    "help": get_substitutions_help(self.config),
                },
                {
                    # Font file chooser — matches FreeCAD's native ShapeString
                    # task panel (Gui::FileChooser for a .ttf path), making it
                    # clear to the user that a font FILE is being selected.
                    "name": "font_file",
                    "label": "Font File (.ttf / .otf)",
                    "type": "file",
                    "default": default_font_path,
                    "filter": "Font Files (*.ttf *.otf *.TTF *.OTF);;All Files (*)",
                    "help": "Same font file as used by FreeCAD ShapeString",
                },
                {
                    "name": "size",
                    "label": "Font Size (mm)",
                    "type": "float",
                    "default": self.config.get("size", 10),
                    "help": "Font size in millimeters",
                },
                {
                    "name": "depth",
                    "label": "Pocket Depth (mm)",
                    "type": "float",
                    "default": self.config.get("depth", 1.0),
                    "help": "Depth of engraved text",
                },
            ]
            super().__init__(parent=parent, title="Text Stamp Configuration", fields=fields)

            # Live preview: show the text with substitutions applied, updated
            # as the user types. Kept fully local to this dialog subclass so
            # the shared MacroConfigDialog (used by other macros) is untouched.
            self._preview_label = _QtWidgets.QLabel(self._render_preview(""))
            self._preview_label.setStyleSheet("color: gray; font-style: italic;")
            self._preview_label.setWordWrap(True)
            self.layout().addWidget(self._preview_label)

            text_widget = self.input_widgets["text"][0]
            text_widget.textChanged.connect(self._update_preview)
            self._update_preview(text_widget.text())

        def _render_preview(self, text: str) -> str:
            """Return the preview label text for the given raw input text."""
            substituted = apply_substitutions(text, self.config.get("substitutions", {}))
            return f"Preview: {substituted}"

        def _update_preview(self, text: str) -> None:
            """Slot connected to the text field's textChanged signal."""
            self._preview_label.setText(self._render_preview(text))


def main() -> None:
    """Main macro entry point."""
    doc = FreeCAD.ActiveDocument
    if doc is None:
        logger.error("No active document")
        if QT_AVAILABLE:
            warnings.warn("Please open a FreeCAD document first", stacklevel=2)
        return

    # Load configuration
    config = load_text_stamp_config(doc)
    logger.debug(f"Using configuration: font={config['font']}, size={config['size']}, depth={config['depth']}")

    # Resolve configured font name → full file path for the dialog default
    try:
        default_font_path = get_font_path_for_name(config.get("font", "Arial"))
        logger.debug(f"Resolved default font path: {default_font_path}")
    except RuntimeError:
        default_font_path = ""
        logger.warning("No system fonts found; font path will be empty")

    # Get selected faces
    selected_faces = get_selected_faces()
    if not selected_faces:
        logger.warning("No faces selected. Please select a face on your body.")
        if QT_AVAILABLE:
            warnings.warn("Please select a face on your body before running this macro", stacklevel=2)
        return

    # Show dialog
    dialog_values: dict[str, Any] = {}
    if not QT_AVAILABLE:
        logger.warning("Qt not available, skipping dialog. Using defaults.")
        dialog_values = {
            "text": "Text",
            "font_file": default_font_path,
            "size": config["size"],
            "depth": config["depth"],
        }
    else:
        # TextStampDialog is only available if QT_AVAILABLE is True
        dialog = TextStampDialog(config=config, default_font_path=default_font_path)  # type: ignore[name-defined]
        if dialog.exec() != 1:  # User cancelled
            logger.debug("User cancelled text stamp operation")
            return

        dialog_values = dialog.get_values()

    # Apply variable substitutions (built-in + custom from config) to the
    # text entered in the dialog before it is used for engraving.
    text = apply_substitutions(dialog_values.get("text", ""), config.get("substitutions", {}))
    logger.debug(f"Text to engrave: {text!r}")

    # Create and engrave text
    try:
        font_path = dialog_values.get("font_file", default_font_path)
        size = float(dialog_values.get("size", config["size"]))
        depth = float(dialog_values.get("depth", config["depth"]))

        text_shape = create_text_shape(text, font_path=font_path, size=size)
        selected_face, source_body = selected_faces[0]
        projected_shape = project_text_to_face(text_shape, selected_face, body=source_body)
        pocket_text(projected_shape, depth=depth, body=source_body)

        logger.debug("Text stamp completed successfully")
        if QT_AVAILABLE:
            warnings.warn(f"Text stamp '{text}' created successfully!", stacklevel=2)
    except Exception as e:
        logger.error(f"Text stamp operation failed: {e}")
        if QT_AVAILABLE:
            warnings.warn(f"Text stamp failed: {e}", stacklevel=2)


if __name__ == "__main__":
    main()
