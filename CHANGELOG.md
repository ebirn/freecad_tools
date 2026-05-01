# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [v0.4.0] - 2026-05-01

### Added

- Body screenshot generation via FreeCAD GUI (`screenshots:` config) for publication-ready PNG/JPGs.
- `--name/-n` option to export a single named item from multi-item configs.
- `--list-exports` option to print configured export item names and exit.
- `--gui-only` and `--screenshots-only` modes to run GUI tasks without rebuilding 3MF output.
- `--gui-session item|run` mode to choose per-item GUI execution or a shared GUI session for the full run.
- Overall run statistics summary with aggregated timings for open/export/gui/shared-gui/total.
- `make export` target for practical full-feature export runs with test config.

### Changed

- README: Document GUI mode flags, `--gui-session`, and `make export` / `make clean` workflows.
- Shared GUI session runner now handles both TechDraw and screenshot tasks in one queued run path.

### Fixed

- Preserve CLI mode flags across `freecadcmd` re-exec via environment propagation.
- Fallback to identity transform in lib3mf build-item creation to avoid intermittent `invalid index` failures.

### Tests

- Add FreeCAD integration coverage for opening `examples/example.FCStd` and resolving exported bodies.
- Add regression tests for run-level timing summary formatting and shared GUI job payload construction.

## [v0.3.0] - 2026-04-28

### Added

- **Explicit Body Selection Mode** (Task #1): Add `body_source` config field and FreeCAD property-based body selection
  - `body_source: config` - Explicit body list in config (default when bodies present)
  - `body_source: properties` - Auto-select bodies with `ExportTo3MF=True` property
  - Support for `ExportCount` property to duplicate bodies
  - Support for `ExportRotation` (App::PropertyRotation) for axis+angle orientation
  - Backward compatible: infers mode from `bodies` list presence with deprecation warning
  - New macro: `macros/set_export_properties.py` for GUI/CLI property management
- **Axis+Angle Rotation Format**: Alternative to Euler angles, matches FreeCAD GUI display
  - Config format: `rotation: {axis: [x, y, z], angle: deg}`
  - Maintains backward compatibility with Euler `[x, y, z]` list format
  - Uses Rodrigues' rotation formula for unambiguous orientation
- **CLI Help and Argument Parsing** (Task #7): Added comprehensive command-line interface to `export.py` and `fc_export.py`
  - `argparse` integration with `--help` for self-documenting usage
  - `--config/-c PATH` flag to specify config file path
  - `--verbose/-v` flag for debug logging output
  - `--dry-run` flag to validate config without performing export
  - Config file auto-discovery from `.freecad_tools/export.yml` or `export_config.yml`
  - Backward compatible with existing positional config file argument
- **BOM Assembly Selection** (Task #6): Allow specifying which assembly to extract BOM from
  - Added `assembly` field to bom config to target specific assembly by name or label
  - Supports multiple BOM sections (list of config dicts) for multi-assembly documents
  - Backward compatible with existing single dict config
  - `extract_bom_from_assembly()` now accepts optional `assembly_name` parameter
- **Quality Metrics** (Task #2): Report mesh statistics and validate 3MF output structure
  - `convert_stl_to_lib3mf_mesh()` returns dict with vertex_count, triangle_count, file_size
  - `create_3mf_from_stls()` returns tuple of (success: bool, quality_metrics: dict)
  - `create_from_json_config()` returns tuple of (success: bool, quality_metrics: dict)
  - `validate_3mf_file()` checks ZIP structure, required files (3dmodel.model), metadata
  - `format_quality_report()` generates human-readable quality report with totals and per-body breakdown
  - Quality metrics logged at INFO level after successful exports
  - Added 5 new unit tests for quality metrics functions
- **BOM Assembly Column Mapping**: Fixed BOM extraction from Assembly::BomObject to map FreeCAD column names to standard fields
  - Maps BomObject columns (Index, Name, Description, File Name, Quantity) to standard names (index, label, description, file_name, quantity)
  - Ensures BOM data populates CSV correctly with config-specified field names
  - BOM CSV always created with headers, even when no data exists
  - BOM section always shown in PDF (displays "No BOM data available" if empty)
- **PDF Document Metadata**: Added metadata to PDF document properties
  - Title, Author, Subject (Version), Keywords (License), CreationDate fields
  - Producer and Creator set to "FreeCAD Tools"
  - Metadata extracted from config metadata and git info
  - Supports additional fields: License, Project, Description
- **Improved Console Logging**: Cleaner, more readable output
  - Section headers with `===` separators for major operations
  - Symbol indicators: → (action), ✓ (success), ✗ (failure), ⚠ (warning)
  - Removed module name prefix from console log format
  - File logging retains detailed format with timestamps and module names
- **Enhanced Test Coverage**: Added tests for BOM and PDF content verification
  - Tests verify BOM data appears in CSV files
  - Tests verify metadata and BOM appear in PDF text content
  - Tests verify PDF document metadata properties

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
