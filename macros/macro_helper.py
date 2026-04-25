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
from typing import Any, Dict, List, Optional

try:
    import FreeCAD  # noqa: F401
    from PySide2 import QtWidgets

    FREECAD_AVAILABLE = True
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


class MacroConfigDialog(QtWidgets.QDialog):
    """
    A dialog for configuring macro parameters.
    Allows users to specify object names/labels and parameter values.
    """

    def __init__(self, parent=None, title="Macro Configuration", fields: List[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.fields = fields or []
        self.values = {}
        self.init_ui()

    def init_ui(self):
        """Initialize the dialog UI."""
        layout = QtWidgets.QVBoxLayout()

        # Add fields based on configuration
        self.input_widgets = {}
        for field in self.fields:
            field_name = field.get("name")
            field_type = field.get("type", "text")
            label_text = field.get("label", field_name)
            default_value = field.get("default", "")
            help_text = field.get("help", "")

            # Create label
            label = QtWidgets.QLabel(label_text)
            layout.addWidget(label)

            # Create input widget based on type
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
                items = field.get("items", [])
                for item in items:
                    widget.addItem(str(item))
            elif field_type == "checkbox":
                widget = QtWidgets.QCheckBox()
                widget.setChecked(bool(default_value))
            else:
                # Default to text
                widget = QtWidgets.QLineEdit()
                widget.setText(str(default_value))

            # Add help text if provided
            if help_text:
                help_label = QtWidgets.QLabel(f"  {help_text}")
                help_label.setStyleSheet("color: gray; font-size: 10px;")
                layout.addWidget(help_label)

            layout.addWidget(widget)
            self.input_widgets[field_name] = (widget, field_type)

        # Add buttons
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

    def get_values(self) -> Dict[str, Any]:
        """Get the values entered by the user."""
        values = {}
        for field_name, (widget, field_type) in self.input_widgets.items():
            if field_type == "text":
                values[field_name] = widget.text()
            elif field_type == "number":
                values[field_name] = widget.value()
            elif field_type == "float":
                values[field_name] = widget.value()
            elif field_type == "list":
                selected_items = [item.text() for item in widget.selectedItems()]
                values[field_name] = selected_items
            elif field_type == "checkbox":
                values[field_name] = widget.isChecked()
        return values


def get_object_by_identifier(doc, identifier: str) -> Optional[object]:
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


def get_objects_with_property(doc, property_name: str, property_value: Any = None) -> List[object]:
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


def get_body_property(obj, property_name: str) -> Optional[Any]:
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


def show_config_dialog(title: str = "Configuration", fields: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Show a configuration dialog to the user and return their input.

    Args:
        title: Dialog title
        fields: List of field definitions (name, type, label, default, help)

    Returns:
        Dictionary of field values if OK clicked, None if cancelled
    """
    if not FREECAD_AVAILABLE:
        logger.error("FreeCAD/PySide2 not available for dialog")
        return None

    dialog = MacroConfigDialog(title=title, fields=fields or [])
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        return dialog.get_values()
    return None


def load_macro_config(config_path: str) -> Optional[Dict[str, Any]]:
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
        logger.info(f"Loaded macro config from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {e}")
        return None


def save_macro_config(config: Dict[str, Any], config_path: str) -> bool:
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
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        logger.info(f"Saved macro config to {config_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save config to {config_path}: {e}")
        return False


def load_or_prompt_config(
    config_path: str,
    dialog_fields: List[Dict[str, Any]] = None,
    dialog_title: str = "Configuration",
) -> Optional[Dict[str, Any]]:
    """
    Load configuration from file, or prompt user with dialog if file doesn't exist.

    Args:
        config_path: Path to configuration file
        dialog_fields: Fields for the configuration dialog
        dialog_title: Title for the dialog

    Returns:
        Configuration dictionary or None if user cancelled
    """
    config_path = Path(config_path)

    # Try to load existing config
    if config_path.exists():
        config = load_macro_config(str(config_path))
        if config:
            logger.info(f"Loaded existing config from {config_path}")
            return config

    # Prompt user for configuration
    logger.info("No config found, prompting user...")
    config = show_config_dialog(title=dialog_title, fields=dialog_fields)

    if config:
        # Optionally save for future use
        if YAML_AVAILABLE:
            save_macro_config(config, str(config_path))
        return config

    logger.warning("User cancelled configuration")
    return None


def find_exportable_bodies(doc) -> List[str]:
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
