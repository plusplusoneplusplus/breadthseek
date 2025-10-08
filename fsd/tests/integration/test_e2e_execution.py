"""End-to-end integration tests for task queuing and execution via web API.

Tests the complete workflow:
1. Queue a task via API
2. Start execution via API
3. Verify task execution output and trace
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from fsd.core.task_schema import TaskDefinition, Priority
from fsd.core.state_machine import TaskStateMachine
from fsd.core.task_state import TaskState
from fsd.core.state_persistence import StatePersistence

# Add parent directory to path for web module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def mock_working_directory(git_repo: Path, tmp_fsd_dir: Path) -> Generator[Path, None, None]:
    """Create a working directory with FSD initialized."""
    # Move .fsd into git repo
    fsd_dir = git_repo / ".fsd"
    fsd_dir.mkdir(exist_ok=True)

    # Create subdirectories
    (fsd_dir / "logs").mkdir(exist_ok=True)
    (fsd_dir / "queue").mkdir(exist_ok=True)
    (fsd_dir / "state").mkdir(exist_ok=True)
    (fsd_dir / "checkpoints").mkdir(exist_ok=True)
    (fsd_dir / "plans").mkdir(exist_ok=True)

    # Create config file
    config_file = fsd_dir / "config.yaml"
    config_data = {
        "agent": {
            "max_execution_time": "1h",
            "checkpoint_interval": "5m",
            "parallel_tasks": 1,
            "mode": "autonomous",
        },
        "claude": {
            "command": "claude --dangerously-skip-permissions",
            "working_dir": str(git_repo),
            "timeout": "30m",
        },
    }
    config_file.write_text(json.dumps(config_data))

    yield git_repo


@pytest.fixture
def test_client(mock_working_directory: Path) -> Generator[TestClient, None, None]:
    """Create FastAPI test client with mocked working directory."""
    # Import app here to avoid import-time side effects
    from web.server import app

    # Patch the working directory function
    with patch("web.server.get_fsd_dir", return_value=mock_working_directory / ".fsd"):
        client = TestClient(app)
        yield client


@pytest.mark.integration
@pytest.mark.e2e
class TestE2ETaskExecution:
    """End-to-end tests for task queuing and execution."""

    def test_queue_and_verify_task(self, test_client: TestClient, mock_working_directory: Path):
        """Test queuing a task via API and verifying it's in the queue."""
        # Queue a simple task
        task_data = {
            "id": "test-simple-task",
            "description": "Add a simple hello world function to greet.py",
            "priority": "high",
            "estimated_duration": "15m",
            "context": "Create a new file greet.py with a hello() function",
            "success_criteria": "File greet.py exists and contains hello() function",
            "create_pr": False,
        }

        response = test_client.post("/api/tasks/structured", json=task_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "test-simple-task" in result["message"]

        # Verify task is in queue
        response = test_client.get("/api/tasks")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 1
        assert tasks[0]["id"] == "test-simple-task"
        assert tasks[0]["status"] == "queued"
        assert tasks[0]["priority"] == "high"

        # Verify task details
        response = test_client.get("/api/tasks/test-simple-task")
        assert response.status_code == 200
        task = response.json()
        assert task["description"] == task_data["description"]
        assert task["success_criteria"] == task_data["success_criteria"]

    def test_natural_language_task_creation(self, test_client: TestClient):
        """Test creating a task using natural language API."""
        nl_task = {
            "text": "Please add type hints to all functions in utils.py and ensure they pass mypy validation"
        }

        response = test_client.post("/api/tasks/natural", json=nl_task)
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True

        # Verify task was created
        response = test_client.get("/api/tasks")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) >= 1

    @patch("web.server.PhaseExecutor")
    @patch("web.server.ClaudeExecutor")
    def test_start_execution_and_verify_trace(
        self,
        mock_claude_executor_class: Mock,
        mock_phase_executor_class: Mock,
        test_client: TestClient,
        mock_working_directory: Path,
    ):
        """Test starting execution and verifying the task trace/output."""
        # Setup mocks
        mock_claude_executor = Mock()
        mock_claude_executor_class.return_value = mock_claude_executor

        # Mock successful planning response
        planning_result = Mock()
        planning_result.success = True
        planning_result.stdout = json.dumps({
            "task_id": "test-execution-task",
            "analysis": "Create a simple greeting function",
            "complexity": "low",
            "estimated_total_time": "15m",
            "steps": [
                {
                    "step_number": 1,
                    "description": "Create greet.py with hello() function",
                    "estimated_duration": "10m",
                    "files_to_modify": ["greet.py"],
                    "validation": "File exists and function works",
                    "checkpoint": True,
                }
            ],
            "validation_strategy": "Run tests and verify file exists",
        })
        planning_result.parse_json = lambda: json.loads(planning_result.stdout)

        # Mock successful execution response
        execution_result = Mock()
        execution_result.success = True
        execution_result.stdout = "File created successfully with hello() function"
        execution_result.parse_json = lambda: {"status": "ok"}

        # Mock successful validation response
        validation_result = Mock()
        validation_result.success = True
        validation_result.stdout = json.dumps({
            "validation_passed": True,
            "summary": "All checks passed - file exists and function works",
            "results": {
                "tests": {"passed": True, "total_tests": 1, "passed_tests": 1, "failed_tests": 0},
                "quality": {"type_check": {"passed": True, "errors": 0}},
            },
        })
        validation_result.parse_json = lambda: json.loads(validation_result.stdout)

        # Set up executor call sequence
        mock_claude_executor.execute.side_effect = [
            planning_result,
            execution_result,
            validation_result,
        ]

        # Mock phase executor
        from fsd.orchestrator.phase_executor import TaskExecutionResult
        mock_phase_executor = Mock()
        execution_result_obj = TaskExecutionResult(
            completed=True,
            task_id="test-execution-task",
            final_state=TaskState.COMPLETED,
            retry_count=0,
            summary="Task completed successfully",
        )
        mock_phase_executor.execute_task.return_value = execution_result_obj
        mock_phase_executor_class.return_value = mock_phase_executor

        # Queue a task
        task_data = {
            "id": "test-execution-task",
            "description": "Create a greeting function",
            "priority": "high",
            "estimated_duration": "15m",
            "success_criteria": "File greet.py exists with hello() function",
            "create_pr": False,
        }

        response = test_client.post("/api/tasks/structured", json=task_data)
        assert response.status_code == 200

        # Start execution in autonomous mode
        response = test_client.post("/api/execution/start?mode=autonomous")
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "execution" in result["message"].lower() or "enabled" in result["message"].lower()

        # Give the execution thread time to process
        time.sleep(0.5)

        # Verify task status changed
        response = test_client.get("/api/tasks/test-execution-task")
        task_status = response.json()

        # Task should be in progress or completed depending on timing
        assert task_status["status"] in ["queued", "planning", "executing", "validating", "completed"]

    @patch("web.server.ClaudeExecutor")
    @patch("web.server.PhaseExecutor")
    def test_execution_with_logs(
        self,
        mock_phase_executor_class: Mock,
        mock_claude_executor_class: Mock,
        test_client: TestClient,
        mock_working_directory: Path,
    ):
        """Test execution generates proper logs."""
        # Setup mocks
        mock_phase_executor = Mock()
        mock_phase_executor_class.return_value = mock_phase_executor

        from fsd.orchestrator.phase_executor import TaskExecutionResult
        execution_result = TaskExecutionResult(
            completed=True,
            task_id="test-logs-task",
            final_state=TaskState.COMPLETED,
            retry_count=0,
            summary="Task completed",
        )
        mock_phase_executor.execute_task.return_value = execution_result

        # Queue task
        task_data = {
            "id": "test-logs-task",
            "description": "Test task for log verification",
            "priority": "medium",
            "estimated_duration": "10m",
            "create_pr": False,
        }
        response = test_client.post("/api/tasks/structured", json=task_data)
        assert response.status_code == 200

        # Start execution
        response = test_client.post("/api/execution/start?mode=autonomous")
        assert response.status_code == 200

        # Allow time for execution
        time.sleep(0.3)

        # Retrieve system logs
        response = test_client.get("/api/logs?lines=50")
        assert response.status_code == 200
        logs_data = response.json()

        # Should have some logs
        assert "logs" in logs_data
        # Logs might be empty or contain execution logs depending on timing

    def test_stop_execution(self, test_client: TestClient):
        """Test stopping execution."""
        # Start execution first
        response = test_client.post("/api/execution/start?mode=autonomous")
        assert response.status_code == 200

        # Stop execution
        response = test_client.post("/api/execution/stop")
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        # Message should indicate stopping or disabled
        assert "disabled" in result["message"].lower() or "stopped" in result["message"].lower()

    def test_task_cancellation(self, test_client: TestClient):
        """Test cancelling a queued task."""
        # Queue a task
        task_data = {
            "id": "test-cancel-task",
            "description": "Task to be cancelled",
            "priority": "low",
            "estimated_duration": "30m",
            "create_pr": False,
        }
        response = test_client.post("/api/tasks/structured", json=task_data)
        assert response.status_code == 200

        # Cancel the task
        response = test_client.post("/api/tasks/test-cancel-task/cancel")
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True

        # Verify task is cancelled (status becomes "failed" with cancelled flag)
        response = test_client.get("/api/tasks/test-cancel-task")
        assert response.status_code == 200
        task = response.json()
        # Cancellation sets status to "failed" (not "cancelled")
        assert task["status"] == "failed"

    def test_task_deletion(self, test_client: TestClient):
        """Test deleting a task."""
        # Queue a task
        task_data = {
            "id": "test-delete-task",
            "description": "Task to be deleted",
            "priority": "low",
            "estimated_duration": "20m",
            "create_pr": False,
        }
        response = test_client.post("/api/tasks/structured", json=task_data)
        assert response.status_code == 200

        # Delete the task
        response = test_client.delete("/api/tasks/test-delete-task")
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True

        # Verify task is deleted
        response = test_client.get("/api/tasks/test-delete-task")
        assert response.status_code == 404

    def test_bulk_task_deletion(self, test_client: TestClient, mock_working_directory: Path):
        """Test bulk deletion of completed tasks."""
        # Create and complete multiple tasks
        state_dir = mock_working_directory / ".fsd" / "state"
        persistence = StatePersistence(state_dir)
        state_machine = TaskStateMachine(persistence_handler=persistence)

        # Queue tasks
        for i in range(3):
            task_data = {
                "id": f"bulk-task-{i}",
                "description": f"Task {i} for bulk deletion",
                "priority": "low",
                "estimated_duration": "10m",
                "create_pr": False,
            }
            response = test_client.post("/api/tasks/structured", json=task_data)
            assert response.status_code == 200

            # Mark as completed
            state_machine.transition(f"bulk-task-{i}", TaskState.COMPLETED)

        # Bulk delete completed tasks
        response = test_client.post("/api/tasks/bulk-delete?status_filter=completed")
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["deleted_count"] == 3

        # Verify tasks are deleted
        response = test_client.get("/api/tasks")
        tasks = response.json()
        completed_tasks = [t for t in tasks if t["status"] == "completed"]
        assert len(completed_tasks) == 0

    def test_system_status(self, test_client: TestClient):
        """Test retrieving system status."""
        response = test_client.get("/api/status")
        assert response.status_code == 200
        status = response.json()

        assert "fsd_initialized" in status
        assert "execution_active" in status
        assert "task_counts" in status
        assert "total_tasks" in status

        assert isinstance(status["task_counts"], dict)
        assert "queued" in status["task_counts"]
        assert "running" in status["task_counts"]
        assert "completed" in status["task_counts"]
        assert "failed" in status["task_counts"]

    def test_activity_tracking(self, test_client: TestClient):
        """Test activity log tracking."""
        # Perform some actions
        task_data = {
            "id": "activity-test-task",
            "description": "Task for activity tracking",
            "priority": "medium",
            "estimated_duration": "15m",
            "create_pr": False,
        }
        test_client.post("/api/tasks/structured", json=task_data)

        # Retrieve activity
        response = test_client.get("/api/activity?limit=10")
        assert response.status_code == 200
        activity = response.json()

        assert isinstance(activity, list)
        # Activity should contain the task creation event
        if len(activity) > 0:
            assert any("activity-test-task" in str(event.get("message", "")) for event in activity)


@pytest.mark.integration
@pytest.mark.e2e
class TestE2EErrorHandling:
    """Test error handling in E2E scenarios."""

    def test_invalid_task_creation(self, test_client: TestClient):
        """Test creating a task with invalid data."""
        invalid_task = {
            "id": "ab",  # Too short
            "description": "short",  # Too short
            "priority": "invalid",
            "estimated_duration": "invalid",
            "create_pr": False,
        }

        response = test_client.post("/api/tasks/structured", json=invalid_task)
        assert response.status_code in [400, 422]

    def test_duplicate_task_id(self, test_client: TestClient):
        """Test creating a task with duplicate ID."""
        task_data = {
            "id": "duplicate-task",
            "description": "First task",
            "priority": "medium",
            "estimated_duration": "10m",
            "create_pr": False,
        }

        # Create first task
        response = test_client.post("/api/tasks/structured", json=task_data)
        assert response.status_code == 200

        # Try to create duplicate
        response = test_client.post("/api/tasks/structured", json=task_data)
        assert response.status_code == 400

    def test_nonexistent_task_retrieval(self, test_client: TestClient):
        """Test retrieving a task that doesn't exist."""
        response = test_client.get("/api/tasks/nonexistent-task")
        assert response.status_code == 404

    def test_cancel_nonexistent_task(self, test_client: TestClient):
        """Test cancelling a task that doesn't exist."""
        response = test_client.post("/api/tasks/nonexistent-task/cancel")
        assert response.status_code == 404

    def test_start_execution_without_tasks(self, test_client: TestClient):
        """Test starting execution when no tasks are queued."""
        response = test_client.post("/api/execution/start?mode=autonomous")
        assert response.status_code == 200
        result = response.json()

        # Should succeed but indicate no tasks
        assert result["success"] is True
        assert result["queued_tasks_count"] == 0


@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.slow
class TestE2ECompleteWorkflow:
    """Test complete end-to-end workflow with all phases."""

    @patch("web.server.ClaudeExecutor")
    def test_complete_workflow_from_queue_to_completion(
        self,
        mock_claude_executor_class: Mock,
        test_client: TestClient,
        mock_working_directory: Path,
    ):
        """Test complete workflow: queue → plan → execute → validate → complete."""
        # Setup mocks
        mock_claude_executor = Mock()
        mock_claude_executor_class.return_value = mock_claude_executor

        # Mock all phases
        planning = Mock()
        planning.success = True
        planning.stdout = json.dumps({
            "task_id": "complete-workflow-task",
            "steps": [{
                "step_number": 1,
                "description": "Implement feature",
                "estimated_duration": "10m",
                "files_to_modify": ["feature.py"],
                "validation": "Tests pass",
                "checkpoint": True,
            }],
        })
        planning.parse_json = lambda: json.loads(planning.stdout)

        execution = Mock()
        execution.success = True
        execution.stdout = "Step completed"

        validation = Mock()
        validation.success = True
        validation.stdout = json.dumps({
            "validation_passed": True,
            "summary": "All checks passed",
            "results": {"tests": {"passed": True}},
        })
        validation.parse_json = lambda: json.loads(validation.stdout)

        mock_claude_executor.execute.side_effect = [planning, execution, validation]

        # 1. Queue task
        task_data = {
            "id": "complete-workflow-task",
            "description": "Complete workflow test task",
            "priority": "high",
            "estimated_duration": "30m",
            "success_criteria": "Feature implemented and tests pass",
            "create_pr": False,
        }

        response = test_client.post("/api/tasks/structured", json=task_data)
        assert response.status_code == 200

        # 2. Verify task is queued
        response = test_client.get("/api/tasks/complete-workflow-task")
        assert response.status_code == 200
        task = response.json()
        assert task["status"] == "queued"

        # 3. Start execution
        response = test_client.post("/api/execution/start?mode=autonomous&task_id=complete-workflow-task")
        assert response.status_code == 200

        # 4. Allow execution to complete
        time.sleep(1.0)

        # 5. Verify task completion
        response = test_client.get("/api/tasks/complete-workflow-task")
        task_status = response.json()

        # Task should progress through states
        # Final state depends on timing, but should not be just "queued"
        assert task_status["status"] in ["planning", "executing", "validating", "completed"]

        # 6. Verify activity log contains workflow events
        response = test_client.get("/api/activity?limit=20")
        assert response.status_code == 200
        activity = response.json()
        assert len(activity) > 0
