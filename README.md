# FreeCAD Tools for 3D Printing

A comprehensive collection of Python utilities for converting FreeCAD designs to 3MF format optimized for 3D printing with PrusaSlicer. Automate exports, embed metadata, position bodies, and preserve printer settings.

## What It Does

**freecad_tools** bridges FreeCAD with modern 3D printing workflows by providing:

- **🎯 3MF Export**: Convert FreeCAD bodies to 3MF files with embedded mesh data, ready for PrusaSlicer
- **🔄 Body Rotation & Positioning**: Specify exact orientation and position in config (no manual adjustment in slicer needed)
- **📊 Metadata Embedding**: Embed project info, version, author, and git metadata directly in 3MF files
- **📄 TechDraw Export**: Extract technical drawings to PDF for documentation
- **📋 Bill of Materials**: Auto-generate BOM CSV from assemblies with custom fields
- **🏷️ Body Marking**: Mark bodies in FreeCAD for automatic export detection
- **⚙️ Parametric Variants**: Generate multiple design variations using FreeCAD macros
- **✍️ Text Engraving**: Personalize parts with custom text stamps and font files
- **📋 Template Support**: Preserve PrusaSlicer printer settings across exports
- **🔗 Git Integration**: Automatically capture commit hash, branch, and tags in exports
- **🚀 Automation**: Use with pre-commit hooks for automatic exports on push

---

## Quick Start (5 Minutes)

### Basic Setup

1. **Copy the example config** to your FreeCAD project:
   ```bash
   mkdir -p MyProject/.freecad_tools
   cp /path/to/freecad_tools/examples/config.yml MyProject/.freecad_tools/config.yml
   ```

2. **Edit the config** to specify your FreeCAD file and bodies:
   ```yaml
   export:
     - name: MyAntenna
       source: MyAntenna.FCStd
       bodies:
         - Feed001
         - Cover001
       output: prints/MyAntenna.3mf
   ```

3. **Run the export**:
   ```bash
   cd MyProject
   python3 /path/to/freecad_tools/tools/export.py
   ```

4. **Open in PrusaSlicer**:
   ```bash
   open prints/MyAntenna.3mf
   ```

That's it! Your 3MF file is ready for printing.

---

## Command-Line Interface

### Quick Reference

```bash
# Auto-discover config in current directory
python3 tools/export.py

# Specify config file
python3 tools/export.py path/to/config.yml
python3 tools/export.py --config path/to/config.yml

# Validate config without exporting
python3 tools/export.py path/to/config.yml --dry-run

# Build slicer commands but do not execute slicers
python3 tools/export.py path/to/config.yml --slicer-dry-run

# Verbose logging
python3 tools/export.py path/to/config.yml --verbose
python3 tools/export.py path/to/config.yml -v

# List available export item names
python3 tools/export.py path/to/config.yml --list-exports

# Export only one item by export[].name
python3 tools/export.py --config .freecad_tools/config.yml --name Moxon_OE1EBG_round

# Run only GUI tasks (screenshots + TechDraw), skip 3MF rebuild
python3 tools/export.py path/to/config.yml --gui-only

# Run only screenshots, skip 3MF and TechDraw
python3 tools/export.py path/to/config.yml --screenshots-only

# Queue GUI work and run one shared GUI session for the full run
python3 tools/export.py path/to/config.yml --gui-session run

# Redirect all generated outputs (prints/docs/images/bom/gcode)
python3 tools/export.py path/to/config.yml --output-root generated

# Show help
python3 tools/export.py --help
```

### Available Options

| Option | Short | Description |
|--------|-------|-------------|
| `--config PATH` | `-c PATH` | Specify YAML config file path |
| `--verbose` | `-v` | Enable debug logging output |
| `--dry-run` | | Validate config without performing export |
| `--slicer-dry-run` | | Build slicer commands but skip slicer execution |
| `--name NAME` | `-n NAME` | Export only the item with this name (from multi-item config) |
| `--list-exports` | | Print available export item names and exit |
| `--gui-only` | | Run GUI tasks only (screenshots/TechDraw), skip 3MF export |
| `--screenshots-only` | | Run screenshot tasks only, skip 3MF and TechDraw |
| `--gui-session MODE` | | GUI batching mode: `item` (default) or `run` (shared GUI session for all queued GUI jobs) |
| `--output-root PATH` | | Override base output directory for generated files |
| `--help` | `-h` | Show usage information |

**GUI Session Modes**:
- `item` (default): run GUI tasks as each export item is processed.
- `run`: queue GUI tasks and execute them in one shared FreeCAD GUI session after non-GUI export steps.

For practical end-to-end runs in this repository:

```bash
make export
```

To remove generated artifacts from `test_output/`:

```bash
make clean
```

Equivalent `just` recipes:

```bash
just export
just export-list
just export-item <name>
just gcode-bounds test_output/gcode/<file>.gcode
```

### Container Image Workflow

This repository can build and publish a container image to GHCR via:

- `.github/workflows/build-container-image.yml`

Triggers:
- Pushes to branches (including `main`)
- Version tags (`v*`)
- Manual run (`workflow_dispatch`)

Published image tags include:
- `latest` for slim image (default branch)
- `freecad-latest` for FreeCAD-enabled image (default branch)
- variant-prefixed branch/tag/SHA tags (for example `slim-main`, `freecad-main`, `slim-<sha>`, `freecad-<sha>`)

Example usage:

```bash
docker pull ghcr.io/ebirn/freecad_tools:latest
docker run --rm -v "$PWD:/workspace" ghcr.io/ebirn/freecad_tools:latest tests/export_test_config.yml --dry-run

docker pull ghcr.io/ebirn/freecad_tools:freecad-latest
docker run --rm -v "$PWD:/workspace" ghcr.io/ebirn/freecad_tools:freecad-latest tests/export_test_config.yml
```

Use `:latest` for lightweight tooling tasks and `:freecad-latest` for full export runs requiring FreeCAD.

### Reusable GitHub Workflows (for Consumer Repos)

`freecad_tools` publishes reusable workflows that consumer repositories can call directly:

- `.github/workflows/reusable-build-3mf-artifacts.yml`
- `.github/workflows/reusable-publish-nightly-release.yml`
- `.github/workflows/reusable-publish-tagged-release.yml`

These workflows are designed for FreeCAD project repositories (for example `Moxon_OE1EBG`) and only validate files available in the caller repository.
They do **not** depend on internal `freecad_tools` Python scripts during consumer runs.

Suggested usage:

```yaml
jobs:
  publish:
    uses: ebirn/freecad_tools/.github/workflows/reusable-publish-nightly-release.yml@main
    with:
      config_path: .freecad_tools/config.yml
      project_root: .
      gui_session: run
      dry_run: false
      bundle_paths: README.md INSTRUCTIONS.md Moxon_OE1EBG.FCStd
      generated_paths: docs prints
```

Notes:

- `bundle_paths` are required repository files; workflow fails if any path is missing.
- `generated_paths` are optional generated directories/files included when present.
- Checksums are generated from `bundle_paths` and published in release notes.
- For stable pipelines, pin reusable workflow usage to a tag or commit SHA instead of `@main`.

### Publishing Runbooks (Operator Guide)

This section is a practical checklist for operators maintaining consumer repos that use
the reusable workflows.

#### Who Does What

- **Contributor**: updates CAD/docs/config and opens PRs.
- **Operator**: runs publishing workflows, reviews run output, and manages releases/tags.

#### Nightly Release Runbook

Use this when you want a rolling, latest bundle for testing/download.

1. Ensure workflow reference is current in your consumer repo:
   - `ebirn/freecad_tools/.github/workflows/reusable-publish-nightly-release.yml@<ref>`
2. Confirm required bundle inputs exist in your repo:
   - every path listed in `bundle_paths`
3. Trigger workflow manually (`workflow_dispatch`) once after config changes.
4. Verify jobs complete:
   - `validate-release-readiness`
   - `validate-export-config / build-3mf-artifacts`
   - `publish-nightly-release`
5. Open the `nightly` release and confirm assets:
   - `<bundle>.tar.gz`, `<bundle>.zip`
   - notes include checksum block

#### Tagged Release Runbook

Use this for versioned, reproducible releases.

1. Ensure workflow reference is current:
   - `ebirn/freecad_tools/.github/workflows/reusable-publish-tagged-release.yml@<ref>`
2. Verify `bundle_paths` and expected generated directories.
3. Trigger by tag push (`v*`) or manual dispatch with `release_tag`.
4. Verify jobs complete:
   - `validate-release-readiness`
   - `validate-export-config / build-3mf-artifacts`
   - `publish-tagged-release`
5. Confirm GitHub release exists for the intended tag with:
   - release notes
   - `.tar.gz` and `.zip` assets
   - checksum section in notes

#### Troubleshooting Quick Guide

- **Missing required bundle path**
  - Symptom: readiness job fails before export.
  - Fix: correct `bundle_paths` or commit the missing files.

- **Artifact download failure in publish job**
  - Symptom: `gh run download` fails for `freecad-tools-artifacts`.
  - Fix: inspect `validate-export-config` job and resolve export/container errors first.

- **Container/export failures**
  - Symptom: failure in `build-3mf-artifacts` during container run.
  - Fix: verify `config_path`, `project_root`, and FreeCAD export config validity; rerun in dry-run first.

- **Unexpected release contents**
  - Symptom: missing docs/prints in final archive.
  - Fix: ensure `generated_paths` matches actual generated output directories.

- **Reference drift**
  - Symptom: behavior changed unexpectedly after upstream workflow updates.
  - Fix: pin reusable workflow references to a tag or commit SHA instead of `@main`.

#### Fresh-User Trial Checklist

Use this to validate docs/workflows from a clean operator perspective:

1. Start from a fresh clone of consumer repo.
2. Follow only README runbook instructions.
3. Run nightly workflow manually.
4. Run tagged workflow manually with a test tag name.
5. Confirm release assets and notes without using local tribal knowledge.
6. Record any ambiguous step and update README immediately.

#### Fresh-User Trial Report (Latest)

Most recent trial date: `2026-05-09`

Trial target repository:
- `ebirn/freecad_release_demo`

Executed workflow runs:
- Nightly (candidate branch): `https://github.com/ebirn/freecad_release_demo/actions/runs/25598613599`
- Tagged (candidate branch): `https://github.com/ebirn/freecad_release_demo/actions/runs/25598663410`
- Nightly (post-merge `@main` baseline): `https://github.com/ebirn/freecad_release_demo/actions/runs/25599105399`
- Tagged (post-merge `@main` baseline): `https://github.com/ebirn/freecad_release_demo/actions/runs/25599105988`

Observed result:
- All workflow jobs completed successfully.
- Release assets and notes were generated as expected.
- No internal `freecad_tools` script dependency was required in caller repositories.

#### Wiki Runbook Outline (Copy to Wiki)

Suggested wiki pages for operator-facing publishing docs:

1. **Nightly Publishing Runbook**
   - Purpose and when to use nightly
   - Required repo files and workflow inputs
   - Manual dispatch steps
   - Verification checklist (assets/checksums)
   - Common failures and quick fixes

2. **Tagged Release Runbook**
   - Version/tag naming guidance
   - Trigger methods (tag push vs manual `release_tag`)
   - Verification checklist (release page assets/notes)
   - Rollback/update procedure for incorrect tags

3. **Reusable Workflow Upgrade Playbook**
   - How to test candidate `freecad_tools` branches in demo harness
   - Required validation runs before merge
   - Post-merge switch back to `@main`
   - Pinning policy for stable consumer repos (tag/SHA)

**Config File Discovery** (when not specified):
1. `.freecad_tools/config.yml` (per-project unified config)
2. `.freecad_tools/export.yml` (legacy per-project export config)
3. `export_config.yml` (legacy config in current directory)

### Output Root Override

You can relocate generated outputs (3MF, TechDraw PDFs, screenshots, BOM CSV, slicer G-code)
without changing individual paths in each export item.

Supported controls:
- CLI: `--output-root PATH`
- Environment: `FREECAD_TOOLS_OUTPUT_ROOT`
- Config: top-level `output_root: PATH`

Precedence:
1. `--output-root`
2. `FREECAD_TOOLS_OUTPUT_ROOT`
3. `output_root` in YAML config
4. Project root (default)

Example:

```yaml
output_root: generated

export:
  - name: Demo
    source: example.FCStd
    output: prints/demo.3mf
    techdraw:
      output_dir: docs
    screenshots:
      enabled: true
      output_dir: docs/images
    bom:
      output: docs/bom.csv
```

With this config, files resolve under `generated/`:
- `generated/prints/demo.3mf`
- `generated/docs/Demo.pdf`
- `generated/docs/images/...`
- `generated/docs/bom.csv`

---

## Body Selection Modes

**NEW!** Explicitly control how bodies are selected for export with the `body_source` field.

| Mode | Description | Use Case |
|------|-------------|----------|
| `config` | Bodies explicitly listed in config | Full control, reproducible exports |
| `properties` | Bodies marked with `ExportTo3MF` property in FreeCAD | Flexible, visual selection |

### Config Mode: `body_source: config`

Bodies are specified explicitly in the YAML config. This is the default mode when `bodies` list is provided.

```yaml
export:
  - name: ExplicitExport
    source: MyDesign.FCStd
    body_source: config      # Required when using explicit bodies list
    bodies:
      - Body1
      - Body2
    output: prints/output.3mf
```

**When to use**:
- Reproducible exports (same bodies every time)
- CI/CD pipelines
- Multiple export configs for same document
- Version-controlled body selection

### Properties Mode: `body_source: properties`

Bodies are selected automatically based on FreeCAD custom properties. No `bodies` list needed.

```yaml
export:
  - name: PropertyExport
    source: MyDesign.FCStd
    body_source: properties   # No bodies list - use properties
    output: prints/output.3mf
```

**Required Properties** (added automatically by `macros/set_export_properties.py`):

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `ExportTo3MF` | App::PropertyBool | false | Set to `True` to export this body |
| `ExportCount` | App::PropertyInteger | 1 | Number of copies to export |
| `ExportRotation` | App::PropertyRotation | identity | Orientation (axis+angle format) |

**All properties are grouped under `freecad_tools` in the FreeCAD Properties panel.**

**Axis+Angle Rotation Format** (matches FreeCAD GUI display):
```yaml
rotation:
  axis: [0, 0, 1]   # X, Y, Z direction vector (normalized automatically)
  angle: 45         # Degrees (positive = counter-clockwise)
```

**Example**: Rotate 90° around X-axis:
```yaml
rotation:
  axis: [1, 0, 0]
  angle: 90
```

**Why Axis+Angle?**
- Unambiguous (no Euler angle convention confusion)
- No gimbal lock issues
- Matches what FreeCAD displays in Properties panel
- `FreeCAD.Rotation` objects use this format natively

### Backward Compatibility

If `body_source` is not specified, it is inferred from the `bodies` list:
- **With `bodies` list**: defaults to `config` mode (with deprecation warning)
- **Without `bodies` list**: defaults to `properties` mode (with deprecation warning)

**Migration**: Add `body_source: config` or `body_source: properties` to your configs to suppress warnings.

---

### Setting Properties via Macro

Use the `macros/set_export_properties.py` macro to set export properties on bodies:

**GUI Mode** (run from FreeCAD Macro menu):
1. Select bodies in the 3D view
2. Run the macro
3. All selected bodies get export properties with `ExportTo3MF=True`

**CLI Mode**:
```bash
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
  /path/to/freecad_tools/macros/set_export_properties.py \
  MyDesign.FCStd Body1 --count 3 --rotation-axis 0 0 1 --rotation-angle 45
```

**List all objects and their properties**:
```bash
freecadcmd /path/to/freecad_tools/macros/set_export_properties.py MyDesign.FCStd --list
```

---

## Common Use Cases

### 1. Simple Export (Basic)

Export bodies from FreeCAD to 3MF:

```yaml
export:
  - name: SimpleProject
    source: MyDesign.FCStd
    bodies:
      - Body
      - Body002
    output: prints/SimpleProject.3mf
```

**What happens**:
- Reads `MyDesign.FCStd`
- Exports "Body" and "Body002" as mesh objects
- Creates `prints/SimpleProject.3mf`
- Ready to open in PrusaSlicer

---

### 2. Export with Orientation (NEW!)

Position bodies exactly where they should be without manual adjustment.

**Two rotation formats supported:**

**Euler Format** (existing, backward compatible):
```yaml
rotation: [0, 0, 45]  # [X, Y, Z] degrees, intrinsic XYZ order
```

**Axis+Angle Format** (NEW - matches FreeCAD GUI):
```yaml
rotation:
  axis: [0, 0, 1]   # Direction vector (normalized automatically)
  angle: 45        # Degrees around that axis
```

**Example with both formats:**

```yaml
export:
  - name: OrientedAntenna
    source: Antenna.FCStd
    bodies:
      # Simple bodies (no rotation)
      - Feed001

      # Euler rotation: 45 degrees around Z-axis
      - body: "Mounting Bracket"
        rotation: [0, 0, 45]

      # Axis+Angle rotation: 90 degrees around X-axis
      - body: "Cable Guide"
        rotation:
          axis: [1, 0, 0]
          angle: 90
        position: [10, 0, 5]  # X, Y, Z in mm
    output: prints/Antenna_Positioned.3mf
```

**Why this matters**:
- ✅ Pre-positioned for optimal printing
- ✅ Save time in PrusaSlicer
- ✅ Consistent orientation across exports
- ✅ Supports multiple copies with different positions
- ✅ Axis+Angle format matches FreeCAD Properties panel display

**Rotation Details**:
- Euler: `rotation: [X, Y, Z]` - degrees around each axis, intrinsic XYZ order
- Axis+Angle: `rotation: {axis: [x, y, z], angle: deg}` - direction vector + angle
- Example Euler: `[45, 0, 0]` = 45° around body's X-axis
- Example Axis+Angle: `{axis: [0, 0, 1], angle: 90}` = 90° around Z-axis

**Position Details**:
- `position: [X, Y, Z]` - millimeter offset from origin
- Example: `[10, 0, 0]` = 10mm in positive X direction
- Example: `[0, 20, 5]` = 20mm in Y, 5mm in Z

---

### 3. Export with Metadata

Embed project information directly in the 3MF file:

```yaml
export:
  - name: MyProject
    source: MyProject.FCStd
    bodies:
      - Body
    output: prints/MyProject.3mf
    metadata:
      Project: "MyAntenna"
      Version: "2.1"
      Author: "Jane Smith"
      Description: "Optimized for 0.4mm nozzle"
```

**Auto-Added Metadata** (if in git repo):
- `GitCommit`: Commit hash (short form)
- `GitBranch`: Current branch name
- `GitTags`: Any tags on current commit
- `GitRemote`: Repository URL

**View in PrusaSlicer**:
- Open the 3MF file
- Metadata appears in object properties
- Track which version of the model is on your print bed

---

### 4. Multiple Exports at Once

Export multiple designs from one config:

```yaml
export:
  - name: Antenna_Main
    source: Antenna.FCStd
    bodies:
      - MainPart
      - Feed
    output: prints/Antenna_Main.3mf

  - name: Antenna_Bracket
    source: Antenna.FCStd
    bodies:
      - MountingBracket
    output: prints/Antenna_Bracket.3mf

  - name: CableGuide
    source: CableGuide.FCStd
    bodies:
      - Guide
    output: prints/CableGuide.3mf
```

**Result**: Three 3MF files created, all with metadata and git info

---

### 5. Export Only Marked Bodies

Mark bodies in FreeCAD and let the tool find them automatically:

**In FreeCAD**:
1. Select a body in the tree
2. Add custom property:
   - Name: `ExportTo3MF`
   - Type: Boolean
   - Value: `True`
3. Repeat for all bodies to export

**In config** (leave bodies empty):
```yaml
export:
  - name: AutoExport
    source: MyDesign.FCStd
    bodies: []  # Empty = use marked bodies
    output: prints/AutoExport.3mf
```

**Benefits**:
- ✅ No need to update config when adding bodies
- ✅ Visual marking in FreeCAD (custom property is visible)
- ✅ Flexible - mark different sets for different exports

---

### 6. Keep STL Files for Inspection

Sometimes you want to inspect the intermediate STL files:

```yaml
export:
  - name: DebugExport
    source: MyDesign.FCStd
    bodies:
      - Body
    output: prints/MyDesign.3mf
    keep_stl: true
    stl_output_dir: prints/stl
```

**Result**:
- `prints/MyDesign.3mf` - Final 3MF file
- `prints/stl/DebugExport_Body.stl` - Intermediate mesh file

**Use cases**:
- Inspect mesh quality before printing
- Use in other tools (Meshmixer, etc.)
- Debug export issues

---

### 7. Export TechDraw Pages to PDF

Extract technical drawings from your FreeCAD documents:

```yaml
export:
  - name: Antenna
    source: Antenna.FCStd
    bodies:
      - MainBody
      - Feed001
    output: prints/Antenna.3mf
    techdraw:
      pages: []              # Empty = export all TechDraw pages
      output_dir: docs       # Where to save exported files
      format: pdf            # Currently only 'pdf' supported
      instructions: INSTRUCTIONS.md  # Optional: markdown rendered into PDF
```

**How It Works**:
TechDraw PDF export uses a two-step pipeline:
1. FreeCAD GUI binary exports individual page PDFs via `TechDrawGui.exportPageAsPdf()`
2. Pages are merged with optional cover page (metadata, TOC, BOM) and instructions

This requires the FreeCAD GUI binary (not freecadcmd). On macOS it runs headlessly without displaying a window. Set `FREECAD_GUI_BINARY` environment variable if FreeCAD is not in a standard location.

**Why use this**:
- Keep technical drawings in sync with CAD model
- Embed in documentation
- Version control drawings alongside 3MF
- PDF preserves all annotations, hatching, dimensions, and balloons

---

### 8. Generate Publication Screenshots

Generate publication-ready screenshots (Thingiverse/Printables) using the FreeCAD GUI renderer.

```yaml
export:
  - name: Antenna
    source: Antenna.FCStd
    bodies: [MainBody, Feed001]
    output: prints/Antenna.3mf
    screenshots:
      enabled: true
      output_dir: docs/images/
      views: [isometric, front, top]
      resolution: [1920, 1080]
      format: png
      composite: true
```

Notes:
- Requires the FreeCAD GUI binary (not `freecadcmd`).
- Screenshot failures are non-fatal to the main export.

---

### 9. Generate Bill of Materials (BOM)

Automatically extract parts lists from assemblies:

```yaml
export:
  - name: Antenna
    source: Antenna.FCStd
    bodies:
      - MainBody
      - Feed001
    output: prints/Antenna.3mf
    bom:
      source: auto          # auto/assembly/spreadsheet/parts
      output: docs/Antenna_BOM.csv
      fields:               # Optional custom fields
        - material
        - vendor
        - price
```

**BOM Sources** (tried in order):

1. **`assembly`** - FreeCAD 1.0+ native Assembly workbench
   - Reads assembly tree and counts duplicates
   - Most detailed and accurate

2. **`spreadsheet`** - FreeCAD Spreadsheet workbench
   - Reads cells from "BOM" spreadsheet
   - Good for manual part lists

3. **`parts`** - Fallback to Part/Body objects
   - Lists all Part and Body objects in document
   - Simple but less detailed

**Custom Spreadsheet Name**:
```yaml
bom:
  source: spreadsheet
  spreadsheet_name: "ComponentList"  # If not named "BOM"
  output: docs/parts.csv
```

**What gets generated**:
- CSV file with columns matching the BOM source:
  - **Assembly**: Columns from BomObject (e.g., `Index`, `Name`, `Description`, `File Name`, `Quantity`)
  - **Spreadsheet**: Columns from spreadsheet cells
  - **Parts**: `label`, `quantity`, plus any custom fields
- Example output (assembly source):
  ```
  Index,Name,Description,File Name,Quantity
  1,Bearing 608,8mm Ball Bearing,Bearing.FCStd,4
  2,Housing,Main housing,Housing.FCStd,1
  ```

**Why use this**:
- ✅ Track bill of materials alongside design
- ✅ Pricing and vendor info
- ✅ Auto-count duplicates in assemblies
- ✅ Easy import to spreadsheets for procurement

---

## Full Configuration Reference

### Top-Level Configuration

```yaml
output_root: generated               # Optional: base dir for relative output paths
export:
  - name: Example
    source: example.FCStd
```

Notes:
- `output_root` applies to relative output fields (`output`, `techdraw.output_dir`, `screenshots.output_dir`, `bom.output`, `slicer.output_dir`).
- Absolute paths are preserved.
- `source` remains resolved from project/config location.

### TechDraw Export Configuration

```yaml
techdraw:                           # Optional: export technical drawings
  pages: []                         # Which pages to export
                                    # - Empty/omitted = all pages
                                    # - List page labels: ["Drawing1", "Assembly"]
  output_dir: docs                  # Where to save exported files
  format: pdf                       # Currently only 'pdf' supported
  instructions: INSTRUCTIONS.md     # Optional: markdown file to include in PDF report
```

### Screenshot Configuration

```yaml
screenshots:                        # Optional: generate PNG/JPG screenshots
  enabled: true                     # Boolean, or use short form: screenshots: true
  output_dir: docs/images           # Where to save images
  views: [isometric, front, top]    # isometric/front/top/right/back/bottom/left
  resolution: [1920, 1080]          # [width, height]
  background: [255, 255, 255, 255]  # RGBA (currently best-effort)
  format: png                       # png or jpg
  composite: true                   # true: all bodies together; false: per-body
```

### BOM Generation Configuration

```yaml
bom:                                # Optional: generate bill of materials
  source: auto                      # Where to get BOM data:
                                    # - 'auto' = try assembly → spreadsheet → parts
                                    # - 'assembly' = only Assembly
                                    # - 'spreadsheet' = only Spreadsheet
                                    # - 'parts' = only Part/Body objects
  assembly: MainAssembly            # (optional) Specific assembly name/label for 'assembly' source
  output: docs/bom.csv              # CSV output file path
  spreadsheet_name: BOM             # (optional) Spreadsheet name if not "BOM"
  fields:                           # (optional) Custom property names to extract
    - material
    - vendor
    - price
    - dimensions
```

### Slicer Configuration (PrusaSlicer / OrcaSlicer)

```yaml
slicer:
  enabled: true
  engine: prusa                    # prusa | orca
  binary: /path/to/slicer          # optional override; auto-detected on macOS/PATH
  output_dir: test_output/gcode    # where generated gcode is written
  output_name: "{name}_{engine}_{date}.gcode"
  run_after_export: true           # optional, default true
  dry_run: false                   # optional per-item slicer dry run

  # Optional: use slicer settings bundle instead of profile triplet
  use_config_bundle: false
  config_bundle: profiles/prusa.ini

  prusa:                           # used when engine=prusa
    printer_profile: "Original Prusa MINI & MINI+ Input Shaper"
    print_profile: "0.20mm STRUCTURAL @MINIIS 0.4 - Flo"
    material_profile: "Generic PLA @MINIIS"
    extra_args: []

  orca:                            # used when engine=orca
    extra_args: []
```

Notes:
- Native-profile mode only: no profile translation between slicers.
- If `template` is set on the export item, profile fields may be omitted.
- Without `template`, provide either profile fields or `use_config_bundle: true`.
- For `engine: prusa`, if profile overrides are omitted and `template` is set, slicer settings are loaded from `Metadata/Slic3r_PE.config` in the template 3MF via a temporary `--load` config bundle.
- For `engine: orca`, if `template` is set and no explicit config bundle is provided, the same template config is passed via `--load-settings`.
- Prusa binary G-code may not be plain text; use `tools/gcode_bounds.py` to report XY bounds.

**Multiple BOMs from Different Assemblies**:
```yaml
bom:
  - assembly: MainAssembly
    output: docs/main_bom.csv
  - assembly: SubAssembly
    output: docs/sub_bom.csv
```

### Complete Export Item with All Features

```yaml
export:
  - name: CompleteProject
    source: CompleteProject.FCStd

    # 3MF export
    bodies:
      - MainAssembly
      - Bracket
    output: prints/Project.3mf
    template: template_print_settings.3mf
    keep_stl: false

    # Technical drawings
    techdraw:
      pages: []                   # All TechDraw pages
      output_dir: docs
      format: pdf
      instructions: INSTRUCTIONS.md

    # Screenshots for publication
    screenshots:
      enabled: true
      output_dir: docs/images
      views: [isometric, front]

    # Bill of materials
    bom:
      source: auto                # Auto-detect from assembly
      output: docs/bom.csv
      fields:
        - material
        - vendor
        - stock_code

    # Metadata
    metadata:
      Project: "CompleteProject"
      Version: "2.0"
      Author: "Engineering Team"
```

---

### Config File Location
```
MyProject/
├── .freecad_tools/
│   └── config.yml          # ← Your config goes here
└── MyProject.FCStd
```

Use `examples/config.yml` as the starter template.

Or legacy location:
```
MyProject/
├── export_config.yml       # ← Alternative location
└── MyProject.FCStd
```

### Configuration Schema

```yaml
export:
  - name: ExportName                      # Required: used for output filename
    source: MyProject.FCStd                # Required: FreeCAD file path

    # Bodies to export (see options below)
    bodies:                               # Can be:
      - Body                              #   - Simple strings
      - body: "Body2"                     #   - Objects with transforms
        rotation: [0, 0, 45]
        position: [10, 0, 0]
    # OR leave empty to use marked bodies:
    # bodies: []

    # Output location (optional, defaults to prints/{name}.3mf)
    output: prints/MyExport.3mf

    # Preserve printer settings from template (optional)
    template: template_print_settings.3mf

    # Keep intermediate STL files (optional, default: false)
    keep_stl: false
    stl_output_dir: prints/stl

    # Embed metadata in 3MF (optional)
    metadata:
      Project: "MyProject"
      Version: "1.0"
      Author: "Your Name"
      Description: "Custom description"
      # Git metadata auto-added if available
```

---

## Advanced Features

### 1. Automatic Exports with Git Hooks

Setup automatic exports when you push to git:

```bash
cd MyProject

# Copy hook config
cp /path/to/freecad_tools/templates/pre-commit-config.yaml.example .pre-commit-config.yaml

# Install pre-commit
pip install pre-commit
pre-commit install --hook-stage pre-push

# Now exports happen automatically on git push!
git add .
git commit -m "Update antenna design"
git push  # → Auto-exports to prints/
```

Manual export hooks use the same config discovery order as the CLI, so projects using the unified
`.freecad_tools/config.yml` do not need a legacy `.freecad_tools/export.yml` symlink:

```bash
pre-commit run freecad-export-manual --hook-stage manual
```

For consumer repos with `just`, Make, or shell wrappers, call the installed CLI directly when you need to pass
an export item name:

```just
export name:
    freecad-export --config .freecad_tools/config.yml --name {{name}}
```

If your `pre-commit` version forwards extra hook args reliably, this form is also supported:

```bash
pre-commit run freecad-export-manual --hook-stage manual -- --config .freecad_tools/config.yml --name Moxon_OE1EBG_round
```

### 2. Multiple Copies with Different Orientations

Export the same body multiple times with different positions:

```yaml
export:
  - name: PrintTray
    source: Cable.FCStd
    bodies:
      # Original position
      - body: "CableGuide"
        position: [0, 0, 0]

      # Copy 1: rotated 90°
      - body: "CableGuide"
        rotation: [0, 0, 90]
        position: [25, 0, 0]

      # Copy 2: rotated 180°
      - body: "CableGuide"
        rotation: [0, 0, 180]
        position: [50, 0, 0]

      # Copy 3: rotated 270°
      - body: "CableGuide"
        rotation: [0, 0, 270]
        position: [75, 0, 0]
    output: prints/Cable_Array.3mf
```

### 3. Generate Parametric Variants

Use FreeCAD macros to create multiple versions:

1. In FreeCAD, run macro:
   - `Macros > Execute > generate_variant_configs.py`

2. Dialog appears asking for:
   - Parameter spreadsheet name
   - Parameter names and values
   - Number of variations

3. Macro generates/updates `.freecad_tools/config.yml` under `macros.generate_variant_configs`

4. Config is reused for consistent variations

**Using Configuration Files** (skip the dialog):

Create `.freecad_tools/config.yml` manually:
```yaml
macros:
  generate_variant_configs:
    spreadsheet_label: VariantData
    parameters:
      - name: PipeDiameter
        start: 10.1
        stop: 10.3
        step: 0.1
      - name: HexIndent
        values: [0.3, 0.5, 0.7, 0.9]
      - name: HexLength
        values: [10]

  variant_array_assignment:
    spreadsheet_label: VariantData
    array_label: VariantTestArray
    cleanup_before_assign: true
    cleanup_untagged_copy_groups: true
    enable_link_copy_on_change: true
```

When the macro runs, it will load its section from this config automatically (or show the dialog if not found).
The old `param1_name` / `param1_values` dialog-style keys are not supported; keep all variant parameters in the
`parameters` list.

The macro enables link copy-on-change by default so each array element can keep an independent selected configuration.
Newly-created managed `CopyOnChangeGroup` objects are tagged with the array name; `cleanup_untagged_copy_groups` keeps
one-time cleanup behavior for old untagged hidden groups from previous macro runs.

#### Zero-Setup Macro Workflow

All FreeCAD macros in this project work **standalone** from the FreeCAD GUI without requiring:
- Virtual environment activation
- External pip packages
- Setup beyond copying files

**How it works**:
1. Copy macro file (e.g., `generate_variant_configs.py`) to your FreeCAD project
2. Open FreeCAD and load your document
3. Go to **Macros > Execute macro...** (or Macro menu > your macro)
4. Select the macro and click Execute
5. Dialog appears (or config is auto-loaded from `.freecad_tools/config.yml`)
6. Your design is updated with variants/configurations

**Why it works**:
- Macros use only FreeCAD's built-in Python packages (PyYAML, PySide, stdlib)
- No venv required - FreeCAD's Python includes everything needed
- Config system auto-detects your project structure
- Tested to work with FreeCAD 1.1.1 bundled Python

**For power users** (batch automation):
If you're processing multiple documents via scripts, you can invoke macros programmatically:
```bash
freecadcmd -c "exec(open('generate_variant_configs.py').read())"
```

### 4. Engrave Custom Text on Parts (Text Stamp Macro)

Add personalized text engraving to your 3D parts with customizable font files, sizes, and pocket depth.

**Features**:
- **Config-Driven**: All parameters stored in `.freecad_tools/config.yml`
- **Interactive Dialog**: Choose font, size, depth, and text in a user-friendly dialog
- **Face Selection**: Select which surface to engrave on
- **Automatic Pocketing**: Creates pocket feature to engrave text

**Quick Start** (from FreeCAD GUI):

1. Open your FreeCAD document
2. Select a body and the face where you want to engrave
3. Go to **Macros > Execute > text_stamp.py**
4. Dialog appears with options:
   - **Text to Engrave**: Enter the text to engrave
   - **Font File**: Choose a `.ttf` or `.otf` font file
   - **Size**: Font size in mm (default: 10mm)
   - **Depth**: Pocket depth in mm (default: 1mm)
5. Click **OK** - text is engraved!

**Configuration** (`.freecad_tools/config.yml`):

```yaml
macros:
  text_stamp:
    # Default settings (can be overridden in dialog)
    font: "Arial"
    size: 10
    depth: 1.0
```

Text is engraved exactly as entered. Variable substitution is planned as a follow-up enhancement.

### 5. Template Metadata Merging

When you specify both a template and metadata in your config, they are merged:

```yaml
export:
  - name: MyProject
    source: MyProject.FCStd
    bodies: [Body]
    output: prints/MyProject.3mf
    template: template_print_settings.3mf
    metadata:
      Project: "MyProject"
      QualityLevel: "Draft"
```

**How merging works**:
1. Template 3MF metadata is read (e.g., `PrinterName`, `MaterialProfile`)
2. Your export metadata is merged on top
3. Export values take precedence over template values for the same key
4. Result contains both template and export metadata

**Creating a Template**:
1. Configure your printer settings in PrusaSlicer
2. Export/save as `template_print_settings.3mf`
3. Reference in config with `template:` key
4. Keep one template per printer setup (e.g., `template_prusa_mk3s.3mf`)

---

## Project Structure

```
freecad_tools/
├── README.md                           # This file (all user documentation)
├── CHANGELOG.md                        # What's new
├── AGENTS.md                           # Agent/developer guide
├── TODO.md                             # Open features & tasks
│
├── tools/                              # Python command-line tools
│   ├── export.py                       # Entry point (user runs this)
│   ├── fc_export.py                    # FreeCAD integration (runs inside FreeCAD)
│   ├── lib3mf_utils.py                 # 3MF creation (runs in venv)
│   ├── git_utils.py                    # Git metadata extraction
│   ├── techdraw_export.py              # TechDraw PDF export (runs in FreeCAD GUI)
│   ├── techdraw_pdf.py                 # PDF merging/cover page (runs in venv)
│   └── bom_utils.py                    # BOM CSV generation utility
│
├── macros/                             # FreeCAD macros
│   ├── macro_helper.py                 # Utilities for macro development
│   ├── generate_variant_configs.py     # Create design variants
│   └── variant_array_assignment.py     # Manage array-based variants
│
├── templates/                          # Example configurations
│   ├── pre-commit-config.yaml.example  # Hook setup template
│   └── export.yml.example              # Legacy export config template
│
├── examples/                           # Sample files
│   ├── example.FCStd                   # Sample FreeCAD document
│   ├── example.3mf                     # Sample output
│   └── config.yml                      # Unified example config
│
├── .pre-commit-hooks.yaml              # Hook definitions for projects
├── pyproject.toml                      # Python dependencies
└── uv.lock                             # Locked dependency versions
```

---

## Installation

### Option 1: Install from PyPI (Recommended for CLI users)

```bash
pip install freecad-tools
```

This installs the `freecad-export` command globally:

```bash
freecad-export --help
freecad-export path/to/config.yml
```

### Option 2: Clone and install from source

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ebirn/freecad_tools.git
   cd freecad_tools
   ```

2. **Create virtual environment and install dependencies**:
   ```bash
   uv sync
   ```

   Or without uv:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

3. **Verify installation**:
   ```bash
   freecad-export --help
   # Or run directly:
   python3 tools/export.py --help
   ```

### System Requirements

- **Python**: 3.10 or higher
- **FreeCAD**: v0.20+ (v1.0+ required for Assembly BOM features)
- **OS**: macOS, Linux, or Windows
- **Dependencies**: PyYAML, lib3mf, pypdf, reportlab (auto-installed via `uv sync`)

---

## Macro Helper API

For macro developers, `macro_helper.py` provides utilities:

### Dialog Configuration
```python
from macro_helper import show_config_dialog

fields = [
    {"name": "param1", "type": "text", "label": "Parameter 1:", "default": "value1"},
    {"name": "count", "type": "number", "label": "Count:", "default": 5}
]
config = show_config_dialog(title="My Configuration", fields=fields)
```

### Object Resolution
```python
from macro_helper import get_object_by_identifier
obj = get_object_by_identifier(doc, "Feed001")  # By Label or Name
```

### Finding Exportable Bodies
```python
from macro_helper import find_exportable_bodies
bodies = find_exportable_bodies(doc)  # Bodies with ExportTo3MF=True
```

### Configuration File Management
```python
from macro_helper import load_or_prompt_config
config = load_or_prompt_config(
    config_path=".freecad_tools/my_config.yml",
    dialog_fields=fields,
    dialog_title="My Macro Configuration"
)
# Loads config from file, or shows dialog and saves result
```

### Custom Properties
```python
from macro_helper import get_body_property, set_body_property
export_flag = get_body_property(obj, "ExportTo3MF")
set_body_property(obj, "ExportTo3MF", True, property_type="App::Bool")
```

---

## Troubleshooting

### "FreeCAD not found"

The tool can't find your FreeCAD installation:

**macOS**:
```bash
# Check if FreeCAD.app exists
ls /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
```

**Linux**:
```bash
which freecadcmd
```

**Windows**:
```cmd
where freecadcmd.exe
```

### "Body not found" warning

The body name in config doesn't match:

**Solution**: Check the exact name in FreeCAD:
- In FreeCAD tree, right-click body → Properties
- Look for "Label" or "Name"
- Use the Label (user-friendly name) in config

### "3MF file not created"

Check the export log:

```bash
cat fc_export.log
```

**Common issues**:
- Invalid FreeCAD file path
- Body has no shape/geometry
- Permissions issue with output directory

### STL files too large

Adjust tessellation (mesh quality):

The tool auto-calculates based on object size (0.1% of max dimension). For finer control, create an issue on GitHub.

---

## Features Comparison

| Feature | Basic | Advanced |
|---------|-------|----------|
| Export to 3MF | ✅ | ✅ |
| Multiple bodies | ✅ | ✅ |
| **Body rotation** | ❌ | ✅ |
| **Body positioning** | ❌ | ✅ |
| **Metadata embedding** | ❌ | ✅ |
| **TechDraw export** | ❌ | ✅ |
| **Bill of Materials** | ❌ | ✅ |
| **Git integration** | ❌ | ✅ |
| **Body marking** | ❌ | ✅ |
| **Auto-export hooks** | ❌ | ✅ |
| **Template support** | ❌ | ✅ |
| Keep STL files | ❌ | ✅ |

---

## Examples

### Real-World Example: Complete Antenna Assembly

```yaml
export:
  - name: Antenna_Complete
    source: Antenna.FCStd

    bodies:
      # Main radiator - centered, no rotation
      - body: "Radiator"
        position: [0, 0, 0]

      # Feed point - centered, rotated for optimal orientation
      - body: "Feed"
        rotation: [45, 0, 0]
        position: [0, 0, 10]

      # Mounting bracket - positioned to side
      - body: "Bracket"
        rotation: [0, 0, 0]
        position: [30, 0, 5]

      # Cable guide - rotated for cable routing
      - body: "CableGuide"
        rotation: [0, 90, 0]
        position: [15, 15, 0]

    output: prints/Antenna_Complete.3mf

    metadata:
      Project: "VHF Antenna"
      Version: "3.2"
      Author: "RF Team"
      Description: "10 element Yagi antenna, optimized for 2m band"
      Material: "PETG"
      Color: "Black"
```

### Git Hook Example

Once configured, exports happen automatically:

```bash
$ git push
Auto-exporting antenna design...
✓ Created antenna.3mf (2.4 MB)
✓ Embedded metadata (GitCommit: abc1234, GitBranch: main)
✓ Ready for printing in PrusaSlicer
```

---

## Tips & Best Practices

1. **Use body Labels**, not Names
   - Names: "Body", "Body002" (auto-generated, change when bodies reorder)
   - Labels: "Feed", "Cover" (user-friendly, stable)

2. **Commit your exports**
   - Keep printed 3MF files in version control
   - Track which version was printed
   - Revert to previous version if needed

3. **Use metadata for traceability**
   ```yaml
   metadata:
     Version: "1.2"  # Update with each design change
     Date: "2024-04-25"
     Notes: "First test print successful"
   ```

4. **Test rotations in FreeCAD first**
   - Rotate the body manually in FreeCAD
   - Note the rotation angles
   - Use in config

5. **Keep a template 3MF**
   - Export once from PrusaSlicer with ideal settings
   - Save as `template_print_settings.3mf`
   - Reference in config to preserve settings

---

## Next Steps

### Try These Examples

1. **Basic Export**: Copy example config, run export
2. **Add Rotation**: Add rotation to one body
3. **Add Metadata**: Include project info
4. **Setup Git Hooks**: Automate on push
5. **Multiple Variants**: Export 3-4 design versions

### Learn More

- **`CHANGELOG.md`**: What's new in each version
- **`examples/`**: Sample files to copy from
- **Issues on GitHub**: Ask questions or report bugs

---

## Testing

The project has comprehensive unit and integration tests.

### Running Tests

**Unit Tests** (no FreeCAD required, fast):
```bash
# Run all unit tests
make test
# or: python3 -m pytest tests/ --ignore=tests/test_fc_export_integration.py

# Run specific test file
python3 -m pytest tests/test_export_config.py -v
```

**Integration Tests** (require FreeCAD):
```bash
# Run integration tests with FreeCAD
make test-integration

# Run a specific integration test
/FreeCAD.app/Contents/Resources/bin/freecadcmd -c "import sys; sys.path.insert(0, 'tests'); sys.path.insert(0, 'tools'); import pytest; pytest.main(['-v', 'tests/test_fc_export_integration.py'])"
```

**All Tests**:
```bash
make test-unit   # Unit tests only
make test-integration  # Integration tests only
make test-all     # Both unit and integration tests
```

### Makefile Targets

| Target | Description | Requires FreeCAD |
|--------|-------------|------------------|
| `test` | All unit tests | No |
| `test-unit` | Unit tests only | No |
| `test-integration` | Integration tests only | Yes |
| `test-all` | Unit + integration | Yes |

**Note**: Integration tests run via FreeCAD's Python (`freecadcmd`) and test actual FreeCAD document interactions. They mock the lib3mf subprocess calls, so lib3mf only needs to be installed in your venv, not in FreeCAD's Python.

### Coverage Reports

Generate HTML coverage reports for visual inspection:

```bash
# Unit tests with HTML coverage report
python3 -m pytest tests/ --ignore=tests/test_fc_export_integration.py --cov=tools --cov-report=html -v

# Open the report in browser
open htmlcov/index.html
```

The `htmlcov/` directory contains interactive coverage reports and is git-ignored.

### Writing New Tests

- Add **unit tests** in `tests/` for pure Python logic (no FreeCAD)
- Add **integration tests** in `tests/test_fc_export_integration.py` for FreeCAD-dependent code
- Use `@skip_if_no_freecad` decorator for tests requiring FreeCAD
- See `tests/conftest.py` for shared fixtures

### Quality Metrics

After each export, quality metrics are automatically collected and logged:

| Metric | Description |
|--------|-------------|
| Vertex Count | Total unique vertices across all meshes |
| Triangle Count | Total triangles across all meshes |
| STL Input Size | Combined size of all input STL files |
| 3MF Output Size | Size of generated 3MF file |
| Per-Body Metrics | Vertex/triangle counts per body (in debug logs) |

The metrics are logged at INFO level after successful exports:
```
Quality Metrics: 15420 vertices, 30840 triangles, 123456 bytes STL input, 98765 bytes 3MF output
```

---

## Release Validation

Before tagging a release, run the release readiness checker to verify your project is in a consistent state:

```bash
# Quick summary (JSON)
python3 tools/release_validator.py --summary

# Individual checks
python3 tools/release_validator.py --check version
python3 tools/release_validator.py --check changelog
python3 tools/release_validator.py --check tests
python3 tools/release_validator.py --check all

# Generate checksums for release files
python3 tools/release_validator.py --checksums README.md CHANGELOG.md pyproject.toml
```

The `--summary` flag validates:
- **Version** — `pyproject.toml` has a version set
- **Changelog** — `CHANGELOG.md` has an entry matching the version
- **Unreleased section** — `CHANGELOG.md` has an `[Unreleased]` section for future changes
- **Tests** — all unit tests pass

The release workflows use these same checks as gates — a tagged release will fail if any check doesn't pass.

---

## Support & Contributing

### Questions?

1. Review examples in `examples/` directory
2. Check `CHANGELOG.md` for recent changes
3. Check `TODO.md` for planned features
4. Open an issue on GitHub

### Found a Bug?

1. Note the error message
2. Check `fc_export.log` for details
3. Open an issue with:
   - OS and FreeCAD version
   - Your config file
   - The error message
   - Steps to reproduce

### Want to Contribute?

See `AGENTS.md` for development guidelines.

---

## Version History

See `CHANGELOG.md` for complete release history.

---

**Happy Printing! 🖨️**

Made with ❤️ for the FreeCAD and 3D printing community.
