"""Tests for state machine functionality."""

import tempfile
from pathlib import Path

import pytest

from fsd.core import (
    StatePersistence,
    StateTransitionError,
    TaskState,
    TaskStateInfo,
    TaskStateMachine,
    get_valid_next_states,
    is_terminal_state,
    is_valid_transition,
)


class TestTaskState:
    """Test TaskState enum and helper functions."""

    def test_valid_transitions(self):
        """Test valid state transition checks."""
        # Valid transitions
        assert is_valid_transition(TaskState.QUEUED, TaskState.PLANNING)
        assert is_valid_transition(TaskState.PLANNING, TaskState.EXECUTING)
        assert is_valid_transition(TaskState.EXECUTING, TaskState.VALIDATING)
        assert is_valid_transition(TaskState.VALIDATING, TaskState.COMPLETED)
        assert is_valid_transition(TaskState.VALIDATING, TaskState.EXECUTING)

        # Any state can transition to FAILED
        assert is_valid_transition(TaskState.QUEUED, TaskState.FAILED)
        assert is_valid_transition(TaskState.PLANNING, TaskState.FAILED)
        assert is_valid_transition(TaskState.EXECUTING, TaskState.FAILED)
        assert is_valid_transition(TaskState.VALIDATING, TaskState.FAILED)

    def test_invalid_transitions(self):
        """Test invalid state transition checks."""
        # Invalid transitions
        assert not is_valid_transition(TaskState.QUEUED, TaskState.EXECUTING)
        assert not is_valid_transition(TaskState.QUEUED, TaskState.VALIDATING)
        assert not is_valid_transition(TaskState.QUEUED, TaskState.COMPLETED)
        assert not is_valid_transition(TaskState.PLANNING, TaskState.VALIDATING)
        assert not is_valid_transition(TaskState.PLANNING, TaskState.COMPLETED)
        assert not is_valid_transition(TaskState.EXECUTING, TaskState.COMPLETED)

        # Terminal states cannot transition
        assert not is_valid_transition(TaskState.COMPLETED, TaskState.QUEUED)
        assert not is_valid_transition(TaskState.FAILED, TaskState.QUEUED)

    def test_terminal_states(self):
        """Test terminal state detection."""
        assert is_terminal_state(TaskState.COMPLETED)
        assert is_terminal_state(TaskState.FAILED)
        assert not is_terminal_state(TaskState.QUEUED)
        assert not is_terminal_state(TaskState.PLANNING)
        assert not is_terminal_state(TaskState.EXECUTING)
        assert not is_terminal_state(TaskState.VALIDATING)

    def test_get_valid_next_states(self):
        """Test getting valid next states."""
        assert TaskState.PLANNING in get_valid_next_states(TaskState.QUEUED)
        assert TaskState.FAILED in get_valid_next_states(TaskState.QUEUED)

        assert TaskState.EXECUTING in get_valid_next_states(TaskState.PLANNING)
        assert TaskState.FAILED in get_valid_next_states(TaskState.PLANNING)

        assert TaskState.VALIDATING in get_valid_next_states(TaskState.EXECUTING)
        assert TaskState.FAILED in get_valid_next_states(TaskState.EXECUTING)

        assert TaskState.COMPLETED in get_valid_next_states(TaskState.VALIDATING)
        assert TaskState.EXECUTING in get_valid_next_states(TaskState.VALIDATING)
        assert TaskState.FAILED in get_valid_next_states(TaskState.VALIDATING)

        # Terminal states have no valid next states
        assert len(get_valid_next_states(TaskState.COMPLETED)) == 0
        assert len(get_valid_next_states(TaskState.FAILED)) == 0


class TestTaskStateInfo:
    """Test TaskStateInfo model."""

    def test_create_state_info(self):
        """Test creating TaskStateInfo."""
        state_info = TaskStateInfo(
            task_id="test-task",
            current_state=TaskState.QUEUED,
        )

        assert state_info.task_id == "test-task"
        assert state_info.current_state == TaskState.QUEUED
        assert len(state_info.history) == 0
        assert state_info.retry_count == 0
        assert state_info.error_message is None

    def test_add_transition(self):
        """Test adding state transitions."""
        state_info = TaskStateInfo(
            task_id="test-task",
            current_state=TaskState.QUEUED,
        )

        state_info.add_transition(TaskState.PLANNING, reason="Starting task")

        assert state_info.current_state == TaskState.PLANNING
        assert len(state_info.history) == 1
        assert state_info.history[0].from_state == TaskState.QUEUED
        assert state_info.history[0].to_state == TaskState.PLANNING
        assert state_info.history[0].reason == "Starting task"


class TestTaskStateMachine:
    """Test TaskStateMachine functionality."""

    @pytest.fixture
    def state_machine(self):
        """Create a state machine without persistence."""
        return TaskStateMachine()

    @pytest.fixture
    def state_machine_with_persistence(self, tmp_path):
        """Create a state machine with persistence."""
        persistence = StatePersistence(tmp_path / "state")
        return TaskStateMachine(persistence_handler=persistence)

    def test_register_task(self, state_machine):
        """Test registering a new task."""
        state_info = state_machine.register_task("task-1")

        assert state_info.task_id == "task-1"
        assert state_info.current_state == TaskState.QUEUED
        assert state_machine.has_task("task-1")

    def test_register_duplicate_task(self, state_machine):
        """Test registering a duplicate task raises error."""
        state_machine.register_task("task-1")

        with pytest.raises(ValueError, match="already registered"):
            state_machine.register_task("task-1")

    def test_register_task_with_custom_state(self, state_machine):
        """Test registering task with custom initial state."""
        state_info = state_machine.register_task(
            "task-1",
            initial_state=TaskState.PLANNING,
        )

        assert state_info.current_state == TaskState.PLANNING

    def test_valid_transition(self, state_machine):
        """Test valid state transition."""
        state_machine.register_task("task-1")
        state_info = state_machine.transition("task-1", TaskState.PLANNING)

        assert state_info.current_state == TaskState.PLANNING
        assert len(state_info.history) == 1

    def test_invalid_transition(self, state_machine):
        """Test invalid state transition raises error."""
        state_machine.register_task("task-1")

        with pytest.raises(StateTransitionError, match="Invalid transition"):
            state_machine.transition("task-1", TaskState.COMPLETED)

    def test_transition_nonexistent_task(self, state_machine):
        """Test transitioning nonexistent task raises error."""
        with pytest.raises(ValueError, match="not found"):
            state_machine.transition("task-1", TaskState.PLANNING)

    def test_full_lifecycle(self, state_machine):
        """Test full task lifecycle."""
        state_machine.register_task("task-1")

        # QUEUED -> PLANNING
        state_machine.transition("task-1", TaskState.PLANNING)
        assert state_machine.get_state("task-1").current_state == TaskState.PLANNING

        # PLANNING -> EXECUTING
        state_machine.transition("task-1", TaskState.EXECUTING)
        assert state_machine.get_state("task-1").current_state == TaskState.EXECUTING

        # EXECUTING -> VALIDATING
        state_machine.transition("task-1", TaskState.VALIDATING)
        assert state_machine.get_state("task-1").current_state == TaskState.VALIDATING

        # VALIDATING -> COMPLETED
        state_machine.transition("task-1", TaskState.COMPLETED)
        assert state_machine.get_state("task-1").current_state == TaskState.COMPLETED

        # Verify history
        history = state_machine.get_history("task-1")
        assert len(history) == 4

    def test_retry_on_validation_failure(self, state_machine):
        """Test retry when validation fails."""
        state_machine.register_task("task-1")
        state_machine.transition("task-1", TaskState.PLANNING)
        state_machine.transition("task-1", TaskState.EXECUTING)
        state_machine.transition("task-1", TaskState.VALIDATING)

        # First retry
        state_machine.transition("task-1", TaskState.EXECUTING)
        state_info = state_machine.get_state("task-1")
        assert state_info.retry_count == 1

        # Second retry
        state_machine.transition("task-1", TaskState.VALIDATING)
        state_machine.transition("task-1", TaskState.EXECUTING)
        state_info = state_machine.get_state("task-1")
        assert state_info.retry_count == 2

    def test_fail_task(self, state_machine):
        """Test marking task as failed."""
        state_machine.register_task("task-1")
        state_machine.transition("task-1", TaskState.PLANNING)

        state_info = state_machine.fail_task(
            "task-1",
            "Planning failed due to API error",
        )

        assert state_info.current_state == TaskState.FAILED
        assert state_info.error_message == "Planning failed due to API error"

    def test_get_tasks_by_state(self, state_machine):
        """Test getting tasks by state."""
        state_machine.register_task("task-1")
        state_machine.register_task("task-2")
        state_machine.register_task("task-3")

        state_machine.transition("task-1", TaskState.PLANNING)
        state_machine.transition("task-2", TaskState.PLANNING)

        planning_tasks = state_machine.get_tasks_by_state(TaskState.PLANNING)
        assert len(planning_tasks) == 2

        queued_tasks = state_machine.get_tasks_by_state(TaskState.QUEUED)
        assert len(queued_tasks) == 1

    def test_is_terminal(self, state_machine):
        """Test checking if task is in terminal state."""
        state_machine.register_task("task-1")
        assert not state_machine.is_terminal("task-1")

        state_machine.fail_task("task-1", "Error")
        assert state_machine.is_terminal("task-1")

    def test_can_transition_to(self, state_machine):
        """Test checking if transition is possible."""
        state_machine.register_task("task-1")

        assert state_machine.can_transition_to("task-1", TaskState.PLANNING)
        assert not state_machine.can_transition_to("task-1", TaskState.COMPLETED)

    def test_state_listeners(self, state_machine):
        """Test state transition listeners."""
        transitions = []

        def listener(task_id, from_state, to_state):
            transitions.append((task_id, from_state, to_state))

        state_machine.add_listener(listener)
        state_machine.register_task("task-1")
        state_machine.transition("task-1", TaskState.PLANNING)

        assert len(transitions) == 1
        assert transitions[0] == ("task-1", TaskState.QUEUED, TaskState.PLANNING)

        # Remove listener
        state_machine.remove_listener(listener)
        state_machine.transition("task-1", TaskState.EXECUTING)
        assert len(transitions) == 1  # No new transitions recorded

    def test_persistence_integration(self, state_machine_with_persistence):
        """Test state machine with persistence."""
        state_machine = state_machine_with_persistence

        # Register and transition task
        state_machine.register_task("task-1")
        state_machine.transition("task-1", TaskState.PLANNING)

        # Create new state machine with same persistence
        persistence = state_machine._persistence
        new_state_machine = TaskStateMachine(persistence_handler=persistence)

        # Verify state was loaded
        assert new_state_machine.has_task("task-1")
        state_info = new_state_machine.get_state("task-1")
        assert state_info.current_state == TaskState.PLANNING


class TestStatePersistence:
    """Test state persistence functionality."""

    @pytest.fixture
    def persistence(self, tmp_path):
        """Create state persistence handler."""
        return StatePersistence(tmp_path / "state")

    def test_save_and_load_state(self, persistence):
        """Test saving and loading state."""
        state_info = TaskStateInfo(
            task_id="test-task",
            current_state=TaskState.EXECUTING,
        )
        state_info.add_transition(TaskState.PLANNING)
        state_info.add_transition(TaskState.EXECUTING)

        # Save
        persistence.save_state(state_info)

        # Load
        loaded_state = persistence.load_state("test-task")
        assert loaded_state is not None
        assert loaded_state.task_id == "test-task"
        assert loaded_state.current_state == TaskState.EXECUTING
        assert len(loaded_state.history) == 2

    def test_load_nonexistent_state(self, persistence):
        """Test loading nonexistent state returns None."""
        loaded_state = persistence.load_state("nonexistent")
        assert loaded_state is None

    def test_load_all_states(self, persistence):
        """Test loading all states."""
        # Save multiple states
        for i in range(3):
            state_info = TaskStateInfo(
                task_id=f"task-{i}",
                current_state=TaskState.QUEUED,
            )
            persistence.save_state(state_info)

        # Load all
        all_states = persistence.load_all_states()
        assert len(all_states) == 3
        assert "task-0" in all_states
        assert "task-1" in all_states
        assert "task-2" in all_states

    def test_delete_state(self, persistence):
        """Test deleting state."""
        state_info = TaskStateInfo(
            task_id="test-task",
            current_state=TaskState.QUEUED,
        )
        persistence.save_state(state_info)

        # Delete
        assert persistence.delete_state("test-task")
        assert persistence.load_state("test-task") is None

        # Delete nonexistent
        assert not persistence.delete_state("nonexistent")

    def test_list_task_ids(self, persistence):
        """Test listing task IDs."""
        # Save states
        for i in range(3):
            state_info = TaskStateInfo(
                task_id=f"task-{i}",
                current_state=TaskState.QUEUED,
            )
            persistence.save_state(state_info)

        task_ids = persistence.list_task_ids()
        assert len(task_ids) == 3
        assert "task-0" in task_ids
        assert "task-1" in task_ids
        assert "task-2" in task_ids

    def test_clear_all_states(self, persistence):
        """Test clearing all states."""
        # Save states
        for i in range(3):
            state_info = TaskStateInfo(
                task_id=f"task-{i}",
                current_state=TaskState.QUEUED,
            )
            persistence.save_state(state_info)

        # Clear
        count = persistence.clear_all_states()
        assert count == 3

        # Verify cleared
        assert len(persistence.list_task_ids()) == 0

    def test_state_file_path(self, persistence, tmp_path):
        """Test getting state file path."""
        path = persistence.get_state_file_path("test-task")
        assert path == tmp_path / "state" / "test-task.json"

    def test_atomic_write(self, persistence):
        """Test that writes are atomic."""
        state_info = TaskStateInfo(
            task_id="test-task",
            current_state=TaskState.QUEUED,
        )

        # Save initial state
        persistence.save_state(state_info)

        # Modify and save again
        state_info.add_transition(TaskState.PLANNING)
        persistence.save_state(state_info)

        # Load should have the latest state
        loaded_state = persistence.load_state("test-task")
        assert loaded_state.current_state == TaskState.PLANNING

    def test_state_dir_creation(self, tmp_path):
        """Test state directory is created if it doesn't exist."""
        state_dir = tmp_path / "nonexistent" / "state"
        persistence = StatePersistence(state_dir)

        assert state_dir.exists()
        assert state_dir.is_dir()
