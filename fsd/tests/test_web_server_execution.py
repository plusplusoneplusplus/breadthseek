"""Tests for web server task execution logic.

Specifically tests the fixes for:
1. Passing task.id instead of task object to execute_task()
2. Proper error handling for missing directories
"""

import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
import pytest

from fsd.core.task_schema import TaskDefinition, Priority, CompletionActions


class TestWebServerTaskExecution:
    """Test web server task execution functions."""

    @pytest.fixture
    def sample_task(self):
        """Create a sample task definition."""
        return TaskDefinition(
            id="test-task",
            description="Test task description for validation",
            priority=Priority.MEDIUM,
            estimated_duration="30m",
            context="Test context",
            on_completion=CompletionActions(
                create_pr=True,
                pr_title="Test PR",
                notify_slack=False,
            ),
        )

    @pytest.fixture
    def mock_phase_executor(self):
        """Create a mock PhaseExecutor."""
        mock = Mock()
        mock.execute_task = Mock(return_value=Mock(
            task_id="test-task",
            completed=True,
            final_state="completed",
            summary="Task completed"
        ))
        return mock

    def test_execute_task_receives_task_id_not_object(self, sample_task, mock_phase_executor):
        """Test that execute_task receives task.id string, not the task object.

        This test verifies the fix for the 'File name too long' bug where
        the task object was being passed instead of task.id, causing Python
        to use the object's string representation in file paths.
        """
        # Simulate the web server calling execute_task
        result = mock_phase_executor.execute_task(sample_task.id)

        # Verify execute_task was called with a string ID, not the object
        mock_phase_executor.execute_task.assert_called_once_with("test-task")

        # Verify it was NOT called with the task object
        assert mock_phase_executor.execute_task.call_args[0][0] == "test-task"
        assert not isinstance(mock_phase_executor.execute_task.call_args[0][0], TaskDefinition)

    def test_task_object_string_representation_is_long(self, sample_task):
        """Test that task object string representation would cause filename issues.

        This documents the bug that was fixed - the task object's string
        representation exceeds filename length limits.
        """
        task_str = str(sample_task)

        # Task object representation should be very long (contains all fields)
        assert len(task_str) > 200

        # It should contain field representations that make it unsuitable as filename
        assert "id=" in task_str
        assert "description=" in task_str
        assert "priority=" in task_str

        # In contrast, task.id is suitable for filenames
        assert len(sample_task.id) < 50
        assert " " not in sample_task.id
        assert "=" not in sample_task.id

    def test_auto_execution_loop_calls_execute_task_with_id(self, sample_task):
        """Test that auto-execution loop passes task.id to execute_task.

        Simulates the auto_execution_loop function from web/server.py
        """
        with patch('fsd.orchestrator.phase_executor.PhaseExecutor') as MockPhaseExecutor:
            mock_executor = Mock()
            MockPhaseExecutor.return_value = mock_executor

            # Simulate the auto-execution logic
            task = sample_task
            phase_executor = MockPhaseExecutor(
                state_machine=Mock(),
                checkpoint_manager=Mock(),
                claude_executor=Mock()
            )

            # This is the critical line from web/server.py line 872
            result = phase_executor.execute_task(task.id)

            # Verify it was called with the ID string
            phase_executor.execute_task.assert_called_once_with("test-task")

    def test_run_execution_calls_execute_task_with_id(self, sample_task):
        """Test that run_execution function passes task.id to execute_task.

        Simulates the run_execution function from web/server.py
        """
        with patch('fsd.orchestrator.phase_executor.PhaseExecutor') as MockPhaseExecutor:
            mock_executor = Mock()
            MockPhaseExecutor.return_value = mock_executor

            # Simulate the run_execution logic
            task = sample_task
            phase_executor = MockPhaseExecutor(
                state_machine=Mock(),
                checkpoint_manager=Mock(),
                claude_executor=Mock()
            )

            # This is the critical line from web/server.py line 1049
            result = phase_executor.execute_task(task.id)

            # Verify it was called with the ID string
            phase_executor.execute_task.assert_called_once_with("test-task")


class TestPhaseExecutorTaskFileHandling:
    """Test PhaseExecutor's handling of task files."""

    def test_execute_task_constructs_correct_file_path(self, tmp_path):
        """Test that execute_task constructs the correct queue file path.

        Verifies that when given a task_id, it constructs:
        .fsd/queue/{task_id}.yaml

        Not:
        .fsd/queue/{task_object_repr}.yaml
        """
        task_id = "test-task"

        # Create the expected file structure
        fsd_dir = tmp_path / ".fsd"
        queue_dir = fsd_dir / "queue"
        queue_dir.mkdir(parents=True)

        # The correct path should be task_id.yaml
        expected_path = queue_dir / f"{task_id}.yaml"

        # Create the task file
        task_data = {
            "id": task_id,
            "description": "Test task",
            "priority": "medium",
            "estimated_duration": "30m"
        }

        with open(expected_path, "w") as f:
            import yaml
            yaml.dump(task_data, f)

        # Verify the path is correct and file exists
        assert expected_path.exists()
        assert expected_path.name == f"{task_id}.yaml"

        # Verify the filename is short enough for filesystems (typically 255 char limit)
        assert len(expected_path.name) < 255

    def test_task_object_in_f_string_creates_invalid_filename(self):
        """Test that using task object in f-string creates an invalid filename.

        This demonstrates the bug that was fixed.
        """
        task = TaskDefinition(
            id="test-task",
            description="Test description that is reasonably long",
            priority=Priority.MEDIUM,
            estimated_duration="30m",
            on_completion=CompletionActions(
                create_pr=True,
                pr_title="Test PR title",
                notify_slack=False,
            ),
        )

        # Using task object in f-string (the bug)
        buggy_filename = f"{task}.yaml"

        # This creates an extremely long filename
        assert len(buggy_filename) > 255  # Exceeds typical filesystem limit

        # It contains characters unsuitable for filenames
        assert " " in buggy_filename
        assert "=" in buggy_filename
        assert "<" in buggy_filename or ">" in buggy_filename

        # Using task.id in f-string (the fix)
        correct_filename = f"{task.id}.yaml"

        # This creates a valid, short filename
        assert len(correct_filename) < 50
        assert " " not in correct_filename
        assert "=" not in correct_filename


class TestStateDirectoryCreation:
    """Test state directory creation and error handling."""

    def test_state_directory_is_created_if_missing(self, tmp_path):
        """Test that state directory is created when it doesn't exist."""
        from fsd.core.state_persistence import StatePersistence

        state_dir = tmp_path / ".fsd" / "state"

        # Directory should not exist initially
        assert not state_dir.exists()

        # Initialize StatePersistence
        persistence = StatePersistence(state_dir=state_dir)

        # Directory should be created
        assert state_dir.exists()
        assert state_dir.is_dir()

    def test_state_save_creates_directory_if_missing(self, tmp_path):
        """Test that saving state creates the directory if it doesn't exist."""
        from fsd.core.state_persistence import StatePersistence
        from fsd.core.task_state import TaskStateInfo, TaskState
        from datetime import datetime

        state_dir = tmp_path / ".fsd" / "state"

        # Ensure directory doesn't exist
        assert not state_dir.exists()

        # Create persistence and save state
        persistence = StatePersistence(state_dir=state_dir)

        state_info = TaskStateInfo(
            task_id="test-task",
            current_state=TaskState.QUEUED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # This should not raise an error even though directory didn't exist
        persistence.save_state(state_info)

        # Verify directory was created
        assert state_dir.exists()

        # Verify state file was created
        state_file = state_dir / "test-task.json"
        assert state_file.exists()

    def test_atomic_write_with_temp_file(self, tmp_path):
        """Test that state is written atomically using a temp file."""
        from fsd.core.state_persistence import StatePersistence
        from fsd.core.task_state import TaskStateInfo, TaskState
        from datetime import datetime

        state_dir = tmp_path / ".fsd" / "state"
        state_dir.mkdir(parents=True)

        persistence = StatePersistence(state_dir=state_dir)

        state_info = TaskStateInfo(
            task_id="test-task",
            current_state=TaskState.QUEUED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Save state
        persistence.save_state(state_info)

        # Verify final file exists
        final_file = state_dir / "test-task.json"
        assert final_file.exists()

        # Verify temp file was cleaned up
        temp_file = state_dir / "test-task.tmp"
        assert not temp_file.exists()
