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

__Name__ = "Generate Variant Configs"
__Comment__ = "Generate parameter combinations for variant/configuration spreadsheets"
__Author__ = "ebirn"
__Date__ = "2026-05-05"
__Version__ = "0.4.0"
__License__ = "MIT"
__Web__ = "https://github.com/ebirn/freecad_tools"
__Wiki__ = "https://github.com/ebirn/freecad_tools/blob/main/README.md"
__Icon__ = ""
__Help__ = "Creates all combinations of parameters defined in a config. Results are stored in a FreeCAD spreadsheet."
__Status__ = "Stable"
__Requires__ = "yaml"
__Communication__ = "https://github.com/ebirn/freecad_tools/issues"
__Files__ = "macro_helper.py"

import itertools
import sys
from decimal import Decimal
from pathlib import Path

import FreeCAD

# Add parent directory to path to import macro_helper
macro_dir = Path(__file__).parent
if str(macro_dir) not in sys.path:
    sys.path.insert(0, str(macro_dir))

try:
    from macro_helper import (
        UNIFIED_CONFIG_RELATIVE_PATH,
        get_object_by_identifier,
        load_or_prompt_config,
    )
except ImportError as e:
    print(f"Error importing macro_helper: {e}")
    print("Make sure macro_helper.py is in the same directory as this macro.")
    sys.exit(1)

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def parse_scalar(value):
    """Parse numeric strings as floats while preserving non-numeric strings."""
    if isinstance(value, int | float):
        return value

    value_str = str(value).strip()
    try:
        return float(value_str)
    except ValueError:
        return value_str


def decimal_places(value):
    """Return the number of decimal places in a configured numeric value."""
    decimal_value = Decimal(str(value))
    return max(0, -decimal_value.as_tuple().exponent)


def generate_range_values(start, stop, step):
    """Generate inclusive range values from start/stop/step without floating point drift."""
    start_decimal = Decimal(str(start))
    stop_decimal = Decimal(str(stop))
    step_decimal = Decimal(str(step))

    if step_decimal == 0:
        raise ValueError("Range step cannot be zero")

    increasing = step_decimal > 0
    precision = max(decimal_places(start), decimal_places(stop), decimal_places(step))
    values = []
    current = start_decimal

    while (increasing and current <= stop_decimal) or (not increasing and current >= stop_decimal):
        values.append(float(round(current, precision)))
        current += step_decimal

    return values


def parse_values(value):
    """Parse list or comma-separated scalar values."""
    if isinstance(value, list | tuple):
        return [parse_scalar(item) for item in value]

    if value is None:
        return []

    return [parse_scalar(item) for item in str(value).split(",") if str(item).strip()]


def build_parameter_lists(config):
    """Build ordered parameter lists from the configured parameter definitions."""
    parameter_lists = {}

    for parameter in config.get("parameters", []):
        name = parameter.get("name")
        if not name:
            continue

        if "values" in parameter:
            parameter_lists[name] = parse_values(parameter["values"])
        elif {"start", "stop", "step"}.issubset(parameter):
            parameter_lists[name] = generate_range_values(parameter["start"], parameter["stop"], parameter["step"])

    return parameter_lists


def build_config_name(combo):
    """Build a config name for any number of parameter values."""
    return "v_" + "_".join(str(value).replace(" ", "") for value in combo)


def parse_parameters_text(parameters_text):
    """Parse dialog YAML text containing the modern parameters list."""
    if not parameters_text:
        return []

    if not YAML_AVAILABLE:
        print("PyYAML is required to parse parameters from dialog text.")
        return []

    parsed = yaml.safe_load(parameters_text)
    if parsed is None:
        return []
    if not isinstance(parsed, list):
        raise ValueError("Parameters must be a YAML list")

    return parsed


def generate_variant_combinations(config=None):
    """
    Generate variant parameter combinations in a spreadsheet.

    Args:
        config: Optional configuration dictionary with keys:
            - spreadsheet_label: Name of spreadsheet to create/use
            - parameters: List of parameter definitions with values or start/stop/step
    """
    doc = FreeCAD.ActiveDocument
    if not doc:
        print("No active document.")
        return

    # Use provided config or use defaults
    if config is None:
        config = {
            "spreadsheet_label": "VariantData",
            "parameters": [
                {"name": "PipeDiameter", "values": [10.1, 10.2]},
                {"name": "HexIndent", "values": [0.3, 0.5, 0.7, 0.9]},
                {"name": "HexLength", "values": [10]},
            ],
        }

    spreadsheet_label = config.get("spreadsheet_label", "VariantData")
    parameter_lists = build_parameter_lists(config)
    column_headers = ["ConfigName"] + list(parameter_lists.keys())

    if not parameter_lists:
        print(
            "No parameters configured. Add a 'parameters' list to macros.generate_variant_configs in .freecad_tools/config.yml."
        )
        return

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
        config_name = build_config_name(combo)

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
            "name": "parameters_yaml",
            "type": "text",
            "label": "Parameters YAML:",
            "default": "- name: PipeDiameter\n  start: 10.1\n  stop: 10.3\n  step: 0.1\n- name: HexLength\n  values: [10]",
            "help": "Prefer editing .freecad_tools/config.yml (macros.generate_variant_configs) for multiple parameters",
        },
    ]

    # Load or prompt for configuration
    config = load_or_prompt_config(
        str(UNIFIED_CONFIG_RELATIVE_PATH),
        dialog_fields=dialog_fields,
        dialog_title="Generate Variant Configurations",
        section="macros.generate_variant_configs",
        doc=doc,
    )

    if config:
        if "parameters" not in config and "parameters_yaml" in config:
            config["parameters"] = parse_parameters_text(config["parameters_yaml"])

        generate_variant_combinations(config=config)


# Run the macro
if __name__ == "__main__":
    main()
else:
    # When called via Macro menu, run main directly
    main()
