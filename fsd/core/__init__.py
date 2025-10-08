"""Core FSD functionality."""

from .checkpoint import (
    CheckpointMetadata,
    CheckpointRestoreInfo,
    CheckpointStats,
    CheckpointType,
)
from .checkpoint_manager import CheckpointError, CheckpointManager
from .exceptions import (
    ActivityTrackingError,
    ConfigurationError,
    ExecutionError,
    FSDError,
    GitOperationError,
    TaskValidationError,
)
from .git_utils import GitUtils
from .state_machine import StateTransitionError, TaskStateMachine
from .state_persistence import StatePersistence, StatePersistenceError
from .task_schema import (
    CompletionActions,
    Priority,
    TaskDefinition,
    load_task_from_yaml,
    load_tasks_from_yaml,
    save_task,
    validate_task,
)
from .task_state import (
    StateTransition,
    TaskState,
    TaskStateInfo,
    get_valid_next_states,
    is_terminal_state,
    is_valid_transition,
)

__all__ = [
    # Exceptions
    "FSDError",
    "TaskValidationError",
    "ConfigurationError",
    "ExecutionError",
    "ActivityTrackingError",
    "GitOperationError",
    "StateTransitionError",
    "StatePersistenceError",
    "CheckpointError",
    # Task schema
    "TaskDefinition",
    "Priority",
    "CompletionActions",
    "load_task_from_yaml",
    "load_tasks_from_yaml",
    "save_task",
    "validate_task",
    # State management
    "TaskState",
    "TaskStateInfo",
    "StateTransition",
    "TaskStateMachine",
    "StatePersistence",
    "is_valid_transition",
    "get_valid_next_states",
    "is_terminal_state",
    # Checkpoint system
    "CheckpointType",
    "CheckpointMetadata",
    "CheckpointRestoreInfo",
    "CheckpointStats",
    "CheckpointManager",
    "GitUtils",
]
