# FreeCAD Tools

A collection of Python utilities for working with FreeCAD designs, enabling:
- **3MF Export**: Convert FreeCAD bodies to 3MF files with embedded mesh data for 3D printing
- **Variant Generation**: Create parametric variants of designs using FreeCAD macros
- **Printer Integration**: Preserve printer settings and configurations through template files

This project bridges FreeCAD with modern 3D printing workflows, particularly PrusaSlicer.

---

## Quick Start

### 1. Export 3MF Files

Run the export tool from your FreeCAD project directory:

```bash
python3 /path/to/freecad_tools/tools/export.py
```

This reads `export_config.yml` from the current directory.

### 2. Using with pre-commit (Recommended)

Each FreeCAD project can use pre-commit to manage freecad_tools:

1. Copy the example config:
   ```bash
   cp templates/pre-commit-config.yaml.example .pre-commit-config.yaml
   ```

2. Install hooks:
   ```bash
   pre-commit install --hook-type pre-push
   ```

3. Create and push a tag to auto-export:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

4. Or run manually:
   ```bash
   pre-commit run --hook-stage manual freecad-export-manual
   ```

5. Update to latest freecad_tools:
   ```bash
   pre-commit autoupdate
   ```

---

## Project Structure

```
freecad_tools/
├── .pre-commit-hooks.yaml           # Hook definitions
├── templates/
│   ├── pre-commit-config.yaml.example  # Template for projects
│   └── export.yml.example             # Example per-project config
├── hooks/                          # pre-commit hook scripts
│   ├── freecad-export
│   └── freecad-export-manual
├── macros/                        # FreeCAD macros
└── tools/                        # Python tools
    ├── export.py
    ├── fc_export.py
    └── lib3mf_utils.py
```

---

## Per-Project Setup

Each FreeCAD project should have:

```
MyProject/
├── .freecad_tools/
│   └── export.yml           # Export configuration
├── .pre-commit-config.yaml
└── MyProject.FCStd
```

Copy `templates/export.yml.example` to `.freecad_tools/export.yml` and customize.