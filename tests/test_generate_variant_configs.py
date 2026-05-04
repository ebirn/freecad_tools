#!/usr/bin/env python3
"""Unit tests for variant configuration generation macro helpers."""

import importlib
import sys
from pathlib import Path


class FakeSheet:
    def __init__(self):
        self.Label = "VariantData"
        self.cells = {}
        self.styles = []
        self.clear_ranges = []

    def set(self, cell, value):
        self.cells[cell] = value

    def setStyle(self, cell_range, style, mode):  # noqa: N802 - FreeCAD API name
        self.styles.append((cell_range, style, mode))

    def clear(self, cell_range):
        self.clear_ranges.append(cell_range)


class FakeDocument:
    def __init__(self):
        self.Objects = []
        self.sheet = None
        self.recompute_count = 0

    def getObject(self, name):  # noqa: N802 - FreeCAD API name
        if self.sheet and name in ("VariantData", self.sheet.Label):
            return self.sheet
        return None

    def addObject(self, _type_id, _name):  # noqa: N802 - FreeCAD API name
        self.sheet = FakeSheet()
        self.Objects.append(self.sheet)
        return self.sheet

    def recompute(self):
        self.recompute_count += 1


def import_generate_variant_configs(monkeypatch, doc=None):
    macros_dir = Path(__file__).parent.parent / "macros"
    monkeypatch.syspath_prepend(str(macros_dir))

    import FreeCAD

    monkeypatch.setattr(FreeCAD, "ActiveDocument", doc, raising=False)
    sys.modules.pop("generate_variant_configs", None)
    return importlib.import_module("generate_variant_configs")


def test_build_parameter_lists_supports_range_config(monkeypatch):
    module = import_generate_variant_configs(monkeypatch)
    config = {
        "parameters": [
            {"name": "PipeDiameter", "start": 10.1, "stop": 10.3, "step": 0.1},
            {"name": "HexLength", "values": [10, 15]},
        ]
    }

    parameter_lists = module.build_parameter_lists(config)

    assert list(parameter_lists) == ["PipeDiameter", "HexLength"]
    assert parameter_lists["PipeDiameter"] == [10.1, 10.2, 10.3]
    assert parameter_lists["HexLength"] == [10, 15]


def test_generate_variant_combinations_handles_single_parameter(monkeypatch):
    doc = FakeDocument()
    module = import_generate_variant_configs(monkeypatch, doc=doc)

    module.generate_variant_combinations(
        {
            "spreadsheet_label": "VariantData",
            "parameters": [{"name": "PipeDiameter", "values": [10.1]}],
        }
    )

    assert doc.sheet.cells["A1"] == "ConfigName"
    assert doc.sheet.cells["B1"] == "PipeDiameter"
    assert doc.sheet.cells["A2"] == "'v_10.1"
    assert doc.sheet.cells["B2"] == "10.1"
    assert doc.recompute_count == 1


def test_parse_parameters_text_returns_parameter_definitions(monkeypatch):
    module = import_generate_variant_configs(monkeypatch)

    parameters = module.parse_parameters_text("- name: PipeDiameter\n  start: 10.1\n  stop: 10.3\n  step: 0.1")

    assert parameters == [{"name": "PipeDiameter", "start": 10.1, "stop": 10.3, "step": 0.1}]
