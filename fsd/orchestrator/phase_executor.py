"""Phase executor for orchestrating task execution through phases.

This module provides the main orchestration logic for executing tasks
through planning, execution, and validation phases using Claude Code CLI.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..core.checkpoint_manager import CheckpointManager, CheckpointType
from ..core.claude_executor import ClaudeExecutor
from ..core.exceptions import ClaudeExecutionError, ClaudeTimeoutError
from ..core.prompt_loader import load_prompt
from ..core.state_machine import TaskStateMachine
from ..core.task_schema import TaskDefinition, load_task_from_yaml
from ..core.task_state import TaskState
from .plan_storage import PlanStorage
from .retry_strategy import RetryConfig, RetryDecision, RetryStrategy


@dataclass
class TaskExecutionResult:
    """Result of task execution through all phases."""

    task_id: str
    completed: bool
    final_state: TaskState
    summary: str
    error_message: Optional[str] = None
    retry_count: int = 0
    duration_seconds: float = 0.0


class PhaseExecutor:
    """Orchestrates task execution through planning, execution, and validation phases."""

    def __init__(
        self,
        state_machine: TaskStateMachine,
        checkpoint_manager: CheckpointManager,
        claude_executor: ClaudeExecutor,
        plan_storage: Optional[PlanStorage] = None,
        retry_strategy: Optional[RetryStrategy] = None,
    ):
        """Initialize phase executor.

        Args:
            state_machine: State machine for task lifecycle
            checkpoint_manager: Checkpoint manager for git checkpoints
            claude_executor: Claude CLI executor
            plan_storage: Plan storage (creates default if None)
            retry_strategy: Retry strategy (creates default if None)
        """
        self.state_machine = state_machine
        self.checkpoint_manager = checkpoint_manager
        self.claude_executor = claude_executor
        self.plan_storage = plan_storage or PlanStorage()
        self.retry_strategy = retry_strategy or RetryStrategy(RetryConfig())

    def execute_task(self, task_id: str, task_file: Optional[Path] = None) -> TaskExecutionResult:
        """Execute a task through all phases.

        Args:
            task_id: Task identifier
            task_file: Path to task YAML file (defaults to .fsd/queue/{task_id}.yaml)

        Returns:
            TaskExecutionResult with execution outcome
        """
        start_time = time.time()

        # Load task definition
        if task_file is None:
            task_file = Path.cwd() / ".fsd" / "queue" / f"{task_id}.yaml"

        task = load_task_from_yaml(task_file)

        # Register task if not already registered
        if not self.state_machine.has_task(task_id):
            self.state_machine.register_task(task_id, initial_state=TaskState.QUEUED)

        try:
            # Mark task start
            self.checkpoint_manager.mark_task_start(task_id)

            # Execute phases
            self._execute_planning_phase(task)
            self._execute_execution_phase(task)

            # Validation with retry loop
            retry_count = 0
            while True:
                validation_passed, validation_result = self._execute_validation_phase(task)

                # Determine retry decision
                decision = self.retry_strategy.should_retry(
                    current_retry_count=retry_count,
                    validation_passed=validation_passed,
                )

                if decision == RetryDecision.COMPLETE:
                    # Success!
                    self.state_machine.transition(task_id, TaskState.COMPLETED)
                    duration = time.time() - start_time

                    return TaskExecutionResult(
                        task_id=task_id,
                        completed=True,
                        final_state=TaskState.COMPLETED,
                        summary=f"Task completed successfully after {retry_count} retries" if retry_count > 0 else "Task completed successfully",
                        retry_count=retry_count,
                        duration_seconds=duration,
                    )

                elif decision == RetryDecision.RETRY:
                    # Retry execution
                    retry_count += 1
                    retry_msg = self.retry_strategy.get_retry_message(
                        decision, retry_count - 1, "Validation failed"
                    )

                    # Execute recovery phase
                    self._execute_recovery_phase(task, validation_result, retry_count)

                    # Go back to execution
                    self.state_machine.transition(task_id, TaskState.EXECUTING)

                    # Re-execute
                    self._execute_execution_phase(task)

                elif decision == RetryDecision.FAIL:
                    # Failed
                    error_msg = self.retry_strategy.get_retry_message(
                        decision, retry_count, "Validation failed"
                    )
                    self.state_machine.fail_task(task_id, error_msg)
                    duration = time.time() - start_time

                    return TaskExecutionResult(
                        task_id=task_id,
                        completed=False,
                        final_state=TaskState.FAILED,
                        summary="Task failed",
                        error_message=error_msg,
                        retry_count=retry_count,
                        duration_seconds=duration,
                    )

        except Exception as e:
            # Unexpected error
            error_msg = f"Task execution failed: {str(e)}"
            self.state_machine.fail_task(task_id, error_msg)
            duration = time.time() - start_time

            return TaskExecutionResult(
                task_id=task_id,
                completed=False,
                final_state=TaskState.FAILED,
                summary="Task failed with exception",
                error_message=error_msg,
                duration_seconds=duration,
            )

    def _execute_planning_phase(self, task: TaskDefinition) -> None:
        """Execute planning phase.

        Args:
            task: Task definition
        """
        # Transition to planning state
        self.state_machine.transition(task.id, TaskState.PLANNING)

        # Create pre-execution checkpoint
        self.checkpoint_manager.create_checkpoint(
            task_id=task.id,
            checkpoint_type=CheckpointType.PRE_EXECUTION,
            description="Starting planning phase",
        )

        # Load and render planning prompt
        prompt = load_prompt(
            "planning",
            task_id=task.id,
            description=task.description,
            priority=task.priority.value,
            estimated_duration=task.estimated_duration,
            context=task.context or "",
            focus_files=task.focus_files or [],
            success_criteria=task.success_criteria or "",
        )

        # Execute Claude with planning prompt
        result = self.claude_executor.execute(
            prompt=prompt,
            timeout=300,  # 5 minutes for planning
            task_id=task.id,
        )

        if not result.success:
            raise ClaudeExecutionError(
                f"Planning phase failed: {result.error_message}"
            )

        # Parse and save plan
        plan = result.parse_json()
        self.plan_storage.save_plan_dict(task.id, plan)

    def _execute_execution_phase(self, task: TaskDefinition) -> None:
        """Execute execution phase.

        Args:
            task: Task definition
        """
        # Transition to executing state
        self.state_machine.transition(task.id, TaskState.EXECUTING)

        # Load plan
        plan = self.plan_storage.load_plan_dict(task.id)
        if plan is None:
            raise ClaudeExecutionError(f"No plan found for task {task.id}")

        # Execute each step
        for step in plan["steps"]:
            # Render execution prompt for this step
            prompt = load_prompt(
                "execution",
                task_id=task.id,
                description=task.description,
                step_number=step["step_number"],
                total_steps=len(plan["steps"]),
                step_description=step["description"],
                step_duration=step.get("estimated_duration", "30m"),
                step_files=", ".join(step.get("files_to_modify", [])),
                step_validation=step.get("validation", ""),
                step_checkpoint=step.get("checkpoint", False),
                plan_summary=plan.get("analysis", ""),
            )

            # Execute step
            result = self.claude_executor.execute(
                prompt=prompt,
                timeout=1800,  # 30 minutes per step
                task_id=task.id,
            )

            if not result.success:
                raise ClaudeExecutionError(
                    f"Execution step {step['step_number']} failed: {result.error_message}"
                )

            # Create checkpoint if specified
            if step.get("checkpoint", False):
                self.checkpoint_manager.create_checkpoint(
                    task_id=task.id,
                    checkpoint_type=CheckpointType.STEP_COMPLETE,
                    step_number=step["step_number"],
                    description=f"Completed step {step['step_number']}: {step['description'][:50]}",
                )

    def _execute_validation_phase(self, task: TaskDefinition) -> tuple[bool, dict]:
        """Execute validation phase.

        Args:
            task: Task definition

        Returns:
            Tuple of (validation_passed, validation_result_dict)
        """
        # Transition to validating state
        self.state_machine.transition(task.id, TaskState.VALIDATING)

        # Create pre-validation checkpoint
        self.checkpoint_manager.create_checkpoint(
            task_id=task.id,
            checkpoint_type=CheckpointType.PRE_VALIDATION,
            description="Starting validation",
        )

        # Load plan for context
        plan = self.plan_storage.load_plan_dict(task.id)

        # Render validation prompt
        prompt = load_prompt(
            "validation",
            task_id=task.id,
            description=task.description,
            priority=task.priority.value,
            success_criteria=task.success_criteria or "",
            execution_summary=plan.get("analysis", "") if plan else "",
        )

        # Execute validation
        result = self.claude_executor.execute(
            prompt=prompt,
            timeout=600,  # 10 minutes for validation
            task_id=task.id,
        )

        if not result.success:
            raise ClaudeExecutionError(
                f"Validation phase failed: {result.error_message}"
            )

        # Parse validation result
        validation_result = result.parse_json()
        validation_passed = validation_result.get("validation_passed", False)

        # Create post-validation checkpoint
        self.checkpoint_manager.create_checkpoint(
            task_id=task.id,
            checkpoint_type=CheckpointType.POST_VALIDATION,
            test_results=validation_result.get("results", {}),
        )

        return validation_passed, validation_result

    def _execute_recovery_phase(
        self, task: TaskDefinition, validation_result: dict, retry_count: int
    ) -> None:
        """Execute recovery phase to fix validation failures.

        Args:
            task: Task definition
            validation_result: Validation result from previous attempt
            retry_count: Current retry attempt number
        """
        # Create pre-recovery checkpoint
        self.checkpoint_manager.create_checkpoint(
            task_id=task.id,
            checkpoint_type=CheckpointType.PRE_RECOVERY,
            description=f"Starting recovery attempt {retry_count}",
        )

        # Extract failed checks
        failed_checks = []
        if "results" in validation_result:
            results = validation_result["results"]

            # Check test failures
            if not results.get("tests", {}).get("passed", True):
                failed_checks.append("Tests failing")

            # Check quality failures
            quality = results.get("quality", {})
            if not quality.get("type_check", {}).get("passed", True):
                failed_checks.append("Type checking errors")
            if not quality.get("linting", {}).get("passed", True):
                failed_checks.append("Linting errors")

        # Render recovery prompt
        prompt = load_prompt(
            "recovery",
            task_id=task.id,
            description=task.description,
            retry_count=retry_count,
            max_retries=self.retry_strategy.config.max_retries,
            validation_failure_summary=validation_result.get("summary", "Validation failed"),
            failed_checks_list="\n".join(f"- {check}" for check in failed_checks),
        )

        # Execute recovery
        result = self.claude_executor.execute(
            prompt=prompt,
            timeout=1200,  # 20 minutes for recovery
            task_id=task.id,
        )

        if not result.success:
            raise ClaudeExecutionError(
                f"Recovery phase failed: {result.error_message}"
            )
