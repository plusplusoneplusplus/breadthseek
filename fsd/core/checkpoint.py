"""Checkpoint metadata and models."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CheckpointType(str, Enum):
    """Types of checkpoints."""

    PRE_EXECUTION = "pre_execution"
    STEP_COMPLETE = "step_complete"
    PRE_VALIDATION = "pre_validation"
    POST_VALIDATION = "post_validation"
    PRE_RECOVERY = "pre_recovery"
    MANUAL = "manual"


class CheckpointMetadata(BaseModel):
    """
    Metadata for a checkpoint.

    Stores all information needed to understand and restore a checkpoint.
    """

    # Identification
    checkpoint_id: str = Field(..., description="Unique checkpoint identifier")
    task_id: str = Field(..., description="Task this checkpoint belongs to")
    checkpoint_type: CheckpointType = Field(..., description="Type of checkpoint")

    # Git information
    commit_hash: str = Field(..., description="Git commit hash")
    branch: str = Field(..., description="Git branch name")
    tag: Optional[str] = Field(None, description="Git tag name if created")

    # Execution context
    step_number: Optional[int] = Field(None, description="Execution step number")
    state_machine_state: Optional[str] = Field(None, description="Task state")

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    duration_since_start: Optional[float] = Field(
        None, description="Seconds since task started"
    )

    # Changes
    files_changed: List[str] = Field(
        default_factory=list, description="Files changed since last checkpoint"
    )

    # Results
    test_results: Optional[Dict[str, Any]] = Field(
        None, description="Test results if validation checkpoint"
    )
    error_info: Optional[Dict[str, Any]] = Field(
        None, description="Error information if checkpoint after failure"
    )

    # Additional context
    description: Optional[str] = Field(None, description="Human-readable description")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    def get_tag_name(self) -> str:
        """
        Generate a tag name for this checkpoint.

        Returns:
            Git tag name
        """
        return f"fsd/{self.task_id}/{self.checkpoint_id}"

    def to_summary(self) -> str:
        """
        Get a human-readable summary of the checkpoint.

        Returns:
            Summary string
        """
        parts = [
            f"Checkpoint {self.checkpoint_id}",
            f"Type: {self.checkpoint_type.value}",
            f"Commit: {self.commit_hash[:8]}",
            f"Created: {self.created_at.isoformat()}",
        ]

        if self.step_number is not None:
            parts.append(f"Step: {self.step_number}")

        if self.description:
            parts.append(f"Description: {self.description}")

        if self.files_changed:
            parts.append(f"Files changed: {len(self.files_changed)}")

        if self.error_info:
            parts.append("⚠️  Contains error information")

        return " | ".join(parts)


class CheckpointRestoreInfo(BaseModel):
    """
    Information about a checkpoint restore operation.

    Used to track what was done during a rollback or resume.
    """

    checkpoint_id: str
    commit_hash: str
    restored_at: datetime = Field(default_factory=datetime.utcnow)
    files_restored: List[str] = Field(default_factory=list)
    stashed_changes: bool = False
    success: bool = True
    error_message: Optional[str] = None


class CheckpointStats(BaseModel):
    """
    Statistics about checkpoints for a task.

    Provides overview of checkpoint usage.
    """

    task_id: str
    total_checkpoints: int = 0
    checkpoints_by_type: Dict[str, int] = Field(default_factory=dict)
    latest_checkpoint: Optional[CheckpointMetadata] = None
    earliest_checkpoint: Optional[CheckpointMetadata] = None
    total_files_changed: int = 0
    average_checkpoint_interval: Optional[float] = None  # seconds
