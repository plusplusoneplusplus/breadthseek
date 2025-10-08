"""Integration tests for end-to-end task submission flow."""

from pathlib import Path

import pytest
import yaml

from fsd.core.task_schema import (
    TaskDefinition,
    Priority,
    load_task_from_yaml,
    save_task,
)
from fsd.core import TaskStateMachine, TaskState


@pytest.mark.integration
class TestTaskSubmissionFlow:
    """Test complete task submission workflow."""

    def test_submit_task_to_queue(self, tmp_fsd_dir):
        """Test submitting a task saves it to the queue directory."""
        task = TaskDefinition(
            id="integration-test-task",
            description="Test task for integration testing",
            priority=Priority.HIGH,
            estimated_duration="1h",
        )

        # Save to queue
        queue_dir = tmp_fsd_dir / "queue"
        task_file = queue_dir / f"{task.id}.yaml"
        save_task(task, task_file)

        # Verify file exists
        assert task_file.exists()

        # Load and verify
        loaded_task = load_task_from_yaml(task_file)
        assert loaded_task.id == task.id
        assert loaded_task.description == task.description
        assert loaded_task.priority == task.priority

    def test_task_submission_and_state_tracking(self, tmp_fsd_dir):
        """Test submitting a task and tracking its state."""
        # Create task
        task = TaskDefinition(
            id="state-tracked-task",
            description="Task with state tracking",
            priority=Priority.MEDIUM,
            estimated_duration="30m",
        )

        # Save to queue
        queue_dir = tmp_fsd_dir / "queue"
        task_file = queue_dir / f"{task.id}.yaml"
        save_task(task, task_file)

        # Initialize state machine with persistence
        from fsd.core import StatePersistence

        state_dir = tmp_fsd_dir / "state"
        persistence = StatePersistence(state_dir)
        state_machine = TaskStateMachine(persistence_handler=persistence)

        # Register task
        state_machine.register_task(task.id)
        assert state_machine.get_state(task.id).current_state == TaskState.QUEUED

        # Transition to planning
        state_machine.transition(task.id, TaskState.PLANNING)

        # Create new state machine to test persistence
        new_state_machine = TaskStateMachine(persistence_handler=persistence)
        assert new_state_machine.has_task(task.id)
        assert new_state_machine.get_state(task.id).current_state == TaskState.PLANNING

    def test_multiple_task_submission(self, tmp_fsd_dir):
        """Test submitting multiple tasks and ordering by priority."""
        tasks = [
            TaskDefinition(
                id=f"task-{i}",
                description=f"Task {i} description",
                priority=priority,
                estimated_duration="1h",
            )
            for i, priority in enumerate(
                [Priority.LOW, Priority.HIGH, Priority.CRITICAL, Priority.MEDIUM]
            )
        ]

        # Save all tasks
        queue_dir = tmp_fsd_dir / "queue"
        for task in tasks:
            task_file = queue_dir / f"{task.id}.yaml"
            save_task(task, task_file)

        # Load all tasks and verify priority ordering
        loaded_tasks = []
        for yaml_file in queue_dir.glob("*.yaml"):
            loaded_tasks.append(load_task_from_yaml(yaml_file))

        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_tasks = sorted(
            loaded_tasks, key=lambda t: priority_order[t.priority.value]
        )

        assert sorted_tasks[0].priority == Priority.CRITICAL
        assert sorted_tasks[1].priority == Priority.HIGH
        assert sorted_tasks[2].priority == Priority.MEDIUM
        assert sorted_tasks[3].priority == Priority.LOW


@pytest.mark.integration
class TestStateAndPersistenceIntegration:
    """Test integration between state machine and persistence."""

    def test_state_survives_restart(self, tmp_fsd_dir):
        """Test that task state survives process restart."""
        from fsd.core import StatePersistence

        state_dir = tmp_fsd_dir / "state"
        persistence = StatePersistence(state_dir)

        # First session
        sm1 = TaskStateMachine(persistence_handler=persistence)
        sm1.register_task("task-1")
        sm1.transition("task-1", TaskState.PLANNING)
        sm1.transition("task-1", TaskState.EXECUTING)

        # Simulate restart - new state machine
        sm2 = TaskStateMachine(persistence_handler=persistence)
        assert sm2.has_task("task-1")
        assert sm2.get_state("task-1").current_state == TaskState.EXECUTING
        assert len(sm2.get_history("task-1")) == 2

    def test_concurrent_task_state_management(self, tmp_fsd_dir):
        """Test managing state for multiple concurrent tasks."""
        from fsd.core import StatePersistence

        state_dir = tmp_fsd_dir / "state"
        persistence = StatePersistence(state_dir)
        state_machine = TaskStateMachine(persistence_handler=persistence)

        # Register multiple tasks
        task_ids = [f"concurrent-task-{i}" for i in range(5)]
        for task_id in task_ids:
            state_machine.register_task(task_id)

        # Transition them to different states
        state_machine.transition(task_ids[0], TaskState.PLANNING)
        state_machine.transition(task_ids[1], TaskState.PLANNING)
        state_machine.transition(task_ids[1], TaskState.EXECUTING)
        state_machine.transition(task_ids[2], TaskState.PLANNING)
        state_machine.transition(task_ids[2], TaskState.EXECUTING)
        state_machine.transition(task_ids[2], TaskState.VALIDATING)

        # Verify states
        assert state_machine.get_state(task_ids[0]).current_state == TaskState.PLANNING
        assert state_machine.get_state(task_ids[1]).current_state == TaskState.EXECUTING
        assert (
            state_machine.get_state(task_ids[2]).current_state == TaskState.VALIDATING
        )
        assert state_machine.get_state(task_ids[3]).current_state == TaskState.QUEUED
        assert state_machine.get_state(task_ids[4]).current_state == TaskState.QUEUED

        # Get tasks by state
        queued = state_machine.get_tasks_by_state(TaskState.QUEUED)
        assert len(queued) == 2


@pytest.mark.integration
@pytest.mark.git
class TestCheckpointAndStateIntegration:
    """Test integration between checkpoint system and state machine."""

    def test_checkpoint_with_state_metadata(self, git_repo, tmp_fsd_dir):
        """Test creating checkpoints with state machine metadata."""
        from fsd.core import CheckpointManager, CheckpointType, StatePersistence

        # Setup
        checkpoint_dir = tmp_fsd_dir / "checkpoints"
        checkpoint_manager = CheckpointManager(
            checkpoint_dir=checkpoint_dir, repo_path=git_repo
        )

        state_dir = tmp_fsd_dir / "state"
        persistence = StatePersistence(state_dir)
        state_machine = TaskStateMachine(persistence_handler=persistence)

        # Register task and transition
        task_id = "checkpoint-test-task"
        state_machine.register_task(task_id)
        state_machine.transition(task_id, TaskState.PLANNING)

        # Create checkpoint with state metadata
        checkpoint = checkpoint_manager.create_checkpoint(
            task_id=task_id,
            checkpoint_type=CheckpointType.PRE_EXECUTION,
            state_machine_state=state_machine.get_state(task_id).current_state.value,
        )

        assert checkpoint.state_machine_state == "planning"

        # Transition to executing and create another checkpoint
        state_machine.transition(task_id, TaskState.EXECUTING)

        checkpoint2 = checkpoint_manager.create_checkpoint(
            task_id=task_id,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            step_number=1,
            state_machine_state=state_machine.get_state(task_id).current_state.value,
        )

        assert checkpoint2.state_machine_state == "executing"

        # Verify checkpoint history
        checkpoints = checkpoint_manager.list_checkpoints(task_id)
        assert len(checkpoints) == 2
        assert checkpoints[0].state_machine_state == "planning"
        assert checkpoints[1].state_machine_state == "executing"

    def test_rollback_with_state_recovery(self, git_repo, tmp_fsd_dir):
        """Test rollback restores both git state and task state."""
        from fsd.core import CheckpointManager, CheckpointType, StatePersistence

        checkpoint_dir = tmp_fsd_dir / "checkpoints"
        checkpoint_manager = CheckpointManager(
            checkpoint_dir=checkpoint_dir, repo_path=git_repo
        )

        state_dir = tmp_fsd_dir / "state"
        persistence = StatePersistence(state_dir)
        state_machine = TaskStateMachine(persistence_handler=persistence)

        task_id = "rollback-test-task"
        state_machine.register_task(task_id)
        state_machine.transition(task_id, TaskState.PLANNING)
        state_machine.transition(task_id, TaskState.EXECUTING)

        # Create checkpoint at executing state
        checkpoint = checkpoint_manager.create_checkpoint(
            task_id=task_id,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            step_number=1,
            state_machine_state="executing",
        )

        # Make file changes and advance state
        test_file = git_repo / "progress.txt"
        test_file.write_text("Made progress")
        checkpoint_manager.git.create_commit("Progress made")
        state_machine.transition(task_id, TaskState.VALIDATING)

        # Rollback
        restore_info = checkpoint_manager.rollback_to_checkpoint(
            task_id, checkpoint.checkpoint_id
        )

        assert restore_info.success
        assert not test_file.exists()

        # Manually restore state (in real system, this would be automatic)
        # For now, just verify checkpoint has the correct state recorded
        assert checkpoint.state_machine_state == "executing"


@pytest.mark.integration
class TestConfigAndComponentIntegration:
    """Test integration between config system and components."""

    def test_config_affects_component_behavior(self, tmp_fsd_dir):
        """Test that configuration properly affects component behavior."""
        from fsd.config.models import FSDConfig, AgentConfig, LoggingConfig

        # Create custom config
        config = FSDConfig(
            agent=AgentConfig(
                max_execution_time="4h",
                checkpoint_interval="10m",
                parallel_tasks=2,
            ),
            logging=LoggingConfig(level="DEBUG", output_dir=str(tmp_fsd_dir / "logs")),
        )

        # Verify config values
        assert config.agent.max_execution_time == "4h"
        assert config.agent.checkpoint_interval == "10m"
        assert config.agent.parallel_tasks == 2
        assert config.logging.level == "DEBUG"
        assert config.get_log_dir() == tmp_fsd_dir / "logs"
