#!/bin/bash
# Release validator: checks version/license sync across project files
# Intended for pre-push hook on release branches

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Release Validator ==="
echo ""

# 1. Check package.xml vs pyproject.toml version
echo "Checking version consistency..."

PACKAGE_VERSION=$(grep -o '<version>[^<]*</version>' package.xml 2>/dev/null | sed 's/.*>\([^<]*\)<.*/\1/')
PYPROJECT_VERSION=$(grep '^version' pyproject.toml | sed 's/.*"\([^"]*\)".*/\1/')
MACRO_VERSION=$(grep '__Version__' macros/*.py | head -1 | sed 's/.*"\([^"]*\)".*/\1/')

if [ -n "$PACKAGE_VERSION" ] && [ -n "$PYPROJECT_VERSION" ]; then
    if [ "$PACKAGE_VERSION" != "$PYPROJECT_VERSION" ]; then
        echo "ERROR: Version mismatch!"
        echo "  package.xml: $PACKAGE_VERSION"
        echo "  pyproject.toml: $PYPROJECT_VERSION"
        exit 1
    fi
    echo "  package.xml = pyproject.toml = $PACKAGE_VERSION ✓"
fi

if [ -n "$MACRO_VERSION" ] && [ -n "$PYPROJECT_VERSION" ]; then
    if [ "$MACRO_VERSION" != "$PYPROJECT_VERSION" ]; then
        echo "ERROR: Macro version mismatch!"
        echo "  macros: $MACRO_VERSION"
        echo "  pyproject.toml: $PYPROJECT_VERSION"
        exit 1
    fi
    echo "  macros = pyproject.toml ✓"
fi

# 2. Check license consistency
echo ""
echo "Checking license consistency..."

PACKAGE_LICENSE=$(grep -o '<license[^>]*>[^<]*</license>' package.xml 2>/dev/null | sed 's/.*>\([^<]*\)<.*/\1/')
PYPROJECT_LICENSE=$(grep '^license' pyproject.toml | sed 's/.*"\([^"]*\)".*/\1/')

if [ -n "$PACKAGE_LICENSE" ] && [ -n "$PYPROJECT_LICENSE" ]; then
    if [ "$PACKAGE_LICENSE" != "$PYPROJECT_LICENSE" ]; then
        echo "ERROR: License mismatch!"
        echo "  package.xml: $PACKAGE_LICENSE"
        echo "  pyproject.toml: $PYPROJECT_LICENSE"
        exit 1
    fi
    echo "  package.xml = pyproject.toml = $PACKAGE_LICENSE ✓"
fi

# 3. Check CHANGELOG.md has no unreleased items
echo ""
echo "Checking CHANGELOG.md..."

if grep -q '## \[Unreleased\]' CHANGELOG.md 2>/dev/null; then
    echo "WARNING: CHANGELOG.md has [Unreleased] section"
    echo "  Consider moving to a versioned section before release"
fi

echo ""
echo "=== All release checks passed! ==="
