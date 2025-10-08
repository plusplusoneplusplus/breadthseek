"""Integration tests for full task execution workflow."""

from pathlib import Path
from time import sleep

import pytest

from fsd.core.task_schema import TaskDefinition, Priority, save_task
from fsd.core import (
    TaskStateMachine,
    TaskState,
    StatePersistence,
    CheckpointManager,
    CheckpointType,
)


@pytest.mark.integration
@pytest.mark.git
class TestFullTaskLifecycle:
    """Test complete task lifecycle from submission to completion."""

    def test_complete_task_workflow(self, git_repo, tmp_fsd_dir):
        """Test full workflow: submit → plan → execute → validate → complete."""
        # Setup components
        queue_dir = tmp_fsd_dir / "queue"
        state_dir = tmp_fsd_dir / "state"
        checkpoint_dir = tmp_fsd_dir / "checkpoints"

        persistence = StatePersistence(state_dir)
        state_machine = TaskStateMachine(persistence_handler=persistence)
        checkpoint_manager = CheckpointManager(
            checkpoint_dir=checkpoint_dir, repo_path=git_repo
        )

        # 1. Submit task
        task = TaskDefinition(
            id="full-workflow-task",
            description="Task for testing complete workflow",
            priority=Priority.HIGH,
            estimated_duration="2h",
            success_criteria="All tests pass and code is clean",
        )
        task_file = queue_dir / f"{task.id}.yaml"
        save_task(task, task_file)

        # 2. Register with state machine (queued state)
        state_machine.register_task(task.id)
        assert state_machine.get_state(task.id).current_state == TaskState.QUEUED

        # 3. Start planning
        checkpoint_manager.mark_task_start(task.id)
        state_machine.transition(task.id, TaskState.PLANNING)

        cp_planning = checkpoint_manager.create_checkpoint(
            task_id=task.id,
            checkpoint_type=CheckpointType.PRE_EXECUTION,
            description="Starting planning phase",
            state_machine_state="planning",
        )

        # Simulate planning work
        planning_file = git_repo / f".fsd/plans/{task.id}.json"
        planning_file.parent.mkdir(parents=True, exist_ok=True)
        planning_file.write_text('{"steps": [{"step": 1, "description": "First step"}]}')

        # 4. Transition to executing
        state_machine.transition(task.id, TaskState.EXECUTING)

        cp_exec_start = checkpoint_manager.create_checkpoint(
            task_id=task.id,
            checkpoint_type=CheckpointType.PRE_EXECUTION,
            description="Starting execution",
            state_machine_state="executing",
        )

        # Simulate execution - create some code
        sleep(0.1)
        code_file = git_repo / "src/feature.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("def new_feature():\n    return 'implemented'\n")
        checkpoint_manager.git.create_commit("Implement feature")

        cp_step1 = checkpoint_manager.create_checkpoint(
            task_id=task.id,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            step_number=1,
            state_machine_state="executing",
        )

        # More work
        sleep(0.1)
        test_file = git_repo / "tests/test_feature.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_feature():\n    assert True\n")
        checkpoint_manager.git.create_commit("Add tests")

        cp_step2 = checkpoint_manager.create_checkpoint(
            task_id=task.id,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            step_number=2,
            state_machine_state="executing",
        )

        # 5. Transition to validating
        state_machine.transition(task.id, TaskState.VALIDATING)

        cp_validation = checkpoint_manager.create_checkpoint(
            task_id=task.id,
            checkpoint_type=CheckpointType.PRE_VALIDATION,
            description="Running validation",
            state_machine_state="validating",
        )

        # Simulate validation passing
        cp_validated = checkpoint_manager.create_checkpoint(
            task_id=task.id,
            checkpoint_type=CheckpointType.POST_VALIDATION,
            test_results={"passed": 10, "failed": 0},
            state_machine_state="validating",
        )

        # 6. Complete task
        state_machine.transition(task.id, TaskState.COMPLETED)

        # Verify final state
        final_state = state_machine.get_state(task.id)
        assert final_state.current_state == TaskState.COMPLETED
        assert len(final_state.history) == 4  # QUEUED→PLANNING→EXECUTING→VALIDATING→COMPLETED

        # Verify checkpoints
        checkpoints = checkpoint_manager.list_checkpoints(task.id)
        assert len(checkpoints) == 7

        # Verify checkpoint stats
        stats = checkpoint_manager.get_checkpoint_stats(task.id)
        assert stats.total_checkpoints == 7
        assert stats.checkpoints_by_type["step_complete"] == 2

    def test_workflow_with_retry(self, git_repo, tmp_fsd_dir):
        """Test workflow with validation failure and retry."""
        # Setup
        state_dir = tmp_fsd_dir / "state"
        checkpoint_dir = tmp_fsd_dir / "checkpoints"

        persistence = StatePersistence(state_dir)
        state_machine = TaskStateMachine(persistence_handler=persistence)
        checkpoint_manager = CheckpointManager(
            checkpoint_dir=checkpoint_dir, repo_path=git_repo
        )

        task_id = "retry-task"
        state_machine.register_task(task_id)

        # Go through states
        state_machine.transition(task_id, TaskState.PLANNING)
        state_machine.transition(task_id, TaskState.EXECUTING)

        # Create work
        code_file = git_repo / "buggy_code.py"
        code_file.write_text("def buggy(): return 'oops'\n")
        checkpoint_manager.git.create_commit("Add buggy code")

        state_machine.transition(task_id, TaskState.VALIDATING)

        # Validation fails
        checkpoint_manager.create_checkpoint(
            task_id=task_id,
            checkpoint_type=CheckpointType.POST_VALIDATION,
            test_results={"passed": 5, "failed": 3},
        )

        # Retry - go back to executing
        state_machine.transition(task_id, TaskState.EXECUTING)
        state_info = state_machine.get_state(task_id)
        assert state_info.retry_count == 1

        # Fix the code
        code_file.write_text("def buggy(): return 'fixed'\n")
        checkpoint_manager.git.create_commit("Fix bug")

        state_machine.transition(task_id, TaskState.VALIDATING)

        # Validation passes
        checkpoint_manager.create_checkpoint(
            task_id=task_id,
            checkpoint_type=CheckpointType.POST_VALIDATION,
            test_results={"passed": 8, "failed": 0},
        )

        state_machine.transition(task_id, TaskState.COMPLETED)

        # Verify retry was tracked
        final_state = state_machine.get_state(task_id)
        assert final_state.current_state == TaskState.COMPLETED
        assert final_state.retry_count == 1

    def test_workflow_failure_recovery(self, git_repo, tmp_fsd_dir):
        """Test workflow with failure and checkpoint recovery."""
        # Setup
        state_dir = tmp_fsd_dir / "state"
        checkpoint_dir = tmp_fsd_dir / "checkpoints"

        persistence = StatePersistence(state_dir)
        state_machine = TaskStateMachine(persistence_handler=persistence)
        checkpoint_manager = CheckpointManager(
            checkpoint_dir=checkpoint_dir, repo_path=git_repo
        )

        task_id = "recovery-task"
        state_machine.register_task(task_id)
        state_machine.transition(task_id, TaskState.PLANNING)
        state_machine.transition(task_id, TaskState.EXECUTING)

        # Create good checkpoint
        good_file = git_repo / "good_code.py"
        good_file.write_text("def good(): return 'good'\n")
        checkpoint_manager.git.create_commit("Good code")

        good_checkpoint = checkpoint_manager.create_checkpoint(
            task_id=task_id,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            step_number=1,
        )

        # Make bad changes
        bad_file = git_repo / "bad_code.py"
        bad_file.write_text("this is broken\n")
        checkpoint_manager.git.create_commit("Bad code")

        # Simulate failure
        state_machine.fail_task(task_id, "Critical error during execution")

        # Verify failed state
        assert state_machine.get_state(task_id).current_state == TaskState.FAILED
        assert "Critical error" in state_machine.get_state(task_id).error_message

        # Recover to last good checkpoint
        restore_info = checkpoint_manager.rollback_to_checkpoint(
            task_id, good_checkpoint.checkpoint_id
        )

        assert restore_info.success
        assert good_file.exists()
        assert not bad_file.exists()

    def test_parallel_task_execution_simulation(self, git_repo, tmp_fsd_dir):
        """Test managing multiple tasks in parallel (simulated)."""
        # Setup
        queue_dir = tmp_fsd_dir / "queue"
        state_dir = tmp_fsd_dir / "state"
        checkpoint_dir = tmp_fsd_dir / "checkpoints"

        persistence = StatePersistence(state_dir)
        state_machine = TaskStateMachine(persistence_handler=persistence)
        checkpoint_manager = CheckpointManager(
            checkpoint_dir=checkpoint_dir, repo_path=git_repo
        )

        # Create multiple tasks
        tasks = []
        for i in range(3):
            task = TaskDefinition(
                id=f"parallel-task-{i}",
                description=f"Task {i} for parallel execution",
                priority=Priority.MEDIUM,
                estimated_duration="1h",
            )
            tasks.append(task)
            save_task(task, queue_dir / f"{task.id}.yaml")
            state_machine.register_task(task.id)

        # Advance tasks to different states
        # Task 0: completed
        state_machine.transition(tasks[0].id, TaskState.PLANNING)
        state_machine.transition(tasks[0].id, TaskState.EXECUTING)
        (git_repo / "task0.txt").write_text("task 0 work")
        checkpoint_manager.git.create_commit("Task 0 work")
        state_machine.transition(tasks[0].id, TaskState.VALIDATING)
        state_machine.transition(tasks[0].id, TaskState.COMPLETED)

        # Task 1: executing
        state_machine.transition(tasks[1].id, TaskState.PLANNING)
        state_machine.transition(tasks[1].id, TaskState.EXECUTING)
        (git_repo / "task1.txt").write_text("task 1 work")
        checkpoint_manager.git.create_commit("Task 1 work")

        # Task 2: planning
        state_machine.transition(tasks[2].id, TaskState.PLANNING)

        # Verify states
        assert state_machine.get_state(tasks[0].id).current_state == TaskState.COMPLETED
        assert state_machine.get_state(tasks[1].id).current_state == TaskState.EXECUTING
        assert state_machine.get_state(tasks[2].id).current_state == TaskState.PLANNING

        # Verify we can query by state
        executing_tasks = state_machine.get_tasks_by_state(TaskState.EXECUTING)
        assert len(executing_tasks) == 1
        assert tasks[1].id in executing_tasks
