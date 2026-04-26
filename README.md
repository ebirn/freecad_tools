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
- **📋 Template Support**: Preserve PrusaSlicer printer settings across exports
- **🔗 Git Integration**: Automatically capture commit hash, branch, and tags in exports
- **🚀 Automation**: Use with pre-commit hooks for automatic exports on push

---

## Quick Start (5 Minutes)

### Basic Setup

1. **Copy the example config** to your FreeCAD project:
   ```bash
   mkdir -p MyProject/.freecad_tools
   cp /path/to/freecad_tools/examples/export_config.yml.example.yml MyProject/.freecad_tools/export.yml
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

Position bodies exactly where they should be without manual adjustment:

```yaml
export:
  - name: OrientedAntenna
    source: Antenna.FCStd
    bodies:
      # Simple bodies (no rotation)
      - Feed001

      # Body rotated 45 degrees around Z-axis
      - body: "Mounting Bracket"
        rotation: [0, 0, 45]

      # Body rotated and moved
      - body: "Cable Guide"
        rotation: [90, 0, 0]
        position: [10, 0, 5]  # X, Y, Z in mm
    output: prints/Antenna_Positioned.3mf
```

**Why this matters**:
- ✅ Pre-positioned for optimal printing
- ✅ Save time in PrusaSlicer
- ✅ Consistent orientation across exports
- ✅ Supports multiple copies with different positions

**Rotation Details**:
- `rotation: [X, Y, Z]` - degrees around each axis
- Applied in intrinsic order: X → Y → Z
- Example: `[45, 0, 0]` = 45° around body's X-axis
- Example: `[0, 0, 90]` = 90° around body's Z-axis

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

### 8. Generate Bill of Materials (BOM)

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

### BOM Generation Configuration

```yaml
bom:                                # Optional: generate bill of materials
  source: auto                      # Where to get BOM data:
                                    # - 'auto' = try assembly → spreadsheet → parts
                                    # - 'assembly' = only Assembly
                                    # - 'spreadsheet' = only Spreadsheet
                                    # - 'parts' = only Part/Body objects
  output: docs/bom.csv              # CSV output file path
  spreadsheet_name: BOM             # (optional) Spreadsheet name if not "BOM"
  fields:                           # (optional) Custom property names to extract
    - material
    - vendor
    - price
    - dimensions
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
│   └── export.yml          # ← Your config goes here
└── MyProject.FCStd
```

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

3. Macro generates `.freecad_tools/macro_config.yml`

4. Config is reused for consistent variations

**Using Configuration Files** (skip the dialog):

Create `.freecad_tools/macro_config.yml` manually:
```yaml
spreadsheet_label: VariantData
param1_name: PipeDiameter
param1_values: "10.1, 10.2, 10.3"
param2_name: HexIndent
param2_values: "0.3, 0.5, 0.7, 0.9"
param3_name: HexLength
param3_values: "10"
```

When the macro runs, it will load this config automatically (or show the dialog if not found).

### 4. Template Metadata Merging

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
│   └── export_config.yml.example.yml   # Config template
│
├── examples/                           # Sample files
│   ├── example.FCStd                   # Sample FreeCAD document
│   ├── example.3mf                     # Sample output
│   └── export_config.yml.example.yml   # Example config
│
├── .pre-commit-hooks.yaml              # Hook definitions for projects
├── pyproject.toml                      # Python dependencies
└── uv.lock                             # Locked dependency versions
```

---

## Installation

### For End Users (Recommended)

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
