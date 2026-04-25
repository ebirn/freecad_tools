# FreeCAD Tools - Development TODO

**Note**: This file tracks open development tasks. For agent workflow guidance, see AGENTS.md (which does NOT contain task lists - only process guidance).

---

## Phase 2 Features - Open Tasks

### 1. Body Orientation Support [HIGH PRIORITY]
**Status**: IN PROGRESS
**Branch**: `agent_body_orientation`
**Effort**: Medium (2-3 hours)
**Impact**: High - Critical for PrusaSlicer users

**Description**: Add support for rotating and positioning bodies in 3MF files without manual editing in slicer.

**Tasks**:
- [ ] Update config schema to support rotation and position specs
- [ ] Document new config fields in USAGE.md with examples
- [ ] Add transform parsing in `tools/fc_export.py`
- [ ] Create `get_body_transforms()` function to extract transforms from config
- [ ] Modify `tools/lib3mf_utils.py` to apply 3MF transformation matrices
- [ ] Test 3MF output with transforms
- [ ] Create PR with comprehensive commit message
- [ ] Merge PR after review

**Config Format**:
```yaml
export:
  - name: MyProject
    bodies:
      - name: Body1
        transform:
          rotation: [45, 0, 0]    # X, Y, Z degrees
          position: [0, 0, 5]     # X, Y, Z offsets
```

**Files to Modify**:
- `tools/fc_export.py`
- `tools/lib3mf_utils.py`
- `examples/export_config.yml.example.yml`
- `USAGE.md`

---

### 2. Template Metadata Merging [HIGH PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_template_metadata`
**Effort**: Medium (2-3 hours)
**Impact**: High - For PrusaSlicer integration

**Description**: Merge printer settings and metadata from template 3MF files into generated exports.

**Tasks**:
- [ ] Read metadata from template 3MF file
- [ ] Parse template metadata structure
- [ ] Implement merge logic with precedence rules (generated > template > default)
- [ ] Update `tools/fc_export.py` to handle template merging
- [ ] Test metadata merge with sample templates
- [ ] Document template usage in USAGE.md
- [ ] Create PR with comprehensive commit message
- [ ] Merge PR after review

**Files to Modify**:
- `tools/fc_export.py`
- `tools/lib3mf_utils.py`
- `USAGE.md`

---

### 3. Batch Processing [MEDIUM PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_batch_processing`
**Effort**: Low-Medium (1-2 hours)
**Impact**: Medium - For power users

**Description**: Process multiple export jobs from queue with parallel execution option.

**Tasks**:
- [ ] Design batch processing interface (CLI args or separate config)
- [ ] Implement export queue management
- [ ] Add progress reporting for batch jobs
- [ ] Handle errors per export (continue on failure)
- [ ] Test with multiple concurrent exports
- [ ] Document batch processing in USAGE.md
- [ ] Create PR with comprehensive commit message
- [ ] Merge PR after review

**Files to Modify**:
- `tools/export.py`
- `tools/fc_export.py`
- `USAGE.md`

---

### 4. Quality Metrics [MEDIUM PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_quality_metrics`
**Effort**: Low (1-2 hours)
**Impact**: Medium - For debugging and validation

**Description**: Report mesh statistics and validate 3MF output structure.

**Tasks**:
- [ ] Add vertex/triangle counting in `tools/lib3mf_utils.py`
- [ ] Parse 3D/3dmodel.model XML for mesh stats
- [ ] Implement file size reporting
- [ ] Add 3MF structure validation
- [ ] Generate quality report after export
- [ ] Test metrics with sample models
- [ ] Document metrics output in USAGE.md
- [ ] Create PR with comprehensive commit message
- [ ] Merge PR after review

**Files to Modify**:
- `tools/lib3mf_utils.py`
- `tools/export.py`
- `USAGE.md`

---

### 5. Multi-Document Support [LOW PRIORITY]
**Status**: NOT STARTED
**Branch**: `agent_multi_document`
**Effort**: Medium (2-3 hours)
**Impact**: Low - Niche use case

**Description**: Export bodies from multiple FCStd files in single export config.

**Tasks**:
- [ ] Design multi-document config schema
- [ ] Implement document loading and switching in `tools/fc_export.py`
- [ ] Handle object resolution across multiple documents
- [ ] Add dependency management between documents
- [ ] Test with multiple FCStd files
- [ ] Document multi-document exports in USAGE.md
- [ ] Create PR with comprehensive commit message
- [ ] Merge PR after review

**Config Format**:
```yaml
export:
  - name: Combined
    documents:
      - source: project1.FCStd
        bodies: [Body1, Body2]
      - source: project2.FCStd
        bodies: [Body3, Body4]
```

**Files to Modify**:
- `tools/fc_export.py`
- `tools/export.py`
- `USAGE.md`

---

## Phase 1 Features - Completed ✅

### Completed in Previous Session
- ✅ Macro helper module with dialog UI and configuration
- ✅ Git metadata extraction (commit, branch, tags, remote)
- ✅ 3MF metadata embedding
- ✅ Body marking system (custom property `ExportTo3MF=True`)
- ✅ Enhanced macros with configuration support
- ✅ Comprehensive documentation (CHANGELOG, USAGE)
- ✅ PR #1 merged to main
- ✅ Agent workflow guidelines in AGENTS.md

### Files Created in Phase 1
- `macros/macro_helper.py` - Macro utilities (409 lines)
- `tools/git_utils.py` - Git integration (159 lines)
- `CHANGELOG.md` - Feature documentation (143 lines)
- `USAGE.md` - User guide (330 lines)
- `PHASE1_SUMMARY.md` - Session summary (429 lines)

### Files Modified in Phase 1
- `tools/fc_export.py` - Added metadata extraction
- `tools/lib3mf_utils.py` - Added metadata embedding
- `macros/generate_variant_configs.py` - Use macro_helper
- `macros/variant_array_assignment.py` - Use macro_helper
- `examples/export_config.yml.example.yml` - Added examples
- `AGENTS.md` - Added PR management guidelines

---

## Development Workflow

### For Each Feature Branch
1. Create feature branch from main: `git checkout -b agent_<feature_name>`
2. Implement feature with regular commits following Conventional Commits
3. Update documentation (USAGE.md, example configs, docstrings)
4. Run pre-commit checks: `pre-commit run --all-files`
5. Push branch: `git push -u origin agent_<feature_name>`
6. Create PR with clear description
7. Monitor PR for review/feedback
8. Merge PR after approval
9. Clean up local branch: `git branch -d agent_<feature_name>`

### Pre-Commit Checks Required
```bash
pre-commit run --all-files
python3 -m py_compile tools/*.py macros/*.py
ruff check tools/ macros/
ruff format tools/ macros/ --check
```

### Commit Message Format
Follow Conventional Commits:
```
feat(scope): description
fix(scope): description
docs(scope): description
style(scope): description
refactor(scope): description
test(scope): description
```

---

## Success Criteria

For each feature to be considered complete:
- ✅ Code passes all pre-commit checks
- ✅ All functions have docstrings
- ✅ No breaking changes (backwards compatible)
- ✅ Documentation updated (USAGE.md, examples, comments)
- ✅ Example config shows new feature usage
- ✅ PR created with comprehensive description
- ✅ PR merged after review
- ✅ Local branch cleaned up

---

## Branch Status

**Main**: Production ready, all Phase 1 features merged
**Develop**: Staging, ready for next PR
**agent_body_orientation**: Ready to start implementation
**agent_template_metadata**: Ready to start implementation
**agent_batch_processing**: Ready to start implementation
**agent_quality_metrics**: Ready to start implementation
**agent_multi_document**: Ready to start implementation

---

## Key Documentation Files

- **AGENTS.md**: Agent development process (workflow, PR management, branch strategy)
- **USAGE.md**: User-facing guide with examples
- **CHANGELOG.md**: Detailed feature documentation
- **README.md**: Project overview and quick start
- **PHASE1_SUMMARY.md**: Phase 1 accomplishments and next steps
- **TESTING.md**: Testing strategy and procedures

---

## Notes

- Feature branches use `agent_<feature_name>` naming convention
- AGENTS.md provides process guidance only (NOT task tracking - this file tracks tasks)
- All development happens on feature branches, merged via PR
- Pre-commit hooks enforce code quality automatically
- Copilot review requested for all PRs
- No external resources needed - use Context7 for API documentation

---

**Last Updated**: April 25, 2026
**Next Focus**: Body Orientation Support (agent_body_orientation)
