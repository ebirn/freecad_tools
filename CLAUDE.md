# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`freecad_tools` is a Python toolset that exports FreeCAD (`.FCStd`) designs to 3MF for 3D printing
(PrusaSlicer/OrcaSlicer), with TechDraw PDF export, screenshots, BOM generation, and FreeCAD macros for
parametric variants and text engraving. See `README.md` for full user-facing docs and `AGENTS.md` for
process/release guidance.

## Commands

### Setup
```bash
uv sync                       # create .venv and install deps
uv pip install -e ".[dev]"    # dev deps (ruff, pylint, yamllint, pytest, pytest-cov)
```

### Tests
```bash
make test                     # = make test-unit (no FreeCAD required)
python3 -m pytest tests/ --ignore=tests/test_fc_export_integration.py -v
python3 -m pytest tests/test_export_config.py -v       # single file
python3 -m pytest tests/test_export_config.py::TestClass::test_name -v  # single test

make test-integration         # requires FreeCAD; runs via freecadcmd
make test-all                 # unit + integration

# Coverage
python3 -m pytest tests/ --ignore=tests/test_fc_export_integration.py --cov=tools --cov-report=term-missing -v
```
`FREECAD_CMD` env var overrides the freecadcmd path (default
`/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd` on macOS).

Macro bundled-Python compatibility check (must pass for any new macro import):
```bash
/Applications/FreeCAD.app/Contents/Resources/bin/python tests/test_macros_bundled_python.py
```

### Lint / Format
```bash
ruff check tools/ tests/
ruff check --fix tools/
ruff format tools/ tests/
yamllint .pre-commit-hooks.yaml
pylint tools/*.py              # pre-push hook, errors/failures focus
```

### Running exports (end-to-end)
```bash
just export                    # = python3 tools/export.py tests/export_test_config.yml --gui-session run
just export-list
just export-item <name>
just export-item-dry-run <name>
just gcode-bounds test_output/gcode/<file>.gcode
just clean                      # rm -rf test_output/*
```
CLI directly: `python3 tools/export.py [config.yml] [--dry-run|--slicer-dry-run|--name X|--list-exports
|--gui-only|--screenshots-only|--gui-session item|run|--output-root PATH|-v]`

### Release validation
```bash
python3 tools/release_validator.py --summary
python3 tools/release_validator.py --check version|changelog|tests|all
```

## Architecture

### Export pipeline (multi-process, by design)
The export pipeline deliberately spans **three separate Python environments** because lib3mf and FreeCAD
cannot reliably coexist in one interpreter:

```
tools/export.py (CLI entry point, runs in venv)
   ↓ subprocess
tools/fc_export.py (runs inside FreeCAD's freecadcmd/Python)
   - loads .FCStd, resolves bodies by Name or Label (resolve_object_identifier)
   - applies rotation/position transforms
   - exports each body to a temp STL with dynamic tessellation (~0.1% of max dimension)
   ↓
tools/lib3mf_utils.py (runs back in venv)
   - parses STL, dedups vertices (rounded to 4 decimals)
   - builds the 3MF via lib3mf C++ bindings (create_3mf_from_stls)
   - merges template metadata (printer/profile settings) and git metadata (tools/git_utils.py)
```
GUI-only steps (TechDraw PDF export, screenshots) require the **FreeCAD GUI binary** (not freecadcmd),
invoked headlessly via `FreeCAD -c "...exec(open(script).read())..."`. These are orchestrated by
`tools/gui_batch_export.py` / `tools/gui_batch_run.py` and run either per export item (`--gui-session item`,
default) or batched once for the whole run (`--gui-session run`).

Key files:
- `tools/export.py` — CLI entry, config discovery, orchestration
- `tools/fc_export.py` (~3200 lines) — core FreeCAD-side logic: body resolution, transforms, STL export,
  body_source modes (`config` vs `properties`), BOM extraction trigger
- `tools/lib3mf_utils.py` — STL → 3MF conversion, metadata/template merging
- `tools/techdraw_export.py` / `tools/techdraw_pdf.py` — TechDraw page export + PDF merge/cover page
- `tools/body_screenshot.py` — GUI screenshot rendering
- `tools/bom_utils.py` — BOM CSV generation (assembly/spreadsheet/parts sources)
- `tools/git_utils.py` — git commit/branch/tag metadata for embedding
- `tools/gcode_bounds.py` — XY bounds reporting for sliced G-code (binary-safe parsing)
- `tools/release_validator.py` — version/changelog/test gates used by release workflows

### Configuration system
- Discovery order: `.freecad_tools/config.yml` → `.freecad_tools/export.yml` (legacy) →
  `export_config.yml` (legacy).
- `output_root` (config/env `FREECAD_TOOLS_OUTPUT_ROOT`/`--output-root`) relocates all relative output
  paths (3MF, techdraw, screenshots, bom, slicer gcode); precedence: CLI > env > config > project root.
- `body_source: config` (explicit `bodies:` list) vs `body_source: properties` (auto-detect bodies with
  `ExportTo3MF=True`, set via `macros/set_export_properties.py`). Backward-compat inference emits
  deprecation warnings if `body_source` is omitted.
- Bodies can be plain strings (Label or Name) or objects with `rotation` (Euler `[x,y,z]` or
  `{axis:[x,y,z], angle:deg}`) and `position: [x,y,z]`.

### Macros (`macros/`)
Run inside FreeCAD's GUI from the Macro menu, **must work with FreeCAD's bundled Python only** — no venv,
no pip packages beyond what FreeCAD ships (PyYAML, PySide, numpy, stdlib; **not** lib3mf). Any new import
in a macro must be added to `tests/test_macros_bundled_python.py` and verified to pass.
- `macro_helper.py` — shared utilities: config dialogs, object resolution by Name/Label, exportable-body
  discovery, `.freecad_tools/config.yml` section loading
- `generate_variant_configs.py` / `variant_array_assignment.py` — parametric variant generation, driven by
  `macros.generate_variant_configs` / `macros.variant_array_assignment` config sections
- `set_export_properties.py` — sets `ExportTo3MF`/`ExportCount`/`ExportRotation` custom properties on
  bodies (CLI via freecadcmd or GUI)
- `text_stamp.py` — engraves text on a selected face via pocket feature, configured under
  `macros.text_stamp`

### FreeCAD automation gotchas (learned the hard way)
- Avoid passing custom CLI args to `freecadcmd` — it parses argv strictly. Use env vars
  (`FREECAD_TOOLS_CONFIG`, `FREECAD_TOOLS_PROJECT_ROOT`, `FREECAD_TOOLS_NAME`) instead.
- Prefer `FreeCAD -c "exec(open(script).read())"` over passing a script path to the GUI binary (the latter
  may open the full app and not exit).
- Don't start a nested Qt event loop; pump with bounded `QApplication.processEvents()` if needed.
- `doc.recompute()` can hang in GUI builds — make it opt-in.
- In `-c` mode, `FreeCADGui` may import without a 3D MDI view existing; create/activate one before
  `activeView().saveImage()`.
- For automation subprocesses, prefer `os._exit()` after writing results to avoid lingering Qt threads.

## Project conventions

- **Test output**: everything generated by tests/dev runs goes in `test_output/` (git-ignored). Never
  write generated/debug files into `examples/` (curated reference files only).
- **Markdown files**: only four are allowed — `README.md` (user docs), `AGENTS.md` (agent/process docs),
  `TODO.md` (pointer to GitHub Issues), `CHANGELOG.md`. Do not create new `.md` files (no PHASE_SUMMARY.md,
  DESIGN.md, etc.). User-facing content goes in `README.md`, agent/process/architecture content in
  `AGENTS.md`.
- **Logging**: use the `logging` module, not `print`, in `tools/`.
- Relative paths preferred for portability; subprocess calls used for tool isolation (FreeCAD vs venv
  Python) — don't try to collapse this into a single process.
- TDD expected for non-trivial bug fixes and new features: write a failing test first, confirm it fails
  for the right reason, then implement until green, then run the full suite.
- Every new feature needs unit/integration test coverage of its main functionality; aim for 80%+ on
  `tools/`, with 100% on config parsing and error handling/validation paths.

## Git & PR workflow

- **Never commit or push without explicit user approval** — these are separate approval steps even within
  the same task. Ask "Ready to commit?" and, after that's done, "Ready to push?".
- Conventional Commits format: `<type>(<scope>): <description>` with types `feat`, `fix`, `docs`, `style`,
  `refactor`, `test`, `chore`.
- Feature branches: `agent_<feature_name>` (lowercase, underscores, one feature per branch), created from
  up-to-date `main`.
- PR workflow: open PR, request review (`gh pr edit <n> --add-reviewer copilot`), address feedback. Agents
  must **never** run `gh pr merge` or `git merge` — merging is an operator-only step. After the operator
  merges, switch to `main`, pull, and delete the feature branch.
- Avoid `--no-verify` (skips pre-commit/pre-push hooks: gitleaks, ruff lint/format, yamllint, pylint)
  except in exceptional, explicitly-approved cases.
- Task tracking lives in GitHub Issues + the Development project, not in `AGENTS.md`/`CLAUDE.md`/`TODO.md`.
  When starting an issue, move it to "In Progress"; when done, comment with the commit SHA and move to
  "Done".
