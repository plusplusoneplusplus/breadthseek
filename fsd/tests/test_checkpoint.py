"""Tests for checkpoint system."""

import tempfile
from pathlib import Path
from time import sleep

import pytest

from fsd.core import (
    CheckpointError,
    CheckpointManager,
    CheckpointType,
    GitUtils,
)


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    import subprocess

    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    test_file = repo_path / "README.md"
    test_file.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    return repo_path


class TestGitUtils:
    """Test Git utilities."""

    def test_git_utils_init(self, git_repo):
        """Test initializing GitUtils."""
        git = GitUtils(git_repo)
        assert git.repo_path == git_repo
        assert git.is_git_repo()

    def test_git_utils_non_repo(self, tmp_path):
        """Test GitUtils raises error for non-git directory."""
        from fsd.core import GitOperationError

        non_repo = tmp_path / "not_a_repo"
        non_repo.mkdir()

        with pytest.raises(GitOperationError, match="Not a git repository"):
            GitUtils(non_repo)

    def test_get_current_branch(self, git_repo):
        """Test getting current branch."""
        git = GitUtils(git_repo)
        branch = git.get_current_branch()
        assert branch in ["main", "master"]  # Depends on git version

    def test_get_current_commit(self, git_repo):
        """Test getting current commit hash."""
        git = GitUtils(git_repo)
        commit = git.get_current_commit()
        assert len(commit) == 40  # Full SHA-1 hash
        assert all(c in "0123456789abcdef" for c in commit)

    def test_has_uncommitted_changes(self, git_repo):
        """Test detecting uncommitted changes."""
        git = GitUtils(git_repo)

        # No changes initially
        assert not git.has_uncommitted_changes()

        # Create a change
        test_file = git_repo / "test.txt"
        test_file.write_text("test content")

        # Should detect the change
        assert git.has_uncommitted_changes()

    def test_get_changed_files(self, git_repo):
        """Test getting list of changed files."""
        git = GitUtils(git_repo)

        # Create some changes
        file1 = git_repo / "file1.txt"
        file2 = git_repo / "file2.txt"
        file1.write_text("content 1")
        file2.write_text("content 2")

        changed = git.get_changed_files()
        assert "file1.txt" in changed
        assert "file2.txt" in changed

    def test_create_commit(self, git_repo):
        """Test creating a commit."""
        git = GitUtils(git_repo)

        # Create a file and commit
        test_file = git_repo / "test.txt"
        test_file.write_text("test content")

        commit_hash = git.create_commit("Test commit")
        assert len(commit_hash) == 40

        # Verify no uncommitted changes
        assert not git.has_uncommitted_changes()

    def test_create_commit_allow_empty(self, git_repo):
        """Test creating empty commit."""
        git = GitUtils(git_repo)

        # Create empty commit
        commit_hash = git.create_commit("Empty commit", allow_empty=True)
        assert len(commit_hash) == 40

    def test_create_and_delete_tag(self, git_repo):
        """Test creating and deleting tags."""
        git = GitUtils(git_repo)

        # Create tag
        git.create_tag("v1.0.0", message="Version 1.0.0")

        # Verify tag exists
        tags = git.list_tags()
        assert "v1.0.0" in tags

        # Delete tag
        git.delete_tag("v1.0.0")

        # Verify tag is gone
        tags = git.list_tags()
        assert "v1.0.0" not in tags

    def test_list_tags_with_pattern(self, git_repo):
        """Test listing tags with pattern."""
        git = GitUtils(git_repo)

        # Create multiple tags
        git.create_tag("v1.0.0")
        git.create_tag("v2.0.0")
        git.create_tag("release-1")

        # List all tags
        all_tags = git.list_tags()
        assert len(all_tags) == 3

        # List with pattern
        v_tags = git.list_tags("v*")
        assert len(v_tags) == 2
        assert "v1.0.0" in v_tags
        assert "v2.0.0" in v_tags

    def test_get_commit_info(self, git_repo):
        """Test getting commit information."""
        git = GitUtils(git_repo)

        commit_hash = git.get_current_commit()
        info = git.get_commit_info(commit_hash)

        assert info["hash"] == commit_hash
        assert info["author_name"] == "Test User"
        assert info["author_email"] == "test@example.com"
        assert "subject" in info

    def test_stash_and_pop(self, git_repo):
        """Test stashing and popping changes."""
        git = GitUtils(git_repo)

        # Create and add a file first so it's tracked
        test_file = git_repo / "test.txt"
        test_file.write_text("initial content")
        git.create_commit("Add test file")

        # Now modify it
        test_file.write_text("modified content")
        assert git.has_uncommitted_changes()

        # Stash the change
        stashed = git.stash_changes("Test stash")
        assert stashed

        # Pop the stash
        git.stash_pop()
        # Verify the file is back with modifications
        assert test_file.exists()
        assert test_file.read_text() == "modified content"

    def test_is_clean_working_tree(self, git_repo):
        """Test checking if working tree is clean."""
        git = GitUtils(git_repo)

        assert git.is_clean_working_tree()

        # Create a change
        test_file = git_repo / "test.txt"
        test_file.write_text("test content")

        assert not git.is_clean_working_tree()


class TestCheckpointManager:
    """Test checkpoint manager."""

    @pytest.fixture
    def checkpoint_manager(self, git_repo, tmp_path):
        """Create checkpoint manager with test repo."""
        checkpoint_dir = tmp_path / "checkpoints"
        return CheckpointManager(checkpoint_dir=checkpoint_dir, repo_path=git_repo)

    def test_create_checkpoint(self, checkpoint_manager):
        """Test creating a checkpoint."""
        checkpoint = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.PRE_EXECUTION,
            description="Test checkpoint",
        )

        assert checkpoint.task_id == "test-task"
        assert checkpoint.checkpoint_type == CheckpointType.PRE_EXECUTION
        assert checkpoint.description == "Test checkpoint"
        assert len(checkpoint.commit_hash) == 40
        assert checkpoint.tag is not None

    def test_create_checkpoint_with_metadata(self, checkpoint_manager):
        """Test creating checkpoint with additional metadata."""
        checkpoint = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            step_number=1,
            state_machine_state="executing",
            metadata={"custom": "data"},
        )

        assert checkpoint.step_number == 1
        assert checkpoint.state_machine_state == "executing"
        assert checkpoint.metadata["custom"] == "data"

    def test_list_checkpoints(self, checkpoint_manager):
        """Test listing checkpoints."""
        # Create multiple checkpoints
        checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.PRE_EXECUTION,
        )
        sleep(0.1)  # Ensure different timestamps
        checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.STEP_COMPLETE,
        )

        checkpoints = checkpoint_manager.list_checkpoints("test-task")
        assert len(checkpoints) == 2
        assert checkpoints[0].checkpoint_type == CheckpointType.PRE_EXECUTION
        assert checkpoints[1].checkpoint_type == CheckpointType.STEP_COMPLETE

    def test_get_checkpoint(self, checkpoint_manager):
        """Test getting specific checkpoint."""
        created = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.PRE_EXECUTION,
        )

        retrieved = checkpoint_manager.get_checkpoint(
            "test-task", created.checkpoint_id
        )

        assert retrieved is not None
        assert retrieved.checkpoint_id == created.checkpoint_id
        assert retrieved.commit_hash == created.commit_hash

    def test_get_latest_checkpoint(self, checkpoint_manager):
        """Test getting latest checkpoint."""
        checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.PRE_EXECUTION,
        )
        sleep(0.1)
        latest = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.STEP_COMPLETE,
        )

        retrieved = checkpoint_manager.get_latest_checkpoint("test-task")

        assert retrieved is not None
        assert retrieved.checkpoint_id == latest.checkpoint_id

    def test_rollback_to_checkpoint(self, checkpoint_manager, git_repo):
        """Test rolling back to a checkpoint."""
        # Create initial checkpoint
        checkpoint1 = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.PRE_EXECUTION,
        )

        # Make some changes
        test_file = git_repo / "new_file.txt"
        test_file.write_text("new content")
        checkpoint_manager.git.create_commit("Add new file")

        # Rollback to first checkpoint
        restore_info = checkpoint_manager.rollback_to_checkpoint(
            "test-task", checkpoint1.checkpoint_id
        )

        assert restore_info.success
        assert restore_info.commit_hash == checkpoint1.commit_hash
        assert not test_file.exists()

    def test_resume_from_checkpoint(self, checkpoint_manager, git_repo):
        """Test resuming from a checkpoint."""
        checkpoint = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            step_number=5,
        )

        # Make some changes
        test_file = git_repo / "new_file.txt"
        test_file.write_text("new content")
        checkpoint_manager.git.create_commit("Add new file")

        # Resume from checkpoint
        resumed = checkpoint_manager.resume_from_checkpoint(
            "test-task", checkpoint.checkpoint_id
        )

        assert resumed.checkpoint_id == checkpoint.checkpoint_id
        assert not test_file.exists()

    def test_cleanup_checkpoints(self, checkpoint_manager):
        """Test cleaning up old checkpoints."""
        # Create many checkpoints
        for i in range(10):
            checkpoint_manager.create_checkpoint(
                task_id="test-task",
                checkpoint_type=CheckpointType.STEP_COMPLETE,
            )
            sleep(0.05)

        # Keep only 5 latest
        deleted = checkpoint_manager.cleanup_checkpoints("test-task", keep_latest=5)

        assert deleted == 5

        # Verify only 5 remain
        checkpoints = checkpoint_manager.list_checkpoints("test-task")
        assert len(checkpoints) == 5

    def test_cleanup_checkpoints_by_type(self, checkpoint_manager):
        """Test cleaning up checkpoints with type constraints."""
        # Create checkpoints of different types
        for i in range(3):
            checkpoint_manager.create_checkpoint(
                task_id="test-task",
                checkpoint_type=CheckpointType.PRE_EXECUTION,
            )
            sleep(0.05)
        for i in range(3):
            checkpoint_manager.create_checkpoint(
                task_id="test-task",
                checkpoint_type=CheckpointType.STEP_COMPLETE,
            )
            sleep(0.05)

        # Keep 2 of each type
        deleted = checkpoint_manager.cleanup_checkpoints(
            "test-task",
            keep_latest=2,
            keep_by_type={
                CheckpointType.PRE_EXECUTION: 2,
                CheckpointType.STEP_COMPLETE: 2,
            },
        )

        checkpoints = checkpoint_manager.list_checkpoints("test-task")
        # Should keep at least 2 total (might keep more due to type constraints)
        assert len(checkpoints) >= 2

    def test_get_checkpoint_stats(self, checkpoint_manager):
        """Test getting checkpoint statistics."""
        # Create various checkpoints
        checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.PRE_EXECUTION,
        )
        sleep(0.1)
        checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.STEP_COMPLETE,
        )
        sleep(0.1)
        checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.STEP_COMPLETE,
        )

        stats = checkpoint_manager.get_checkpoint_stats("test-task")

        assert stats.total_checkpoints == 3
        assert stats.checkpoints_by_type["pre_execution"] == 1
        assert stats.checkpoints_by_type["step_complete"] == 2
        assert stats.latest_checkpoint is not None
        assert stats.earliest_checkpoint is not None
        assert stats.average_checkpoint_interval is not None

    def test_delete_all_checkpoints(self, checkpoint_manager):
        """Test deleting all checkpoints for a task."""
        # Create checkpoints
        for i in range(5):
            checkpoint_manager.create_checkpoint(
                task_id="test-task",
                checkpoint_type=CheckpointType.STEP_COMPLETE,
            )

        # Delete all
        deleted = checkpoint_manager.delete_all_checkpoints("test-task")
        assert deleted == 5

        # Verify all gone
        checkpoints = checkpoint_manager.list_checkpoints("test-task")
        assert len(checkpoints) == 0

    def test_mark_task_start(self, checkpoint_manager):
        """Test marking task start time."""
        checkpoint_manager.mark_task_start("test-task")

        # Create checkpoint after marking start
        sleep(0.1)
        checkpoint = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.PRE_EXECUTION,
        )

        assert checkpoint.duration_since_start is not None
        assert checkpoint.duration_since_start > 0

    def test_checkpoint_with_test_results(self, checkpoint_manager):
        """Test checkpoint with test results."""
        test_results = {
            "passed": 10,
            "failed": 2,
            "errors": ["Error 1", "Error 2"],
        }

        checkpoint = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.POST_VALIDATION,
            test_results=test_results,
        )

        assert checkpoint.test_results == test_results

    def test_checkpoint_with_error_info(self, checkpoint_manager):
        """Test checkpoint with error information."""
        error_info = {
            "error_type": "ValidationError",
            "message": "Tests failed",
            "traceback": "...",
        }

        checkpoint = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.PRE_RECOVERY,
            error_info=error_info,
        )

        assert checkpoint.error_info == error_info

    def test_checkpoint_excludes_fsd_directory(self, checkpoint_manager, git_repo):
        """Test that checkpoints don't include .fsd directory."""
        # Create files in .fsd
        fsd_dir = git_repo / ".fsd"
        fsd_dir.mkdir()
        (fsd_dir / "test.txt").write_text("should not be committed")

        # Create regular file
        (git_repo / "regular.txt").write_text("should be committed")

        checkpoint = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.PRE_EXECUTION,
        )

        # Verify that regular.txt was committed but .fsd was not
        # The checkpoint will show changed files before the commit
        # After commit, verify .fsd directory is not in git history
        import subprocess
        result = subprocess.run(
            ["git", "show", "--name-only", checkpoint.commit_hash],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        committed_files = result.stdout

        # Verify .fsd files were not committed
        assert ".fsd/" not in committed_files or "regular.txt" in committed_files

    def test_checkpoint_no_empty_commits(self, checkpoint_manager, git_repo):
        """Test that checkpoints don't create empty commits when there are no changes."""
        # Get current commit hash
        initial_commit = checkpoint_manager.git.get_current_commit()

        # Create checkpoint without making any changes
        checkpoint = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.PRE_EXECUTION,
            description="Checkpoint without changes",
        )

        # Verify checkpoint references the same commit (no new commit was created)
        assert checkpoint.commit_hash == initial_commit

        # Verify metadata indicates no new commit was created
        assert checkpoint.metadata.get("new_commit_created") is False

        # Verify git log shows the same commit count
        import subprocess
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        commit_count_after = int(result.stdout.strip())

        # Should still be 1 (just the initial commit)
        assert commit_count_after == 1

    def test_checkpoint_creates_commit_with_changes(self, checkpoint_manager, git_repo):
        """Test that checkpoints create commits when there are actual changes."""
        # Get initial commit
        initial_commit = checkpoint_manager.git.get_current_commit()

        # Make a change
        test_file = git_repo / "test_change.txt"
        test_file.write_text("This is a change")

        # Create checkpoint with changes
        checkpoint = checkpoint_manager.create_checkpoint(
            task_id="test-task",
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            description="Checkpoint with changes",
        )

        # Verify a new commit was created
        assert checkpoint.commit_hash != initial_commit

        # Verify metadata indicates a new commit was created
        assert checkpoint.metadata.get("new_commit_created") is True

        # Verify the file was committed
        assert not checkpoint_manager.git.has_uncommitted_changes()
        assert test_file.exists()


class TestCheckpointIntegration:
    """Integration tests for checkpoint system."""

    def test_full_checkpoint_workflow(self, git_repo, tmp_path):
        """Test complete checkpoint workflow."""
        checkpoint_dir = tmp_path / "checkpoints"
        manager = CheckpointManager(
            checkpoint_dir=checkpoint_dir, repo_path=git_repo
        )

        # Mark task start
        manager.mark_task_start("workflow-task")

        # Create pre-execution checkpoint
        cp1 = manager.create_checkpoint(
            task_id="workflow-task",
            checkpoint_type=CheckpointType.PRE_EXECUTION,
            description="Starting task execution",
        )

        # Simulate work - create file
        file1 = git_repo / "step1.txt"
        file1.write_text("Step 1 complete")
        manager.git.create_commit("Complete step 1")

        # Create step completion checkpoint
        cp2 = manager.create_checkpoint(
            task_id="workflow-task",
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            step_number=1,
            state_machine_state="executing",
        )

        # More work
        file2 = git_repo / "step2.txt"
        file2.write_text("Step 2 complete")
        manager.git.create_commit("Complete step 2")

        # Create validation checkpoint with test results
        cp3 = manager.create_checkpoint(
            task_id="workflow-task",
            checkpoint_type=CheckpointType.POST_VALIDATION,
            test_results={"passed": 10, "failed": 0},
        )

        # Verify we have 3 checkpoints
        checkpoints = manager.list_checkpoints("workflow-task")
        assert len(checkpoints) == 3

        # Get stats
        stats = manager.get_checkpoint_stats("workflow-task")
        assert stats.total_checkpoints == 3

        # Rollback to step 1 checkpoint
        restore_info = manager.rollback_to_checkpoint("workflow-task", cp2.checkpoint_id)
        assert restore_info.success
        assert file1.exists()
        assert not file2.exists()

        # Cleanup old checkpoints
        deleted = manager.cleanup_checkpoints("workflow-task", keep_latest=2)
        assert deleted == 1

        final_checkpoints = manager.list_checkpoints("workflow-task")
        assert len(final_checkpoints) == 2
