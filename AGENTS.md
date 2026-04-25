# FreeCAD Tools - Project Documentation for Agents

## Project Overview

**freecad_tools** is a collection of Python utilities for working with FreeCAD designs, enabling:
- **3MF Export**: Convert FreeCAD bodies to 3MF files with embedded mesh data for 3D printing
- **Variant Generation**: Create parametric variants of designs using FreeCAD macros
- **Printer Integration**: Preserve printer settings and configurations through template files

This project bridges FreeCAD (a powerful 3D CAD tool) with modern 3D printing workflows, particularly PrusaSlicer.

---

## Commit & Push Guidelines

### Always Ask Before Committing
- **NEVER commit and push without explicit user approval**
- Present the changes and ask "Ready to commit?" or similar
- Wait for user confirmation before running `git commit`
- Wait for user confirmation before running `git push`

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
- Requires Python 3.7+

### Environment
- **Virtual Environment**: Created with `uv` in `.venv/`
- **FreeCAD**: External tool, invoked via `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd` (macOS) or system `freecadcmd`

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

### Testing
1. **Unit tests**: Add to `tests/` directory (not yet created)
2. **Integration tests**: Test full pipeline with sample FCStd files in `examples/`
3. **Regression tests**: Ensure 3MF output remains valid across changes

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
- Python version: 3.7+
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

## Contact & Questions

When working on this project:
- Check existing log output first (very verbose debug logging in place)
- Review `export_config.yml.example` for all available options
- Test with sample files before modifying core logic
- Preserve backward compatibility with existing configs

---

*Last Updated: April 25, 2026*
*Agents Note: This project is actively maintained. Check git log for recent changes.*
