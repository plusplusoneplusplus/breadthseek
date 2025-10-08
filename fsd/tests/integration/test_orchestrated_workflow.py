"""Integration tests for orchestrated task workflow.

Tests the complete workflow from task submission through planning,
execution, validation, and potential recovery.
"""

import json
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, patch

import pytest

from fsd.core.checkpoint_manager import CheckpointManager, CheckpointType
from fsd.core.state_machine import TaskStateMachine
from fsd.core.task_state import TaskState
from fsd.orchestrator.phase_executor import PhaseExecutor, TaskExecutionResult
from fsd.orchestrator.plan_storage import PlanStorage
from fsd.orchestrator.retry_strategy import RetryConfig, RetryStrategy


@pytest.fixture
def orchestrated_workspace(tmp_path, git_repo):
    """Create workspace for orchestrated workflow tests."""
    # Create FSD directory structure
    fsd_dir = git_repo / ".fsd"
    fsd_dir.mkdir(exist_ok=True)

    (fsd_dir / "state").mkdir(exist_ok=True)
    (fsd_dir / "plans").mkdir(exist_ok=True)
    (fsd_dir / "queue").mkdir(exist_ok=True)

    # Create sample task file
    task_file = fsd_dir / "queue" / "add-feature.yaml"
    task_content = """
id: add-feature
description: Add user authentication feature
priority: high
estimated_duration: 3h
success_criteria: |
  - Auth module implemented
  - Tests pass
  - Type checking passes
context: |
  Implement JWT-based authentication
focus_files:
  - src/auth.py
  - tests/test_auth.py
"""
    task_file.write_text(task_content)

    return git_repo


@pytest.fixture
def mock_claude_responses():
    """Create realistic mock Claude responses for each phase."""

    def planning_response():
        """Successful planning response."""
        result = Mock()
        result.success = True
        result.stdout = json.dumps(
            {
                "task_id": "add-feature",
                "analysis": "Need to implement JWT authentication with token generation and validation",
                "complexity": "medium",
                "estimated_total_time": "3h",
                "steps": [
                    {
                        "step_number": 1,
                        "description": "Create authentication module with JWT support",
                        "estimated_duration": "1h",
                        "files_to_modify": ["src/auth.py"],
                        "validation": "Module imports without errors",
                        "checkpoint": True,
                    },
                    {
                        "step_number": 2,
                        "description": "Add authentication tests",
                        "estimated_duration": "1h",
                        "files_to_modify": ["tests/test_auth.py"],
                        "validation": "Tests run and pass",
                        "checkpoint": True,
                    },
                    {
                        "step_number": 3,
                        "description": "Update documentation",
                        "estimated_duration": "30m",
                        "files_to_modify": ["docs/auth.md"],
                        "validation": "Documentation complete",
                        "checkpoint": False,
                    },
                ],
                "dependencies": ["PyJWT"],
                "risks": ["Token security", "Key management"],
                "validation_strategy": "Run test suite and type checking",
            }
        )
        result.parse_json = lambda: json.loads(result.stdout)
        return result

    def execution_response():
        """Successful execution response."""
        result = Mock()
        result.success = True
        result.stdout = "Step completed successfully"
        result.parse_json = lambda: {"status": "ok"}
        return result

    def validation_success_response():
        """Successful validation response."""
        result = Mock()
        result.success = True
        result.stdout = json.dumps(
            {
                "validation_passed": True,
                "summary": "All checks passed",
                "results": {
                    "tests": {
                        "passed": True,
                        "total_tests": 10,
                        "passed_tests": 10,
                        "failed_tests": 0,
                    },
                    "quality": {
                        "type_check": {"passed": True, "errors": 0},
                        "linting": {"passed": True, "errors": 0},
                    },
                    "security": {"secrets_found": False, "vulnerabilities": []},
                },
            }
        )
        result.parse_json = lambda: json.loads(result.stdout)
        return result

    def validation_failure_response():
        """Failed validation response."""
        result = Mock()
        result.success = True
        result.stdout = json.dumps(
            {
                "validation_passed": False,
                "summary": "Tests failing",
                "results": {
                    "tests": {
                        "passed": False,
                        "total_tests": 10,
                        "passed_tests": 8,
                        "failed_tests": 2,
                        "failures": ["test_token_expiry", "test_invalid_token"],
                    },
                    "quality": {
                        "type_check": {"passed": True, "errors": 0},
                        "linting": {"passed": True, "errors": 0},
                    },
                },
            }
        )
        result.parse_json = lambda: json.loads(result.stdout)
        return result

    def recovery_response():
        """Successful recovery response."""
        result = Mock()
        result.success = True
        result.stdout = "Recovery completed, issues fixed"
        result.parse_json = lambda: {"status": "recovered"}
        return result

    return {
        "planning": planning_response,
        "execution": execution_response,
        "validation_success": validation_success_response,
        "validation_failure": validation_failure_response,
        "recovery": recovery_response,
    }


class TestFullWorkflowSuccess:
    """Tests for successful task workflow."""

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_complete_workflow_first_try(
        self, mock_load_prompt, orchestrated_workspace, mock_claude_responses
    ):
        """Test complete workflow succeeding on first validation."""
        # Setup
        state_machine = TaskStateMachine(state_dir=orchestrated_workspace / ".fsd" / "state")
        checkpoint_manager = CheckpointManager(repo_path=orchestrated_workspace)
        plan_storage = PlanStorage(plans_dir=orchestrated_workspace / ".fsd" / "plans")

        # Mock Claude executor
        mock_executor = Mock()
        call_sequence = [
            mock_claude_responses["planning"](),  # Planning phase
            mock_claude_responses["execution"](),  # Step 1
            mock_claude_responses["execution"](),  # Step 2
            mock_claude_responses["execution"](),  # Step 3
            mock_claude_responses["validation_success"](),  # Validation
        ]
        mock_executor.execute.side_effect = call_sequence

        # Create phase executor
        phase_executor = PhaseExecutor(
            state_machine=state_machine,
            checkpoint_manager=checkpoint_manager,
            claude_executor=mock_executor,
            plan_storage=plan_storage,
        )

        # Mock prompt loading
        mock_load_prompt.return_value = "Test prompt"

        # Execute
        task_file = orchestrated_workspace / ".fsd" / "queue" / "add-feature.yaml"
        result = phase_executor.execute_task("add-feature", task_file)

        # Verify result
        assert result.completed is True
        assert result.task_id == "add-feature"
        assert result.final_state == TaskState.COMPLETED
        assert result.retry_count == 0

        # Verify state transitions
        final_state = state_machine.get_state("add-feature")
        assert final_state == TaskState.COMPLETED

        # Verify plan was saved
        saved_plan = plan_storage.load_plan("add-feature")
        assert saved_plan is not None
        assert len(saved_plan.steps) == 3

        # Verify Claude was called correct number of times
        # 1 planning + 3 steps + 1 validation = 5
        assert mock_executor.execute.call_count == 5


class TestWorkflowWithRetries:
    """Tests for workflow with retry logic."""

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_workflow_with_single_retry(
        self, mock_load_prompt, orchestrated_workspace, mock_claude_responses
    ):
        """Test workflow that requires one retry."""
        # Setup
        state_machine = TaskStateMachine(
            state_dir=orchestrated_workspace / ".fsd" / "state"
        )
        checkpoint_manager = CheckpointManager(repo_path=orchestrated_workspace)
        plan_storage = PlanStorage(plans_dir=orchestrated_workspace / ".fsd" / "plans")

        # Mock Claude executor with failure then success
        mock_executor = Mock()
        call_sequence = [
            mock_claude_responses["planning"](),  # Planning
            mock_claude_responses["execution"](),  # Step 1
            mock_claude_responses["execution"](),  # Step 2
            mock_claude_responses["execution"](),  # Step 3
            mock_claude_responses["validation_failure"](),  # Validation - FAIL
            mock_claude_responses["recovery"](),  # Recovery
            mock_claude_responses["execution"](),  # Re-execute Step 1
            mock_claude_responses["execution"](),  # Re-execute Step 2
            mock_claude_responses["execution"](),  # Re-execute Step 3
            mock_claude_responses["validation_success"](),  # Validation - PASS
        ]
        mock_executor.execute.side_effect = call_sequence

        # Create phase executor
        phase_executor = PhaseExecutor(
            state_machine=state_machine,
            checkpoint_manager=checkpoint_manager,
            claude_executor=mock_executor,
            plan_storage=plan_storage,
        )

        mock_load_prompt.return_value = "Test prompt"

        # Execute
        task_file = orchestrated_workspace / ".fsd" / "queue" / "add-feature.yaml"
        result = phase_executor.execute_task("add-feature", task_file)

        # Verify result
        assert result.completed is True
        assert result.retry_count == 1
        assert "after 1 retries" in result.summary.lower()

        # Verify final state
        final_state = state_machine.get_state("add-feature")
        assert final_state == TaskState.COMPLETED

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_workflow_exhausts_retries(
        self, mock_load_prompt, orchestrated_workspace, mock_claude_responses
    ):
        """Test workflow that exhausts all retries."""
        # Setup
        state_machine = TaskStateMachine(
            state_dir=orchestrated_workspace / ".fsd" / "state"
        )
        checkpoint_manager = CheckpointManager(repo_path=orchestrated_workspace)
        plan_storage = PlanStorage(plans_dir=orchestrated_workspace / ".fsd" / "plans")

        # Configure retry strategy with max 2 retries
        retry_config = RetryConfig(max_retries=2)
        retry_strategy = RetryStrategy(config=retry_config)

        # Mock Claude executor that always fails validation
        mock_executor = Mock()
        responses = [mock_claude_responses["planning"]()] + [
            mock_claude_responses["execution"]() for _ in range(3)
        ]

        # Add failing validations and recoveries
        for _ in range(3):  # Initial + 2 retries
            responses.append(mock_claude_responses["validation_failure"]())
            responses.append(mock_claude_responses["recovery"]())
            responses.extend([mock_claude_responses["execution"]() for _ in range(3)])

        mock_executor.execute.side_effect = responses

        # Create phase executor
        phase_executor = PhaseExecutor(
            state_machine=state_machine,
            checkpoint_manager=checkpoint_manager,
            claude_executor=mock_executor,
            plan_storage=plan_storage,
            retry_strategy=retry_strategy,
        )

        mock_load_prompt.return_value = "Test prompt"

        # Execute
        task_file = orchestrated_workspace / ".fsd" / "queue" / "add-feature.yaml"
        result = phase_executor.execute_task("add-feature", task_file)

        # Verify result
        assert result.completed is False
        assert result.final_state == TaskState.FAILED
        assert result.retry_count == 2
        assert result.error_message is not None

        # Verify final state
        final_state = state_machine.get_state("add-feature")
        assert final_state == TaskState.FAILED


class TestWorkflowErrorHandling:
    """Tests for error handling in workflow."""

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_workflow_handles_planning_failure(
        self, mock_load_prompt, orchestrated_workspace
    ):
        """Test workflow handles planning phase failure."""
        # Setup
        state_machine = TaskStateMachine(
            state_dir=orchestrated_workspace / ".fsd" / "state"
        )
        checkpoint_manager = CheckpointManager(repo_path=orchestrated_workspace)

        # Mock Claude executor with planning failure
        mock_executor = Mock()
        planning_result = Mock()
        planning_result.success = False
        planning_result.error_message = "Planning failed"
        mock_executor.execute.return_value = planning_result

        # Create phase executor
        phase_executor = PhaseExecutor(
            state_machine=state_machine,
            checkpoint_manager=checkpoint_manager,
            claude_executor=mock_executor,
        )

        mock_load_prompt.return_value = "Test prompt"

        # Execute
        task_file = orchestrated_workspace / ".fsd" / "queue" / "add-feature.yaml"
        result = phase_executor.execute_task("add-feature", task_file)

        # Verify result
        assert result.completed is False
        assert result.final_state == TaskState.FAILED
        assert "Planning failed" in result.error_message

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_workflow_handles_execution_failure(
        self, mock_load_prompt, orchestrated_workspace, mock_claude_responses
    ):
        """Test workflow handles execution phase failure."""
        # Setup
        state_machine = TaskStateMachine(
            state_dir=orchestrated_workspace / ".fsd" / "state"
        )
        checkpoint_manager = CheckpointManager(repo_path=orchestrated_workspace)
        plan_storage = PlanStorage(plans_dir=orchestrated_workspace / ".fsd" / "plans")

        # Mock Claude executor with execution failure on step 2
        mock_executor = Mock()
        call_sequence = [
            mock_claude_responses["planning"](),  # Planning succeeds
            mock_claude_responses["execution"](),  # Step 1 succeeds
        ]

        # Step 2 fails
        failed_execution = Mock()
        failed_execution.success = False
        failed_execution.error_message = "Execution error"
        call_sequence.append(failed_execution)

        mock_executor.execute.side_effect = call_sequence

        # Create phase executor
        phase_executor = PhaseExecutor(
            state_machine=state_machine,
            checkpoint_manager=checkpoint_manager,
            claude_executor=mock_executor,
            plan_storage=plan_storage,
        )

        mock_load_prompt.return_value = "Test prompt"

        # Execute
        task_file = orchestrated_workspace / ".fsd" / "queue" / "add-feature.yaml"
        result = phase_executor.execute_task("add-feature", task_file)

        # Verify result
        assert result.completed is False
        assert result.final_state == TaskState.FAILED
        assert "Execution step 2 failed" in result.error_message


class TestWorkflowCheckpoints:
    """Tests for checkpoint creation during workflow."""

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_workflow_creates_checkpoints(
        self, mock_load_prompt, orchestrated_workspace, mock_claude_responses
    ):
        """Test that checkpoints are created at appropriate points."""
        # Setup
        state_machine = TaskStateMachine(
            state_dir=orchestrated_workspace / ".fsd" / "state"
        )
        checkpoint_manager = CheckpointManager(repo_path=orchestrated_workspace)
        plan_storage = PlanStorage(plans_dir=orchestrated_workspace / ".fsd" / "plans")

        # Mock Claude executor
        mock_executor = Mock()
        call_sequence = [
            mock_claude_responses["planning"](),
            mock_claude_responses["execution"](),  # Step 1 (checkpoint)
            mock_claude_responses["execution"](),  # Step 2 (checkpoint)
            mock_claude_responses["execution"](),  # Step 3 (no checkpoint)
            mock_claude_responses["validation_success"](),
        ]
        mock_executor.execute.side_effect = call_sequence

        # Create phase executor
        phase_executor = PhaseExecutor(
            state_machine=state_machine,
            checkpoint_manager=checkpoint_manager,
            claude_executor=mock_executor,
            plan_storage=plan_storage,
        )

        mock_load_prompt.return_value = "Test prompt"

        # Execute
        task_file = orchestrated_workspace / ".fsd" / "queue" / "add-feature.yaml"
        phase_executor.execute_task("add-feature", task_file)

        # Verify checkpoints exist
        checkpoints = checkpoint_manager.list_checkpoints("add-feature")
        assert len(checkpoints) > 0

        # Should have checkpoints for:
        # - Pre-execution
        # - Step 1 complete
        # - Step 2 complete
        # - Pre-validation
        # - Post-validation
        checkpoint_types = [cp.checkpoint_type for cp in checkpoints]
        assert CheckpointType.PRE_EXECUTION in checkpoint_types
        assert CheckpointType.STEP_COMPLETE in checkpoint_types
        assert CheckpointType.PRE_VALIDATION in checkpoint_types
        assert CheckpointType.POST_VALIDATION in checkpoint_types


class TestWorkflowStateTransitions:
    """Tests for state transitions during workflow."""

    @patch("fsd.orchestrator.phase_executor.load_prompt")
    def test_workflow_state_transitions(
        self, mock_load_prompt, orchestrated_workspace, mock_claude_responses
    ):
        """Test that state transitions occur correctly."""
        # Setup
        state_machine = TaskStateMachine(
            state_dir=orchestrated_workspace / ".fsd" / "state"
        )
        checkpoint_manager = CheckpointManager(repo_path=orchestrated_workspace)
        plan_storage = PlanStorage(plans_dir=orchestrated_workspace / ".fsd" / "plans")

        # Mock Claude executor
        mock_executor = Mock()
        call_sequence = [
            mock_claude_responses["planning"](),
            mock_claude_responses["execution"](),
            mock_claude_responses["execution"](),
            mock_claude_responses["execution"](),
            mock_claude_responses["validation_success"](),
        ]
        mock_executor.execute.side_effect = call_sequence

        # Track state changes
        states_seen = []

        original_transition = state_machine.transition

        def tracked_transition(task_id, new_state):
            states_seen.append(new_state)
            return original_transition(task_id, new_state)

        state_machine.transition = tracked_transition

        # Create phase executor
        phase_executor = PhaseExecutor(
            state_machine=state_machine,
            checkpoint_manager=checkpoint_manager,
            claude_executor=mock_executor,
            plan_storage=plan_storage,
        )

        mock_load_prompt.return_value = "Test prompt"

        # Execute
        task_file = orchestrated_workspace / ".fsd" / "queue" / "add-feature.yaml"
        phase_executor.execute_task("add-feature", task_file)

        # Verify state progression
        # Should see: PLANNING -> EXECUTING -> VALIDATING -> COMPLETED
        assert TaskState.PLANNING in states_seen
        assert TaskState.EXECUTING in states_seen
        assert TaskState.VALIDATING in states_seen
        assert TaskState.COMPLETED in states_seen

        # Verify order is correct
        planning_idx = states_seen.index(TaskState.PLANNING)
        executing_idx = states_seen.index(TaskState.EXECUTING)
        validating_idx = states_seen.index(TaskState.VALIDATING)
        completed_idx = states_seen.index(TaskState.COMPLETED)

        assert planning_idx < executing_idx < validating_idx < completed_idx
