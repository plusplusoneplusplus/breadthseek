"""State machine for managing task lifecycle."""

import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .exceptions import ExecutionError
from .task_state import (
    TaskState,
    TaskStateInfo,
    get_valid_next_states,
    is_terminal_state,
    is_valid_transition,
)


class StateTransitionError(ExecutionError):
    """Raised when an invalid state transition is attempted."""

    pass


class TaskStateMachine:
    """
    Manages task state transitions with validation and history tracking.

    This class provides:
    - Enforced valid state transitions
    - State history tracking
    - Event hooks for state changes
    - Thread-safe operations
    - State persistence integration
    """

    def __init__(self, persistence_handler: Optional["StatePersistence"] = None):
        """
        Initialize the state machine.

        Args:
            persistence_handler: Optional handler for state persistence
        """
        self._states: Dict[str, TaskStateInfo] = {}
        self._lock = threading.RLock()
        self._persistence = persistence_handler
        self._listeners: List[Callable[[str, TaskState, TaskState], None]] = []

        # Load existing state if persistence is enabled
        if self._persistence:
            try:
                self._states = self._persistence.load_all_states()
            except Exception:
                # If loading fails, start with empty state
                self._states = {}

    def register_task(
        self,
        task_id: str,
        initial_state: TaskState = TaskState.QUEUED,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskStateInfo:
        """
        Register a new task with the state machine.

        Args:
            task_id: Unique task identifier
            initial_state: Initial state (default: QUEUED)
            metadata: Optional metadata for the task

        Returns:
            TaskStateInfo object for the new task

        Raises:
            ValueError: If task already exists
        """
        with self._lock:
            if task_id in self._states:
                raise ValueError(f"Task {task_id} is already registered")

            state_info = TaskStateInfo(
                task_id=task_id,
                current_state=initial_state,
                metadata=metadata or {},
            )

            self._states[task_id] = state_info

            # Persist if handler is available
            if self._persistence:
                self._persistence.save_state(state_info)

            return state_info

    def transition(
        self,
        task_id: str,
        to_state: TaskState,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskStateInfo:
        """
        Transition a task to a new state.

        Args:
            task_id: Task identifier
            to_state: Target state
            reason: Optional reason for the transition
            metadata: Optional metadata for the transition

        Returns:
            Updated TaskStateInfo

        Raises:
            ValueError: If task doesn't exist
            StateTransitionError: If transition is invalid
        """
        with self._lock:
            if task_id not in self._states:
                raise ValueError(f"Task {task_id} not found")

            state_info = self._states[task_id]
            from_state = state_info.current_state

            # Check if transition is valid
            if not is_valid_transition(from_state, to_state):
                valid_states = get_valid_next_states(from_state)
                raise StateTransitionError(
                    f"Invalid transition for task {task_id}: "
                    f"{from_state.value} -> {to_state.value}. "
                    f"Valid next states: {[s.value for s in valid_states]}"
                )

            # Add transition to history
            state_info.add_transition(to_state, reason=reason, metadata=metadata)

            # Handle retry count
            if to_state == TaskState.EXECUTING and from_state == TaskState.VALIDATING:
                state_info.retry_count += 1

            # Persist the updated state
            if self._persistence:
                self._persistence.save_state(state_info)

            # Notify listeners
            self._notify_listeners(task_id, from_state, to_state)

            return state_info

    def fail_task(
        self,
        task_id: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskStateInfo:
        """
        Mark a task as failed with an error message.

        Args:
            task_id: Task identifier
            error_message: Error message
            metadata: Optional metadata

        Returns:
            Updated TaskStateInfo
        """
        with self._lock:
            if task_id not in self._states:
                raise ValueError(f"Task {task_id} not found")

            state_info = self._states[task_id]
            state_info.error_message = error_message

            return self.transition(
                task_id,
                TaskState.FAILED,
                reason=error_message,
                metadata=metadata,
            )

    def get_state(self, task_id: str) -> TaskStateInfo:
        """
        Get current state information for a task.

        Args:
            task_id: Task identifier

        Returns:
            TaskStateInfo for the task

        Raises:
            ValueError: If task doesn't exist
        """
        with self._lock:
            if task_id not in self._states:
                raise ValueError(f"Task {task_id} not found")
            return self._states[task_id]

    def get_all_states(self) -> Dict[str, TaskStateInfo]:
        """Get state information for all tasks."""
        with self._lock:
            return dict(self._states)

    def get_tasks_by_state(self, state: TaskState) -> List[TaskStateInfo]:
        """Get all tasks in a specific state."""
        with self._lock:
            return [
                info for info in self._states.values() if info.current_state == state
            ]

    def has_task(self, task_id: str) -> bool:
        """Check if a task is registered."""
        with self._lock:
            return task_id in self._states

    def is_terminal(self, task_id: str) -> bool:
        """
        Check if a task is in a terminal state.

        Args:
            task_id: Task identifier

        Returns:
            True if task is in terminal state

        Raises:
            ValueError: If task doesn't exist
        """
        state_info = self.get_state(task_id)
        return is_terminal_state(state_info.current_state)

    def can_transition_to(self, task_id: str, to_state: TaskState) -> bool:
        """
        Check if a task can transition to a given state.

        Args:
            task_id: Task identifier
            to_state: Target state

        Returns:
            True if transition is valid
        """
        try:
            state_info = self.get_state(task_id)
            return is_valid_transition(state_info.current_state, to_state)
        except ValueError:
            return False

    def add_listener(
        self, listener: Callable[[str, TaskState, TaskState], None]
    ) -> None:
        """
        Add a listener for state transitions.

        Args:
            listener: Callback function(task_id, from_state, to_state)
        """
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(
        self, listener: Callable[[str, TaskState, TaskState], None]
    ) -> None:
        """
        Remove a state transition listener.

        Args:
            listener: Listener to remove
        """
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _notify_listeners(
        self, task_id: str, from_state: TaskState, to_state: TaskState
    ) -> None:
        """Notify all registered listeners of a state transition."""
        for listener in self._listeners:
            try:
                listener(task_id, from_state, to_state)
            except Exception as e:
                # Log but don't fail on listener errors
                print(f"Error in state transition listener: {e}")

    def get_history(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get state transition history for a task.

        Args:
            task_id: Task identifier

        Returns:
            List of transition dictionaries

        Raises:
            ValueError: If task doesn't exist
        """
        state_info = self.get_state(task_id)
        return [
            {
                "from_state": t.from_state.value,
                "to_state": t.to_state.value,
                "timestamp": t.timestamp.isoformat(),
                "reason": t.reason,
                "metadata": t.metadata,
            }
            for t in state_info.history
        ]

    def rollback(
        self, task_id: str, steps: int = 1
    ) -> Optional[TaskStateInfo]:
        """
        Rollback a task to a previous state.

        Args:
            task_id: Task identifier
            steps: Number of steps to roll back (default: 1)

        Returns:
            Updated TaskStateInfo if successful, None if not enough history

        Raises:
            ValueError: If task doesn't exist
        """
        with self._lock:
            state_info = self.get_state(task_id)

            if len(state_info.history) < steps:
                return None

            # Find the target state
            target_transition = state_info.history[-(steps + 1)] if len(state_info.history) > steps else None

            if target_transition:
                target_state = target_transition.to_state
            else:
                # No previous transition, keep current state
                return None

            # Update current state
            state_info.current_state = target_state
            state_info.updated_at = datetime.utcnow()

            # Add rollback transition to history
            state_info.history.append(
                StateTransition(
                    from_state=state_info.current_state,
                    to_state=target_state,
                    reason=f"Rolled back {steps} step(s)",
                    metadata={"rollback": True, "steps": steps},
                )
            )

            # Persist
            if self._persistence:
                self._persistence.save_state(state_info)

            return state_info
