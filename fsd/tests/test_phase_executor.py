"""Tests for phase executor orchestration.

Tests the orchestration logic that coordinates task execution through
planning, execution, validation, and recovery phases.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, MagicMock, patch, call

import pytest

from fsd.core.exceptions import ClaudeExecutionError, ClaudeTimeoutError
from fsd.core.task_state import TaskState
from fsd.orchestrator.phase_executor import (
    PhaseExecutor,
    TaskExecutionResult,
)
from fsd.orchestrator.retry_strategy import RetryDecision


@pytest.fixture
def mock_state_machine():
    """Mock state machine."""
    mock = Mock()
    mock.has_task.return_value = False
    mock.transition.return_value = None
    mock.fail_task.return_value = None
    return mock


@pytest.fixture
def mock_checkpoint_manager():
    """Mock checkpoint manager."""
    mock = Mock()
    mock.mark_task_start.return_value = None
    mock.create_checkpoint.return_value = None
    return mock


@pytest.fixture
def mock_claude_executor():
    """Mock Claude executor."""
    mock = Mock()

    # Default successful result
    result = Mock()
    result.success = True
    result.stdout = '{"status": "ok"}'
    result.stderr = ""
    result.exit_code = 0
    result.duration_seconds = 1.0
    result.error_message = None
    result.parse_json.return_value = {"status": "ok"}

    mock.execute.return_value = result
    return mock


@pytest.fixture
def mock_plan_storage(tmp_path):
    """Mock plan storage."""
    mock = Mock()

    # Sample plan
    plan = {
        "task_id": "test-task",
        "analysis": "Simple task",
        "complexity": "low",
        "estimated_total_time": "1h",
        "steps": [
            {
                "step_number": 1,
                "description": "Implement feature",
                "estimated_duration": "30m",
                "files_to_modify": ["main.py"],
                "validation": "Run tests",
                "checkpoint": True,
            }
        ],
        "dependencies": [],
        "risks": [],
        "validation_strategy": "Run test suite",
    }

    mock.save_plan_dict.return_value = tmp_path / "plan.json"
    mock.load_plan_dict.return_value = plan
    mock.plan_exists.return_value = True

    return mock


@pytest.fixture
def mock_retry_strategy():
    """Mock retry strategy."""
    mock = Mock()
    mock.config.max_retries = 3
    mock.should_retry.return_value = RetryDecision.COMPLETE
    mock.get_retry_message.return_value = "Task completed"
    return mock


@pytest.fixture
def phase_executor(
    mock_state_machine,
    mock_checkpoint_manager,
    mock_claude_executor,
    mock_plan_storage,
    mock_retry_strategy,
):
    """Create phase executor with mocked dependencies."""
    return PhaseExecutor(
        state_machine=mock_state_machine,
        checkpoint_manager=mock_checkpoint_manager,
        claude_executor=mock_claude_executor,
        plan_storage=mock_plan_storage,
        retry_strategy=mock_retry_strategy,
    )


@pytest.fixture
def sample_task_file(tmp_path):
    """Create a sample task file."""
    task_file = tmp_path / "test-task.yaml"
    task_content = """
id: test-task
description: Test task for orchestration
priority: medium
estimated_duration: 2h
success_criteria: |
  - Feature implemented
  - Tests pass
context: |
  Simple test task
focus_files:
  - main.py
  - tests/test_main.py
"""
    task_file.write_text(task_content)
    return task_file


class TestPhaseExecutorInit:
    """Tests for PhaseExecutor initialization."""

    def test_init_with_all_dependencies(
        self,
        mock_state_machine,
        mock_checkpoint_manager,
        mock_claude_executor,
        mock_plan_storage,
        mock_retry_strategy,
    ):
        """Test initialization with all dependencies provided."""
        executor = PhaseExecutor(
            state_machine=mock_state_machine,
            checkpoint_manager=mock_checkpoint_manager,
            claude_executor=mock_claude_executor,
            plan_storage=mock_plan_storage,
            retry_strategy=mock_retry_strategy,
        )

        assert executor.state_machine == mock_state_machine
        assert executor.checkpoint_manager == mock_checkpoint_manager
        assert executor.claude_executor == mock_claude_executor
        assert executor.plan_storage == mock_plan_storage
        assert executor.retry_strategy == mock_retry_strategy

    def test_init_creates_defaults(
        self, mock_state_machine, mock_checkpoint_manager, mock_claude_executor
    ):
        """Test initialization creates default plan storage and retry strategy."""
        executor = PhaseExecutor(
            state_machine=mock_state_machine,
            checkpoint_manager=mock_checkpoint_manager,
            claude_executor=mock_claude_executor,
        )

        assert executor.plan_storage is not None
        assert executor.retry_strategy is not None


class TestPlanningPhase:
    """Tests for planning phase execution."""

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_planning_phase_success(
        self, mock_load_prompt, phase_executor, complete_task
    ):
        """Test successful planning phase execution."""
        # Setup
        mock_load_prompt.return_value = "Planning prompt"

        plan_data = {
            "task_id": "test-task",
            "analysis": "Task analysis",
            "complexity": "medium",
            "steps": [],
        }

        phase_executor.claude_executor.execute.return_value.parse_json.return_value = (
            plan_data
        )

        # Execute
        phase_executor._execute_planning_phase(complete_task)

        # Verify state transition
        phase_executor.state_machine.transition.assert_called_with(
            complete_task.id, TaskState.PLANNING
        )

        # Verify checkpoint created
        phase_executor.checkpoint_manager.create_checkpoint.assert_called()

        # Verify Claude executed
        phase_executor.claude_executor.execute.assert_called_once()
        call_kwargs = phase_executor.claude_executor.execute.call_args[1]
        assert call_kwargs["prompt"] == "Planning prompt"
        assert call_kwargs["timeout"] == 300
        assert call_kwargs["task_id"] == complete_task.id

        # Verify plan saved
        phase_executor.plan_storage.save_plan_dict.assert_called_once_with(
            complete_task.id, plan_data
        )

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_planning_phase_failure(
        self, mock_load_prompt, phase_executor, complete_task
    ):
        """Test planning phase with execution failure."""
        mock_load_prompt.return_value = "Planning prompt"

        # Simulate failure
        phase_executor.claude_executor.execute.return_value.success = False
        phase_executor.claude_executor.execute.return_value.error_message = (
            "Execution failed"
        )

        # Execute and verify exception
        with pytest.raises(ClaudeExecutionError, match="Planning phase failed"):
            phase_executor._execute_planning_phase(complete_task)


class TestExecutionPhase:
    """Tests for execution phase."""

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_execution_phase_single_step(
        self, mock_load_prompt, phase_executor, complete_task
    ):
        """Test execution phase with single step."""
        mock_load_prompt.return_value = "Execution prompt"

        # Execute
        phase_executor._execute_execution_phase(complete_task)

        # Verify state transition
        phase_executor.state_machine.transition.assert_called_with(
            complete_task.id, TaskState.EXECUTING
        )

        # Verify plan loaded
        phase_executor.plan_storage.load_plan_dict.assert_called_once_with(
            complete_task.id
        )

        # Verify Claude executed once for the single step
        assert phase_executor.claude_executor.execute.call_count == 1

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_execution_phase_multiple_steps(
        self, mock_load_prompt, phase_executor, complete_task, mock_plan_storage
    ):
        """Test execution phase with multiple steps."""
        # Plan with 3 steps
        plan = {
            "steps": [
                {"step_number": 1, "description": "Step 1", "checkpoint": False},
                {"step_number": 2, "description": "Step 2", "checkpoint": True},
                {"step_number": 3, "description": "Step 3", "checkpoint": False},
            ]
        }
        mock_plan_storage.load_plan_dict.return_value = plan

        mock_load_prompt.return_value = "Execution prompt"

        # Execute
        phase_executor._execute_execution_phase(complete_task)

        # Verify Claude executed 3 times
        assert phase_executor.claude_executor.execute.call_count == 3

        # Verify checkpoint created only for step 2
        checkpoint_calls = [
            call
            for call in phase_executor.checkpoint_manager.create_checkpoint.call_args_list
            if "step_number" in str(call)
        ]
        assert len(checkpoint_calls) == 1

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_execution_phase_no_plan(
        self, mock_load_prompt, phase_executor, complete_task, mock_plan_storage
    ):
        """Test execution phase when no plan exists."""
        mock_plan_storage.load_plan_dict.return_value = None

        with pytest.raises(ClaudeExecutionError, match="No plan found"):
            phase_executor._execute_execution_phase(complete_task)

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_execution_phase_step_failure(
        self, mock_load_prompt, phase_executor, complete_task
    ):
        """Test execution phase when a step fails."""
        mock_load_prompt.return_value = "Execution prompt"

        # Simulate step failure
        phase_executor.claude_executor.execute.return_value.success = False
        phase_executor.claude_executor.execute.return_value.error_message = "Step failed"

        with pytest.raises(ClaudeExecutionError, match="Execution step 1 failed"):
            phase_executor._execute_execution_phase(complete_task)


class TestValidationPhase:
    """Tests for validation phase."""

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_validation_phase_success(
        self, mock_load_prompt, phase_executor, complete_task
    ):
        """Test successful validation."""
        mock_load_prompt.return_value = "Validation prompt"

        validation_result = {
            "validation_passed": True,
            "results": {"tests": {"passed": True}},
        }

        phase_executor.claude_executor.execute.return_value.parse_json.return_value = (
            validation_result
        )

        # Execute
        passed, result = phase_executor._execute_validation_phase(complete_task)

        # Verify
        assert passed is True
        assert result == validation_result

        # Verify state transition
        phase_executor.state_machine.transition.assert_called_with(
            complete_task.id, TaskState.VALIDATING
        )

        # Verify checkpoints created (pre and post validation)
        assert phase_executor.checkpoint_manager.create_checkpoint.call_count == 2

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_validation_phase_failure(
        self, mock_load_prompt, phase_executor, complete_task
    ):
        """Test validation failure."""
        mock_load_prompt.return_value = "Validation prompt"

        validation_result = {
            "validation_passed": False,
            "results": {"tests": {"passed": False, "failed_tests": 2}},
            "failed_checks": ["2 tests failing"],
        }

        phase_executor.claude_executor.execute.return_value.parse_json.return_value = (
            validation_result
        )

        # Execute
        passed, result = phase_executor._execute_validation_phase(complete_task)

        # Verify
        assert passed is False
        assert result["validation_passed"] is False

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_validation_phase_execution_error(
        self, mock_load_prompt, phase_executor, complete_task
    ):
        """Test validation phase execution error."""
        mock_load_prompt.return_value = "Validation prompt"

        phase_executor.claude_executor.execute.return_value.success = False
        phase_executor.claude_executor.execute.return_value.error_message = (
            "Validation execution failed"
        )

        with pytest.raises(ClaudeExecutionError, match="Validation phase failed"):
            phase_executor._execute_validation_phase(complete_task)


class TestRecoveryPhase:
    """Tests for recovery phase."""

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_recovery_phase_success(
        self, mock_load_prompt, phase_executor, complete_task
    ):
        """Test recovery phase execution."""
        mock_load_prompt.return_value = "Recovery prompt"

        validation_result = {
            "results": {
                "tests": {"passed": False},
                "quality": {
                    "type_check": {"passed": False},
                    "linting": {"passed": True},
                },
            },
            "summary": "Tests and type checking failed",
        }

        # Execute
        phase_executor._execute_recovery_phase(complete_task, validation_result, 1)

        # Verify checkpoint created
        phase_executor.checkpoint_manager.create_checkpoint.assert_called()

        # Verify Claude executed
        phase_executor.claude_executor.execute.assert_called_once()

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_recovery_phase_extracts_failed_checks(
        self, mock_load_prompt, phase_executor, complete_task
    ):
        """Test recovery phase extracts failed checks correctly."""
        mock_load_prompt.return_value = "Recovery prompt"

        validation_result = {
            "results": {
                "tests": {"passed": False},
                "quality": {
                    "type_check": {"passed": False},
                    "linting": {"passed": False},
                },
            }
        }

        phase_executor._execute_recovery_phase(complete_task, validation_result, 1)

        # Verify prompt includes failed checks
        call_kwargs = mock_load_prompt.call_args[1]
        failed_checks = call_kwargs["failed_checks_list"]
        assert "Tests failing" in failed_checks
        assert "Type checking errors" in failed_checks
        assert "Linting errors" in failed_checks


class TestExecuteTask:
    """Tests for complete task execution."""

    @patch("fsd.orchestrator.phase_executor.load_task_from_yaml")
    def test_execute_task_success_first_try(
        self, mock_load_task, phase_executor, complete_task, sample_task_file
    ):
        """Test task completion on first validation attempt."""
        mock_load_task.return_value = complete_task

        # Setup validation to pass immediately
        validation_result = {"validation_passed": True}
        phase_executor.claude_executor.execute.return_value.parse_json.return_value = (
            validation_result
        )

        phase_executor.retry_strategy.should_retry.return_value = RetryDecision.COMPLETE

        # Execute
        result = phase_executor.execute_task("test-task", sample_task_file)

        # Verify
        assert result.completed is True
        assert result.task_id == "test-task"
        assert result.final_state == TaskState.COMPLETED
        assert result.retry_count == 0
        assert "successfully" in result.summary.lower()

        # Verify task marked as completed
        phase_executor.state_machine.transition.assert_any_call(
            "test-task", TaskState.COMPLETED
        )

    @patch("fsd.orchestrator.phase_executor.load_task_from_yaml")
    def test_execute_task_with_retries(
        self, mock_load_task, phase_executor, complete_task, sample_task_file
    ):
        """Test task completion after retries."""
        mock_load_task.return_value = complete_task

        # Setup validation to fail twice, then pass
        call_count = 0

        def validation_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return {"validation_passed": False}
            return {"validation_passed": True}

        phase_executor.claude_executor.execute.return_value.parse_json.side_effect = (
            lambda: validation_side_effect()
        )

        # Setup retry strategy
        retry_decisions = [RetryDecision.RETRY, RetryDecision.RETRY, RetryDecision.COMPLETE]
        phase_executor.retry_strategy.should_retry.side_effect = retry_decisions

        # Execute
        result = phase_executor.execute_task("test-task", sample_task_file)

        # Verify
        assert result.completed is True
        assert result.retry_count == 2
        assert "after 2 retries" in result.summary.lower()

    @patch("fsd.orchestrator.phase_executor.load_task_from_yaml")
    def test_execute_task_max_retries_exhausted(
        self, mock_load_task, phase_executor, complete_task, sample_task_file
    ):
        """Test task failure after max retries."""
        mock_load_task.return_value = complete_task

        # Setup validation to always fail
        validation_result = {"validation_passed": False}
        phase_executor.claude_executor.execute.return_value.parse_json.return_value = (
            validation_result
        )

        # Setup retry strategy to exhaust retries
        phase_executor.retry_strategy.should_retry.side_effect = [
            RetryDecision.RETRY,
            RetryDecision.RETRY,
            RetryDecision.RETRY,
            RetryDecision.FAIL,
        ]
        phase_executor.retry_strategy.get_retry_message.return_value = (
            "Task failed after 3 retries"
        )

        # Execute
        result = phase_executor.execute_task("test-task", sample_task_file)

        # Verify
        assert result.completed is False
        assert result.final_state == TaskState.FAILED
        assert result.retry_count == 3
        assert "failed" in result.summary.lower()

        # Verify task marked as failed
        phase_executor.state_machine.fail_task.assert_called()

    @patch("fsd.orchestrator.phase_executor.load_task_from_yaml")
    def test_execute_task_unexpected_exception(
        self, mock_load_task, phase_executor, complete_task, sample_task_file
    ):
        """Test handling of unexpected exceptions."""
        mock_load_task.return_value = complete_task

        # Simulate unexpected exception during planning
        phase_executor.claude_executor.execute.side_effect = RuntimeError(
            "Unexpected error"
        )

        # Execute
        result = phase_executor.execute_task("test-task", sample_task_file)

        # Verify
        assert result.completed is False
        assert result.final_state == TaskState.FAILED
        assert "Unexpected error" in result.error_message

        # Verify task marked as failed
        phase_executor.state_machine.fail_task.assert_called()

    @patch("fsd.orchestrator.phase_executor.load_task_from_yaml")
    def test_execute_task_registers_new_task(
        self, mock_load_task, phase_executor, complete_task, sample_task_file
    ):
        """Test that new tasks are registered with state machine."""
        mock_load_task.return_value = complete_task
        phase_executor.state_machine.has_task.return_value = False

        validation_result = {"validation_passed": True}
        phase_executor.claude_executor.execute.return_value.parse_json.return_value = (
            validation_result
        )
        phase_executor.retry_strategy.should_retry.return_value = RetryDecision.COMPLETE

        # Execute
        phase_executor.execute_task("test-task", sample_task_file)

        # Verify task registered
        phase_executor.state_machine.register_task.assert_called_once_with(
            "test-task", initial_state=TaskState.QUEUED
        )

    @patch("fsd.orchestrator.phase_executor.load_task_from_yaml")
    def test_execute_task_skips_registration_if_exists(
        self, mock_load_task, phase_executor, complete_task, sample_task_file
    ):
        """Test that existing tasks are not re-registered."""
        mock_load_task.return_value = complete_task
        phase_executor.state_machine.has_task.return_value = True

        validation_result = {"validation_passed": True}
        phase_executor.claude_executor.execute.return_value.parse_json.return_value = (
            validation_result
        )
        phase_executor.retry_strategy.should_retry.return_value = RetryDecision.COMPLETE

        # Execute
        phase_executor.execute_task("test-task", sample_task_file)

        # Verify task not registered
        phase_executor.state_machine.register_task.assert_not_called()

    @patch("fsd.orchestrator.phase_executor.load_task_from_yaml")
    def test_execute_task_uses_default_path(
        self, mock_load_task, phase_executor, complete_task
    ):
        """Test that default task path is used when not provided."""
        mock_load_task.return_value = complete_task

        validation_result = {"validation_passed": True}
        phase_executor.claude_executor.execute.return_value.parse_json.return_value = (
            validation_result
        )
        phase_executor.retry_strategy.should_retry.return_value = RetryDecision.COMPLETE

        # Execute without task_file
        phase_executor.execute_task("test-task")

        # Verify default path used
        expected_path = Path.cwd() / ".fsd" / "queue" / "test-task.yaml"
        mock_load_task.assert_called_once_with(expected_path)


class TestTaskExecutionResult:
    """Tests for TaskExecutionResult dataclass."""

    def test_result_creation_success(self):
        """Test creating successful result."""
        result = TaskExecutionResult(
            task_id="test-task",
            completed=True,
            final_state=TaskState.COMPLETED,
            summary="Success",
            retry_count=0,
            duration_seconds=120.5,
        )

        assert result.task_id == "test-task"
        assert result.completed is True
        assert result.final_state == TaskState.COMPLETED
        assert result.summary == "Success"
        assert result.error_message is None
        assert result.retry_count == 0
        assert result.duration_seconds == 120.5

    def test_result_creation_failure(self):
        """Test creating failure result."""
        result = TaskExecutionResult(
            task_id="test-task",
            completed=False,
            final_state=TaskState.FAILED,
            summary="Failed",
            error_message="Tests failed",
            retry_count=3,
            duration_seconds=300.0,
        )

        assert result.completed is False
        assert result.final_state == TaskState.FAILED
        assert result.error_message == "Tests failed"
        assert result.retry_count == 3
