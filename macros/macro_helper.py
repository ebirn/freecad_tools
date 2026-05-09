#!/usr/bin/env python3
"""
macro_helper.py - Helper module for FreeCAD macros.

Provides utilities for:
- Displaying dialogs to ask users for configuration
- Loading/saving macro configuration from YAML files
- Resolving object identifiers (by Name or Label)
- Working with custom properties on FreeCAD objects

This module is designed to be imported by macros running inside FreeCAD.
"""

import logging
from pathlib import Path
from typing import Any

QtWidgets = None
FREECAD_AVAILABLE = False
QT_AVAILABLE = False

try:
    import FreeCAD  # type: ignore

    try:
        from unittest.mock import MagicMock

        if isinstance(FreeCAD, MagicMock):
            FreeCAD = None  # type: ignore[assignment]
    except Exception:
        pass

    if FreeCAD is not None:
        FREECAD_AVAILABLE = True

        # FreeCAD bundles either PySide6 (newer) or PySide2 (older).
        try:
            from PySide6 import QtWidgets as _QtWidgets  # noqa: N812
        except ImportError:  # pragma: no cover
            try:
                from PySide2 import QtWidgets as _QtWidgets  # noqa: N812
            except ImportError:
                _QtWidgets = None

        QtWidgets = _QtWidgets
        QT_AVAILABLE = QtWidgets is not None
except ImportError:
    FREECAD_AVAILABLE = False

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format="macro_helper - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

UNIFIED_CONFIG_RELATIVE_PATH = Path(".freecad_tools") / "config.yml"
LEGACY_MACRO_CONFIG_RELATIVE_PATH = Path(".freecad_tools") / "macro_config.yml"


def _resolve_section(config: dict[str, Any], section: str) -> dict[str, Any] | None:
    """Resolve a dotted section path from a config mapping."""
    current: Any = config
    for key in section.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current if isinstance(current, dict) else None


def get_macro_config_candidates(doc=None, preferred_path: str | None = None) -> list[Path]:
    """Return candidate config files in lookup order."""
    candidates: list[Path] = []
    doc_root: Path | None = None
    if doc is not None and getattr(doc, "FileName", None):
        doc_root = Path(str(doc.FileName)).parent

    if preferred_path:
        preferred = Path(preferred_path)
        if doc_root is not None and not preferred.is_absolute():
            candidates.append(doc_root / preferred)
        candidates.append(preferred)
    else:
        if doc_root is not None:
            candidates.append(doc_root / UNIFIED_CONFIG_RELATIVE_PATH)
            candidates.append(doc_root / LEGACY_MACRO_CONFIG_RELATIVE_PATH)

        candidates.append(UNIFIED_CONFIG_RELATIVE_PATH)
        candidates.append(LEGACY_MACRO_CONFIG_RELATIVE_PATH)

    unique_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_candidates.append(candidate)
    return unique_candidates


if QT_AVAILABLE:

    class MacroConfigDialog(QtWidgets.QDialog):
        """A dialog for configuring macro parameters."""

        def __init__(self, parent=None, title="Macro Configuration", fields: list[dict[str, Any]] | None = None):
            super().__init__(parent)
            self.setWindowTitle(title)
            self.fields = fields or []
            self.values: dict[str, Any] = {}
            self.input_widgets: dict[str, tuple[Any, str]] = {}
            self.init_ui()

        def init_ui(self) -> None:
            """Initialize the dialog UI."""
            layout = QtWidgets.QVBoxLayout()

            for field in self.fields:
                field_name = field.get("name")
                field_type = field.get("type", "text")
                label_text = field.get("label", field_name)
                default_value = field.get("default", "")
                help_text = field.get("help", "")

                label = QtWidgets.QLabel(label_text)
                layout.addWidget(label)

                if field_type == "text":
                    widget = QtWidgets.QLineEdit()
                    widget.setText(str(default_value))
                elif field_type == "number":
                    widget = QtWidgets.QSpinBox()
                    widget.setValue(int(default_value) if default_value else 0)
                elif field_type == "float":
                    widget = QtWidgets.QDoubleSpinBox()
                    widget.setValue(float(default_value) if default_value else 0.0)
                elif field_type == "list":
                    widget = QtWidgets.QListWidget()
                    for item in field.get("items", []):
                        widget.addItem(str(item))
                elif field_type == "checkbox":
                    widget = QtWidgets.QCheckBox()
                    widget.setChecked(bool(default_value))
                else:
                    widget = QtWidgets.QLineEdit()
                    widget.setText(str(default_value))

                if help_text:
                    help_label = QtWidgets.QLabel(f"  {help_text}")
                    help_label.setStyleSheet("color: gray; font-size: 10px;")
                    layout.addWidget(help_label)

                layout.addWidget(widget)
                self.input_widgets[field_name] = (widget, field_type)

            button_layout = QtWidgets.QHBoxLayout()
            ok_button = QtWidgets.QPushButton("OK")
            cancel_button = QtWidgets.QPushButton("Cancel")

            ok_button.clicked.connect(self.accept)
            cancel_button.clicked.connect(self.reject)

            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)

            self.setLayout(layout)
            self.setMinimumWidth(400)

        def get_values(self) -> dict[str, Any]:
            """Get the values entered by the user."""
            values: dict[str, Any] = {}
            for field_name, (widget, field_type) in self.input_widgets.items():
                if field_type == "text":
                    values[field_name] = widget.text()
                elif field_type == "number":
                    values[field_name] = widget.value()
                elif field_type == "float":
                    values[field_name] = widget.value()
                elif field_type == "list":
                    values[field_name] = [item.text() for item in widget.selectedItems()]
                elif field_type == "checkbox":
                    values[field_name] = widget.isChecked()
            return values

else:

    class MacroConfigDialog:  # pragma: no cover
        """Placeholder dialog when Qt is unavailable."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("QtWidgets is not available in this environment")


def get_object_by_identifier(doc, identifier: str) -> object | None:
    """
    Find a FreeCAD object by Name or Label.

    Args:
        doc: FreeCAD document
        identifier: Object Name or Label to find

    Returns:
        FreeCAD object or None if not found
    """
    if not FREECAD_AVAILABLE:
        logger.error("FreeCAD not available")
        return None

    # Try exact Name match first
    obj = doc.getObject(identifier)
    if obj is not None:
        logger.debug(f"Resolved '{identifier}' as Name → {obj.Name}")
        return obj

    # Then try Label match
    for obj in doc.Objects:
        if hasattr(obj, "Label") and obj.Label == identifier:
            logger.debug(f"Resolved '{identifier}' as Label → {obj.Name} (Label: {obj.Label})")
            return obj

    logger.warning(f"Could not resolve object '{identifier}' by Name or Label")
    return None


def get_objects_with_property(doc, property_name: str, property_value: Any = None) -> list[object]:
    """
    Get all objects in a document that have a specific custom property.

    Args:
        doc: FreeCAD document
        property_name: Name of the custom property
        property_value: Optional - only return objects with this property value

    Returns:
        List of matching FreeCAD objects
    """
    if not FREECAD_AVAILABLE:
        logger.error("FreeCAD not available")
        return []

    matching_objects = []
    for obj in doc.Objects:
        try:
            if hasattr(obj, "setPropertyStatus"):  # Check if object supports custom properties
                # Try to get the property value
                try:
                    value = obj.getPropertyByName(property_name)
                    if property_value is None or value == property_value:
                        matching_objects.append(obj)
                except AttributeError:
                    # Property doesn't exist on this object
                    pass
        except Exception as e:
            logger.debug(f"Error checking property on {obj.Name}: {e}")

    return matching_objects


def get_body_property(obj, property_name: str) -> Any | None:
    """
    Get a custom property value from a FreeCAD object.

    Args:
        obj: FreeCAD object
        property_name: Name of the custom property

    Returns:
        Property value or None if not found
    """
    try:
        # Try dynamic property first
        if hasattr(obj, property_name):
            return getattr(obj, property_name)
        # Try via getPropertyByName if available
        if hasattr(obj, "getPropertyByName"):
            return obj.getPropertyByName(property_name)
    except AttributeError:
        pass
    return None


def set_body_property(obj, property_name: str, value: Any, property_type: str = "String") -> bool:
    """
    Set a custom property on a FreeCAD object.

    Args:
        obj: FreeCAD object
        property_name: Name of the custom property
        value: Value to set
        property_type: Property type (String, Integer, Float, Bool)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Try using addProperty if available
        if hasattr(obj, "addProperty") and not hasattr(obj, property_name):
            obj.addProperty(f"App::{property_type}", property_name)
            logger.info(f"Created custom property {property_name} on {obj.Name}")

        # Set the property value
        if hasattr(obj, property_name):
            setattr(obj, property_name, value)
            logger.info(f"Set {property_name}={value} on {obj.Name}")
            return True
    except Exception as e:
        logger.error(f"Failed to set property {property_name} on {obj.Name}: {e}")
        return False

    return False


def show_config_dialog(title: str = "Configuration", fields: list[dict[str, Any]] = None) -> dict[str, Any] | None:
    """
    Show a configuration dialog to the user and return their input.

    Args:
        title: Dialog title
        fields: List of field definitions (name, type, label, default, help)

    Returns:
        Dictionary of field values if OK clicked, None if cancelled
    """
    if not (FREECAD_AVAILABLE and QT_AVAILABLE):
        logger.error("FreeCAD/Qt not available for dialog")
        return None

    dialog = MacroConfigDialog(title=title, fields=fields or [])
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        return dialog.get_values()
    return None


def load_macro_config(config_path: str, section: str | None = None) -> dict[str, Any] | None:
    """
    Load macro configuration from a YAML file.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary or None if failed
    """
    if not YAML_AVAILABLE:
        logger.error("PyYAML not available")
        return None

    config_path = Path(config_path)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return None

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
        if not isinstance(config, dict):
            logger.error(f"Config root must be a mapping: {config_path}")
            return None

        if section:
            section_config = _resolve_section(config, section)
            if section_config is not None:
                logger.info(f"Loaded macro config section '{section}' from {config_path}")
                return section_config

            if section.startswith("macros.") and "macros" not in config:
                logger.info(f"Using legacy flat macro config from {config_path}")
                return config

            logger.error(f"Config section '{section}' not found in {config_path}")
            return None

        logger.info(f"Loaded macro config from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {e}")
        return None


def save_macro_config(config: dict[str, Any], config_path: str, section: str | None = None) -> bool:
    """
    Save macro configuration to a YAML file.

    Args:
        config: Configuration dictionary
        config_path: Path where to save

    Returns:
        True if successful, False otherwise
    """
    if not YAML_AVAILABLE:
        logger.error("PyYAML not available")
        return False

    config_path = Path(config_path)
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        to_write: dict[str, Any] = config

        if section:
            existing: dict[str, Any] = {}
            if config_path.exists():
                with open(config_path) as existing_file:
                    loaded = yaml.safe_load(existing_file)
                if isinstance(loaded, dict):
                    existing = loaded

            cursor = existing
            keys = section.split(".")
            for key in keys[:-1]:
                next_value = cursor.get(key)
                if not isinstance(next_value, dict):
                    next_value = {}
                    cursor[key] = next_value
                cursor = next_value
            cursor[keys[-1]] = config
            to_write = existing

        with open(config_path, "w") as f:
            yaml.dump(to_write, f, default_flow_style=False)
        logger.info(f"Saved macro config to {config_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save config to {config_path}: {e}")
        return False


def load_or_prompt_config(
    config_path: str | None = None,
    dialog_fields: list[dict[str, Any]] = None,
    dialog_title: str = "Configuration",
    section: str | None = None,
    doc=None,
) -> dict[str, Any] | None:
    """
    Load configuration from file, or prompt user with dialog if file doesn't exist.

    Args:
        config_path: Path to configuration file
        dialog_fields: Fields for the configuration dialog
        dialog_title: Title for the dialog

    Returns:
        Configuration dictionary or None if user cancelled
    """
    candidates = get_macro_config_candidates(doc=doc, preferred_path=config_path)

    for candidate in candidates:
        if candidate.exists():
            config = load_macro_config(str(candidate), section=section)
            if config:
                logger.info(f"Loaded existing config from {candidate}")
                return config

    # Prompt user for configuration
    logger.info("No config found, prompting user...")
    config = show_config_dialog(title=dialog_title, fields=dialog_fields)

    if config:
        save_target = (
            candidates[0] if candidates else (Path(config_path) if config_path else UNIFIED_CONFIG_RELATIVE_PATH)
        )
        if YAML_AVAILABLE:
            save_macro_config(config, str(save_target), section=section)
        return config

    logger.warning("User cancelled configuration")
    return None


def find_exportable_bodies(doc) -> list[str]:
    """
    Find all bodies in a FreeCAD document that are marked for export.

    Bodies are marked for export if they have the 'ExportTo3MF' custom property set to True.
    If no bodies are marked, returns all bodies in the document.

    Args:
        doc: FreeCAD document

    Returns:
        List of body identifiers (Names or Labels)
    """
    if not FREECAD_AVAILABLE:
        logger.error("FreeCAD not available")
        return []

    marked_bodies = []
    all_bodies = []

    for obj in doc.Objects:
        # Look for Body objects
        if obj.TypeId in ("PartDesign::Body", "Part::Feature"):
            all_bodies.append(obj.Label if hasattr(obj, "Label") else obj.Name)

            # Check for ExportTo3MF property
            try:
                if hasattr(obj, "ExportTo3MF") and obj.ExportTo3MF:
                    marked_bodies.append(obj.Label if hasattr(obj, "Label") else obj.Name)
            except AttributeError:
                pass

    # If no bodies explicitly marked, return all bodies
    if marked_bodies:
        logger.info(f"Found {len(marked_bodies)} marked bodies for export")
        return marked_bodies
    elif all_bodies:
        logger.info(f"No bodies marked for export, returning all {len(all_bodies)} bodies")
        return all_bodies
    else:
        logger.warning("No bodies found in document")
        return []
