#!/usr/bin/env python3
"""Basic import/guard tests for FreeCAD macro helpers.

These tests run outside FreeCAD. They ensure importing macro_helper does not
crash when Qt/FreeCAD are not available.
"""

import sys
from pathlib import Path

import yaml


def test_macro_helper_import_and_dialog_guard():
    macros_dir = Path(__file__).parent.parent / "macros"
    sys.path.insert(0, str(macros_dir))
    try:
        import macro_helper

        # In unit test runs, FreeCAD is mocked by conftest; macro_helper should
        # treat that as not available.
        assert macro_helper.FREECAD_AVAILABLE is False
        assert macro_helper.show_config_dialog(title="Test", fields=[]) is None
    finally:
        sys.path.remove(str(macros_dir))


def test_load_macro_config_section_from_unified_config(tmp_path):
    macros_dir = Path(__file__).parent.parent / "macros"
    sys.path.insert(0, str(macros_dir))
    try:
        import macro_helper

        config_path = tmp_path / ".freecad_tools" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.safe_dump(
                {
                    "macros": {
                        "generate_variant_configs": {
                            "spreadsheet_label": "VariantData",
                            "parameters": [{"name": "PipeDiameter", "values": [10.1]}],
                        }
                    }
                }
            )
        )

        config = macro_helper.load_macro_config(str(config_path), section="macros.generate_variant_configs")

        assert config is not None
        assert config["spreadsheet_label"] == "VariantData"
        assert config["parameters"][0]["name"] == "PipeDiameter"
    finally:
        sys.path.remove(str(macros_dir))


def test_load_macro_config_section_falls_back_to_full_mapping(tmp_path):
    macros_dir = Path(__file__).parent.parent / "macros"
    sys.path.insert(0, str(macros_dir))
    try:
        import macro_helper

        config_path = tmp_path / ".freecad_tools" / "macro_config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump({"spreadsheet_label": "LegacyVariants"}))

        config = macro_helper.load_macro_config(str(config_path), section="macros.generate_variant_configs")

        assert config is not None
        assert config["spreadsheet_label"] == "LegacyVariants"
    finally:
        sys.path.remove(str(macros_dir))
