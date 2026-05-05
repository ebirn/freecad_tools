#!/usr/bin/env python3
"""Unit tests for release_validator.py."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_test_dir = Path(__file__).parent
_tools_dir = _test_dir.parent / "tools"
sys.path.insert(0, str(_tools_dir))

import release_validator  # noqa: E402


class TestValidateVersionInPyproject:
    """Tests for validate_version_in_pyproject function."""

    def test_returns_version_when_present(self, tmp_path):
        """Should return version string when pyproject.toml has it."""
        # Given
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nversion = "1.2.3"\n')

        # When
        result = release_validator.validate_version_in_pyproject(str(tmp_path))

        # Then
        assert result == "1.2.3"

    def test_raises_when_no_version(self, tmp_path):
        """Should raise when pyproject.toml has no version."""
        # Given
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "myproject"\n')

        # When/Then
        with pytest.raises(release_validator.ReleaseValidationError, match="version.*not found"):
            release_validator.validate_version_in_pyproject(str(tmp_path))

    def test_raises_when_file_missing(self, tmp_path):
        """Should raise when pyproject.toml does not exist."""
        # Given/When/Then
        with pytest.raises(release_validator.ReleaseValidationError, match="pyproject.toml.*not found"):
            release_validator.validate_version_in_pyproject(str(tmp_path))


class TestValidateChangelogHasVersion:
    """Tests for validate_changelog_has_version function."""

    def test_returns_true_when_changelog_has_version(self, tmp_path):
        """Should return True when CHANGELOG.md contains the version."""
        # Given
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("## [v1.2.3] - 2026-05-05\n\n### Added\n- Feature\n")

        # When
        result = release_validator.validate_changelog_has_version(str(tmp_path), "1.2.3")

        # Then
        assert result is True

    def test_raises_when_version_missing(self, tmp_path):
        """Should raise when CHANGELOG.md does not contain the version."""
        # Given
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("## [v1.0.0] - 2026-01-01\n\n### Added\n- Feature\n")

        # When/Then
        with pytest.raises(release_validator.ReleaseValidationError, match="CHANGELOG.*1.2.3"):
            release_validator.validate_changelog_has_version(str(tmp_path), "1.2.3")

    def test_raises_when_file_missing(self, tmp_path):
        """Should raise when CHANGELOG.md does not exist."""
        # Given/When/Then
        with pytest.raises(release_validator.ReleaseValidationError, match="CHANGELOG.*not found"):
            release_validator.validate_changelog_has_version(str(tmp_path), "1.2.3")


class TestValidateChangelogHasUnreleasedSection:
    """Tests for validate_changelog_has_unreleased_section function."""

    def test_passes_when_unreleased_section_exists(self, tmp_path):
        """Should pass when CHANGELOG has an [Unreleased] section."""
        # Given
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("## [Unreleased]\n\n## [v1.0.0] - 2026-01-01\n")

        # When
        result = release_validator.validate_changelog_has_unreleased_section(str(tmp_path))

        # Then
        assert result is True

    def test_passes_when_unreleased_section_empty(self, tmp_path):
        """Should pass even if [Unreleased] section has no content."""
        # Given
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("## [Unreleased]\n\n## [v1.0.0] - 2026-01-01\n")

        # When
        result = release_validator.validate_changelog_has_unreleased_section(str(tmp_path))

        # Then
        assert result is True

    def test_raises_when_no_unreleased_section(self, tmp_path):
        """Should raise when CHANGELOG has no [Unreleased] section."""
        # Given
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("## [v1.0.0] - 2026-01-01\n")

        # When/Then
        with pytest.raises(release_validator.ReleaseValidationError, match="Unreleased"):
            release_validator.validate_changelog_has_unreleased_section(str(tmp_path))


class TestValidateTestsPass:
    """Tests for validate_tests_pass function."""

    @patch("release_validator.subprocess.run")
    def test_passes_when_tests_succeed(self, mock_run):
        """Should pass when pytest returns 0."""
        # Given
        mock_run.return_value = MagicMock(returncode=0)

        # When
        result = release_validator.validate_tests_pass(cwd="/fake/path")

        # Then
        assert result is True
        mock_run.assert_called_once()

    @patch("release_validator.subprocess.run")
    def test_raises_when_tests_fail(self, mock_run):
        """Should raise when pytest returns non-zero."""
        # Given
        mock_run.return_value = MagicMock(returncode=1)

        # When/Then
        with pytest.raises(release_validator.ReleaseValidationError, match="tests.*failed"):
            release_validator.validate_tests_pass(cwd="/fake/path")


class TestGenerateChecksums:
    """Tests for generate_checksums function."""

    def test_generates_sha256_for_file(self, tmp_path):
        """Should generate SHA256 checksum for a single file."""
        # Given
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        # When
        result = release_validator.generate_checksums([str(test_file)])

        # Then
        assert len(result) == 1
        assert "test.txt" in result
        assert result["test.txt"].startswith("sha256:")

    def test_generates_checksums_for_multiple_files(self, tmp_path):
        """Should generate checksums for multiple files."""
        # Given
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"
        file1.write_text("aaa")
        file2.write_text("bbb")

        # When
        result = release_validator.generate_checksums([str(file1), str(file2)])

        # Then
        assert len(result) == 2
        assert "a.txt" in result
        assert "b.txt" in result

    def test_skips_nonexistent_files(self, tmp_path):
        """Should skip files that don't exist."""
        # Given
        test_file = tmp_path / "exists.txt"
        test_file.write_text("content")

        # When
        result = release_validator.generate_checksums([str(test_file), "/nonexistent/file.txt"])

        # Then
        assert len(result) == 1
        assert "exists.txt" in result


class TestFormatChecksumFile:
    """Tests for format_checksum_file function."""

    def test_formats_sha256sum_style(self, tmp_path):
        """Should output sha256sum-compatible format."""
        # Given
        checksums = {"file1.txt": "sha256:abc123", "file2.txt": "sha256:def456"}
        output_file = tmp_path / "checksums.sha256"

        # When
        release_validator.format_checksum_file(checksums, str(output_file))

        # Then
        content = output_file.read_text()
        assert "abc123  file1.txt" in content
        assert "def456  file2.txt" in content


class TestGenerateReleaseSummary:
    """Tests for generate_release_summary function."""

    @patch("release_validator.validate_version_in_pyproject")
    @patch("release_validator.validate_changelog_has_version")
    @patch("release_validator.validate_changelog_has_unreleased_section")
    @patch("release_validator.validate_tests_pass")
    @patch("release_validator.get_commit_hash")
    def test_generates_summary_on_success(
        self,
        mock_git,
        mock_tests,
        mock_unreleased,
        mock_changelog,
        mock_version,
        tmp_path,
    ):
        """Should generate summary dict with all checks passing."""
        # Given
        mock_version.return_value = "1.2.3"
        mock_changelog.return_value = True
        mock_unreleased.return_value = True
        mock_tests.return_value = True
        mock_git.return_value = "abc1234"

        # When
        result = release_validator.generate_release_summary(str(tmp_path))

        # Then
        assert result["version"] == "1.2.3"
        assert result["version_check"] is True
        assert result["changelog_check"] is True
        assert result["unreleased_check"] is True
        assert result["tests_check"] is True
        assert result["commit"] == "abc1234"
        assert result["all_checks_passed"] is True

    @patch("release_validator.validate_version_in_pyproject")
    @patch("release_validator.validate_changelog_has_version")
    @patch("release_validator.validate_changelog_has_unreleased_section")
    @patch("release_validator.validate_tests_pass")
    @patch("release_validator.get_commit_hash")
    def test_all_checks_false_on_failure(
        self,
        mock_git,
        mock_tests,
        mock_unreleased,
        mock_changelog,
        mock_version,
        tmp_path,
    ):
        """Should set all_checks_passed to False when any check fails."""
        # Given
        mock_version.side_effect = release_validator.ReleaseValidationError("no version")
        mock_changelog.return_value = True
        mock_unreleased.return_value = True
        mock_tests.return_value = True
        mock_git.return_value = "abc"

        # When
        result = release_validator.generate_release_summary(str(tmp_path))

        # Then
        assert result["all_checks_passed"] is False
        assert result["version_check"] is False


class TestRunAllChecks:
    """Tests for run_all_checks function."""

    @patch("release_validator.validate_version_in_pyproject")
    @patch("release_validator.validate_changelog_has_version")
    @patch("release_validator.validate_changelog_has_unreleased_section")
    @patch("release_validator.validate_tests_pass")
    def test_raises_on_first_failure(
        self,
        mock_tests,
        mock_unreleased,
        mock_changelog,
        mock_version,
        tmp_path,
    ):
        """Should raise on the first failing check."""
        # Given
        mock_version.return_value = "1.2.3"
        mock_changelog.side_effect = release_validator.ReleaseValidationError("missing version in changelog")

        # When/Then
        with pytest.raises(release_validator.ReleaseValidationError, match="missing version in changelog"):
            release_validator.run_all_checks(str(tmp_path), version="1.2.3")

    @patch("release_validator.validate_version_in_pyproject")
    @patch("release_validator.validate_changelog_has_version")
    @patch("release_validator.validate_changelog_has_unreleased_section")
    @patch("release_validator.validate_tests_pass")
    def test_passes_when_all_ok(
        self,
        mock_tests,
        mock_unreleased,
        mock_changelog,
        mock_version,
        tmp_path,
    ):
        """Should return True when all checks pass."""
        # Given
        mock_version.return_value = "1.2.3"
        mock_changelog.return_value = True
        mock_unreleased.return_value = True
        mock_tests.return_value = True

        # When
        result = release_validator.run_all_checks(str(tmp_path), version="1.2.3")

        # Then
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
