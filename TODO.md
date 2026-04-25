# FreeCAD Tools - Development TODO

**Note**: This file tracks open development tasks. For agent workflow guidance, see AGENTS.md (which does NOT contain task lists - only process guidance).

---

## Phase 2 Features - Open Tasks

### 1. Body Orientation Support [HIGH PRIORITY]
**Status**: ✅ COMPLETE
**Branch**: `agent_body_orientation` (merged to main)
**PR**: #2 (merged)

**Description**: Add support for rotating and positioning bodies in 3MF files without manual editing in slicer.

**Completed Features**:
- ✅ Config schema supports rotation and position specs
- ✅ Comprehensive documentation in README.md (new section with examples)
- ✅ Transform parsing in `tools/fc_export.py` via `parse_body_specs()`
- ✅ `create_euler_transform()` function for Euler angle rotation matrices
- ✅ 3MF transformation matrices applied via `lib3mf_utils.py`
- ✅ Full implementation tested and validated
- ✅ PR #2 created and merged

**Config Format** (now supported):
```yaml
export:
  - name: MyProject
    bodies:
      - Feed001                    # Simple format (no transform)
      - body: "Angle Round"
        rotation: [45, 0, 0]       # X, Y, Z degrees
        position: [0, 0, 5]        # X, Y, Z mm offset
```

**Files Modified**:
- `tools/fc_export.py`: Added parse_body_specs(), updated export_bodies_to_3mf_with_template()
- `tools/lib3mf_utils.py`: Added create_euler_transform(), updated create_3mf_from_stls()
- `examples/export_config.yml.example.yml`: Added example with oriented bodies
- `README.md`: New "Body Orientation and Positioning" section

---

### 2. Template Metadata Merging [COMPLETE - PR #3]
**Status**: MERGED
**Branch**: `agent_template_metadata` (merged to main)
**Effort**: Medium (2-3 hours)
**Impact**: High - For PrusaSlicer integration

**Description**: Merge printer settings and metadata from template 3MF files into generated exports.

**Implementation Summary**:
- ✅ Implemented `read_metadata_from_3mf()` in `lib3mf_utils.py` to extract template metadata
- ✅ Implemented `merge_metadata()` with "export", "template", and "merge" precedence modes
- ✅ Updated `create_3mf_from_stls()` to read and merge template metadata
- ✅ Pipeline already passed template path through fc_export → lib3mf_utils
- ✅ Added 7 unit tests for metadata functions (all pass)
- ✅ Updated README.md with comprehensive template metadata guide (120+ lines)
- ✅ Created PR #3 with 2,847 additions across 3 files

**Files Modified**:
- `tools/lib3mf_utils.py` - Added read_metadata_from_3mf(), merge_metadata()
- `tools/fc_export.py` - No changes needed (template pipeline already in place)
- `tests/test_lib3mf_utils.py` - Added TestMetadataFunctions class with 7 tests
- `README.md` - Added "Template Metadata Merging" section with examples

**Merged**: Yes (PR #3 merged to main)

---

### 3. Batch Processing [MEDIUM PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_batch_processing`
**Effort**: Low-Medium (1-2 hours)
**Impact**: Medium - For power users

**Description**: Process multiple export jobs from queue with parallel execution option.

**Tasks**:
- [ ] Design batch processing interface (CLI args or separate config)
- [ ] Implement export queue management
- [ ] Add progress reporting for batch jobs
- [ ] Handle errors per export (continue on failure)
- [ ] Test with multiple concurrent exports
- [ ] Document batch processing in README.md
- [ ] Create PR with comprehensive commit message
- [ ] Merge PR after review

**Files to Modify**:
- `tools/export.py`
- `tools/fc_export.py`
- `README.md`

---

### 4. Quality Metrics [MEDIUM PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_quality_metrics`
**Effort**: Low (1-2 hours)
**Impact**: Medium - For debugging and validation

**Description**: Report mesh statistics and validate 3MF output structure.

**Tasks**:
- [ ] Add vertex/triangle counting in `tools/lib3mf_utils.py`
- [ ] Parse 3D/3dmodel.model XML for mesh stats
- [ ] Implement file size reporting
- [ ] Add 3MF structure validation
- [ ] Generate quality report after export
- [ ] Test metrics with sample models
- [ ] Document metrics output in README.md
- [ ] Create PR with comprehensive commit message
- [ ] Merge PR after review

**Files to Modify**:
- `tools/lib3mf_utils.py`
- `tools/export.py`
- `README.md`

---

### 5. Multi-Document Support [LOW PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_multi_document`
**Effort**: Medium (2-3 hours)
**Impact**: Low - Niche use case

**Description**: Export bodies from multiple FCStd files in single export config.

**Tasks**:
- [ ] Design multi-document config schema
- [ ] Implement document loading and switching in `tools/fc_export.py`
- [ ] Handle object resolution across multiple documents
- [ ] Add dependency management between documents
- [ ] Test with multiple FCStd files
- [ ] Document multi-document exports in README.md
- [ ] Create PR with comprehensive commit message
- [ ] Merge PR after review

**Config Format**:
```yaml
export:
  - name: Combined
    documents:
      - source: project1.FCStd
        bodies: [Body1, Body2]
      - source: project2.FCStd
        bodies: [Body3, Body4]
```

**Files to Modify**:
- `tools/fc_export.py`
- `tools/export.py`
- `README.md`

---

### 6. TechDraw PDF Export & Bill of Materials [MEDIUM PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_techdraw_export`
**Effort**: Medium-High (3-5 hours)
**Impact**: High - Completes the design-to-production pipeline

**Description**: Export technical drawings as PDF and generate a bill of materials (BOM) from FreeCAD projects. BOM could be standalone or extracted from TechDraw pages.

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

**Possible Config Format**:
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

**Files to Modify/Create**:
- `tools/fc_export.py` - TechDraw PDF export, BOM extraction
- `tools/export.py` - Config handling for new sections
- `README.md`

---

### 7. Printables.com Upload & Publishing [LOW PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_printables_upload`
**Effort**: High (5-10 hours)
**Impact**: High - Closes the design-to-publish loop
**Depends on**: #6 TechDraw PDF Export & BOM

**Description**: Upload exported project artifacts (3MF, STL, PDF drawings, BOM) to Printables.com, including build/assembly instructions from a project markdown file.

**Key Constraint**: Printables.com has **no public API** (as of 2026). Options:
1. **Browser automation** (Selenium/Playwright) - fragile, breaks on site changes
2. **Undocumented GraphQL API** - reverse-engineer from browser DevTools, no stability guarantee
3. **Preparation-only mode** - package everything into a zip/folder ready for manual upload, with metadata pre-filled (title, description, tags, license) so the user only drags & drops

Recommendation: Start with option 3 (prepare upload package), add option 1 or 2 later if a stable API surface emerges.

**Build Instructions**:
- User creates `INSTRUCTIONS.md` (or similar) in the project directory
- Markdown is converted to HTML/plain text for the Printables description field
- Could include images referenced from a `docs/` or `images/` folder
- Config points to the instructions file

**Research Needed**:
- [ ] Monitor Printables for public API announcements
- [ ] Reverse-engineer GraphQL endpoint (browser DevTools) to assess feasibility
- [ ] Evaluate Playwright vs Selenium for browser automation robustness
- [ ] Determine Printables upload form fields (title, description, category, license, tags, files)
- [ ] Investigate Printables markdown/HTML support in description field

**Phase A - Upload Package Preparation** (no API needed):
- [ ] Define `printables` config section in export.yml
- [ ] Collect all export artifacts (3MF, STL, PDF, BOM) into a staging folder
- [ ] Convert INSTRUCTIONS.md to Printables-compatible description (HTML/text)
- [ ] Generate `printables_metadata.json` with title, description, tags, license, category
- [ ] Create zip archive ready for manual upload
- [ ] Copy description to clipboard (optional convenience)
- [ ] Document in README.md

**Phase B - Automated Upload** (requires API or browser automation):
- [ ] Implement Printables authentication (token or browser session)
- [ ] Implement model creation/update via GraphQL or Selenium
- [ ] Upload files (3MF, STL, PDF, images)
- [ ] Set description, tags, license, category
- [ ] Handle model updates (detect existing model, update files)
- [ ] Add `--dry-run` mode for testing without actual upload
- [ ] Test with real Printables account
- [ ] Document in README.md

**Possible Config Format**:
```yaml
export:
  - name: MyAntenna
    source: MyAntenna.FCStd
    bodies: [Feed, Cover]
    output: prints/MyAntenna.3mf
    techdraw:
      output: docs/MyAntenna_drawing.pdf
    bom:
      output: docs/MyAntenna_bom.csv

    printables:
      title: "VHF Yagi Antenna - 3D Printed"
      description_file: INSTRUCTIONS.md    # Build instructions markdown
      category: "Hobby & DIY"
      tags: [antenna, ham-radio, yagi, vhf]
      license: "CC-BY-SA-4.0"
      files:                               # Auto-collected if omitted
        - prints/MyAntenna.3mf
        - prints/stl/*.stl
        - docs/MyAntenna_drawing.pdf
        - docs/MyAntenna_bom.csv
      images:                              # Photos/renders for listing
        - docs/images/assembled.jpg
        - docs/images/printing.jpg
      staging_dir: .printables_upload/     # Where to prepare the package
```

**Files to Create/Modify**:
- `tools/printables_prep.py` - Upload package preparation (Phase A)
- `tools/printables_upload.py` - Automated upload (Phase B, later)
- `tools/export.py` - Integrate printables step into pipeline
- `README.md`

---

### 8. Explicit Body Selection Mode: Config vs FreeCAD Properties [HIGH PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_body_selection_mode`
**Effort**: Medium (3-4 hours)
**Impact**: High - Fixes ambiguity in current design, adds missing property-driven features

**Description**: Currently the body selection system is ambiguous: `bodies: []` is supposed to use FreeCAD-marked bodies, but the two modes (config-driven vs property-driven) can be mixed in confusing ways. This feature makes the mode **explicit** in the config and extends the FreeCAD property system with orientation and count.

**Problem**:
- Current `bodies: []` silently means "use marked bodies" - not obvious
- `find_exportable_bodies()` in macro_helper.py isn't actually wired into fc_export.py pipeline
- No way to specify orientation or count via FreeCAD body properties
- User could accidentally mix both approaches with undefined behavior

**Design**: Add an explicit `body_source` field to config:

```yaml
export:
  - name: MyProject
    source: MyProject.FCStd
    body_source: config          # "config" or "properties" - REQUIRED if bodies listed
    bodies:                      # Only used when body_source: config
      - Feed001
      - body: "Cover"
        rotation: [0, 0, 45]

  - name: AutoProject
    source: AutoProject.FCStd
    body_source: properties      # Read everything from FreeCAD body properties
    output: prints/AutoProject.3mf
    # No bodies list needed - reads from FreeCAD properties
```

**FreeCAD Custom Properties** (on each body, when `body_source: properties`):

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `ExportTo3MF` | Bool | Yes | Mark body for export (existing) |
| `ExportCount` | Int | No | Number of copies to export (default: 1) |
| `ExportRotation` | String | No | "X,Y,Z" degrees, e.g. "0,0,45" |
| `ExportPosition` | String | No | "X,Y,Z" mm offset, e.g. "10,0,5" (per-copy offset TBD) |

Notes on position: For multiple copies (`ExportCount > 1`), position could be:
- Same position for all (user arranges in slicer)
- Auto-arrayed with configurable spacing
- Defined per-copy (would need list property - complex)

Recommendation: Start without position in properties mode. Orientation is the key need. Position is better handled in config mode where per-body control is natural.

**Tasks**:

*Phase 1 - Make mode explicit, wire up property reading:*
- [ ] Add `body_source` field to config schema (`config` | `properties`)
- [ ] Validate: error if `body_source: config` but `bodies` is empty
- [ ] Validate: error if `body_source: properties` but `bodies` is non-empty
- [ ] Backwards compat: if `body_source` omitted, infer from `bodies` presence (warn about deprecation)
- [ ] Wire `find_exportable_bodies()` into fc_export.py for `body_source: properties`
- [ ] Read `ExportTo3MF` property to select bodies (existing logic)
- [ ] Add tests for mode validation and selection

*Phase 2 - Extend properties with orientation and count:*
- [ ] Read `ExportCount` property (default 1)
- [ ] Read `ExportRotation` property, parse "X,Y,Z" string to rotation tuple
- [ ] Generate duplicate entries with rotation when count > 1
- [ ] Feed property-derived body specs into existing `parse_body_specs` pipeline
- [ ] Add `set_export_properties()` helper to macro_helper.py for convenience
- [ ] Add tests for property reading and transform parsing

*Phase 3 - Documentation and tooling:*
- [ ] Document both modes clearly in README.md
- [ ] Add FreeCAD macro to set export properties via dialog
- [ ] Update example config with both modes
- [ ] Migration guide for existing users

**Files to Modify**:
- `tools/fc_export.py` - body_source validation, property reading, pipeline wiring
- `macros/macro_helper.py` - extend find_exportable_bodies() with orientation/count
- `tests/test_export_config.py` - body_source validation tests
- `tests/test_lib3mf_utils.py` - property-driven export tests
- `examples/export_config.yml.example.yml` - both modes
- `README.md`

---

### 9. GitHub Actions CI Workflow [HIGH PRIORITY]
**Status**: ✅ COMPLETE
**Branch**: `agent_github_ci` (merged to main via copilot/optimize-github-workflow-ci)
**Effort**: Low (1-2 hours)
**Impact**: High - Automated quality gate for all PRs and pushes

**Description**: Add a GitHub Actions workflow that mirrors the pre-commit hook checks and runs the test suite on every push and PR.

**Jobs**:

1. **Lint** (fast, ~30s):
   - Ruff lint (`ruff check tools/ tests/ macros/`)
   - Ruff format check (`ruff format --check tools/ tests/ macros/`)
   - yamllint on all YAML files
   - Pylint errors/failures only (`pylint --disable=all --enable=E,F tools/`)

2. **Test** (medium, ~1-2min):
   - Install dependencies via `uv pip install -e ".[dev]"`
   - Run unit tests (no FreeCAD): `pytest tests/test_git_utils.py tests/test_lib3mf_utils.py tests/test_export_config.py -v`

3. **Optional: Integration test** (slow, only if FreeCAD available):
   - Skip by default (FreeCAD not available in standard runners)
   - Could use a Docker image with FreeCAD for full pipeline test later

**Tasks**:
- [ ] Create `.github/workflows/ci.yml`
- [ ] Configure triggers: push to main, all PRs
- [ ] Set up Python environment with uv
- [ ] Run lint checks (ruff, yamllint, pylint)
- [ ] Run unit test suite
- [ ] Add branch protection rule recommendation to README.md
- [ ] Test workflow on a PR

**Workflow Skeleton**:
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv pip install ruff yamllint pylint --system
      - run: ruff check tools/ tests/ macros/
      - run: ruff format --check tools/ tests/ macros/
      - run: yamllint .pre-commit-hooks.yaml .yamllint
      - run: pylint --disable=all --enable=E,F tools/*.py

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv venv && uv pip install -e ".[dev]"
      - run: uv run pytest tests/test_git_utils.py tests/test_lib3mf_utils.py tests/test_export_config.py -v
```

**Files to Create**:
- `.github/workflows/ci.yml`

---

## Phase 1 Features - Completed ✅

### Completed in Previous Session
- ✅ Macro helper module with dialog UI and configuration
- ✅ Git metadata extraction (commit, branch, tags, remote)
- ✅ 3MF metadata embedding
- ✅ Body marking system (custom property `ExportTo3MF=True`)
- ✅ Enhanced macros with configuration support
- ✅ Comprehensive documentation (CHANGELOG, USAGE)
- ✅ PR #1 merged to main
- ✅ Agent workflow guidelines in AGENTS.md

### Files Created in Phase 1
- `macros/macro_helper.py` - Macro utilities (409 lines)
- `tools/git_utils.py` - Git integration (159 lines)
- `CHANGELOG.md` - Feature documentation (143 lines)

### Files Modified in Phase 1
- `tools/fc_export.py` - Added metadata extraction
- `tools/lib3mf_utils.py` - Added metadata embedding
- `macros/generate_variant_configs.py` - Use macro_helper
- `macros/variant_array_assignment.py` - Use macro_helper
- `examples/export_config.yml.example.yml` - Added examples
- `AGENTS.md` - Added PR management guidelines

---

## Notes

- Feature branches use `agent_<feature_name>` naming convention
- See AGENTS.md for development process, branching, PR management, commit format, and testing
- All development happens on feature branches, merged via PR
- Pre-commit hooks enforce code quality automatically

---

**Last Updated**: April 25, 2026
**Next Focus**: Batch Processing (agent_batch_processing)
