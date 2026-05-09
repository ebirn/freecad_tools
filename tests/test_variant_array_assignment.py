#!/usr/bin/env python3
"""Unit tests for the variant array assignment macro helpers."""

import importlib
import sys
from pathlib import Path


class FakeObject:
    def __init__(self, name, label=None, config="old", link_mode=None, visible=True):
        self.Name = name
        self.Label = label or name
        self.config = config
        self.LinkCopyOnChange = "Enabled"
        self.property_status_changes = []
        self.added_properties = []
        if link_mode is not None:
            self.LinkMode = link_mode
        if visible is not None:
            self.ViewObject = FakeViewObject(visible)

    def setPropertyStatus(self, property_name, status):  # noqa: N802 - FreeCAD API name
        self.property_status_changes.append((property_name, status))

    def addProperty(self, property_type, property_name, *args):  # noqa: N802 - FreeCAD API name, ARG002
        self.added_properties.append((property_type, property_name))
        setattr(self, property_name, None)


class FakeViewObject:
    def __init__(self, visible):
        self.Visibility = visible


class FakeArray:
    def __init__(self, base, elements):
        self.Name = "Array"
        self.Label = "Variant Array"
        self.Base = base
        self.OutList = [base, *elements]
        self.NumberX = 3
        self.NumberY = 1
        self.NumberZ = 1


class FakeDocument:
    def __init__(self, array, objects):
        self.array = array
        self.Objects = list(objects)
        self.objects = {obj.Name: obj for obj in objects}
        self.removed = []
        self.recompute_count = 0

    def getObject(self, name):  # noqa: N802 - FreeCAD API name
        return self.objects.get(name)

    def removeObject(self, name):  # noqa: N802 - FreeCAD API name
        self.removed.append(name)
        self.objects.pop(name, None)
        self.Objects = [obj for obj in self.Objects if obj.Name != name]

    def recompute(self):
        self.recompute_count += 1
        if self.array.NumberX == 1 and self.array.NumberY == 1:
            self.array.OutList = self.array.OutList[:2]


class FakeSpreadsheet:
    def __init__(self, values):
        self.values = values

    def get(self, cell):
        if cell not in self.values:
            raise ValueError(cell)
        return self.values[cell]


def import_variant_array_assignment(monkeypatch):
    macros_dir = Path(__file__).parent.parent / "macros"
    monkeypatch.syspath_prepend(str(macros_dir))

    import FreeCAD

    monkeypatch.setattr(FreeCAD, "ActiveDocument", None, raising=False)
    sys.modules.pop("variant_array_assignment", None)
    return importlib.import_module("variant_array_assignment")


def test_set_array_dimensions_updates_number_properties(monkeypatch):
    module = import_variant_array_assignment(monkeypatch)
    array = FakeArray(FakeObject("Base"), [])

    assert module.set_array_dimensions(array, 4, 2, 1) is True

    assert array.NumberX == 4
    assert array.NumberY == 2
    assert array.NumberZ == 1


def test_get_array_elements_excludes_base_object(monkeypatch):
    module = import_variant_array_assignment(monkeypatch)
    base = FakeObject("Base")
    element = FakeObject("Element001")
    array = FakeArray(base, [element])

    assert module.get_array_elements(array) == [element]


def test_cleanup_array_before_assignment_removes_stale_elements(monkeypatch):
    module = import_variant_array_assignment(monkeypatch)
    base = FakeObject("Base")
    element_1 = FakeObject("Element001")
    element_2 = FakeObject("Element002")
    element_3 = FakeObject("Element003")
    array = FakeArray(base, [element_1, element_2, element_3])
    doc = FakeDocument(array, [base, element_1, element_2, element_3])

    module.cleanup_array_before_assignment(doc, array)

    assert array.NumberX == 1
    assert array.NumberY == 1
    assert array.NumberZ == 1
    assert doc.removed == ["Element002", "Element003"]
    assert doc.recompute_count == 2
    assert element_1.LinkCopyOnChange == "Disabled"
    assert ("config", "-CopyOnChange") in element_1.property_status_changes
    assert ("config", "-Touched") in element_1.property_status_changes


def test_cleanup_array_before_assignment_removes_hidden_auto_delete_copy_groups(monkeypatch):
    module = import_variant_array_assignment(monkeypatch)
    base = FakeObject("Base")
    element = FakeObject("Element001")
    copy_group = FakeObject("CopyOnChangeGroup001", link_mode="Auto Delete", visible=False)
    unrelated_visible_group = FakeObject("CopyOnChangeGroup002", link_mode="Auto Delete", visible=True)
    unrelated_hidden_object = FakeObject("HiddenBody", link_mode="Manual", visible=False)
    array = FakeArray(base, [element])
    doc = FakeDocument(array, [base, element, copy_group, unrelated_visible_group, unrelated_hidden_object])

    module.cleanup_array_before_assignment(doc, array)

    assert "CopyOnChangeGroup001" in doc.removed
    assert "CopyOnChangeGroup002" not in doc.removed
    assert "HiddenBody" not in doc.removed


def test_tag_new_copy_on_change_groups_marks_new_hidden_auto_delete_groups(monkeypatch):
    module = import_variant_array_assignment(monkeypatch)
    base = FakeObject("Base")
    element = FakeObject("Element001")
    array = FakeArray(base, [element])
    existing_group = FakeObject("CopyOnChangeGroup001", link_mode="Auto Delete", visible=False)
    new_group = FakeObject("CopyOnChangeGroup002", link_mode="Auto Delete", visible=False)
    doc = FakeDocument(array, [base, element, existing_group, new_group])
    before_names = {base.Name, element.Name, existing_group.Name}

    tagged_count = module.tag_new_copy_on_change_groups(doc, array, before_names)

    assert tagged_count == 1
    assert new_group.FreeCADToolsManagedCopyOnChange is True
    assert new_group.FreeCADToolsArrayName == "Array"
    assert new_group.FreeCADToolsArrayLabel == "Variant Array"
    assert not hasattr(existing_group, "FreeCADToolsManagedCopyOnChange")


def test_cleanup_removes_tagged_copy_group_for_matching_array(monkeypatch):
    module = import_variant_array_assignment(monkeypatch)
    base = FakeObject("Base")
    element = FakeObject("Element001")
    array = FakeArray(base, [element])
    tagged_group = FakeObject("CopyOnChangeGroup001", link_mode="Auto Delete", visible=False)
    other_array_group = FakeObject("CopyOnChangeGroup002", link_mode="Auto Delete", visible=False)
    tagged_group.FreeCADToolsManagedCopyOnChange = True
    tagged_group.FreeCADToolsArrayName = "Array"
    other_array_group.FreeCADToolsManagedCopyOnChange = True
    other_array_group.FreeCADToolsArrayName = "OtherArray"
    doc = FakeDocument(array, [base, element, tagged_group, other_array_group])

    module.remove_hidden_auto_delete_copy_groups(doc, array, remove_untagged=False)

    assert "CopyOnChangeGroup001" in doc.removed
    assert "CopyOnChangeGroup002" not in doc.removed


def test_normalize_config_name_strips_forced_string_prefix(monkeypatch):
    module = import_variant_array_assignment(monkeypatch)

    assert module.normalize_config_name("'v_10.1") == "v_10.1"


def test_apply_configs_enables_link_copy_on_change_by_default(monkeypatch):
    module = import_variant_array_assignment(monkeypatch)
    base = FakeObject("Base")
    element = FakeObject("Element001")
    element.LinkCopyOnChange = "Disabled"
    array = FakeArray(base, [element])
    spreadsheet = FakeSpreadsheet({"A2": "'v_10.1"})
    doc = FakeDocument(array, [base, element])

    import FreeCAD

    monkeypatch.setattr(FreeCAD, "ActiveDocument", doc, raising=False)
    monkeypatch.setattr(
        module,
        "get_object_by_user_label",
        lambda _doc, identifier: spreadsheet if identifier == "VariantData" else array,
    )

    module.apply_configs_to_array(
        {"spreadsheet_label": "VariantData", "array_label": "Array", "cleanup_before_assign": False}
    )

    assert element.LinkCopyOnChange == "Enabled"
    assert element.config == "v_10.1"
    assert ("config", "CopyOnChange") in element.property_status_changes


def test_main_uses_unified_config_section(monkeypatch):
    module = import_variant_array_assignment(monkeypatch)
    doc = type("Doc", (), {"FileName": "/tmp/example.FCStd"})()

    import FreeCAD

    monkeypatch.setattr(FreeCAD, "ActiveDocument", doc, raising=False)

    called = {}

    def fake_load_or_prompt_config(config_path, dialog_fields=None, dialog_title=None, section=None, doc=None):
        called["config_path"] = config_path
        called["dialog_title"] = dialog_title
        called["section"] = section
        called["doc"] = doc
        return {"spreadsheet_label": "VariantData", "array_label": "Array"}

    monkeypatch.setattr(module, "load_or_prompt_config", fake_load_or_prompt_config)
    monkeypatch.setattr(module, "apply_configs_to_array", lambda config=None: called.setdefault("applied", config))

    module.main()

    assert called["config_path"].endswith(".freecad_tools/config.yml")
    assert called["section"] == "macros.variant_array_assignment"
    assert called["doc"] is doc
    assert called["applied"]["array_label"] == "Array"
