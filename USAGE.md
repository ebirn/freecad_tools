# Usage Guide for Enhanced FreeCAD Tools

This guide covers the new features added to freecad_tools for macros, metadata, and body marking.

## Table of Contents

1. [Macro Configuration](#macro-configuration)
2. [Body Marking System](#body-marking-system)
3. [Body Orientation and Positioning](#body-orientation-and-positioning)
4. [Metadata in 3MF Files](#metadata-in-3mf-files)
5. [Git Integration](#git-integration)
6. [Macro Helper API](#macro-helper-api)

## Macro Configuration

### Using Configuration Dialogs

The improved macros now support interactive configuration dialogs. When you run a macro without a config file, you'll be prompted with a dialog:

1. Run the macro (e.g., `Macros > Execute macro > generate_variant_configs.py`)
2. A dialog appears with configurable fields
3. Enter your values
4. Click "OK" to proceed

The configuration is automatically saved to `.freecad_tools/macro_config.yml` for future use.

### Using Configuration Files

Instead of dialogs, you can create a YAML config file:

**`.freecad_tools/macro_config.yml`:**
```yaml
spreadsheet_label: VariantData
param1_name: PipeDiameter
param1_values: "10.1, 10.2, 10.3"
param2_name: HexIndent
param2_values: "0.3, 0.5, 0.7, 0.9"
param3_name: HexLength
param3_values: "10"
```

When the macro runs, it will:
1. Check for `.freecad_tools/macro_config.yml`
2. If found, load and use it
3. If not found, show the dialog and save the entered config

## Body Marking System

### How to Mark Bodies for Export

Instead of hardcoding body names in the export config, you can mark them in FreeCAD:

1. Open your FreeCAD document
2. Select a body in the tree view
3. In the Property Editor, add a custom property:
   - Right-click on the body
   - Select "Properties"
   - Add a new custom property:
     - Name: `ExportTo3MF`
     - Type: `Boolean`
     - Value: `True`

4. Repeat for all bodies you want to export

### Using Marked Bodies in Export Config

In your `export.yml`, leave the `bodies` list empty:

```yaml
export:
  - name: MyProject
    source: MyProject.FCStd
    bodies: []  # Empty - will use marked bodies
    output: prints/MyProject.3mf
```

The exporter will automatically find all bodies with `ExportTo3MF=True` and export them.

### Programmatic Body Marking

In macros, you can check for marked bodies:

```python
from macro_helper import find_exportable_bodies

doc = FreeCAD.ActiveDocument
marked_bodies = find_exportable_bodies(doc)
print(f"Found {len(marked_bodies)} marked bodies: {marked_bodies}")
```

## Body Orientation and Positioning

### Why Use Body Orientation?

Instead of rotating models in PrusaSlicer after export, you can specify body orientations directly in the export configuration. This allows you to:

- Pre-position bodies for optimal printing
- Export multiple copies of the same body in different orientations
- Preserve intended positioning across multiple exports
- Avoid manual adjustments in the slicer

### Specifying Body Transforms

Bodies can be specified in two formats:

**Simple Format (String):**
```yaml
bodies:
  - Feed001
  - "Angle Round"
```

**Transform Format (Object):**
```yaml
bodies:
  - body: "Angle Round"
    rotation: [45, 0, 0]    # X, Y, Z rotation in degrees
    position: [10, 0, 5]    # X, Y, Z offset in mm
```

### Rotation Details

- **Rotation Order**: Intrinsic (body-relative). First X rotation, then Y, then Z
- **Units**: Degrees (0-360)
- **Example**: `[45, 0, 0]` rotates 45° around X-axis
- **Optional**: Leave blank or omit to use default (no rotation)

### Position Details

- **Position Offset**: Translation in 3D space
- **Units**: Millimeters (mm)
- **Reference**: Offset from body origin
- **Example**: `[10, 0, 5]` moves 10mm in X, 0mm in Y, 5mm in Z
- **Optional**: Leave blank or omit to use default (no offset)

### Complete Example

```yaml
export:
  - name: Antenna_Oriented
    source: Antenna.FCStd
    bodies:
      # Body without transforms (default orientation)
      - Feed001

      # Same body rotated 45° around Z-axis
      - body: "Feed001"
        rotation: [0, 0, 45]

      # Body rotated and positioned
      - body: "Angle Round"
        rotation: [90, 0, 0]
        position: [5, 5, 10]

      # Multiple copies with different orientations
      - body: "Mounting Bracket"
        rotation: [0, 0, 0]
        position: [0, 0, 0]

      - body: "Mounting Bracket"
        rotation: [0, 0, 90]
        position: [20, 0, 0]

      - body: "Mounting Bracket"
        rotation: [0, 0, 180]
        position: [40, 0, 0]

      - body: "Mounting Bracket"
        rotation: [0, 0, 270]
        position: [60, 0, 0]

    output: prints/Antenna_Oriented.3mf
    metadata:
      Project: "Antenna"
      Version: "2.0"
      Author: "Jane Doe"
```

### Mixing Simple and Transform Formats

You can mix both formats in the same export:

```yaml
bodies:
  - Feed001                    # Simple format
  - body: "Angle Round"        # Transform format
    rotation: [45, 0, 0]
  - "Another Body"             # Simple format
  - body: "Bracket"            # Transform format
    position: [10, 10, 0]
```

### Tips for Best Results

1. **Test in FreeCAD**: Visualize the orientation in FreeCAD before exporting
2. **Use PrusaSlicer to Validate**: Import the 3MF and verify positioning in the slicer
3. **Document Your Orientations**: Add comments in the config for complex layouts
4. **Reuse Configs**: Save successful configurations for repeated use

## Metadata in 3MF Files

### Adding Metadata to Exports

Add a `metadata` section to your export configuration:

```yaml
export:
  - name: Moxon_OE1EBG
    source: Moxon_OE1EBG.FCStd
    bodies:
      - Feed001
      - Cover001
    output: prints/Moxon_OE1EBG.3mf
    metadata:
      Project: "Moxon_OE1EBG"
      Author: "John Doe"
      Version: "1.0"
      Description: "Moxon antenna design"
```

### Available Metadata Fields

**User-Specified Fields:**
- `Project`: Project name
- `Author`: Author name
- `Version`: Version string
- `Description`: Project description
- Any custom fields you want

**Automatically Added Git Fields:**
- `GitCommit`: Short commit hash (7 chars)
- `GitCommitFull`: Full commit hash
- `GitBranch`: Current branch name (or "(detached)")
- `GitTags`: Tags for current commit
- `GitRemote`: Remote URL

Git metadata is automatically added if your FreeCAD project is in a git repository.

### Viewing Metadata in PrusaSlicer

The embedded metadata can be viewed in PrusaSlicer:
1. Open the 3MF file in PrusaSlicer
2. Look for metadata in the object properties or file information

## Git Integration

### Automatic Git Metadata

If your FreeCAD project is in a git repository, metadata is automatically extracted:

```
$ cd MyProject
$ git log -1 --oneline
abc1234 (HEAD -> main, tag: v1.0) feat: add new antenna design
$ python3 path/to/freecad_tools/tools/export.py
```

The exported 3MF will include:
- `GitCommit: abc1234`
- `GitBranch: main`
- `GitTags: v1.0`

### Disabling Automatic Git Metadata

To prevent automatic git metadata extraction, explicitly set the fields:

```yaml
metadata:
  GitCommit: "manual"  # Won't be overridden
```

Git metadata is only added if not already specified in the config.

### Requirements

Git integration requires:
- Git to be installed and in PATH
- The project directory to be in a git repository
- No special permissions needed

## Macro Helper API

### Dialog Configuration

Show a configuration dialog:

```python
from macro_helper import show_config_dialog

fields = [
    {
        "name": "param1",
        "type": "text",
        "label": "Parameter 1:",
        "default": "value1",
        "help": "Description of parameter 1"
    },
    {
        "name": "count",
        "type": "number",
        "label": "Count:",
        "default": 5
    }
]

config = show_config_dialog(title="My Configuration", fields=fields)
if config:
    print(f"User entered: {config}")
```

### Object Resolution

Find objects by Name or Label:

```python
from macro_helper import get_object_by_identifier

obj = get_object_by_identifier(doc, "Feed001")  # By Label
obj = get_object_by_identifier(doc, "Body")     # By Name
```

### Finding Exportable Bodies

Find all bodies marked for export:

```python
from macro_helper import find_exportable_bodies

bodies = find_exportable_bodies(doc)
print(f"Bodies to export: {bodies}")
```

### Configuration File Management

Load or prompt for configuration:

```python
from macro_helper import load_or_prompt_config

config = load_or_prompt_config(
    config_path=".freecad_tools/my_config.yml",
    dialog_fields=fields,
    dialog_title="My Macro Configuration"
)
```

This will:
1. Try to load `.freecad_tools/my_config.yml`
2. If not found, show the dialog
3. Save the entered config for future use

### Custom Properties

Read/write custom properties on FreeCAD objects:

```python
from macro_helper import get_body_property, set_body_property

# Read property
export_flag = get_body_property(obj, "ExportTo3MF")

# Write property
set_body_property(obj, "ExportTo3MF", True, property_type="App::Bool")
set_body_property(obj, "Description", "My body", property_type="App::String")
```

## Example Workflow

### Complete Export with Metadata

1. **Mark bodies in FreeCAD:**
   - Add custom property `ExportTo3MF=True` to each body to export

2. **Create export config:**
   ```yaml
   export:
     - name: MyProject_v2
       source: MyProject.FCStd
       bodies: []  # Use marked bodies
       output: prints/MyProject_v2.3mf
       metadata:
         Project: "MyProject"
         Author: "Jane Smith"
         Version: "2.0"
   ```

3. **Run export:**
   ```bash
   cd MyProject
   python3 path/to/freecad_tools/tools/export.py
   ```

4. **Result:**
   - `prints/MyProject_v2.3mf` is created
   - Contains marked bodies
   - Includes metadata (Project, Author, Version, Git info)

### Using Variant Macros

1. **Generate variants:**
   - Run `generate_variant_configs.py`
   - Enter parameters in dialog (or use config file)
   - A spreadsheet is created with all combinations

2. **Apply to array:**
   - Create an array in FreeCAD
   - Run `variant_array_assignment.py`
   - Enter spreadsheet and array names
   - Each array element gets a configuration

3. **Export different versions:**
   - Configure export for each variant
   - Use metadata to track versions
   - Use git tags for releases

## Troubleshooting

### Dialog Not Appearing

- Make sure FreeCAD is running with the macro
- Check that PySide2 is available (usually bundled with FreeCAD)
- Look for error messages in FreeCAD console

### Config File Not Loading

- Check file path: `.freecad_tools/macro_config.yml`
- Verify YAML syntax (use online YAML validator)
- Check file permissions

### Git Metadata Not Found

- Verify git is installed: `git --version`
- Check project is in git repo: `git status`
- Look in `fc_export.log` for details

### Bodies Not Marked

- Confirm property is exactly named `ExportTo3MF`
- Confirm property value is `True` (boolean, not string)
- Check FreeCAD's Property Editor for typos
