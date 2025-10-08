# Task 11: Phase Orchestration

**ID:** `fsd-phase-orchestration`
**Priority:** High
**Estimated Duration:** 3 hours

## Description

Implement the orchestration layer that coordinates task execution through planning, executing, and validation phases using Claude CLI.

**Key Insight:** We don't need separate agents. Claude Code CLI can handle planning, execution, and validation when given the right prompts. The orchestrator simply manages the workflow, state transitions, and checkpoints.

The Phase Orchestrator provides:
- **Workflow coordination** - Move tasks through lifecycle states
- **Prompt selection** - Choose appropriate template per phase
- **Checkpoint integration** - Create checkpoints at phase boundaries
- **State management** - Update state machine after each phase
- **Error recovery** - Handle failures and retry logic
- **Result storage** - Save outputs from each phase

Core capabilities:
- Execute planning phase (QUEUED → PLANNING → EXECUTING)
- Execute execution phase (EXECUTING with checkpoints)
- Execute validation phase (EXECUTING → VALIDATING → COMPLETED/retry)
- Manage retries when validation fails
- Integrate with state machine for lifecycle tracking
- Create checkpoints before/after critical phases
- Log all phase transitions and results

Orchestration workflow:
```python
def execute_task(task_id: str):
    """Execute a task through all phases."""

    # 1. Planning Phase
    state_machine.transition(task_id, TaskState.PLANNING)
    checkpoint_manager.create_checkpoint(task_id, PRE_EXECUTION)

    prompt = load_prompt("planning", task=task)
    result = claude_executor.execute(prompt)
    plan = result.parse_json()
    save_plan(task_id, plan)

    # 2. Execution Phase
    state_machine.transition(task_id, TaskState.EXECUTING)

    for step in plan.steps:
        prompt = load_prompt("execution", task=task, step=step)
        result = claude_executor.execute(prompt)
        checkpoint_manager.create_checkpoint(task_id, STEP_COMPLETE, step_number=step.number)

    # 3. Validation Phase
    state_machine.transition(task_id, TaskState.VALIDATING)
    checkpoint_manager.create_checkpoint(task_id, PRE_VALIDATION)

    prompt = load_prompt("validation", task=task, plan=plan)
    result = claude_executor.execute(prompt)
    validation_result = result.parse_json()

    if validation_result.passed:
        state_machine.transition(task_id, TaskState.COMPLETED)
    else:
        # Retry or fail
        if retry_count < max_retries:
            state_machine.transition(task_id, TaskState.EXECUTING)
        else:
            state_machine.fail_task(task_id, validation_result.error)
```

## Context

- Integrates prompt loader (Task 09) and Claude executor (Task 10)
- Uses existing state machine and checkpoint system
- No direct code modification - Claude CLI handles that
- Focus on orchestrating phases and managing state
- Handle the full lifecycle: QUEUED → PLANNING → EXECUTING → VALIDATING → COMPLETED
- Support retry loop: VALIDATING → EXECUTING (if tests fail)
- Create checkpoints at phase boundaries for rollback
- Log all phase transitions and Claude outputs
- Simple, sequential execution (no complex parallelization yet)

## Success Criteria

- ✅ Can execute a task through all phases end-to-end
- ✅ State transitions happen at correct times
- ✅ Checkpoints created at phase boundaries
- ✅ Planning output stored and accessible
- ✅ Validation failures trigger retries (configurable limit)
- ✅ All Claude outputs logged to activity tracker
- ✅ Integration with existing state machine
- ✅ Integration with existing checkpoint system
- ✅ Unit tests with mocked Claude executor
- ✅ Integration test with full workflow
- ✅ Documentation on orchestration flow

## Focus Files

- `fsd/orchestrator/phase_executor.py` - Main orchestration logic
- `fsd/orchestrator/retry_strategy.py` - Retry logic for failures
- `fsd/orchestrator/plan_storage.py` - Save/load execution plans
- `tests/test_phase_executor.py` - Orchestrator tests
- `tests/integration/test_orchestrated_workflow.py` - End-to-end test
- `docs/orchestration.md` - Workflow documentation

## Example Usage

```python
from fsd.orchestrator.phase_executor import PhaseExecutor

executor = PhaseExecutor(
    state_machine=state_machine,
    checkpoint_manager=checkpoint_manager,
    claude_executor=claude_executor,
)

# Execute a task through all phases
try:
    result = executor.execute_task(task_id="my-task")

    if result.completed:
        print(f"Task completed: {result.summary}")
    else:
        print(f"Task failed: {result.error_message}")

except Exception as e:
    state_machine.fail_task(task_id, str(e))
```

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Phase orchestration for end-to-end task execution"
- **Notify Slack:** No
