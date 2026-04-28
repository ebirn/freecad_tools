# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- **CLI Help and Argument Parsing** (Task #7): Added comprehensive command-line interface to `export.py` and `fc_export.py`
  - `argparse` integration with `--help` for self-documenting usage
  - `--config/-c PATH` flag to specify config file path
  - `--verbose/-v` flag for debug logging output
  - `--dry-run` flag to validate config without performing export
  - Config file auto-discovery from `.freecad_tools/export.yml` or `export_config.yml`
  - Backward compatible with existing positional config file argument

### Fixed

- README: Python version corrected from 3.7 to 3.10+ (matches pyproject.toml)
- README: Added missing dependencies (pypdf, reportlab) to requirements list
- README: Documented `techdraw.instructions` config option for markdown in PDF reports
- README: Fixed installation instructions — replaced `requirements.txt` with `uv sync` / `pip install -e .`
- README: Added new tools to project structure (techdraw_export.py, techdraw_pdf.py, bom_utils.py)
- README: Removed duplicate "Full Configuration Reference" heading
- README: FreeCAD version note — v1.0+ required for Assembly BOM features
- README: Fixed BOM CSV column description — assembly source uses BomObject columns, not label/quantity
- README: Cleaned up outdated version history section

## [v0.2.0] - 2026-04-26

### Added

- **TechDraw PDF Export** (PR #6): Pixel-perfect technical drawing export via FreeCAD GUI binary
  - Two-step pipeline: `techdraw_export.py` (FreeCAD GUI) + `techdraw_pdf.py` (pypdf/reportlab)
  - Cover page with metadata, TOC, and inline BOM table
  - Assembly instructions from markdown files
  - Consistent page footers (title, page numbers, date/version)
  - Mixed landscape/portrait page support
- **Bill of Materials Generation** (PR #6): BOM extraction and CSV output
  - Primary: reads from Assembly::BomObject (respects user's FreeCAD BOM config)
  - Fallback: Spreadsheet → Part/Body inspection
  - CSV output with configurable fields
  - Config sections: `techdraw:` and `bom:` in export.yml
- **New dependencies**: `pypdf>=5.0`, `reportlab>=4.0`

## [v0.1.0] - 2026-04-26

First tagged release. Includes all features developed across PRs #1-#5.

### Added

- **3MF Export Pipeline**: Convert FreeCAD bodies to 3MF files with embedded mesh data via lib3mf C++ bindings
- **Body Orientation & Positioning** (PR #2): Specify rotation and position transforms per body in config
  - Intrinsic Euler rotation (X, Y, Z degrees)
  - Position offset (X, Y, Z mm)
  - Multiple copies of same body with different transforms
- **Template Metadata Merging** (PR #3): Merge printer settings from template 3MF files into exports
  - `read_metadata_from_3mf()` and `merge_metadata()` in lib3mf_utils.py
  - Export metadata takes precedence over template metadata
- **Git Metadata Integration**: Automatic embedding of commit, branch, tags, remote URL in 3MF
  - `git_utils.py` module for metadata extraction
- **3MF Metadata Embedding**: Custom metadata fields in config (Project, Author, Version, etc.)
- **Body Marking System**: Mark FreeCAD bodies with `ExportTo3MF=True` custom property
- **Macro Helper Module** (`macro_helper.py`):
  - PySide2 dialog UI system for configuration
  - YAML-based config file support
  - Object resolution by Name or Label
  - Custom property management
  - Exportable body discovery
- **Parametric Variant Macros**: `generate_variant_configs.py` and `variant_array_assignment.py` with config dialog support
- **Pre-commit Hooks**: Reusable hook definitions for automatic export on git push
- **GitHub Actions CI** (PRs #4, #5): Lint (ruff, yamllint, pylint) and unit test jobs on push/PR

### Changed

- Macros refactored to use macro_helper module
- Export config supports both simple string and object body specs
- Config file location: `.freecad_tools/export.yml` (with legacy `export_config.yml` fallback)

### Breaking Changes

None. All changes are backward compatible.
