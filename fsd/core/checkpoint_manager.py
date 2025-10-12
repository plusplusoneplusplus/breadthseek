"""Checkpoint manager for creating and managing Git-based checkpoints."""

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .checkpoint import (
    CheckpointMetadata,
    CheckpointRestoreInfo,
    CheckpointStats,
    CheckpointType,
)
from .exceptions import ExecutionError, GitOperationError
from .git_utils import GitUtils


class CheckpointError(ExecutionError):
    """Raised when checkpoint operations fail."""

    pass


class CheckpointManager:
    """
    Manages Git-based checkpoints for task execution.

    Provides functionality to create checkpoints, rollback to previous states,
    resume from checkpoints, and manage checkpoint metadata.
    """

    def __init__(
        self,
        checkpoint_dir: Optional[Path] = None,
        repo_path: Optional[Path] = None,
    ):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory for checkpoint metadata (default: .fsd/checkpoints)
            repo_path: Path to git repository (default: current directory)
        """
        if checkpoint_dir is None:
            checkpoint_dir = Path.cwd() / ".fsd" / "checkpoints"

        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.git = GitUtils(repo_path)
        except GitOperationError as e:
            raise CheckpointError(f"Failed to initialize git utilities: {e}") from e

        self._lock = threading.Lock()
        self._task_start_times: Dict[str, datetime] = {}

    def _get_task_checkpoint_dir(self, task_id: str) -> Path:
        """Get the checkpoint directory for a specific task."""
        task_dir = self.checkpoint_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def _get_checkpoint_file(self, task_id: str, checkpoint_id: str) -> Path:
        """Get the metadata file path for a checkpoint."""
        return self._get_task_checkpoint_dir(task_id) / f"{checkpoint_id}.json"

    def _generate_checkpoint_id(self, task_id: str, checkpoint_type: CheckpointType) -> str:
        """Generate a unique checkpoint ID."""
        import random
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        # Add random component to avoid collisions when creating multiple checkpoints per second
        random_suffix = random.randint(1000, 9999)
        return f"{checkpoint_type.value}_{timestamp}_{random_suffix}"

    def _save_checkpoint_metadata(self, metadata: CheckpointMetadata) -> None:
        """Save checkpoint metadata to disk."""
        checkpoint_file = self._get_checkpoint_file(
            metadata.task_id, metadata.checkpoint_id
        )

        try:
            with open(checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(metadata.model_dump(mode="json"), f, indent=2, default=str)
        except Exception as e:
            raise CheckpointError(
                f"Failed to save checkpoint metadata: {e}"
            ) from e

    def _load_checkpoint_metadata(
        self, task_id: str, checkpoint_id: str
    ) -> Optional[CheckpointMetadata]:
        """Load checkpoint metadata from disk."""
        checkpoint_file = self._get_checkpoint_file(task_id, checkpoint_id)

        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CheckpointMetadata(**data)
        except Exception as e:
            raise CheckpointError(
                f"Failed to load checkpoint metadata: {e}"
            ) from e

    def create_checkpoint(
        self,
        task_id: str,
        checkpoint_type: CheckpointType,
        description: Optional[str] = None,
        step_number: Optional[int] = None,
        state_machine_state: Optional[str] = None,
        test_results: Optional[Dict[str, Any]] = None,
        error_info: Optional[Dict[str, Any]] = None,
        create_tag: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CheckpointMetadata:
        """
        Create a checkpoint at the current state.

        Args:
            task_id: Task identifier
            checkpoint_type: Type of checkpoint
            description: Human-readable description
            step_number: Execution step number
            state_machine_state: Current state machine state
            test_results: Test results if applicable
            error_info: Error information if applicable
            create_tag: Whether to create a Git tag
            metadata: Additional metadata

        Returns:
            CheckpointMetadata for the created checkpoint

        Raises:
            CheckpointError: If checkpoint creation fails
        """
        with self._lock:
            start_time = time.time()

            try:
                # Generate checkpoint ID
                checkpoint_id = self._generate_checkpoint_id(task_id, checkpoint_type)

                # Get current git state
                current_branch = self.git.get_current_branch()
                files_changed = self.git.get_changed_files()

                # Check if there are any changes to commit
                has_changes = self.git.has_uncommitted_changes()

                # Create git commit only if there are changes
                if has_changes:
                    commit_message = f"[FSD Checkpoint] {task_id}: {checkpoint_type.value}"
                    if description:
                        commit_message += f"\n\n{description}"

                    commit_hash = self.git.create_commit(commit_message, allow_empty=False)
                else:
                    # No changes - reference current commit without creating a new one
                    commit_hash = self.git.get_current_commit()

                # Create git tag if requested
                tag_name = None
                if create_tag:
                    tag_name = f"fsd/{task_id}/{checkpoint_id}"
                    self.git.create_tag(tag_name, message=f"Checkpoint: {description or checkpoint_type.value}")

                # Calculate duration since task start
                duration_since_start = None
                if task_id in self._task_start_times:
                    duration_since_start = (
                        datetime.utcnow() - self._task_start_times[task_id]
                    ).total_seconds()

                # Add information about whether a new commit was created
                checkpoint_meta = metadata or {}
                checkpoint_meta["new_commit_created"] = has_changes

                # Create checkpoint metadata
                checkpoint_metadata = CheckpointMetadata(
                    checkpoint_id=checkpoint_id,
                    task_id=task_id,
                    checkpoint_type=checkpoint_type,
                    commit_hash=commit_hash,
                    branch=current_branch,
                    tag=tag_name,
                    step_number=step_number,
                    state_machine_state=state_machine_state,
                    files_changed=files_changed,
                    test_results=test_results,
                    error_info=error_info,
                    description=description,
                    duration_since_start=duration_since_start,
                    metadata=checkpoint_meta,
                )

                # Save metadata
                self._save_checkpoint_metadata(checkpoint_metadata)

                elapsed = time.time() - start_time
                if elapsed > 1.0:
                    print(f"Warning: Checkpoint creation took {elapsed:.2f}s (target: <1s)")

                return checkpoint_metadata

            except Exception as e:
                raise CheckpointError(f"Failed to create checkpoint: {e}") from e

    def list_checkpoints(self, task_id: str) -> List[CheckpointMetadata]:
        """
        List all checkpoints for a task.

        Args:
            task_id: Task identifier

        Returns:
            List of checkpoint metadata, sorted by creation time
        """
        task_dir = self._get_task_checkpoint_dir(task_id)

        if not task_dir.exists():
            return []

        checkpoints = []
        for checkpoint_file in task_dir.glob("*.json"):
            checkpoint_id = checkpoint_file.stem
            metadata = self._load_checkpoint_metadata(task_id, checkpoint_id)
            if metadata:
                checkpoints.append(metadata)

        # Sort by creation time
        checkpoints.sort(key=lambda c: c.created_at)

        return checkpoints

    def get_checkpoint(
        self, task_id: str, checkpoint_id: str
    ) -> Optional[CheckpointMetadata]:
        """
        Get checkpoint metadata.

        Args:
            task_id: Task identifier
            checkpoint_id: Checkpoint identifier

        Returns:
            CheckpointMetadata if found, None otherwise
        """
        return self._load_checkpoint_metadata(task_id, checkpoint_id)

    def get_latest_checkpoint(self, task_id: str) -> Optional[CheckpointMetadata]:
        """
        Get the most recent checkpoint for a task.

        Args:
            task_id: Task identifier

        Returns:
            Latest CheckpointMetadata if any exist
        """
        checkpoints = self.list_checkpoints(task_id)
        return checkpoints[-1] if checkpoints else None

    def rollback_to_checkpoint(
        self,
        task_id: str,
        checkpoint_id: str,
        stash_changes: bool = True,
    ) -> CheckpointRestoreInfo:
        """
        Rollback to a specific checkpoint.

        Args:
            task_id: Task identifier
            checkpoint_id: Checkpoint to rollback to
            stash_changes: Stash uncommitted changes before rollback

        Returns:
            CheckpointRestoreInfo with restore details

        Raises:
            CheckpointError: If rollback fails
        """
        with self._lock:
            try:
                # Load checkpoint metadata
                checkpoint = self.get_checkpoint(task_id, checkpoint_id)
                if not checkpoint:
                    raise CheckpointError(
                        f"Checkpoint {checkpoint_id} not found for task {task_id}"
                    )

                # Stash changes if requested
                stashed = False
                if stash_changes and self.git.has_uncommitted_changes():
                    stashed = self.git.stash_changes(
                        message=f"FSD pre-rollback stash for {task_id}"
                    )

                # Reset to checkpoint commit
                self.git.reset_hard(checkpoint.commit_hash)

                # Get list of files that were restored
                files_restored = self.git.get_changed_files(
                    since_commit=self.git.get_current_commit()
                )

                return CheckpointRestoreInfo(
                    checkpoint_id=checkpoint_id,
                    commit_hash=checkpoint.commit_hash,
                    files_restored=files_restored,
                    stashed_changes=stashed,
                    success=True,
                )

            except Exception as e:
                return CheckpointRestoreInfo(
                    checkpoint_id=checkpoint_id,
                    commit_hash="",
                    success=False,
                    error_message=str(e),
                )

    def resume_from_checkpoint(
        self, task_id: str, checkpoint_id: str
    ) -> CheckpointMetadata:
        """
        Resume execution from a checkpoint.

        Similar to rollback but optimized for continuing execution.

        Args:
            task_id: Task identifier
            checkpoint_id: Checkpoint to resume from

        Returns:
            CheckpointMetadata of the resume point

        Raises:
            CheckpointError: If resume fails
        """
        checkpoint = self.get_checkpoint(task_id, checkpoint_id)
        if not checkpoint:
            raise CheckpointError(
                f"Checkpoint {checkpoint_id} not found for task {task_id}"
            )

        # Rollback to the checkpoint
        restore_info = self.rollback_to_checkpoint(
            task_id, checkpoint_id, stash_changes=True
        )

        if not restore_info.success:
            raise CheckpointError(
                f"Failed to resume from checkpoint: {restore_info.error_message}"
            )

        # Reset task start time for duration tracking
        self._task_start_times[task_id] = datetime.utcnow()

        return checkpoint

    def cleanup_checkpoints(
        self,
        task_id: str,
        keep_latest: int = 5,
        keep_by_type: Optional[Dict[CheckpointType, int]] = None,
    ) -> int:
        """
        Clean up old checkpoints to avoid clutter.

        Args:
            task_id: Task identifier
            keep_latest: Number of latest checkpoints to keep
            keep_by_type: Number of checkpoints to keep per type

        Returns:
            Number of checkpoints deleted

        Raises:
            CheckpointError: If cleanup fails
        """
        with self._lock:
            try:
                checkpoints = self.list_checkpoints(task_id)

                if len(checkpoints) <= keep_latest:
                    return 0

                # Determine which checkpoints to keep
                keep_ids = set()

                # Keep the latest N checkpoints
                for checkpoint in checkpoints[-keep_latest:]:
                    keep_ids.add(checkpoint.checkpoint_id)

                # Keep N checkpoints per type if specified
                if keep_by_type:
                    by_type: Dict[CheckpointType, List[CheckpointMetadata]] = {}
                    for checkpoint in checkpoints:
                        if checkpoint.checkpoint_type not in by_type:
                            by_type[checkpoint.checkpoint_type] = []
                        by_type[checkpoint.checkpoint_type].append(checkpoint)

                    for cp_type, keep_count in keep_by_type.items():
                        if cp_type in by_type:
                            for checkpoint in by_type[cp_type][-keep_count:]:
                                keep_ids.add(checkpoint.checkpoint_id)

                # Delete checkpoints not in keep list
                deleted_count = 0
                for checkpoint in checkpoints:
                    if checkpoint.checkpoint_id not in keep_ids:
                        # Delete metadata file
                        checkpoint_file = self._get_checkpoint_file(
                            task_id, checkpoint.checkpoint_id
                        )
                        checkpoint_file.unlink(missing_ok=True)

                        # Delete git tag if it exists
                        if checkpoint.tag:
                            self.git.delete_tag(checkpoint.tag)

                        deleted_count += 1

                return deleted_count

            except Exception as e:
                raise CheckpointError(f"Failed to cleanup checkpoints: {e}") from e

    def get_checkpoint_stats(self, task_id: str) -> CheckpointStats:
        """
        Get statistics about checkpoints for a task.

        Args:
            task_id: Task identifier

        Returns:
            CheckpointStats with overview information
        """
        checkpoints = self.list_checkpoints(task_id)

        if not checkpoints:
            return CheckpointStats(task_id=task_id)

        # Count by type
        by_type: Dict[str, int] = {}
        total_files = 0

        for checkpoint in checkpoints:
            cp_type = checkpoint.checkpoint_type.value
            by_type[cp_type] = by_type.get(cp_type, 0) + 1
            total_files += len(checkpoint.files_changed)

        # Calculate average interval
        avg_interval = None
        if len(checkpoints) > 1:
            total_seconds = (
                checkpoints[-1].created_at - checkpoints[0].created_at
            ).total_seconds()
            avg_interval = total_seconds / (len(checkpoints) - 1)

        return CheckpointStats(
            task_id=task_id,
            total_checkpoints=len(checkpoints),
            checkpoints_by_type=by_type,
            latest_checkpoint=checkpoints[-1],
            earliest_checkpoint=checkpoints[0],
            total_files_changed=total_files,
            average_checkpoint_interval=avg_interval,
        )

    def mark_task_start(self, task_id: str) -> None:
        """
        Mark the start time for a task.

        Used to calculate duration_since_start in checkpoints.

        Args:
            task_id: Task identifier
        """
        self._task_start_times[task_id] = datetime.utcnow()

    def delete_all_checkpoints(self, task_id: str) -> int:
        """
        Delete all checkpoints for a task.

        Args:
            task_id: Task identifier

        Returns:
            Number of checkpoints deleted
        """
        checkpoints = self.list_checkpoints(task_id)
        count = len(checkpoints)

        for checkpoint in checkpoints:
            # Delete metadata file
            checkpoint_file = self._get_checkpoint_file(
                task_id, checkpoint.checkpoint_id
            )
            checkpoint_file.unlink(missing_ok=True)

            # Delete git tag if it exists
            if checkpoint.tag:
                self.git.delete_tag(checkpoint.tag)

        return count
