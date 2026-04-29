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

### 4. Refactor Export Core + Batch GUI Runs [HIGH PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_refactor_fc_export`
**Effort**: Medium-High (4-8 hours)

Refactor `tools/fc_export.py` (core export orchestrator) to reduce complexity and improve maintainability.

**Primary goal**: When an export item requires FreeCAD GUI (TechDraw, screenshots, etc.), batch all GUI-dependent steps into a single FreeCAD GUI launch per export run (or per export item), instead of launching FreeCAD multiple times.

**Tasks**:
- [ ] Refactor `fc_export.py` into clearer pipeline stages (config load, STL export, lib3mf, GUI tasks)
- [ ] Introduce a single GUI session execution path for all GUI-required steps (TechDraw + screenshots)
- [ ] Define a simple IPC contract for GUI runs (inputs: config/name, outputs: artifacts + structured result)
- [ ] Ensure non-GUI exports remain fast and do not require GUI binary
- [ ] Add regression tests around the pipeline boundaries (unit) and one integration test that exercises GUI batching
- [ ] Reduce GUI subprocess noise: keep logs structured in result JSON, emit concise summaries to stderr
- [ ] Add basic screenshot output validation (detect near-uniform images and warn)
- [ ] Add `--screenshots-only` / `--gui-only` mode to run GUI tasks without rebuilding 3MF (optional)
- [ ] Add `--list-exports` to print available export item names (pairs with `--name`)

---

## Notes

- Feature branches use `agent_<feature_name>` naming convention
- See AGENTS.md for development process, branching, PR management, commit format, and testing
- All development happens on feature branches, merged via PR
- Pre-commit hooks enforce code quality automatically
