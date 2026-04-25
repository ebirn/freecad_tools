#!/usr/bin/env python3
"""Unit tests for git_utils.py."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add tools/ to path - go up from tests/ to freecad_tools/, then into tools/
_test_dir = Path(__file__).parent
_tools_dir = _test_dir.parent / "tools"
sys.path.insert(0, str(_tools_dir))

# Import the module under test
import git_utils  # noqa: E402


class TestIsGitRepo:
    """Tests for is_git_repo function."""

    def test_returns_true_for_git_repo(self):
        """Should return True when in a git repository."""
        # Given a path in this git repo
        test_path = str(Path(__file__).parent.parent)

        # When
        result = git_utils.is_git_repo(test_path)

        # Then
        assert result is True

    def test_returns_false_for_non_repo(self, tmp_path):
        """Should return False when not in a git repository."""
        # Given a temp directory (not a git repo)
        test_path = str(tmp_path)

        # When
        result = git_utils.is_git_repo(test_path)

        # Then
        assert result is False


class TestGetCommitHash:
    """Tests for get_commit_hash function."""

    def test_gets_current_commit(self):
        """Should return current commit hash."""
        # Given this repo
        test_path = str(Path(__file__).parent.parent)

        # When
        result = git_utils.get_commit_hash(cwd=test_path, short=True)

        # Then
        assert result is not None
        assert len(result) == 7  # short hash

    def test_returns_none_for_non_repo(self, tmp_path):
        """Should return None when not in a git repo."""
        # Given a non-git directory
        test_path = str(tmp_path)

        # When
        result = git_utils.get_commit_hash(cwd=test_path)

        # Then
        assert result is None

    @patch("git_utils.run_git_command")
    def test_get_full_hash(self, mock_run):
        """Should return full hash when short=False."""
        # Given
        mock_run.return_value = "abc123def456789"

        # When
        result = git_utils.get_commit_hash(cwd="/fake/path", short=False)

        # Then
        assert result == "abc123def456789"
        mock_run.assert_called_once_with("rev-parse HEAD", cwd="/fake/path")

    @patch("git_utils.run_git_command")
    def test_get_short_hash(self, mock_run):
        """Should return short hash when short=True."""
        # Given
        mock_run.return_value = "abc1234"

        # When
        result = git_utils.get_commit_hash(cwd="/fake/path", short=True)

        # Then
        assert result == "abc1234"
        mock_run.assert_called_once_with("rev-parse --short HEAD", cwd="/fake/path")


class TestGetBranchName:
    """Tests for get_branch_name function."""

    @patch("git_utils.run_git_command")
    def test_returns_branch_name(self, mock_run):
        """Should return branch name."""
        # Given
        mock_run.return_value = "main"

        # When
        result = git_utils.get_branch_name(cwd="/fake/path")

        # Then
        assert result == "main"

    @patch("git_utils.run_git_command")
    def test_returns_none_on_failure(self, mock_run):
        """Should return None when command fails."""
        # Given
        mock_run.return_value = None

        # When
        result = git_utils.get_branch_name(cwd="/fake/path")

        # Then
        assert result is None


class TestGetBranchNameOrDetached:
    """Tests for get_branch_name_or_detached function."""

    @patch("git_utils.get_branch_name")
    def test_returns_branch_name(self, mock_get_branch):
        """Should return branch name when not detached."""
        # Given
        mock_get_branch.return_value = "feature/test"

        # When
        result = git_utils.get_branch_name_or_detached(cwd="/fake/path")

        # Then
        assert result == "feature/test"

    @patch("git_utils.get_branch_name")
    def test_returns_detached_when_head(self, mock_get_branch):
        """Should return '(detached)' when in detached HEAD state."""
        # Given
        mock_get_branch.return_value = "HEAD"

        # When
        result = git_utils.get_branch_name_or_detached(cwd="/fake/path")

        # Then
        assert result == "(detached)"


class TestGetTags:
    """Tests for get_tags function."""

    @patch("git_utils.run_git_command")
    def test_returns_tags(self, mock_run):
        """Should return space-separated tags."""
        # Given
        mock_run.return_value = "v1.0.0 v1.1.0"

        # When
        result = git_utils.get_tags(cwd="/fake/path")

        # Then
        assert result == "v1.0.0 v1.1.0"

    @patch("git_utils.run_git_command")
    def test_returns_none_when_no_tags(self, mock_run):
        """Should return None when no tags exist."""
        # Given
        mock_run.return_value = None

        # When
        result = git_utils.get_tags(cwd="/fake/path")

        # Then
        assert result is None


class TestGetRemoteUrl:
    """Tests for get_remote_url function."""

    @patch("git_utils.run_git_command")
    def test_returns_remote_url(self, mock_run):
        """Should return remote URL."""
        # Given
        mock_run.return_value = "https://github.com/user/repo.git"

        # When
        result = git_utils.get_remote_url(cwd="/fake/path", remote="origin")

        # Then
        assert result == "https://github.com/user/repo.git"
        mock_run.assert_called_once_with("config --get remote.origin.url", cwd="/fake/path")

    @patch("git_utils.run_git_command")
    def test_uses_custom_remote(self, mock_run):
        """Should use custom remote name."""
        # Given
        mock_run.return_value = "upstream_url"

        # When
        git_utils.get_remote_url(cwd="/fake/path", remote="upstream")

        # Then
        mock_run.assert_called_once_with("config --get remote.upstream.url", cwd="/fake/path")


class TestGetGitMetadata:
    """Tests for get_git_metadata function."""

    @patch("git_utils.get_remote_url")
    @patch("git_utils.get_tags")
    @patch("git_utils.get_branch_name_or_detached")
    @patch("git_utils.get_commit_hash")
    @patch("git_utils.is_git_repo")
    def test_returns_all_metadata(
        self,
        mock_is_repo,
        mock_commit,
        mock_branch,
        mock_tags,
        mock_remote,
    ):
        """Should return complete metadata dictionary."""
        # Given
        mock_is_repo.return_value = True
        mock_commit.side_effect = ["abc123def456789", "abc1234"]  # full, short
        mock_branch.return_value = "main"
        mock_tags.return_value = "v1.0.0"
        mock_remote.return_value = "https://github.com/user/repo.git"

        # When
        result = git_utils.get_git_metadata(cwd="/fake/path")

        # Then
        assert result["is_git_repo"] is True
        assert result["commit_hash"] == "abc123def456789"
        assert result["commit_short"] == "abc1234"
        assert result["branch"] == "main"
        assert result["tags"] == "v1.0.0"
        assert result["remote_url"] == "https://github.com/user/repo.git"

    @patch("git_utils.is_git_repo")
    def test_returns_none_for_non_repo(self, mock_is_repo):
        """Should return None values for non-repo path."""
        # Given
        mock_is_repo.return_value = False

        # When
        result = git_utils.get_git_metadata(cwd="/fake/path")

        # Then
        assert result["is_git_repo"] is False
        assert result["commit_hash"] is None
        assert result["branch"] is None


class TestRunGitCommand:
    """Tests for run_git_command function."""

    @patch("subprocess.run")
    def test_returns_stripped_output(self, mock_run):
        """Should return stripped command output."""
        # Given
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  main  \n"
        mock_run.return_value = mock_result

        # When
        result = git_utils.run_git_command("rev-parse --abbrev-ref HEAD", cwd="/fake")

        # Then
        assert result == "main"

    @patch("subprocess.run")
    def test_returns_none_on_failure(self, mock_run):
        """Should return None when command fails."""
        # Given
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        # When
        result = git_utils.run_git_command("invalid-command", cwd="/fake")

        # Then
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
