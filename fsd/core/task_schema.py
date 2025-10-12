"""Task definition schema and validation."""

import re
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class Priority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CompletionActions(BaseModel):
    """Actions to take when a task completes."""

    create_pr: bool = False
    pr_title: Optional[str] = None
    notify_slack: bool = False


class TaskDefinition(BaseModel):
    """Task definition model."""

    id: str = Field(..., description="Unique task identifier")
    numeric_id: Optional[int] = Field(None, description="Sequential numeric identifier")
    description: str = Field(..., description="Natural language task description")
    priority: Priority = Field(..., description="Task priority level")
    estimated_duration: str = Field(
        ..., description="Estimated duration (e.g., '2h', '30m')"
    )

    # Optional fields
    context: Optional[str] = Field(None, description="Additional context information")
    focus_files: Optional[List[str]] = Field(None, description="Files to focus on")
    success_criteria: Optional[str] = Field(None, description="Success criteria")
    on_completion: Optional[CompletionActions] = Field(
        None, description="Completion actions"
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate task ID format."""
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                "Task ID must contain only lowercase letters, numbers, and hyphens"
            )
        if len(v) < 3:
            raise ValueError("Task ID must be at least 3 characters long")
        if len(v) > 50:
            raise ValueError("Task ID must be no more than 50 characters long")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate task description."""
        if not v.strip():
            raise ValueError("Task description cannot be empty")
        if len(v.strip()) < 10:
            raise ValueError("Task description must be at least 10 characters long")
        return v.strip()

    @field_validator("estimated_duration")
    @classmethod
    def validate_duration(cls, v: str) -> str:
        """Validate duration format."""
        if not _parse_duration(v):
            raise ValueError(
                "Invalid duration format. Use formats like '2h', '30m', '1h30m'"
            )
        return v

    @field_validator("focus_files")
    @classmethod
    def validate_focus_files(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate focus files patterns."""
        if v is None:
            return v

        for pattern in v:
            if not pattern.strip():
                raise ValueError("Focus file patterns cannot be empty")

        return [pattern.strip() for pattern in v]

    @model_validator(mode="after")
    def validate_completion_actions(self) -> "TaskDefinition":
        """Validate completion actions consistency."""
        if (
            self.on_completion
            and self.on_completion.create_pr
            and not self.on_completion.pr_title
        ):
            raise ValueError("PR title is required when create_pr is True")
        return self

    @model_validator(mode="after")
    def ensure_execution_requirements(self) -> "TaskDefinition":
        """Ensure task has all fields needed for successful execution.

        Auto-generates success_criteria if not provided to ensure the
        validation phase can function properly.
        """
        # Auto-generate success_criteria if not provided
        if not self.success_criteria:
            # Generate basic success criteria based on task description
            self.success_criteria = (
                "- Implementation matches the task description\n"
                "- All existing tests continue to pass\n"
                "- Code quality checks pass (linting, type checking)\n"
                "- No security issues or secrets in code"
            )

        return self

    def get_duration_seconds(self) -> int:
        """Get estimated duration in seconds."""
        duration = _parse_duration(self.estimated_duration)
        if duration is None:
            raise ValueError(f"Invalid duration format: {self.estimated_duration}")
        return int(duration.total_seconds())

    def get_duration_timedelta(self) -> timedelta:
        """Get estimated duration as timedelta."""
        duration = _parse_duration(self.estimated_duration)
        if duration is None:
            raise ValueError(f"Invalid duration format: {self.estimated_duration}")
        return duration


def _parse_duration(duration_str: str) -> Optional[timedelta]:
    """Parse duration string into timedelta."""
    duration_str = duration_str.strip().lower()

    # Pattern for duration like "2h", "30m", "1h30m", "2h15m"
    pattern = r"^(?:(\d+)h)?(?:(\d+)m)?$"
    match = re.match(pattern, duration_str)

    if not match:
        return None

    hours_str, minutes_str = match.groups()
    hours = int(hours_str) if hours_str else 0
    minutes = int(minutes_str) if minutes_str else 0

    if hours == 0 and minutes == 0:
        return None

    return timedelta(hours=hours, minutes=minutes)


def load_task_from_yaml(file_path: Union[str, Path]) -> TaskDefinition:
    """Load a task definition from a YAML file."""
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Task file not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {file_path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Task file must contain a YAML object, got {type(data)}")

    try:
        return TaskDefinition(**data)
    except Exception as e:
        raise ValueError(f"Invalid task definition in {file_path}: {e}") from e


def load_tasks_from_yaml(file_path: Union[str, Path]) -> List[TaskDefinition]:
    """Load multiple task definitions from a YAML file."""
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Task file not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        raise ValueError(f"Could not read {file_path}: {e}") from e

    # Split on YAML document separators
    documents = content.split("---")
    tasks = []

    for i, doc in enumerate(documents):
        doc = doc.strip()
        if not doc or doc.startswith("#"):
            continue

        try:
            data = yaml.safe_load(doc)
        except yaml.YAMLError as e:
            raise ValueError(
                f"Invalid YAML in document {i+1} of {file_path}: {e}"
            ) from e

        if not isinstance(data, dict):
            continue

        try:
            task = TaskDefinition(**data)
            tasks.append(task)
        except Exception as e:
            raise ValueError(
                f"Invalid task definition in document {i+1} of {file_path}: {e}"
            ) from e

    if not tasks:
        raise ValueError(f"No valid task definitions found in {file_path}")

    return tasks


def validate_task(task_data: Dict[str, Any]) -> TaskDefinition:
    """Validate a task definition from a dictionary."""
    try:
        return TaskDefinition(**task_data)
    except Exception as e:
        raise ValueError(f"Invalid task definition: {e}") from e


def save_task(task: TaskDefinition, file_path: Union[str, Path]) -> None:
    """Save a task definition to a YAML file."""
    file_path = Path(file_path)

    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict and clean up None values, convert enums to strings
    task_dict = task.model_dump(exclude_none=True, mode="json")

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(task_dict, f, default_flow_style=False, sort_keys=False, indent=2)
    except Exception as e:
        raise ValueError(f"Could not save task to {file_path}: {e}") from e
