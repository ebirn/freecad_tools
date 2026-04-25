#!/usr/bin/env python3
"""
generate_variant_configs.py - FreeCAD macro to generate variant parameter combinations.

This macro creates a spreadsheet with all combinations of parameter values.
It can be configured via a dialog or config file.

Usage:
    1. Open a FreeCAD document with parameters
    2. Run this macro via Macro > Execute macro or Macro > Macros...
    3. Enter configuration parameters when prompted
    4. The macro will create/populate a spreadsheet with all combinations
"""

import itertools
import sys
from pathlib import Path

import FreeCAD

# Add parent directory to path to import macro_helper
macro_dir = Path(__file__).parent
if str(macro_dir) not in sys.path:
    sys.path.insert(0, str(macro_dir))

try:
    from macro_helper import (
        get_object_by_identifier,
        load_or_prompt_config,
    )
except ImportError as e:
    print(f"Error importing macro_helper: {e}")
    print("Make sure macro_helper.py is in the same directory as this macro.")
    sys.exit(1)


def get_object_by_user_label(doc, user_label):
    """Legacy helper function - use get_object_by_identifier instead."""
    return get_object_by_identifier(doc, user_label)


def generate_variant_combinations(config=None):
    """
    Generate variant parameter combinations in a spreadsheet.

    Args:
        config: Optional configuration dictionary with keys:
            - spreadsheet_label: Name of spreadsheet to create/use
            - parameter_lists: Dict of parameter names to value lists
            - column_headers: List of column headers (optional)
    """
    doc = FreeCAD.ActiveDocument
    if not doc:
        print("No active document.")
        return

    # Use provided config or use defaults
    if config is None:
        config = {
            "spreadsheet_label": "VariantData",
            "column_headers": ["ConfigName", "PipeDiameter", "HexIndent", "HexLength"],
            "parameter_lists": {
                "PipeDiameter": [10.1, 10.2],
                "HexIndent": [0.3, 0.5, 0.7, 0.9],
                "HexLength": [10],
            },
        }

    spreadsheet_label = config.get("spreadsheet_label", "VariantData")
    column_headers = config.get("column_headers")
    parameter_lists = config.get("parameter_lists", {})

    # Auto-generate column headers from parameter_lists if not provided
    if not column_headers:
        column_headers = ["ConfigName"] + list(parameter_lists.keys())

    sheet = get_object_by_identifier(doc, spreadsheet_label)

    if not sheet:
        # If the spreadsheet doesn't exist, create it automatically
        sheet = doc.addObject("Spreadsheet::Sheet", "VariantData")
        sheet.Label = spreadsheet_label
        print(f"Created new spreadsheet: {spreadsheet_label}")

    # --- 2. WRITE SPREADSHEET HEADERS (Row 1) ---
    for col_idx, header in enumerate(column_headers, start=1):
        cell = chr(64 + col_idx) + "1"  # Convert 1->A, 2->B, etc.
        sheet.set(cell, header)

    # Optional: Make headers bold
    col_range = chr(64 + 1) + "1:" + chr(64 + len(column_headers)) + "1"
    sheet.setStyle(col_range, "bold", "add")

    # --- 3. GENERATE ALL COMBINATIONS ---
    # Get the value lists in the order of column headers (excluding ConfigName)
    param_names = column_headers[1:]  # Skip ConfigName
    param_values_lists = [parameter_lists.get(name, []) for name in param_names]

    # itertools.product creates every possible combination of the lists provided
    combinations = list(itertools.product(*param_values_lists))

    print(f"Generating {len(combinations)} total variants...")

    # --- 4. WRITE DATA TO SPREADSHEET ---
    current_row = 2
    for combo in combinations:
        # Create a unique config name, e.g., "v_10_5.5_3mm"
        # We strip spaces from the generated name to keep it clean
        config_name = f"v_{combo[0]}_{combo[1]}_{combo[2]}".replace(" ", "")

        # Write ConfigName to column A
        sheet.set(f"A{current_row}", f"'{config_name}")  # The ' prefix forces string

        # Write parameter values to subsequent columns
        for col_idx, value in enumerate(combo, start=2):
            cell = chr(64 + col_idx) + str(current_row)
            sheet.set(cell, str(value))

        current_row += 1

    # Clear any leftover data below the new list if you ran this previously with more items
    # (Optional, but good practice if you reduce your parameter counts)
    sheet.clear(f"A{current_row}:{chr(64 + len(column_headers))}{current_row + 1000}")

    doc.recompute()
    print("Spreadsheet successfully populated!")


def main():
    """Main entry point - can be called with or without configuration."""
    doc = FreeCAD.ActiveDocument
    if not doc:
        print("No active document.")
        return

    # Check if a config file exists in the document's directory
    doc_path = Path(doc.FileName) if hasattr(doc, "FileName") and doc.FileName else None
    config_path = None
    if doc_path:
        config_dir = doc_path.parent
        config_path = config_dir / ".freecad_tools" / "macro_config.yml"

    # Define dialog fields for user configuration
    dialog_fields = [
        {
            "name": "spreadsheet_label",
            "type": "text",
            "label": "Spreadsheet Name:",
            "default": "VariantData",
            "help": "Name of the spreadsheet to create/populate",
        },
        {
            "name": "param1_name",
            "type": "text",
            "label": "First Parameter Name:",
            "default": "PipeDiameter",
            "help": "Name of the first parameter",
        },
        {
            "name": "param1_values",
            "type": "text",
            "label": "First Parameter Values (comma-separated):",
            "default": "10.1, 10.2",
            "help": "e.g., 10.1, 10.2, 10.3",
        },
        {
            "name": "param2_name",
            "type": "text",
            "label": "Second Parameter Name:",
            "default": "HexIndent",
            "help": "Name of the second parameter",
        },
        {
            "name": "param2_values",
            "type": "text",
            "label": "Second Parameter Values (comma-separated):",
            "default": "0.3, 0.5, 0.7, 0.9",
            "help": "e.g., 0.3, 0.5, 0.7, 0.9",
        },
        {
            "name": "param3_name",
            "type": "text",
            "label": "Third Parameter Name:",
            "default": "HexLength",
            "help": "Name of the third parameter",
        },
        {
            "name": "param3_values",
            "type": "text",
            "label": "Third Parameter Values (comma-separated):",
            "default": "10",
            "help": "e.g., 10, 15, 20",
        },
    ]

    # Load or prompt for configuration
    config = load_or_prompt_config(
        str(config_path) if config_path else ".freecad_tools/macro_config.yml",
        dialog_fields=dialog_fields,
        dialog_title="Generate Variant Configurations",
    )

    if config:
        # Convert comma-separated strings to lists
        param_lists = {}
        for i in range(1, 4):
            param_name = config.get(f"param{i}_name")
            param_values_str = config.get(f"param{i}_values", "")
            if param_name and param_values_str:
                # Parse comma-separated values, trying to convert to float
                values = []
                for val_str in param_values_str.split(","):
                    val_str = val_str.strip()
                    try:
                        values.append(float(val_str))
                    except ValueError:
                        values.append(val_str)
                param_lists[param_name] = values

        # Call the variant generator with configuration
        config_dict = {
            "spreadsheet_label": config.get("spreadsheet_label", "VariantData"),
            "column_headers": ["ConfigName"]
            + [config.get(f"param{i}_name") for i in range(1, 4) if config.get(f"param{i}_name")],
            "parameter_lists": param_lists,
        }
        generate_variant_combinations(config=config_dict)


# Run the macro
if __name__ == "__main__":
    main()
else:
    # When called via Macro menu, run main directly
    main()
