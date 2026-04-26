# FreeCAD Tools - Development TODO

Open development tasks. Completed items go to CHANGELOG.md.
For process guidance see AGENTS.md.

---

## Open Tasks

### 1. Batch Processing [MEDIUM PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_batch_processing`
**Effort**: Low-Medium (1-2 hours)

Process multiple export jobs with parallel execution and per-job error handling.

**Tasks**:
- [ ] Design batch processing interface (CLI args or separate config)
- [ ] Implement export queue management
- [ ] Add progress reporting for batch jobs
- [ ] Handle errors per export (continue on failure)
- [ ] Test with multiple concurrent exports
- [ ] Document in README.md

---

### 2. Quality Metrics [MEDIUM PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_quality_metrics`
**Effort**: Low (1-2 hours)

Report mesh statistics (vertex/triangle counts, file sizes) and validate 3MF output structure.

**Tasks**:
- [ ] Add vertex/triangle counting in `tools/lib3mf_utils.py`
- [ ] Implement file size reporting
- [ ] Add 3MF structure validation
- [ ] Generate quality report after export
- [ ] Test with sample models
- [ ] Document in README.md

---

### 3. Multi-Document Support [LOW PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_multi_document`
**Effort**: Medium (2-3 hours)

Export bodies from multiple FCStd files in a single export config.

**Possible Config**:
```yaml
export:
  - name: Combined
    documents:
      - source: project1.FCStd
        bodies: [Body1, Body2]
      - source: project2.FCStd
        bodies: [Body3, Body4]
```

---

### 4. TechDraw PDF Export & Bill of Materials [COMPLETE]
**Status**: DONE
**Branch**: `agent_techdraw_export`
**Completed**: April 26, 2026

Export technical drawings and generate a bill of materials (BOM) from FreeCAD projects.

**Completed Features**:
- ✅ BOM extraction from FreeCAD 1.0+ Assembly workbench
- ✅ BOM fallback extraction from Spreadsheet objects
- ✅ BOM fallback extraction from Part/Body inspection
- ✅ CSV generation with custom fields support
- ✅ Config schema extended with `techdraw:` and `bom:` sections
- ✅ Multi-page TechDraw detection
- ✅ Graceful handling of headless mode limitations
- ✅ 106 unit tests passing (56 config + 13 BOM CSV + 37 lib3mf/git utils)
- ✅ End-to-end testing with realistic Assembly documents
- ✅ Documentation in README.md

**Implementation Notes**:
- TechDraw SVG export is **limited by FreeCAD 1.1.1**: requires GUI rendering
- Workaround: export TechDraw pages manually from FreeCAD GUI (documented)
- BOM extraction is **fully production-ready**
- **Reads from existing Assembly::BomObject** (respects user's BOM configuration)
- CSV output columns match BomObject exactly (Index, Name, Description, File Name, Quantity, etc.)
- Falls back to Spreadsheet then Part/Body inspection if no BomObject found

**Config Format** (fully implemented):
```yaml
export:
  - name: MyProject
    source: MyProject.FCStd
    bodies: [Body]
    output: prints/MyProject.3mf

    techdraw:
      pages: []                    # Empty = all, or list specific labels
      output_dir: docs            # Where to save (future SVG export)
      format: svg                 # Only SVG currently recognized

    bom:
      source: assembly            # auto/assembly/spreadsheet/parts
      output: docs/MyProject_bom.csv
      spreadsheet_name: BOM       # If source: spreadsheet
      fields:                      # Optional custom fields
        - material
        - vendor
        - price
```

---

### 5. Printables.com Upload & Publishing [LOW PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_printables_upload`
**Effort**: High (5-10 hours)
**Depends on**: #4 TechDraw PDF Export & BOM

Upload exported project artifacts (3MF, STL, PDF, BOM) to Printables.com, including build/assembly instructions from a project markdown file.

**Key Constraint**: Printables.com has **no public API** (as of 2026). Options:
1. **Browser automation** (Selenium/Playwright) - fragile, breaks on site changes
2. **Undocumented GraphQL API** - reverse-engineer, no stability guarantee
3. **Preparation-only mode** - package everything into a zip/folder for manual upload

Recommendation: Start with option 3 (prepare upload package).

**Build Instructions**: User creates `INSTRUCTIONS.md` in project, converted to HTML/text for the Printables description field.

**Research Needed**:
- [ ] Monitor Printables for public API announcements
- [ ] Reverse-engineer GraphQL endpoint to assess feasibility
- [ ] Determine Printables upload form fields (title, description, category, license, tags, files)

**Phase A - Upload Package Preparation** (no API needed):
- [ ] Define `printables` config section in export.yml
- [ ] Collect all export artifacts into a staging folder
- [ ] Convert INSTRUCTIONS.md to Printables-compatible description
- [ ] Generate `printables_metadata.json` with title, description, tags, license
- [ ] Create zip archive ready for manual upload
- [ ] Document in README.md

**Phase B - Automated Upload** (requires API or browser automation):
- [ ] Implement Printables authentication
- [ ] Implement model creation/update
- [ ] Upload files, set description/tags/license
- [ ] Handle model updates (detect existing, update files)
- [ ] Add `--dry-run` mode
- [ ] Document in README.md

**Possible Config**:
```yaml
printables:
  title: "VHF Yagi Antenna - 3D Printed"
  description_file: INSTRUCTIONS.md
  category: "Hobby & DIY"
  tags: [antenna, ham-radio, yagi, vhf]
  license: "CC-BY-SA-4.0"
  images:
    - docs/images/assembled.jpg
  staging_dir: .printables_upload/
```

---

### 6. Explicit Body Selection Mode: Config vs FreeCAD Properties [HIGH PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_body_selection_mode`
**Effort**: Medium (3-4 hours)

Make body selection mode **explicit** in config (`body_source: config | properties`) and extend FreeCAD property system with orientation and count.

**Problem**:
- `bodies: []` silently means "use marked bodies" - not obvious
- `find_exportable_bodies()` isn't wired into fc_export.py pipeline
- No way to specify orientation or count via FreeCAD body properties
- Mixing both approaches has undefined behavior

**Design**:
```yaml
export:
  - name: MyProject
    source: MyProject.FCStd
    body_source: config          # "config" or "properties"
    bodies:
      - Feed001
      - body: "Cover"
        rotation: {axis: [0, 0, 1], angle: 45}   # 45 deg around Z

  - name: AutoProject
    source: AutoProject.FCStd
    body_source: properties      # Read from FreeCAD body properties
    output: prints/AutoProject.3mf
```

**FreeCAD Custom Properties** (when `body_source: properties`):

| Property | FreeCAD Type | Required | Description |
|----------|--------------|----------|-------------|
| `ExportTo3MF` | `App::PropertyBool` | Yes | Mark body for export |
| `ExportCount` | `App::PropertyInteger` | No | Number of copies (default: 1) |
| `ExportRotation` | `App::PropertyRotation` | No | Orientation for export |

All properties are grouped under `freecad_tools` in the Properties panel.

**`App::PropertyRotation` details**:
- FreeCAD GUI displays this as **Axis (x,y,z) + Angle** — not Euler angles
- Axis+Angle is unambiguous (no Euler convention confusion, no gimbal lock)
- Read in Python via `obj.ExportRotation` → `FreeCAD.Rotation` object
- Convert to rotation matrix for 3MF transform via `.toMatrix()`
- Construct in scripts: `FreeCAD.Rotation(FreeCAD.Vector(0,0,1), 45)` = 45 deg around Z

**Config rotation format** (when `body_source: config`):
- **Axis+Angle dict** (matches FreeCAD property): `rotation: {axis: [0, 0, 1], angle: 45}`
- This is the same representation shown in FreeCAD's Properties panel
- Axis is a direction vector (will be normalized), angle is in degrees
- No Euler angle ambiguity — what you set in config = what you see in FreeCAD GUI

**Implementation notes**:
- Current `parse_body_specs()` and `create_euler_transform()` use Euler X,Y,Z rotation order
- Must replace with axis+angle → rotation matrix conversion
- Rename `create_euler_transform()` → `create_axis_angle_transform()` (or similar)
- When reading `App::PropertyRotation` from FreeCAD, the `FreeCAD.Rotation` object
  can be converted to axis+angle via `.Axis` and `.Angle` properties
- All existing rotation tests must be updated for axis+angle format

**Test data** (in `examples/`):

| File | Bodies | Properties | Purpose |
|------|--------|------------|---------|
| `example.FCStd` | Simple geometry | None | Basic export pipeline testing |
| `example_properties.FCStd` | Angles, Ball, Cube, Doughnut | `ExportTo3MF`, `ExportCount`, `ExportRotation` | Property-based selection testing |
| `example_multi.FCStd` | Multiple bodies | None | Multi-document export testing |
| `example_techdraw.FCStd` | Bodies + TechDraw pages | None | TechDraw/BOM testing (Task #4) |

`example_properties.FCStd` body configurations:

| Body | ExportTo3MF | ExportCount | ExportRotation |
|------|-------------|-------------|----------------|
| Angles | true | 1 | identity (no rotation) |
| Ball | true | 1 | 90 deg around X |
| Cube | true | 3 | 45 deg around Z |
| Doughnut | false | 1 | identity (no rotation) |

**Phase 1** - Make mode explicit, wire up property reading:
- [ ] Add `body_source` field to config schema
- [ ] Validate: error if mode and bodies list conflict
- [ ] Backwards compat: infer from `bodies` presence if `body_source` omitted (deprecation warning)
- [ ] Wire `find_exportable_bodies()` into fc_export.py
- [ ] Add tests for mode validation

**Phase 2** - Extend properties with orientation and count:
- [ ] Read `ExportCount` and `ExportRotation` (`App::PropertyRotation`) properties
- [ ] Convert `FreeCAD.Rotation` → axis+angle for pipeline
- [ ] Update `parse_body_specs()` to accept `{axis: [x,y,z], angle: N}` dict format
- [ ] Replace `create_euler_transform()` with axis+angle → rotation matrix
- [ ] Feed property-derived body specs into existing pipeline
- [ ] Add `set_export_properties()` helper to macro_helper.py (using `App::PropertyRotation`)
- [ ] Update all rotation tests for axis+angle format

**Phase 3** - Documentation:
- [ ] Document both modes in README.md
- [ ] Add FreeCAD macro to set export properties via dialog
- [ ] Update example config with both modes

---

## Notes

- Feature branches use `agent_<feature_name>` naming convention
- See AGENTS.md for development process, branching, PR management, commit format, and testing
- All development happens on feature branches, merged via PR
- Pre-commit hooks enforce code quality automatically
