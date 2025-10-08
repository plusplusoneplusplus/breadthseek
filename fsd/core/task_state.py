"""Task state definitions and transitions."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    """Task lifecycle states."""

    QUEUED = "queued"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class StateTransition(BaseModel):
    """Represents a state transition event."""

    from_state: TaskState
    to_state: TaskState
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskStateInfo(BaseModel):
    """Complete state information for a task."""

    task_id: str
    current_state: TaskState
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    history: List[StateTransition] = Field(default_factory=list)
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def add_transition(
        self,
        to_state: TaskState,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a state transition to history."""
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            reason=reason,
            metadata=metadata or {},
        )
        self.history.append(transition)
        self.current_state = to_state
        self.updated_at = datetime.utcnow()


# Valid state transitions
VALID_TRANSITIONS: Dict[TaskState, List[TaskState]] = {
    TaskState.QUEUED: [TaskState.PLANNING, TaskState.FAILED],
    TaskState.PLANNING: [TaskState.EXECUTING, TaskState.FAILED],
    TaskState.EXECUTING: [TaskState.VALIDATING, TaskState.FAILED],
    TaskState.VALIDATING: [
        TaskState.COMPLETED,
        TaskState.EXECUTING,  # Retry on validation failure
        TaskState.FAILED,
    ],
    TaskState.COMPLETED: [],  # Terminal state
    TaskState.FAILED: [],  # Terminal state
}


def is_valid_transition(from_state: TaskState, to_state: TaskState) -> bool:
    """Check if a state transition is valid."""
    return to_state in VALID_TRANSITIONS.get(from_state, [])


def get_valid_next_states(current_state: TaskState) -> List[TaskState]:
    """Get list of valid next states for a given state."""
    return VALID_TRANSITIONS.get(current_state, [])


def is_terminal_state(state: TaskState) -> bool:
    """Check if a state is terminal (no further transitions allowed)."""
    return len(VALID_TRANSITIONS.get(state, [])) == 0
