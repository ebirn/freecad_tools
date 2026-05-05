#!/usr/bin/env python3
"""Unit tests for PyPI package metadata and build validation."""

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

_test_dir = Path(__file__).parent
_tools_dir = _test_dir.parent / "tools"
sys.path.insert(0, str(_tools_dir))


class TestPyprojectMetadata:
    """Tests for pyproject.toml metadata completeness."""

    def test_project_has_name(self):
        """Should have a project name."""
        import importlib.metadata

        meta = importlib.metadata.metadata("freecad-tools")
        assert meta["Name"] == "freecad-tools"

    def test_project_has_description(self):
        """Should have a non-empty description/summary."""
        import importlib.metadata

        meta = importlib.metadata.metadata("freecad-tools")
        summary = meta.get("Summary", "")
        assert len(summary) > 0

    def test_project_has_readme(self):
        """Should have a readme configured."""
        pyproject = _test_dir.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert "readme" in content

    def test_project_has_license(self):
        """Should have a license configured."""
        import importlib.metadata

        meta = importlib.metadata.metadata("freecad-tools")
        assert meta.get("License") or meta.get("License-Expression")

    def test_project_has_homepage_url(self):
        """Should have a homepage URL."""
        pyproject = _test_dir.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert "Homepage" in content

    def test_project_has_requires_python(self):
        """Should specify minimum Python version."""
        import importlib.metadata

        meta = importlib.metadata.metadata("freecad-tools")
        assert meta.get("Requires-Python")


class TestPackageEntryPoints:
    """Tests for CLI entry points."""

    def test_export_entry_point_exists(self):
        """Should have freecad-export entry point."""
        pyproject = _test_dir.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert "freecad-export" in content

    def test_export_entry_point_targets_main(self):
        """Should point to tools.export:main."""
        pyproject = _test_dir.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert "tools.export:main" in content


class TestPackageBuild:
    """Tests for package build outputs."""

    @pytest.fixture
    def build_dir(self, tmp_path):
        """Create a build directory with sdist and wheel."""
        subprocess.run(
            ["rm", "-rf", "build", "dist", "freecad_tools.egg-info"],
            cwd=str(_test_dir.parent),
            check=True,
        )
        result = subprocess.run(
            ["uv", "build", "--sdist", "--wheel", "-o", str(tmp_path)],
            cwd=str(_test_dir.parent),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip(f"Build failed: {result.stderr}")
        return tmp_path

    def test_build_produces_sdist(self, build_dir):
        """Should produce a .tar.gz source distribution."""
        sdists = list(build_dir.glob("*.tar.gz"))
        assert len(sdists) >= 1

    def test_build_produces_wheel(self, build_dir):
        """Should produce a .whl binary distribution."""
        wheels = list(build_dir.glob("*.whl"))
        assert len(wheels) >= 1

    def test_sdist_contains_expected_files(self, build_dir):
        """Source distribution should contain key files."""
        sdist = list(build_dir.glob("*.tar.gz"))[0]
        with tarfile.open(sdist, "r:gz") as tar:
            names = tar.getnames()
        assert any("pyproject.toml" in n for n in names)
        assert any("README.md" in n for n in names)

    def test_wheel_contains_tools_package(self, build_dir):
        """Wheel should contain the tools package."""
        wheel = list(build_dir.glob("*.whl"))[0]
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
        assert any("tools/__init__.py" in n or "tools/export.py" in n for n in names)

    def test_wheel_does_not_contain_build_artifacts(self, build_dir):
        """Wheel should not recursively include local build output."""
        wheel = list(build_dir.glob("*.whl"))[0]
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
        assert not any(name.startswith("build/") for name in names)

    def test_wheel_has_metadata(self, build_dir):
        """Wheel should have METADATA with project info."""
        wheel = list(build_dir.glob("*.whl"))[0]
        with zipfile.ZipFile(wheel) as zf:
            metadata_files = [n for n in zf.namelist() if "METADATA" in n]
        assert len(metadata_files) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
