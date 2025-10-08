"""Storage and retrieval of execution plans.

This module handles saving and loading execution plans generated
during the planning phase, storing them in .fsd/plans/ directory.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExecutionPlan(BaseModel):
    """Represents an execution plan for a task."""

    task_id: str = Field(description="Task identifier")
    analysis: str = Field(description="Task analysis")
    complexity: str = Field(description="Complexity level (low/medium/high)")
    estimated_total_time: str = Field(description="Total estimated time")
    steps: List[Dict[str, Any]] = Field(description="List of execution steps")
    dependencies: List[str] = Field(default_factory=list, description="Dependencies")
    risks: List[str] = Field(default_factory=list, description="Potential risks")
    validation_strategy: str = Field(description="Validation approach")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")

    def model_post_init(self, __context: Any) -> None:
        """Set created_at if not provided."""
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat() + "Z"


class PlanStorage:
    """Manages storage and retrieval of execution plans."""

    def __init__(self, plans_dir: Optional[Path] = None):
        """Initialize plan storage.

        Args:
            plans_dir: Directory for storing plans (defaults to .fsd/plans/)
        """
        if plans_dir is None:
            plans_dir = Path.cwd() / ".fsd" / "plans"

        self.plans_dir = Path(plans_dir)
        self.plans_dir.mkdir(parents=True, exist_ok=True)

    def save_plan(self, plan: ExecutionPlan) -> Path:
        """Save an execution plan.

        Args:
            plan: ExecutionPlan to save

        Returns:
            Path to saved plan file
        """
        plan_file = self.plans_dir / f"{plan.task_id}.json"

        # Convert to dict and save
        plan_data = plan.model_dump(mode="json")

        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, indent=2, ensure_ascii=False)

        return plan_file

    def save_plan_dict(self, task_id: str, plan_dict: Dict[str, Any]) -> Path:
        """Save a plan from a dictionary (from Claude output).

        Args:
            task_id: Task identifier
            plan_dict: Plan as dictionary

        Returns:
            Path to saved plan file
        """
        # Ensure task_id is in the dict
        if "task_id" not in plan_dict:
            plan_dict["task_id"] = task_id

        # Create ExecutionPlan and save
        plan = ExecutionPlan(**plan_dict)
        return self.save_plan(plan)

    def load_plan(self, task_id: str) -> Optional[ExecutionPlan]:
        """Load an execution plan.

        Args:
            task_id: Task identifier

        Returns:
            ExecutionPlan if found, None otherwise
        """
        plan_file = self.plans_dir / f"{task_id}.json"

        if not plan_file.exists():
            return None

        try:
            with open(plan_file, "r", encoding="utf-8") as f:
                plan_data = json.load(f)

            return ExecutionPlan(**plan_data)
        except Exception:
            # If plan is corrupted, return None
            return None

    def load_plan_dict(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load a plan as dictionary.

        Args:
            task_id: Task identifier

        Returns:
            Plan dictionary if found, None otherwise
        """
        plan = self.load_plan(task_id)
        if plan is None:
            return None

        return plan.model_dump(mode="json")

    def plan_exists(self, task_id: str) -> bool:
        """Check if a plan exists for a task.

        Args:
            task_id: Task identifier

        Returns:
            True if plan file exists
        """
        plan_file = self.plans_dir / f"{task_id}.json"
        return plan_file.exists()

    def delete_plan(self, task_id: str) -> bool:
        """Delete a plan file.

        Args:
            task_id: Task identifier

        Returns:
            True if plan was deleted, False if not found
        """
        plan_file = self.plans_dir / f"{task_id}.json"

        if plan_file.exists():
            plan_file.unlink()
            return True

        return False

    def list_plans(self) -> List[str]:
        """List all task IDs that have plans.

        Returns:
            List of task IDs
        """
        if not self.plans_dir.exists():
            return []

        return [f.stem for f in self.plans_dir.glob("*.json")]

    def get_plan_summary(self, task_id: str) -> Optional[str]:
        """Get a brief summary of the plan.

        Args:
            task_id: Task identifier

        Returns:
            Summary string or None if plan not found
        """
        plan = self.load_plan(task_id)
        if plan is None:
            return None

        return (
            f"{len(plan.steps)} steps, "
            f"complexity: {plan.complexity}, "
            f"estimated: {plan.estimated_total_time}"
        )
