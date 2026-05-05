#!/usr/bin/env python3
"""
release_validator.py - Release readiness checks and artifact integrity verification.

Provides gates for validating release readiness (version consistency, changelog,
tests) and generating checksums/metadata for published artifacts.
"""

import hashlib
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

try:
    from git_utils import get_commit_hash
except ImportError:
    get_commit_hash = None

logger = logging.getLogger(__name__)


class ReleaseValidationError(Exception):
    """Raised when a release readiness check fails."""


def _parse_pyproject_version(content):
    """Extract version from pyproject.toml content using regex."""
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if match:
        return match.group(1)
    return None


def validate_version_in_pyproject(project_root):
    """Return the version string from pyproject.toml, or raise on failure."""
    pyproject_path = Path(project_root) / "pyproject.toml"
    if not pyproject_path.exists():
        raise ReleaseValidationError("pyproject.toml not found in project root")

    content = pyproject_path.read_text()
    version = _parse_pyproject_version(content)
    if not version:
        raise ReleaseValidationError("version not found in pyproject.toml [project] section")

    return str(version)


def validate_changelog_has_version(project_root, version):
    """Verify CHANGELOG.md contains an entry for the given version."""
    changelog_path = Path(project_root) / "CHANGELOG.md"
    if not changelog_path.exists():
        raise ReleaseValidationError("CHANGELOG.md not found in project root")

    content = changelog_path.read_text()
    version_tag = f"[v{version}]"
    if version_tag not in content:
        raise ReleaseValidationError(f"CHANGELOG.md does not contain entry for version {version_tag}")

    return True


def validate_changelog_has_unreleased_section(project_root):
    """Verify CHANGELOG.md has an [Unreleased] section."""
    changelog_path = Path(project_root) / "CHANGELOG.md"
    if not changelog_path.exists():
        raise ReleaseValidationError("CHANGELOG.md not found in project root")

    content = changelog_path.read_text()
    if "[Unreleased]" not in content:
        raise ReleaseValidationError("CHANGELOG.md is missing an [Unreleased] section")

    return True


def validate_tests_pass(cwd=None):
    """Run pytest and return True if all tests pass, raise otherwise."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise ReleaseValidationError("tests failed")

    return True


def generate_checksums(file_paths):
    """Generate SHA256 checksums for a list of file paths.

    Returns a dict mapping basename to "sha256:<hex>" string.
    """
    checksums = {}
    for path_str in file_paths:
        path = Path(path_str)
        if not path.is_file():
            logger.warning("Skipping non-existent file: %s", path_str)
            continue

        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        checksums[path.name] = f"sha256:{sha256.hexdigest()}"

    return checksums


def format_checksum_file(checksums, output_path):
    """Write checksums in sha256sum-compatible format to output_path."""
    with open(output_path, "w") as f:
        for filename, checksum in sorted(checksums.items()):
            hash_value = checksum.replace("sha256:", "")
            f.write(f"{hash_value}  {filename}\n")


def generate_release_summary(project_root):
    """Run all release checks and return a summary dict.

    Returns a dict with:
    - version: the version from pyproject.toml (or None)
    - version_check: bool
    - changelog_check: bool
    - unreleased_check: bool
    - tests_check: bool
    - commit: git commit hash
    - all_checks_passed: bool
    """
    summary = {
        "version": None,
        "version_check": False,
        "changelog_check": False,
        "unreleased_check": False,
        "tests_check": False,
        "commit": None,
        "all_checks_passed": False,
    }

    try:
        summary["version"] = validate_version_in_pyproject(project_root)
        summary["version_check"] = True
    except ReleaseValidationError as e:
        logger.error("Version check failed: %s", e)

    try:
        if summary["version"]:
            validate_changelog_has_version(project_root, summary["version"])
            summary["changelog_check"] = True
    except ReleaseValidationError as e:
        logger.error("Changelog version check failed: %s", e)

    try:
        validate_changelog_has_unreleased_section(project_root)
        summary["unreleased_check"] = True
    except ReleaseValidationError as e:
        logger.error("Unreleased section check failed: %s", e)

    try:
        validate_tests_pass(cwd=project_root)
        summary["tests_check"] = True
    except ReleaseValidationError as e:
        logger.error("Tests check failed: %s", e)

    try:
        if get_commit_hash:
            summary["commit"] = get_commit_hash(cwd=project_root, short=True)
    except Exception:
        logger.debug("Could not retrieve git commit hash")

    summary["all_checks_passed"] = all(
        [
            summary["version_check"],
            summary["changelog_check"],
            summary["unreleased_check"],
            summary["tests_check"],
        ]
    )

    return summary


def run_all_checks(project_root, version=None):
    """Run all release readiness checks. Raise on first failure.

    If version is not provided, it is read from pyproject.toml.
    """
    if version is None:
        version = validate_version_in_pyproject(project_root)

    validate_changelog_has_version(project_root, version)
    validate_changelog_has_unreleased_section(project_root)
    validate_tests_pass(cwd=project_root)

    return True


def main():
    """CLI entry point for release validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate release readiness")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Version to validate (default: from pyproject.toml)",
    )
    parser.add_argument(
        "--check",
        choices=["version", "changelog", "unreleased", "tests", "all"],
        default="all",
        help="Specific check to run",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Generate and print release summary as JSON",
    )
    parser.add_argument(
        "--checksums",
        nargs="*",
        default=None,
        help="Generate checksums for listed files",
    )
    parser.add_argument(
        "--checksum-output",
        default=None,
        help="Output file for checksums",
    )

    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()

    if args.summary:
        summary = generate_release_summary(str(project_root))
        print(json.dumps(summary, indent=2))
        sys.exit(0 if summary["all_checks_passed"] else 1)

    if args.checksums:
        checksums = generate_checksums(args.checksums)
        if args.checksum_output:
            format_checksum_file(checksums, args.checksum_output)
            logger.info("Checksums written to %s", args.checksum_output)
        else:
            for filename, checksum in sorted(checksums.items()):
                print(f"{checksum}  {filename}")
        sys.exit(0)

    checks = {
        "version": lambda: validate_version_in_pyproject(str(project_root)),
        "changelog": lambda: validate_changelog_has_version(
            str(project_root), args.version or validate_version_in_pyproject(str(project_root))
        ),
        "unreleased": lambda: validate_changelog_has_unreleased_section(str(project_root)),
        "tests": lambda: validate_tests_pass(cwd=str(project_root)),
        "all": lambda: run_all_checks(str(project_root), args.version),
    }

    try:
        result = checks[args.check]()
        if isinstance(result, str):
            print(result)
        logger.info("Check '%s' passed", args.check)
        sys.exit(0)
    except ReleaseValidationError as e:
        logger.error("Check '%s' failed: %s", args.check, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
