#!/usr/bin/env python3
"""Tests for the shell steps of the reusable release workflow."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-publish-release.yml"
STEP_NAME = "Validate bundle paths and generate checksums"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("sha256sum") is None,
    reason="needs bash and sha256sum",
)


def _step_script(bundle_paths):
    """The workflow step's script with the bundle_paths input filled in."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == STEP_NAME:
                return step["run"].replace("${{ inputs.bundle_paths }}", bundle_paths)
    raise AssertionError(f"step {STEP_NAME!r} not found in {WORKFLOW.name}")


def _run_step(project_dir, bundle_paths):
    return subprocess.run(
        ["bash", "-c", _step_script(bundle_paths)],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(name="project_dir")
def _project_dir(tmp_path):
    (tmp_path / "README.md").write_text("readme\n")
    (tmp_path / "notebooks" / "data").mkdir(parents=True)
    (tmp_path / "notebooks" / "calc.ipynb").write_text("{}\n")
    (tmp_path / "notebooks" / "data" / "log.csv").write_text("a,b\n")
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "plot.png").write_bytes(b"\x89PNG")
    return tmp_path


class TestChecksumStep:
    """The checksum step has to cope with the bundle paths a project lists."""

    def test_checksums_plain_files(self, project_dir):
        # Given / When
        result = _run_step(project_dir, "README.md")

        # Then
        assert result.returncode == 0, result.stderr
        assert (project_dir / "dist" / "checksums.sha256").read_text().endswith("  README.md\n")

    def test_checksums_files_inside_directories(self, project_dir):
        # Given / When
        result = _run_step(project_dir, "README.md notebooks img")

        # Then
        assert result.returncode == 0, result.stderr
        lines = (project_dir / "dist" / "checksums.sha256").read_text().splitlines()
        assert [line.split("  ", 1)[1] for line in lines] == [
            "README.md",
            "img/plot.png",
            "notebooks/calc.ipynb",
            "notebooks/data/log.csv",
        ]

    def test_checksum_file_verifies(self, project_dir):
        # Given
        step = _run_step(project_dir, "README.md notebooks img")
        assert step.returncode == 0, step.stderr

        # When
        result = subprocess.run(
            ["sha256sum", "-c", "dist/checksums.sha256"], cwd=project_dir, capture_output=True, text=True, check=False
        )

        # Then
        assert result.returncode == 0, result.stdout + result.stderr

    def test_missing_bundle_path_fails(self, project_dir):
        # Given / When
        result = _run_step(project_dir, "README.md nope")

        # Then
        assert result.returncode != 0
        assert "Missing required bundle path: nope" in result.stderr
