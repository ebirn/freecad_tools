# FreeCAD Tools - Development TODO

Open development tasks. Completed items go to CHANGELOG.md.
For process guidance see AGENTS.md.

---

## Open Tasks

### 1. Batch Job Runner (Multi-Job Queue) [LOW PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_batch_processing`
**Effort**: Low-Medium (1-2 hours)

Run multiple independent export jobs as a managed queue (across one or more config files/projects), with per-job progress and failure isolation.

**Tasks**:
- [ ] Design batch interface (`--batch` CLI and/or batch YAML)
- [ ] Support multiple config paths and output roots per batch job
- [ ] Implement queue execution with per-job status (pending/running/success/failed)
- [ ] Add continue-on-error mode and final summary report
- [ ] Optionally add bounded parallelism for independent jobs
- [ ] Add tests for mixed success/failure jobs and summary output
- [ ] Document batch runner usage in README.md

---

### 2. Multi-Document Support [LOW PRIORITY]
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

### 3. Printables.com Upload & Publishing [LOW PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_printables_upload`
**Effort**: High (5-10 hours)

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

### 4. Multi-Slicer CLI Slicing Automation (Native Profiles) [MEDIUM PRIORITY]
**Status**: IN PROGRESS
**Branch**: `agent_slicer_cli`
**Effort**: Medium (2-4 hours)

Add optional automation to slice exported 3MFs with multiple slicers in native-profile mode.

**Scope (v1)**:
- Supported slicers: **PrusaSlicer** and **OrcaSlicer**
- Native-profile mode only (no cross-slicer profile translation)
- Input 3MF comes from existing export output (`input_3mf: auto` default)

**Research**:
- [x] Confirm supported CLI flags on macOS for both slicers (`PrusaSlicer --help`, `OrcaSlicer --help`)
- [x] Map profile flags per slicer (`printer` + `print/process` + `filament`) and `--load` config bundle support
- [x] Decide output conventions for G-code (per-export-item) and where to write files

**Config + validation rules**:
- [x] Add optional `slicer:` section with `enabled`, `engine` (`prusa|orca`), `output_dir`, `output_name`, `run_after_export`, and engine-specific blocks
- [x] Allow profile fields to be optional when export item has `template` 3MF; require profiles or `use_config_bundle` when no template is present
- [ ] Define precedence when both template and profiles are set (profiles override template settings where slicer supports it)
- [x] Validate and report clear actionable errors for missing engine/binary/profile inputs

**Implementation ideas**:
- [x] Implement slicer command builders for PrusaSlicer and OrcaSlicer under a shared runner interface
- [x] Support G-code export path generation with stable naming tokens (e.g. `{name}`, `{engine}`, `{date}`)
- [x] Ensure slicing can run independently of FreeCAD (operate on generated 3MF only)
- [x] Add optional `--dry-run` for slicer command preview
- [x] Document native-profile behavior and template/profile compatibility notes in README.md

## Notes

- Feature branches use `agent_<feature_name>` naming convention
- See AGENTS.md for development process, branching, PR management, commit format, and testing
- All development happens on feature branches, merged via PR
- Pre-commit hooks enforce code quality automatically
