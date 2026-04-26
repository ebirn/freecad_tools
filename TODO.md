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

### 4. TechDraw PDF Export & Bill of Materials [MEDIUM PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_techdraw_export`
**Effort**: Medium-High (3-5 hours)

Export technical drawings as PDF and generate a bill of materials (BOM) from FreeCAD projects.

**Research Needed**:
- [ ] Investigate FreeCAD TechDraw workbench API for headless PDF export
- [ ] Determine best BOM source: TechDraw BOM table vs Part/Assembly inspection
- [ ] Evaluate output formats for BOM (CSV, PDF table, embedded in TechDraw)

**Tasks**:
- [ ] Implement TechDraw page detection and PDF export via freecadcmd
- [ ] Implement BOM extraction (parts list, quantities, materials)
- [ ] Extend export config schema with `techdraw` and `bom` sections
- [ ] Handle multiple TechDraw pages per document
- [ ] Test with example FreeCAD documents containing TechDraw pages
- [ ] Document in README.md

**Possible Config**:
```yaml
export:
  - name: MyProject
    source: MyProject.FCStd
    bodies: [Body]
    output: prints/MyProject.3mf
    techdraw:
      pages: []              # Empty = all pages, or list specific page labels
      output: docs/MyProject_drawing.pdf
    bom:
      output: docs/MyProject_bom.csv
      format: csv            # csv, or pdf (as TechDraw table)
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
        rotation: [0, 0, 45]

  - name: AutoProject
    source: AutoProject.FCStd
    body_source: properties      # Read from FreeCAD body properties
    output: prints/AutoProject.3mf
```

**FreeCAD Custom Properties** (when `body_source: properties`):

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `ExportTo3MF` | Bool | Yes | Mark body for export (existing) |
| `ExportCount` | Int | No | Number of copies (default: 1) |
| `ExportRotation` | String | No | "X,Y,Z" degrees, e.g. "0,0,45" |

Position omitted for properties mode - better handled in config mode.

**Phase 1** - Make mode explicit, wire up property reading:
- [ ] Add `body_source` field to config schema
- [ ] Validate: error if mode and bodies list conflict
- [ ] Backwards compat: infer from `bodies` presence if `body_source` omitted (deprecation warning)
- [ ] Wire `find_exportable_bodies()` into fc_export.py
- [ ] Add tests for mode validation

**Phase 2** - Extend properties with orientation and count:
- [ ] Read `ExportCount` and `ExportRotation` properties
- [ ] Feed property-derived body specs into existing pipeline
- [ ] Add `set_export_properties()` helper to macro_helper.py
- [ ] Add tests

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
