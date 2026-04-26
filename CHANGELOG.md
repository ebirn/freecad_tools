# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

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
