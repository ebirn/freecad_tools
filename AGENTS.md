# FreeCAD Tools - Agent Documentation

> **Bootstrap Prompt**: _"Read AGENTS.md, then continue work on the next open GitHub Issue in the Development project."_

**IMPORTANT**: This file provides process guidance, architecture overview, and development context. **Task tracking is in GitHub Issues + the Development project - NOT in this file.** Use issues for open tasks and feature status.

## Project Overview

**freecad_tools** is a collection of Python utilities for working with FreeCAD designs, enabling:
- **3MF Export**: Convert FreeCAD bodies to 3MF files with embedded mesh data for 3D printing
- **Variant Generation**: Create parametric variants of designs using FreeCAD macros
- **Printer Integration**: Preserve printer settings and configurations through template files

This project bridges FreeCAD (a powerful 3D CAD tool) with modern 3D printing workflows, particularly PrusaSlicer.

---

## Commit & Push Guidelines

### Always Ask Before Committing AND Pushing
- **NEVER commit without explicit user approval** - present changes and ask "Ready to commit?"
- **NEVER push without explicit user approval** - after committing, ask "Ready to push?" before running `git push`
- Wait for user confirmation before running `git commit`
- Wait for user confirmation before running `git push`
- These are separate approval steps - even if commit was approved, ask again before pushing

### Commit Message Format
All commit messages must follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification:

```
<type>(<scope>): <description>

[optional body]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Build, tooling, dependencies

**Examples:**
```
feat(hooks): add pre-commit integration for reusable export

fix(hooks): use stages instead of types for git hook events

docs(readme): add usage section for pre-commit workflow
```

---

## Test-Driven Development (TDD) for Bug Fixes and New Features

When a bug or error is reported or detected (except trivial ones), and when implementing new features, follow this process:

1. **Write a failing test first** - Create a test case that reproduces the error
2. **Verify the test fails** - Run the test to confirm it captures the bug
3. **Fix the code** - Develop against the failing test until it passes
4. **Verify all tests pass** - Run the full test suite to ensure no regressions

This ensures every non-trivial bug fix is backed by a regression test, preventing the same issue from recurring.

For **new features**, tests define the intended behavior and acceptance criteria:

1. **Design tests with care first** - Cover expected behavior, edge cases, and failure modes before coding
2. **Add tests before implementation** - New feature tests must be written first
3. **Confirm tests fail initially** - Verify they fail for the right reason before changing production code
4. **Implement until green** - Add functionality incrementally until the new tests pass
5. **Treat green tests as feature completeness signal** - Passing feature tests indicates the behavior is correctly implemented

Important: Great care is required when designing tests for new features. Poorly designed tests can hide defects or enforce the wrong behavior.

---

## Project Structure

```
freecad_tools/
├── AGENTS.md                          # This file - agent guidance
├── README.md                          # User-facing documentation
├── pyproject.toml                     # Python dependencies & project config
├── uv.lock                            # Locked dependencies
├── .envrc                             # Environment config (direnv)
├── .pre-commit-hooks.yaml             # pre-commit hook definitions
├── .venv/                             # Virtual environment (created by uv)
├── hooks/                             # pre-commit hook scripts
│   ├── freecad-export                 # Auto-run on git push
│   └── freecad-export-manual          # Manual trigger
├── macros/                            # FreeCAD macros
│   ├── generate_variant_configs.py    # Generate variant parameter configs
│   └── variant_array_assignment.py    # Manage array-based variants
├── templates/                         # Templates for projects
│   ├── pre-commit-config.yaml.example # pre-commit config template
│   ├── export.yml.example             # Export config template
│   └── template_print_settings.3mf   # PrusaSlicer settings template
├── tests/                             # Test suite
└── tools/                             # Python tools
    ├── export.py                      # CLI entry point
    ├── fc_export.py                   # FreeCAD integration layer
    └── lib3mf_utils.py                # 3MF creation (runs in venv)
```

---

## Core Concepts & Architecture

### 1. 3MF Export Pipeline

**Problem**: FreeCAD's native 3MF export works from the GUI, but users need:
- Automated batch exports via CLI
- Printer settings preservation (via templates)
- Control over STL file retention
- Support for exporting the same body multiple times

**Solution**: Multi-stage export pipeline

```
FreeCAD Model (FCStd)
    ↓
[fc_export.py] - Runs inside FreeCAD
    • Loads FreeCAD document
    • Resolves objects by Name or Label
    • Generates STL files with dynamic tessellation
    ↓
STL Files (temporary)
    ↓
[lib3mf_utils.py] - Runs in venv (outside FreeCAD)
    • Parses binary STL files
    • Embeds mesh data in 3MF via lib3mf C++ bindings
    • Creates valid 3MF with build items
    ↓
3MF File (with embedded meshes)
    ↓
[Optional Template Integration]
    • Preserve printer settings from template
    • Merge metadata/config
```

**Key Design Decision**: Use `lib3mf` (official 3MF Consortium C++ library) instead of manual XML:
- 100x+ faster (C++ bindings vs Python string manipulation)
- Properly handles 3MF spec compliance
- Maintains build plate settings and metadata

### 2. File Resolution System

**Problem**: Users have both internal names (e.g., "Body", "Body002") and friendly labels (e.g., "Feed", "Cover")

**Solution**: `resolve_object_identifier()` function in `fc_export.py`
- Try exact Name match first
- Fall back to Label match (case-sensitive)
- Returns tuple: (obj, resolved_name, resolved_label)
- User-friendly: accept Label in config, system handles resolution

**Example**:
```yaml
bodies:
  - Feed001          # Resolves by Label
  - Body002          # Resolves by Name
  - "Angle Round"    # Spaces OK with quotes
  - "Angle Round"    # Can export same body twice (gets _2 suffix)
```

### 3. STL File Management

**Naming Convention**: `{export_name}_{body_label}.stl` or `{export_name}_{body_label}_{count}.stl` if duplicated

**Example**: Export item with `name: Moxon_OE1EBG` exporting "Feed001" and "Angle Round" twice produces:
```
Moxon_OE1EBG_Feed001.stl
Moxon_OE1EBG_Angle_Round.stl
Moxon_OE1EBG_Angle_Round_2.stl
```

**Retention**: Config option `keep_stl` determines:
- `true`: Retain STL files in `stl_output_dir` for inspection/reuse
- `false` (default): Delete after 3MF creation (temp directory cleaned up)

### 4. Tessellation & Mesh Quality

**Dynamic Tolerance**: 0.1% of object's maximum dimension (minimum 0.001mm)
- For 50×50×15mm parts: tolerance = 0.05mm → high quality
- Calculated per-body in FreeCAD before conversion

**Mesh Deduplication**: In `lib3mf_utils.py`:
- Round vertex coordinates to 4 decimals
- Skip duplicate vertices during parsing
- Result: Smaller file size, no quality loss

**Example**: Feed body (4.8MB STL) → 50,765 vertices, 101,602 triangles in 3MF

### 5. Configuration System

**Location**: `export_config.yml` in project directory (or symlink to template)

**Schema**:
```yaml
export:
  - name: ExportName                    # Used for STL file prefixing & default output name
    source: Moxon_OE1EBG.FCStd          # FreeCAD document path
    bodies:                             # List of bodies to export (by Name or Label)
      - Feed001
      - Cover001
      - "Angle Round"
      - "Angle Round"                   # Same body twice
    output: prints/Moxon_OE1EBG.3mf     # 3MF output path (optional, defaults to prints/{name}.3mf)
    template: template_print_settings.3mf  # Optional: preserve printer settings
    keep_stl: true                      # Optional: retain STL files (default: false)
    stl_output_dir: prints/stl          # Optional: where to store STL files
```

**Defaults**:
- `output`: `prints/{name}.3mf` if not specified
- `keep_stl`: `false`
- `template`: Not used if not specified

### 6. Template System

**Purpose**: Preserve PrusaSlicer printer settings and metadata across exports

**How It Works**:
1. User exports once from PrusaSlicer GUI, saves as `template_print_settings.3mf`
2. Place in project directory
3. Reference in `export_config.yml`
4. Subsequent CLI exports use same settings

**Current Limitation**: Template integration not fully implemented yet. Placeholder in code for future enhancement.

### 7. Macros (FreeCAD Integration)

**`generate_variant_configs.py`**
- Purpose: Generate parameter variations of designs
- Use case: Create multiple sizes/configurations
- Input: Base design + parameter ranges
- Output: Config files for each variant

**`variant_array_assignment.py`**
- Purpose: Manage array-based design variations
- Use case: Handle instances/copies in arrays
- Input: FreeCAD document with arrays
- Output: Variant assignments

**Note**: These run *inside* FreeCAD (either via GUI macro menu or programmatically)

---

## Technology Stack

### Dependencies (pyproject.toml)
- **lib3mf** (2.5.0): Official 3MF Consortium library with Python bindings
- **PyYAML**: Config file parsing

### Python Version
- Requires Python 3.10+

### Environment
- **Virtual Environment**: Created with `uv` in `.venv/`
- **FreeCAD**: External tool, invoked via `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd` (macOS) or system `freecadcmd`

**IMPORTANT**: NEVER modify FreeCAD's embedded Python environment (`/Applications/FreeCAD.app/.../bin/python`).
- FreeCAD's Python is managed by the FreeCAD application and has its own dependencies
- Our virtual environment (`.venv/`) is separate and contains project-specific dependencies like pytest, lib3mf, etc.
- Integration tests should work with FreeCAD's Python as-is, using only what FreeCAD already provides
- lib3mf is a C++ library with Python bindings — the venv has it for Python 3.13, FreeCAD's Python 3.11 may have its own version

---

## Workflow: User Perspective

### Basic Export (Single Command)
```bash
cd Moxon_OE1EBG/
python3 ../freecad_tools/export/export.py
```

**Steps**:
1. Reads `export_config.yml` in current directory
2. Launches FreeCAD headless via `fc_export.py`
3. Exports bodies to temporary STL files
4. Calls `lib3mf_utils.py` to create 3MF with embedded meshes
5. Places output in `prints/Moxon_OE1EBG.3mf`
6. Optionally retains STL files in `prints/stl/`

### With Templates (Printer Settings Preservation)
```yaml
export:
  - name: Moxon_OE1EBG
    source: Moxon_OE1EBG.FCStd
    bodies: [Feed001, Cover001, "Angle Round", "Angle Round"]
    output: prints/Moxon_OE1EBG.3mf
    template: template_print_settings.3mf    # ← Added
    keep_stl: true
    stl_output_dir: prints/stl
```

---

## Known Limitations & Future Enhancements

### Current Limitations
1. **Template Metadata**: Placeholder code exists but not fully integrated
   - Extracts printer settings from template 3MF
   - Should merge into generated 3MF
   - Status: Framework in place, implementation pending

2. **Platform Detection**: Hardcoded FreeCAD path for macOS
   - `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd`
   - Needs fallback for Linux/Windows

3. **Error Recovery**: Limited graceful handling of malformed FCStd files

### Potential Enhancements
1. **Multi-Document Support**: Export from multiple FCStd files in one config
2. **Batch Processing**: Queue multiple export jobs
3. **Web UI**: REST API for export requests
4. **Variant Automation**: Auto-generate variant configs with parameter sweeps
5. **Quality Metrics**: Report mesh stats (vertex count, triangle count, file size)
6. **Template Creator Tool**: GUI to generate templates from existing prints

*Agents Note: This project is actively maintained. Check git log for recent changes.*

---

## For Agents: Release Procedure

### Version Numbering
- Follow [Semantic Versioning 2.0](https://semver.org/) (MAJOR.MINOR.PATCH)
- `pyproject.toml` is the source of truth for version
- Git tags follow format: `vMAJOR.MINOR.PATCH` (e.g., `v0.3.0`)
- CHANGELOG.md uses `[vMAJOR.MINOR.PATCH] - YYYY-MM-DD` format

### Release Steps

1. **Update Version in pyproject.toml**
   ```toml
   version = "X.Y.Z"
   ```

2. **Update CHANGELOG.md**
   - Move `[Unreleased]` section to `[vX.Y.Z] - YYYY-MM-DD`
   - Add release date
   - Ensure all changes since last release are documented

3. **Run Full Test Suite**
   ```bash
   make test           # Run all unit + integration tests
   ruff check          # Code quality
   ruff format         # Code formatting
   ```

4. **Commit Documentation Changes**
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "chore(release): prepare vX.Y.Z"
   ```

5. **Create Annotated Tag**
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

6. **Create GitHub Release** (Optional)
   - Go to: https://github.com/ebirn/freecad_tools/releases/new
   - Tag: `vX.Y.Z`
   - Title: `vX.Y.Z`
   - Description: Copy from CHANGELOG.md `[vX.Y.Z]` section

7. **Post-Release**
   - Ensure open follow-up work is captured in GitHub Issues/Development project
   - Announce in appropriate channels
   - Open PR for next version development

---

## For Agents: Branching Strategy & PR Management

### Feature Branch Naming Convention

All feature branches created by agents must follow this naming pattern:

```
agent_<feature_name>
```

**Examples:**
```
agent_body_orientation       # For body rotation/positioning features
agent_template_metadata      # For template metadata merging
agent_batch_processing       # For batch export improvements
agent_quality_metrics        # For mesh quality reporting
```

**Rules:**
- Prefix with `agent_` (required)
- Use lowercase with underscores
- Keep names descriptive but concise
- One feature per branch

### Pull Request Workflow

When creating a PR:

1. **Request Code Review from Copilot**
   ```bash
   gh pr edit <pr_number> --add-reviewer copilot
   ```

2. **Monitor PR Status**
   - Check for automated checks (pre-commit hooks, linting)
   - Monitor for Copilot review comments
   - Address any issues raised in review

3. **NEVER Merge PRs**
   - **Merging is a mandatory operator (human) task — agents must NEVER merge PRs.**
   - Do NOT run `gh pr merge`, `git merge`, or any merge command.
   - Once CI is green and review comments are addressed, inform the user that the PR is ready for their review and merge.
   - **Lesson learned**: PR #6 was merged by an agent with commits that should have been squashed. Squashing and merge strategy decisions belong to the operator.

4. **When PR is Merged (by operator)**
   - Switch back to main branch: `git checkout main`
   - Update main: `git pull origin main`
   - Delete feature branch: `git branch -d agent_<feature_name>`
   - Verify changes: `git log --oneline -5`

5. **Continue Development**
   - If starting new feature, create new `agent_<feature_name>` branch
   - Keep separate branches for each major feature
   - Do NOT reuse feature branches for different features

### Example Workflow

```bash
# 1. Create feature branch from main
git checkout main
git pull origin main
git checkout -b agent_body_orientation

# 2. Make changes and commit
# ... implement feature ...
git add -A
git commit -m "feat: add body orientation support in 3MF exports"

# 3. Push and create PR
git push -u origin agent_body_orientation
gh pr create --title "feat: add body orientation support" --body "..."

# 4. Request review
gh pr edit 2 --add-reviewer copilot

# 5. Wait for approval and merge
# ... address review comments if any ...
# DO NOT merge — inform the user the PR is ready for their review and merge

# 6. After merge (done by operator), clean up
git checkout main
git pull origin main
git branch -d agent_body_orientation
```

### Current Open Features

Use GitHub Issues and the Development project as the source of truth for open features.
When starting work, pick the next prioritized issue and create a matching `agent_<feature_name>` branch.

---

## For Agents: How to Continue Development

### Adding Features
1. **New export formats**: Modify `lib3mf_utils.py` to call different writers
2. **Config validation**: Enhance `load_config()` in `fc_export.py`
3. **Error handling**: Wrap FreeCAD operations in try/catch with detailed logging
4. **Platform support**: Add system detection in `export.py` for Windows/Linux paths

### Debugging
- **Log file**: `fc_export.log` in calling directory (created by `fc_export.py`)
- **STL inspection**: Keep `keep_stl: true` to inspect intermediate files
- **3MF validation**: Use `unzip -l output.3mf` to inspect structure
- **Mesh counting**: Parse 3D/3dmodel.model XML for vertex/triangle stats

### FreeCAD Automation Findings (Screenshots, TechDraw)

Practical learnings from implementing TechDraw export and body screenshot generation.

- **Avoid passing arbitrary CLI args to `freecadcmd`**: it parses argv and may reject unknown flags. Prefer env vars (`FREECAD_TOOLS_CONFIG`, `FREECAD_TOOLS_PROJECT_ROOT`, `FREECAD_TOOLS_NAME`).
- **Prefer `FreeCAD` GUI binary `-c` for automation**: invoking the GUI binary with a script path may open the full app and not exit. `FreeCAD -c "...exec(open('script.py').read())"` is more reliable.
- **Do not start your own Qt event loop**: nested `QEventLoop.exec_()` can hang. If you must, pump events via bounded `QApplication.processEvents()`.
- **`doc.recompute()` can hang** in GUI builds depending on document/workbench threads; make recompute opt-in for screenshots.
- **GUI available does not imply a 3D view exists**: in `-c` mode, `FreeCADGui` can import but there may be no 3D MDI view. Screenshot code must create/activate a 3D view before calling `activeView().saveImage()`.
- **`sys.exit()` may not terminate GUI subprocesses**: for automation subprocesses, consider `os._exit()` after writing the result file to avoid Qt threads keeping the process alive.
- **Ignore noisy optional framework warnings** unless they block (e.g. missing `3DconnexionNavlib.framework` on macOS).

### Test Output Directory

**All test/debug output goes in `test_output/` at the project root.**

- This directory is git-ignored (has its own `.gitignore` that excludes everything)
- **NEVER write test output into `examples/`** — that directory is for curated reference files only
- Integration test configs (e.g., `examples/export_techdraw_test.yml`) should write output to `test_output/`
- Pytest tests should use `tempfile.TemporaryDirectory()` or `test_output/`
- Temporary research/debug scripts should NOT be committed to `examples/`

```bash
# Run integration test from project root
python3 tools/export.py examples/export_techdraw_test.yml
# Output goes to test_output/assembly_test.3mf, test_output/bom.csv, etc.
```

### Testing
See the testing section below for the complete testing strategy.

Quick reference:
1. **Unit tests**: `python -m pytest tests/test_git_utils.py tests/test_lib3mf_utils.py -v`
2. **Integration tests**: Run from project root with FreeCAD, output to `test_output/`
3. **Regression**: Validate 3MF output structure

### Code Organization
- All Python code uses logging module (not print statements)
- Relative paths preferred for portability
- Subprocess calls for tool isolation (FreeCAD vs venv Python)

---

## Example Files for Development & Testing

Located in `examples/` directory:

- **`example.FCStd`** - Sample FreeCAD document for testing exports
  - Contains simple geometry to test the full export pipeline
  - Use with `examples/export_config.yml.example.yml` for testing

- **`example.3mf`** - Sample 3MF output for reference/testing
  - Shows expected structure of generated 3MF files
  - Can inspect with `unzip -l example.3mf` to view internal structure

- **`export_config.yml.example.yml`** - Template export configuration
  - Copy to `.freecad_tools/export.yml` in your test project
  - Update paths to point to your FCStd files
  - Shows all available config options with comments

- **`pre-commit-config.yaml.example`** - Pre-commit hook configuration template
  - Copy to `.pre-commit-config.yaml` in your test project
  - Configures freecad-export hooks with correct repository reference

### Quick Development Test

```bash
# 1. Set up a test project directory
mkdir test_project
cd test_project

# 2. Copy example configs
cp ../freecad_tools/examples/export_config.yml.example.yml .freecad_tools/export.yml
cp ../freecad_tools/examples/example.FCStd .

# 3. Update export.yml to reference example.FCStd
# Edit .freecad_tools/export.yml and update:
#   source: example.FCStd
#   bodies: [Body, Body001, ...]  (check with FreeCAD GUI)

# 4. Run export
python3 ../freecad_tools/tools/fc_export.py

# 5. Check output
ls -lh prints/example.3mf
unzip -l prints/example.3mf | grep model
```

---

## Key Files to Understand First

1. **`export.py`** (44 lines)
   - Entry point, simple CLI wrapper
   - Finds and calls `fc_export.py`

2. **`fc_export.py`** (464 lines)
   - Core FreeCAD integration
   - Key functions:
     - `resolve_object_identifier()` - Label/Name resolution
     - `export_bodies_to_3mf_with_template()` - Main export logic
     - `main()` - Config loading and orchestration

3. **`lib3mf_utils.py`** (240 lines)
   - Pure 3MF creation via lib3mf
   - Key functions:
     - `convert_stl_to_lib3mf_mesh()` - STL → lib3mf mesh conversion
     - `create_3mf_from_stls()` - Main 3MF creation
     - `create_from_json_config()` - Config-driven creation

---

## Development Tools & Workflows

### Installing Dev Dependencies
```bash
uv pip install -e ".[dev]"
```

### Pre-Commit Hooks Setup

This project uses **pre-commit** framework for automated code quality checks on every commit.

#### Installation & Setup
```bash
# Install pre-commit framework
pip install pre-commit

# Install hooks into git
pre-commit install
pre-commit install --hook-stage pre-push  # Install push-stage hooks

# Test hooks on all files
pre-commit run --all-files

# Update hook versions to latest
pre-commit autoupdate
```

#### What Hooks Run When

**On every `git commit` (pre-commit stage - FAST ~100ms):**
- **gitleaks** - Detect secrets/API keys before commit
- **Ruff lint** - Fast Python linting with auto-fix
- **Ruff format** - Python code formatting (replaces Black)
- **yamllint** - YAML syntax validation
- **Generic hooks** - Trailing whitespace, file endings, large files

**On `git push` (pre-push stage - SLOWER ~5-10s):**
- **pylint** - Deep Python code analysis (errors/failures only)

#### Hook Overview

| Hook | Purpose | Speed | Auto-fixes | Stage |
|------|---------|-------|-----------|-------|
| gitleaks | Detect secrets | Fast | ❌ | commit |
| Ruff lint | Lint & basic fixes | Fast | ✅ | commit |
| Ruff format | Code formatting | Fast | ✅ | commit |
| yamllint | YAML validation | Fast | ❌ | commit |
| Trailing-ws | Remove trailing spaces | Fast | ✅ | commit |
| End-of-file | Add newline at end | Fast | ✅ | commit |
| pylint | Deep analysis | Slow | ❌ | push |

#### Configuration Files

- **`.pre-commit-config.yaml`** - Defines all hooks and versions
- **`.yamllint`** - YAML linting rules (max line length 120, 2-space indent)
- **`pyproject.toml`** - Ruff and pylint configurations

### Manual Tool Usage

Tools can also be run directly without pre-commit:

#### Ruff (Python linting + formatting)
```bash
# Lint only (show errors)
ruff check tools/

# Lint and auto-fix
ruff check --fix tools/

# Format code
ruff format tools/

# Lint specific file
ruff check tools/fc_export.py
```

#### Pylint (Deep analysis)
```bash
# Run pylint manually
pylint tools/*.py

# Check for errors/failures only
pylint --disable=all --enable=E,F tools/
```

#### yamllint (YAML validation)
```bash
# Check YAML files
yamllint .pre-commit-hooks.yaml

# Check with strict mode
yamllint --strict .freecad_tools/export.yml
```

### Tool Configuration

**Ruff** (`pyproject.toml`)
- Line length: 120 characters
- Python version: 3.10+
- Rules: Includes E, F, I (imports), N (naming), W, UP, B (bugbear), C4 (comprehensions)

**Pylint** (`pyproject.toml`)
- Deep semantic analysis for errors/failures
- Runs on pre-push (slower, provides detailed feedback)
- Checks for logic errors, undefined variables, unused imports

**yamllint** (`.yamllint`)
- Max line length: 120 (warning at 120)
- Indent: 2 spaces
- No document-start marker required
- No trailing spaces allowed

### Skipping Hooks (Use Sparingly)

To skip a specific hook for one commit:
```bash
# Skip pre-commit hooks
git commit --no-verify

# Skip pre-push hooks
git push --no-verify
```

⚠️ **Warning**: Use `--no-verify` only in exceptional cases. It defeats the purpose of automated checks.

### Available Tools (for reference)

- **Ruff** - Modern, fast Python linter + formatter (consolidated tool)
  - 100x faster than traditional tools
  - Replaces Black + isort + Flake8
  - Latest version: 0.11.7

- **Pylint** - Deep Python code analysis
  - Catches complex logical errors
  - Runs only on pre-push to avoid slowing down commits
  - Latest version: 3.0.5

- **yamllint** - YAML syntax and style validation
  - Strict configuration to catch common YAML mistakes
  - Validates all `.yaml` and `.yml` files

### Documentation Access via Context7
When researching or implementing features, use the Context7 documentation tool:
- **Purpose**: Access up-to-date docs for libraries used in the project
- **Usage**: Call `mcp-server-context7_resolve-library-id` first to get the library ID, then `mcp-server-context7_query-docs` to fetch specific documentation
- **Libraries in this project**:
  - `PyYAML` - YAML parsing and serialization
  - `lib3mf` - 3MF file format creation and manipulation
  - `FreeCAD` - 3D CAD modeling (external tool, not in pip)
  - `Ruff` - Fast Python linter and formatter
  - `Pylint` - Deep Python code analysis
- **Example**: If implementing new YAML config features, query PyYAML docs for safe parsing practices

---

## Testing Strategy

### Test Organization

```
tests/
├── __init__.py              # Package marker
├── conftest.py              # Shared fixtures (examples_dir, sample files)
├── test_3mf.py              # 3MF file validation (standalone)
├── test_bom_utils.py        # BOM extraction utilities
├── test_export.py           # FreeCAD document inspection (requires FreeCAD)
├── test_export_config.py    # Config parsing, body specs, path resolution
├── test_fc_export_functions.py    # fc_export.py utility functions (unit tests)
├── test_fc_export_integration.py # fc_export.py FreeCAD-dependent functions
├── test_git_utils.py        # Git utilities (unit tests)
├── test_lib3mf_utils.py     # 3MF creation utilities (unit tests)
├── test_techdraw_pdf.py      # TechDraw PDF generation
└── test_yaml.py             # YAML config parsing (requires config)
```

### Test Categories

**Unit Tests (no FreeCAD required)** - Run anywhere:
- `test_bom_utils.py` - BOM utilities
- `test_export_config.py` - Config parsing, body specs, path resolution, metadata
- `test_fc_export_functions.py` - Utility functions from fc_export.py
- `test_git_utils.py` - Git metadata extraction
- `test_lib3mf_utils.py` - STL parsing, metadata functions, 3MF creation
- `test_techdraw_pdf.py` - PDF generation utilities
- `test_yaml.py` - YAML config parsing

```bash
# Run all unit tests
make test
# or: python -m pytest tests/ --ignore=tests/test_fc_export_integration.py -v

# Run specific module
python -m pytest tests/test_export_config.py -v
```

**Integration Tests (require FreeCAD)** - Test FreeCAD document interactions:
- `test_export.py` - Opens example.FCStd, inspects objects
- `test_fc_export_integration.py` - fc_export.py functions with real FreeCAD objects

**Note**: Integration tests run via FreeCAD's Python (`freecadcmd`), bypassing the venv.
The conftest.py auto-detects FreeCAD environment and skips mocking when appropriate.

```bash
# Run integration tests
make test-integration

# Run both unit and integration
make test-all
```
- `test_3mf.py` - Validates generated 3MF files

```bash
python tools/export.py
python -m pytest tests/test_3mf.py -v
```

### Test Data

| File | Location | Purpose |
|------|----------|---------|
| `example.FCStd` | `examples/` | Sample FreeCAD document |
| `example.3mf` | `examples/` | Reference 3MF output |
| `default.3mf` | `examples/` | Template 3MF with metadata |
| `export_config.yml.example.yml` | `examples/` | Comprehensive config example |
| `template_print_settings.3mf` | `templates/` | Printer settings template |

Shared fixtures in `tests/conftest.py` provide paths to all test data.

### Writing New Tests

**IMPORTANT**: Every new feature MUST include corresponding unit or integration tests. Tests should be created BEFORE the feature implementation (TDD approach) or immediately after for bug fixes.

Use Given-When-Then pattern:
```python
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

class TestModuleName:
    def test_function_with_given_then_expected(self):
        # Given
        input_data = "test_value"
        # When
        result = function_to_test(input_data)
        # Then
        assert result == expected_value
```

### Test Coverage

This project uses **pytest-cov** for code coverage reporting. Coverage helps identify untested code paths and ensures new features are properly tested.

**Installation** (already in dev dependencies):
```bash
uv pip install pytest-cov
```

**Running Tests with Coverage**:
```bash
# Run unit tests with coverage
python -m pytest tests/test_git_utils.py tests/test_lib3mf_utils.py tests/test_export_config.py --cov=tools --cov-report=term-missing -v

# Full test run with coverage
python -m pytest tests/ --cov=tools --cov-report=term-missing -v

# Generate HTML coverage report
python -m pytest tests/ --cov=tools --cov-report=html -v
# Open report: open htmlcov/index.html
```

**Coverage Report Options**:
- `term`: Terminal output (default)
- `term-missing`: Terminal output with line numbers of untested code
- `html`: Interactive HTML report in `htmlcov/` directory
- `xml`: Cobertura XML format for CI integration

**Target & Requirements**:
- **Minimum requirement**: Every new feature PR MUST include tests that cover at least the main functionality
- **Target coverage**: Aim for **80%+ overall** for the tools/ directory
- **Critical paths**: 100% coverage required for:
  - Configuration parsing (`load_config()` functions)
  - Error handling and validation
  - New public API functions
- **Focus areas**:
  - New functions and methods
  - Edge cases and error handling
  - Configuration parsing and validation
  - All code paths in new features

**Coverage Threshold**: Add minimum threshold in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
addopts = "--cov=tools --cov-fail-under=80"
```

**CI Integration**: Coverage is integrated into CI workflow (`.github/workflows/ci.yml`):
- Automatically generates coverage XML report and terminal output on every push/PR
- Uses pinned commit SHA for codecov-action (required by GitHub Actions security policy)
- Uploads to Codecov for historical tracking (optional, can be skipped)
- Terminal output shows missing lines during CI runs

**Action Security**: All GitHub Actions should be pinned to specific commit SHAs (not tags) for security. Prefer actions published by GitHub or verified Marketplace creators.

To view coverage locally:
```bash
# View coverage report in terminal
uv run pytest tests/test_git_utils.py tests/test_lib3mf_utils.py tests/test_export_config.py --cov=tools --cov-report=term-missing -v

# Generate and view HTML report
uv run pytest tests/ --cov=tools --cov-report=html -v
open htmlcov/index.html
```

### Running All Tests

```bash
# Quick (no FreeCAD required)
python -m pytest tests/test_git_utils.py tests/test_lib3mf_utils.py tests/test_export_config.py -v

# Full (requires FreeCAD)
cd examples && python ../tools/export.py && python -m pytest ../tests/ -v

# CI order: lint → unit → integration
ruff check tools/ tests/
ruff format --check tools/ tests/
python -m pytest tests/test_git_utils.py tests/test_lib3mf_utils.py -v
```

### Coverage Gaps (known)

- Full export pipeline end-to-end (requires FreeCAD)
- Real body extraction from FCStd (requires FreeCAD)
- Template metadata merging with actual 3MF files (integration)
- Git integration tests (require .git directory)

---

## Documentation & File Management Rules

### Allowed Markdown Files

This project uses exactly **four** markdown files. Do NOT create additional `.md` files.

| File | Purpose | Audience |
|------|---------|----------|
| `README.md` | All user-facing documentation | Humans |
| `AGENTS.md` | Agent process guidance, architecture, dev context | Agents |
| `TODO.md` | Pointer to issue-based task tracking | Agents |
| `CHANGELOG.md` | Version history (standard convention) | Both |

### Rules for Agents

- **NEVER create new `.md` files** (no PHASE_SUMMARY.md, no TESTING.md, no DESIGN.md, etc.)
- **User-facing docs** (usage, features, troubleshooting, API) go in `README.md`
- **Agent-facing docs** (architecture, process, testing strategy) go in `AGENTS.md`
- **Task tracking** (open tasks, priorities, status) goes in GitHub Issues + Development project
- **Release notes** go in `CHANGELOG.md`
- If you need to document something, find the right section in one of these four files
- When in doubt, add to `AGENTS.md` for dev context or `README.md` for user docs

### Issue Tracking Hygiene

Use GitHub Issues + Development project as the source of truth:

- Keep issue status current in the project board (Backlog/Ready/In Progress/Blocked/Done).
- When starting work on an issue, move it to **In Progress** in the Development project.
- When implementation is complete, add a comment referencing the commit SHA and move the issue to **Done**.
- Use structured issue templates for new tasks.
- When a task is finished, document shipped user-facing changes in **CHANGELOG.md** and **README.md** as needed.
- Keep `TODO.md` minimal as a pointer; do not duplicate issue-level task details there.

### Issue Update Workflow

When working on an issue, update it via GitHub comments (not AGENTS.md):

1. **When starting**: Comment with plan/scope, move to "In Progress"
2. **During work**: Comment on significant milestones, blockers, or scope changes
3. **When complete**: Comment with commit SHA, move to "Done", close if acceptance criteria met

Example commit message format:
```
feat(addon): implement FreeCAD Addon Manager macro collection support (#19)

- Created package.xml with XSD-compliant macro entries
- Added FreeCAD metadata headers to 3 macro files
- Added xmllint pre-commit hooks for XML validation
- Created tests/test_addon_package.py with 20 tests
```

The commit SHA should be referenced in the final issue comment.

### Ready vs In-Progress

When selecting work from the Development project:
- **Ready** issues should be worked on first (highest priority)
- **In Progress** issues are already being worked on (check if stuck/blocked)
- Only move an issue to "In Progress" when you actually start coding on it

### Release Process

When the user asks to cut a release:

1. **Pre-release checklist** (verify all before proceeding):
   - All tests pass (`python -m pytest` via venv)
   - CHANGELOG.md is up to date (no items left under `[Unreleased]` without a version)
   - Open follow-up work is captured as GitHub issues in the Development project
   - README.md reflects all current features and config options
   - Linter passes (`ruff check`, `ruff format --check`)

2. **Update CHANGELOG.md**:
   - Rename `[Unreleased]` to `[vX.Y.Z] - YYYY-MM-DD` with today's date
   - Add a fresh empty `[Unreleased]` section above it

3. **Commit and tag**:
   ```bash
   git add -A
   git commit -m "chore(release): vX.Y.Z"
   git tag vX.Y.Z
   ```

4. **Push** (only after user approval):
   ```bash
   git push && git push --tags
   ```

---

## Contact & Questions

When working on this project:
- Check existing log output first (very verbose debug logging in place)
- Review `export_config.yml.example` for all available options
- Test with sample files before modifying core logic
- Preserve backward compatibility with existing configs

---

*Agents Note: This project is actively maintained. Check git log for recent changes.*
