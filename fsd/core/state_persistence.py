"""State persistence layer for saving and loading task states."""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .exceptions import ExecutionError
from .task_state import StateTransition, TaskState, TaskStateInfo


class StatePersistenceError(ExecutionError):
    """Raised when state persistence operations fail."""

    pass


class StatePersistence:
    """
    Handles persistence of task states to disk.

    States are stored as JSON files in a designated directory, with one file
    per task. This allows for easy debugging and recovery.
    """

    def __init__(self, state_dir: Optional[Path] = None):
        """
        Initialize state persistence.

        Args:
            state_dir: Directory for state files (default: .fsd/state)
        """
        if state_dir is None:
            state_dir = Path.cwd() / ".fsd" / "state"

        self.state_dir = Path(state_dir)
        self._lock = threading.Lock()
        self._ensure_state_dir()

    def _ensure_state_dir(self) -> None:
        """Ensure the state directory exists."""
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise StatePersistenceError(
                f"Failed to create state directory {self.state_dir}: {e}"
            ) from e

    def _get_state_file(self, task_id: str) -> Path:
        """Get the file path for a task's state."""
        # Sanitize task_id for filename
        safe_task_id = task_id.replace("/", "_").replace("\\", "_")
        return self.state_dir / f"{safe_task_id}.json"

    def save_state(self, state_info: TaskStateInfo) -> None:
        """
        Save task state to disk.

        Args:
            state_info: Task state information to save

        Raises:
            StatePersistenceError: If save fails
        """
        with self._lock:
            state_file = self._get_state_file(state_info.task_id)

            try:
                # Convert to dict with proper serialization
                state_dict = self._serialize_state(state_info)

                # Write atomically by writing to temp file first
                temp_file = state_file.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(state_dict, f, indent=2, default=str)

                # Rename to final location (atomic on POSIX systems)
                temp_file.replace(state_file)

            except Exception as e:
                raise StatePersistenceError(
                    f"Failed to save state for task {state_info.task_id}: {e}"
                ) from e

    def load_state(self, task_id: str) -> Optional[TaskStateInfo]:
        """
        Load task state from disk.

        Args:
            task_id: Task identifier

        Returns:
            TaskStateInfo if found, None otherwise

        Raises:
            StatePersistenceError: If load fails
        """
        with self._lock:
            state_file = self._get_state_file(task_id)

            if not state_file.exists():
                return None

            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state_dict = json.load(f)

                return self._deserialize_state(state_dict)

            except Exception as e:
                raise StatePersistenceError(
                    f"Failed to load state for task {task_id}: {e}"
                ) from e

    def load_all_states(self) -> Dict[str, TaskStateInfo]:
        """
        Load all task states from disk.

        Returns:
            Dictionary mapping task_id to TaskStateInfo

        Raises:
            StatePersistenceError: If load fails
        """
        with self._lock:
            states: Dict[str, TaskStateInfo] = {}

            if not self.state_dir.exists():
                return states

            try:
                for state_file in self.state_dir.glob("*.json"):
                    if state_file.name.endswith(".tmp"):
                        continue

                    try:
                        with open(state_file, "r", encoding="utf-8") as f:
                            state_dict = json.load(f)

                        state_info = self._deserialize_state(state_dict)
                        states[state_info.task_id] = state_info

                    except Exception as e:
                        # Log error but continue loading other states
                        print(f"Warning: Failed to load {state_file}: {e}")
                        continue

                return states

            except Exception as e:
                raise StatePersistenceError(
                    f"Failed to load states from {self.state_dir}: {e}"
                ) from e

    def delete_state(self, task_id: str) -> bool:
        """
        Delete task state from disk.

        Args:
            task_id: Task identifier

        Returns:
            True if deleted, False if not found

        Raises:
            StatePersistenceError: If delete fails
        """
        with self._lock:
            state_file = self._get_state_file(task_id)

            if not state_file.exists():
                return False

            try:
                state_file.unlink()
                return True
            except Exception as e:
                raise StatePersistenceError(
                    f"Failed to delete state for task {task_id}: {e}"
                ) from e

    def list_task_ids(self) -> list[str]:
        """
        List all task IDs with persisted states.

        Returns:
            List of task IDs
        """
        with self._lock:
            if not self.state_dir.exists():
                return []

            task_ids = []
            for state_file in self.state_dir.glob("*.json"):
                if state_file.name.endswith(".tmp"):
                    continue

                # Extract task_id from filename (reverse sanitization)
                task_id = state_file.stem
                task_ids.append(task_id)

            return task_ids

    def _serialize_state(self, state_info: TaskStateInfo) -> Dict[str, Any]:
        """
        Serialize TaskStateInfo to a JSON-compatible dictionary.

        Args:
            state_info: Task state information

        Returns:
            Dictionary ready for JSON serialization
        """
        return {
            "task_id": state_info.task_id,
            "current_state": state_info.current_state.value,
            "created_at": state_info.created_at.isoformat(),
            "updated_at": state_info.updated_at.isoformat(),
            "history": [
                {
                    "from_state": t.from_state.value,
                    "to_state": t.to_state.value,
                    "timestamp": t.timestamp.isoformat(),
                    "reason": t.reason,
                    "metadata": t.metadata,
                }
                for t in state_info.history
            ],
            "error_message": state_info.error_message,
            "retry_count": state_info.retry_count,
            "metadata": state_info.metadata,
        }

    def _deserialize_state(self, state_dict: Dict[str, Any]) -> TaskStateInfo:
        """
        Deserialize a dictionary to TaskStateInfo.

        Args:
            state_dict: Dictionary from JSON

        Returns:
            TaskStateInfo object
        """
        # Parse history transitions
        history = [
            StateTransition(
                from_state=TaskState(t["from_state"]),
                to_state=TaskState(t["to_state"]),
                timestamp=datetime.fromisoformat(t["timestamp"]),
                reason=t.get("reason"),
                metadata=t.get("metadata", {}),
            )
            for t in state_dict.get("history", [])
        ]

        return TaskStateInfo(
            task_id=state_dict["task_id"],
            current_state=TaskState(state_dict["current_state"]),
            created_at=datetime.fromisoformat(state_dict["created_at"]),
            updated_at=datetime.fromisoformat(state_dict["updated_at"]),
            history=history,
            error_message=state_dict.get("error_message"),
            retry_count=state_dict.get("retry_count", 0),
            metadata=state_dict.get("metadata", {}),
        )

    def get_state_file_path(self, task_id: str) -> Path:
        """
        Get the file path where a task's state is stored.

        Args:
            task_id: Task identifier

        Returns:
            Path to the state file
        """
        return self._get_state_file(task_id)

    def clear_all_states(self) -> int:
        """
        Clear all persisted states.

        Returns:
            Number of states cleared

        Raises:
            StatePersistenceError: If clear fails
        """
        with self._lock:
            if not self.state_dir.exists():
                return 0

            try:
                count = 0
                for state_file in self.state_dir.glob("*.json"):
                    state_file.unlink()
                    count += 1

                return count

            except Exception as e:
                raise StatePersistenceError(
                    f"Failed to clear states from {self.state_dir}: {e}"
                ) from e
