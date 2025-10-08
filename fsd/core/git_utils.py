"""Git utilities for checkpoint operations."""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .exceptions import GitOperationError


class GitUtils:
    """
    Utility class for Git operations used by checkpoint system.

    Provides safe wrappers around Git commands for creating commits,
    managing branches, and querying repository state.
    """

    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize Git utilities.

        Args:
            repo_path: Path to git repository (default: current directory)
        """
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()

        if not self.is_git_repo():
            raise GitOperationError(
                f"Not a git repository: {self.repo_path}"
            )

    def _run_git(
        self, *args: str, check: bool = True, capture: bool = True
    ) -> Tuple[int, str, str]:
        """
        Run a git command.

        Args:
            args: Git command arguments
            check: Raise error on non-zero exit
            capture: Capture stdout/stderr

        Returns:
            Tuple of (returncode, stdout, stderr)

        Raises:
            GitOperationError: If command fails and check=True
        """
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_path,
                capture_output=capture,
                text=True,
                check=False,
            )

            if check and result.returncode != 0:
                raise GitOperationError(
                    f"Git command failed: git {' '.join(args)}\n"
                    f"Error: {result.stderr}"
                )

            return result.returncode, result.stdout, result.stderr

        except FileNotFoundError as e:
            raise GitOperationError("Git command not found") from e
        except Exception as e:
            raise GitOperationError(f"Git operation failed: {e}") from e

    def is_git_repo(self) -> bool:
        """Check if the current directory is a git repository."""
        returncode, _, _ = self._run_git(
            "rev-parse", "--git-dir", check=False, capture=True
        )
        return returncode == 0

    def get_current_branch(self) -> str:
        """
        Get the name of the current branch.

        Returns:
            Current branch name

        Raises:
            GitOperationError: If not on a branch
        """
        _, stdout, _ = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        branch = stdout.strip()

        if branch == "HEAD":
            raise GitOperationError("Not currently on a branch (detached HEAD)")

        return branch

    def get_current_commit(self) -> str:
        """
        Get the current commit hash.

        Returns:
            Current commit SHA
        """
        _, stdout, _ = self._run_git("rev-parse", "HEAD")
        return stdout.strip()

    def has_uncommitted_changes(self) -> bool:
        """
        Check if there are uncommitted changes.

        Returns:
            True if there are uncommitted changes
        """
        _, stdout, _ = self._run_git("status", "--porcelain")
        return bool(stdout.strip())

    def get_changed_files(self, since_commit: Optional[str] = None) -> List[str]:
        """
        Get list of changed files.

        Args:
            since_commit: Compare against this commit (default: HEAD)

        Returns:
            List of changed file paths
        """
        if since_commit:
            _, stdout, _ = self._run_git("diff", "--name-only", since_commit)
        else:
            _, stdout, _ = self._run_git("status", "--porcelain")
            # Parse porcelain format: "XY filename"
            files = []
            for line in stdout.strip().split("\n"):
                if line:
                    # Skip the status codes (first 3 chars)
                    files.append(line[3:])
            return files

        return [f for f in stdout.strip().split("\n") if f]

    def create_commit(
        self,
        message: str,
        allow_empty: bool = False,
        files: Optional[List[str]] = None,
    ) -> str:
        """
        Create a git commit.

        Args:
            message: Commit message
            allow_empty: Allow empty commits
            files: Specific files to commit (None = all changes)

        Returns:
            Commit hash

        Raises:
            GitOperationError: If commit fails
        """
        # Add files
        if files:
            for file in files:
                self._run_git("add", file)
        else:
            # Add all changes except .fsd directory
            # First, add everything
            self._run_git("add", "-A")
            # Then unstage .fsd directory if it exists
            fsd_path = self.repo_path / ".fsd"
            if fsd_path.exists():
                self._run_git("reset", "--", ".fsd/", check=False)

        # Create commit
        args = ["commit", "-m", message]
        if allow_empty:
            args.append("--allow-empty")

        _, stdout, _ = self._run_git(*args)

        # Get the commit hash
        return self.get_current_commit()

    def create_tag(self, tag_name: str, message: Optional[str] = None) -> None:
        """
        Create a git tag.

        Args:
            tag_name: Tag name
            message: Optional tag message (creates annotated tag)

        Raises:
            GitOperationError: If tag creation fails
        """
        args = ["tag"]
        if message:
            args.extend(["-a", tag_name, "-m", message])
        else:
            args.append(tag_name)

        self._run_git(*args)

    def delete_tag(self, tag_name: str) -> None:
        """
        Delete a git tag.

        Args:
            tag_name: Tag name to delete
        """
        self._run_git("tag", "-d", tag_name, check=False)

    def list_tags(self, pattern: Optional[str] = None) -> List[str]:
        """
        List git tags.

        Args:
            pattern: Optional pattern to filter tags

        Returns:
            List of tag names
        """
        args = ["tag", "-l"]
        if pattern:
            args.append(pattern)

        _, stdout, _ = self._run_git(*args)
        return [tag for tag in stdout.strip().split("\n") if tag]

    def checkout(self, ref: str) -> None:
        """
        Checkout a git reference.

        Args:
            ref: Branch, tag, or commit to checkout

        Raises:
            GitOperationError: If checkout fails
        """
        self._run_git("checkout", ref)

    def reset_hard(self, ref: str) -> None:
        """
        Hard reset to a git reference.

        Args:
            ref: Reference to reset to

        Raises:
            GitOperationError: If reset fails
        """
        self._run_git("reset", "--hard", ref)

    def get_commit_info(self, commit: str) -> dict:
        """
        Get information about a commit.

        Args:
            commit: Commit hash or reference

        Returns:
            Dictionary with commit information
        """
        # Get commit details
        _, stdout, _ = self._run_git(
            "show",
            "--no-patch",
            "--format=%H%n%an%n%ae%n%at%n%s%n%b",
            commit,
        )

        lines = stdout.strip().split("\n")

        return {
            "hash": lines[0] if len(lines) > 0 else "",
            "author_name": lines[1] if len(lines) > 1 else "",
            "author_email": lines[2] if len(lines) > 2 else "",
            "timestamp": int(lines[3]) if len(lines) > 3 else 0,
            "subject": lines[4] if len(lines) > 4 else "",
            "body": "\n".join(lines[5:]) if len(lines) > 5 else "",
        }

    def stash_changes(self, message: Optional[str] = None) -> bool:
        """
        Stash current changes.

        Args:
            message: Optional stash message

        Returns:
            True if changes were stashed, False if nothing to stash
        """
        if not self.has_uncommitted_changes():
            return False

        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])

        self._run_git(*args)
        return True

    def stash_pop(self) -> None:
        """
        Pop the most recent stash.

        Raises:
            GitOperationError: If pop fails
        """
        self._run_git("stash", "pop")

    def get_repo_root(self) -> Path:
        """
        Get the repository root directory.

        Returns:
            Path to repository root
        """
        _, stdout, _ = self._run_git("rev-parse", "--show-toplevel")
        return Path(stdout.strip())

    def is_clean_working_tree(self) -> bool:
        """
        Check if working tree is clean (no uncommitted changes).

        Returns:
            True if working tree is clean
        """
        return not self.has_uncommitted_changes()

    def get_file_at_commit(self, file_path: str, commit: str) -> str:
        """
        Get file contents at a specific commit.

        Args:
            file_path: Path to file
            commit: Commit hash or reference

        Returns:
            File contents

        Raises:
            GitOperationError: If file doesn't exist at commit
        """
        _, stdout, _ = self._run_git("show", f"{commit}:{file_path}")
        return stdout
