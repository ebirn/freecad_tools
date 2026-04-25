# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

#### Macro Enhancements
- **macro_helper.py**: New module providing utilities for FreeCAD macros
  - Dialog UI system for user configuration with PySide2
  - YAML-based configuration file support
  - Object resolution by Name or Label (user-friendly)
  - Custom property management for FreeCAD objects
  - Body marking system: find bodies marked with `ExportTo3MF` property
  - Automatic config loading/saving to `.freecad_tools/macro_config.yml`

- **generate_variant_configs.py**: Refactored to use macro_helper
  - Now supports configuration dialogs
  - Flexible parameter list definition
  - Dynamic column header generation
  - Config file support for repetitive tasks

- **variant_array_assignment.py**: Refactored to use macro_helper
  - Configuration dialog for spreadsheet and array names
  - Config file support
  - Improved error handling

#### Git Metadata Integration
- **git_utils.py**: New utility module for git metadata extraction
  - Get current commit hash (full or short)
  - Get branch name with detached HEAD detection
  - Get tags for current commit
  - Get remote URL
  - Repository detection
  - Comprehensive metadata extraction in single function

#### Metadata Support in 3MF Files
- **fc_export.py** enhancements:
  - `get_export_metadata()` function to extract metadata from config and git
  - Automatic git metadata extraction (commit, branch, tags, remote)
  - Metadata passed through to lib3mf subprocess
  - Support for custom metadata fields in config YAML

- **lib3mf_utils.py** enhancements:
  - `add_metadata_to_model()` function to embed metadata in 3MF files
  - Updated `create_3mf_from_stls()` to accept and embed metadata
  - Updated `create_from_json_config()` to support metadata field
  - Metadata fields: Project, Author, Version, GitCommit, GitCommitFull, GitBranch, GitTags, GitRemote

#### Configuration Enhancements
- **export_config.yml** format extended with:
  - `metadata` section for custom metadata
  - Git metadata automatically added (can be overridden)
  - Example configurations showing metadata usage
  - Example showing body marking approach

### Changed

- **export.py**: Already supported CLI parameters (confirmed working)
- **fc_export.py**: Enhanced with metadata extraction logic
- **lib3mf_utils.py**: Enhanced with metadata embedding support
- **export_config.yml.example.yml**: Added metadata examples and body marking documentation

### Technical Details

#### Body Marking System
Bodies can be marked for export using FreeCAD's custom properties:
- Property name: `ExportTo3MF`
- Property value: `True` (boolean)
- If bodies list is empty in config, all marked bodies are exported
- Use `macro_helper.find_exportable_bodies()` in macros

#### Metadata Embedding
Metadata is embedded in the 3MF file's metadata group:
- Readable by PrusaSlicer and other 3MF-aware tools
- Common fields: Project, Author, Version
- Git fields: GitCommit (short), GitCommitFull, GitBranch, GitTags, GitRemote
- Custom fields can be added to config

#### Configuration File Location
Macros can use config files at:
- `.freecad_tools/macro_config.yml` (per-project)
- User is prompted if config doesn't exist
- Config is saved for future use

### Files Modified
- `macros/generate_variant_configs.py`
- `macros/variant_array_assignment.py`
- `tools/fc_export.py`
- `tools/lib3mf_utils.py`
- `examples/export_config.yml.example.yml`

### Files Added
- `macros/macro_helper.py`
- `tools/git_utils.py`

### Breaking Changes
None. All changes are backward compatible.

### Migration Guide

#### For Users
1. No changes required for existing configurations
2. To add metadata to exports:
   - Add `metadata` section to export config
   - Specify fields like `Project`, `Author`, `Version`
   - Git metadata is automatically added

3. To mark bodies for automatic export:
   - Add custom property `ExportTo3MF=True` to bodies in FreeCAD
   - Leave `bodies: []` in config (empty list)
   - All marked bodies will be exported

#### For Developers
1. New utilities available in `macro_helper`:
   - Use `show_config_dialog()` for user input
   - Use `load_or_prompt_config()` for flexible config loading
   - Use `find_exportable_bodies()` for body selection

2. New utilities in `git_utils`:
   - Use `get_git_metadata()` for comprehensive git info
   - Use `is_git_repo()` to check if directory is in git
   - Use individual functions for specific metadata

### Testing Notes

All Python files pass syntax checking and linting:
- `python3 -m py_compile` on all new/modified files
- Ruff lint and format checks pass
- YAML syntax validation passes

No runtime tests performed (requires FreeCAD environment).

### Future Enhancements

From TODO.md, not yet implemented:
- Body duplication with different orientations in 3MF
- Rotation/position specifications in config for bodies
- Template metadata merging (code exists, needs testing)
- Multi-document support in single config
- Batch processing improvements
- Quality metrics reporting
