#!/usr/bin/env python3
"""
git_utils.py - Utilities for extracting git metadata.

Provides functions to:
- Get current git commit hash
- Get current git branch name
- Get current git tags
- Get git remote URL
- Detect if a directory is in a git repository
"""

import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def run_git_command(command: str, cwd: str = None) -> Optional[str]:
    """
    Run a git command and return its output.

    Args:
        command: Git command to run (without 'git' prefix)
        cwd: Working directory for the command

    Returns:
        Command output (stripped) or None if command failed
    """
    try:
        result = subprocess.run(
            f"git {command}",
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning(f"Git command timed out: {command}")
    except Exception as e:
        logger.debug(f"Git command failed: {e}")
    return None


def is_git_repo(path: str) -> bool:
    """
    Check if a path is inside a git repository.

    Args:
        path: Path to check

    Returns:
        True if inside a git repo, False otherwise
    """
    return run_git_command("rev-parse --git-dir", cwd=path) is not None


def get_commit_hash(cwd: str = None, short: bool = False) -> Optional[str]:
    """
    Get the current git commit hash.

    Args:
        cwd: Working directory
        short: If True, return short hash (7 chars)

    Returns:
        Commit hash or None if not in git repo
    """
    command = "rev-parse --short HEAD" if short else "rev-parse HEAD"
    return run_git_command(command, cwd=cwd)


def get_branch_name(cwd: str = None) -> Optional[str]:
    """
    Get the current git branch name.

    Args:
        cwd: Working directory

    Returns:
        Branch name or None if not in git repo
    """
    return run_git_command("rev-parse --abbrev-ref HEAD", cwd=cwd)


def get_branch_name_or_detached(cwd: str = None) -> Optional[str]:
    """
    Get the current git branch name or "(detached)" if in detached HEAD state.

    Args:
        cwd: Working directory

    Returns:
        Branch name or "(detached)" or None if not in git repo
    """
    branch = get_branch_name(cwd=cwd)
    if branch == "HEAD":
        return "(detached)"
    return branch


def get_tags(cwd: str = None) -> Optional[str]:
    """
    Get git tags for the current commit.

    Args:
        cwd: Working directory

    Returns:
        Space-separated tags or None if not in git repo or no tags
    """
    tags = run_git_command("tag --points-at HEAD", cwd=cwd)
    return tags if tags else None


def get_remote_url(cwd: str = None, remote: str = "origin") -> Optional[str]:
    """
    Get git remote URL.

    Args:
        cwd: Working directory
        remote: Remote name (default: origin)

    Returns:
        Remote URL or None if not found
    """
    return run_git_command(f"config --get remote.{remote}.url", cwd=cwd)


def get_git_metadata(cwd: str = None) -> Dict[str, Optional[str]]:
    """
    Get comprehensive git metadata for the current directory.

    Args:
        cwd: Working directory (defaults to current directory)

    Returns:
        Dictionary with keys: commit_hash, commit_short, branch, tags, remote_url
        Values are None if not in a git repo or if the command failed
    """
    if cwd is None:
        cwd = Path.cwd()

    metadata = {
        "is_git_repo": is_git_repo(str(cwd)),
        "commit_hash": get_commit_hash(cwd=str(cwd)),
        "commit_short": get_commit_hash(cwd=str(cwd), short=True),
        "branch": get_branch_name_or_detached(cwd=str(cwd)),
        "tags": get_tags(cwd=str(cwd)),
        "remote_url": get_remote_url(cwd=str(cwd)),
    }

    logger.debug(f"Git metadata: {metadata}")
    return metadata
