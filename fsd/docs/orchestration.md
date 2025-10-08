# Phase Orchestration

The Phase Orchestrator coordinates task execution through planning, execution, validation, and recovery phases, managing the complete lifecycle of autonomous coding tasks.

## Overview

The orchestration system provides:

- **Phase coordination** - Manages planning → execution → validation → recovery workflow
- **Retry logic** - Automatic recovery from validation failures
- **State management** - Tracks task progression through lifecycle states
- **Checkpoint integration** - Creates git checkpoints at key points
- **Plan persistence** - Saves and loads execution plans

## Architecture

```
orchestrator/
├── phase_executor.py    # Main orchestration logic
├── plan_storage.py      # Execution plan persistence
└── retry_strategy.py    # Retry and failure handling
```

The orchestrator integrates multiple components:

```
PhaseExecutor
├── StateM Machine (task lifecycle)
├── CheckpointManager (git checkpoints)
├── ClaudeExecutor (CLI execution)
├── PlanStorage (plan persistence)
├── RetryStrategy (failure handling)
└── PromptLoader (template rendering)
```

## Workflow Phases

### 1. Planning Phase

**Purpose**: Analyze task and create detailed execution plan

**Process**:
1. Transition task to `PLANNING` state
2. Create pre-execution checkpoint
3. Load and render planning prompt template
4. Execute Claude with planning prompt
5. Parse JSON plan from output
6. Save plan to `.fsd/plans/{task_id}.json`

**Output**: Structured execution plan with steps, estimates, and validation strategy

**Typical Duration**: 5-10 minutes

```python
# Planning output structure
{
  "task_id": "add-auth",
  "analysis": "Task analysis...",
  "complexity": "medium",
  "estimated_total_time": "3h",
  "steps": [
    {
      "step_number": 1,
      "description": "Create auth module",
      "estimated_duration": "1h",
      "files_to_modify": ["src/auth.py"],
      "validation": "Module imports correctly",
      "checkpoint": true
    }
  ],
  "dependencies": ["PyJWT"],
  "risks": ["Token security"],
  "validation_strategy": "Run tests and type checking"
}
```

### 2. Execution Phase

**Purpose**: Implement each step of the plan

**Process**:
1. Transition task to `EXECUTING` state
2. Load saved execution plan
3. For each step:
   - Render execution prompt with step details
   - Execute Claude with execution prompt
   - Check for errors
   - Create checkpoint if specified
4. Complete all steps sequentially

**Output**: Modified codebase according to plan

**Typical Duration**: 30-60 minutes (varies by complexity)

### 3. Validation Phase

**Purpose**: Verify implementation meets success criteria

**Process**:
1. Transition task to `VALIDATING` state
2. Create pre-validation checkpoint
3. Load plan for context
4. Render validation prompt
5. Execute Claude with validation prompt
6. Parse validation results
7. Create post-validation checkpoint

**Output**: Validation report with test results, quality checks, and pass/fail status

**Typical Duration**: 10-15 minutes

```python
# Validation output structure
{
  "validation_passed": true,
  "summary": "All checks passed",
  "results": {
    "tests": {
      "passed": true,
      "total_tests": 25,
      "passed_tests": 25,
      "failed_tests": 0
    },
    "quality": {
      "type_check": {"passed": true, "errors": 0},
      "linting": {"passed": true, "errors": 0}
    },
    "security": {
      "secrets_found": false,
      "vulnerabilities": []
    }
  }
}
```

### 4. Recovery Phase (on validation failure)

**Purpose**: Fix issues identified during validation

**Process**:
1. Create pre-recovery checkpoint
2. Extract failed checks from validation results
3. Render recovery prompt with failure details
4. Execute Claude with recovery prompt
5. Return to execution phase to re-run

**Output**: Fixed code addressing validation failures

**Typical Duration**: 10-20 minutes

## Retry Logic

The orchestrator implements intelligent retry logic for validation failures.

### Retry Strategy

```python
class RetryConfig:
    max_retries: int = 3                      # Maximum retry attempts
    retry_on_validation_failure: bool = True  # Retry validation failures
    retry_on_execution_error: bool = False    # Don't retry execution errors
    allow_partial_success: bool = False       # Require all checks to pass
```

### Retry Decision Flow

```
Validation Complete
    ↓
Is validation passed?
    ├─ YES → COMPLETE (mark task completed)
    └─ NO → Check retry count
               ↓
        Retry count < max_retries?
            ├─ YES → RETRY (execute recovery)
            └─ NO → Check partial success
                       ↓
                Partial success allowed and achieved?
                    ├─ YES → COMPLETE (with warnings)
                    └─ NO → FAIL (mark task failed)
```

### Retry Execution

When retry is triggered:

1. Increment retry count
2. Execute recovery phase
3. Transition back to `EXECUTING` state
4. Re-execute all plan steps
5. Run validation again
6. Repeat until success or max retries exhausted

### Exponential Backoff

Retry delays use exponential backoff:

```python
delay = 5 * (2 ** retry_count)  # 5s, 10s, 20s, 40s, ...
delay = min(delay, 60)          # Capped at 60 seconds
```

## Usage

### Basic Usage

```python
from fsd.core.checkpoint_manager import CheckpointManager
from fsd.core.claude_executor import ClaudeExecutor
from fsd.core.state_machine import TaskStateMachine
from fsd.orchestrator.phase_executor import PhaseExecutor

# Initialize components
state_machine = TaskStateMachine()
checkpoint_manager = CheckpointManager(repo_path=".")
claude_executor = ClaudeExecutor()

# Create orchestrator
orchestrator = PhaseExecutor(
    state_machine=state_machine,
    checkpoint_manager=checkpoint_manager,
    claude_executor=claude_executor,
)

# Execute task
result = orchestrator.execute_task("add-auth")

if result.completed:
    print(f"✓ Task completed in {result.duration_seconds:.1f}s")
    if result.retry_count > 0:
        print(f"  (after {result.retry_count} retries)")
else:
    print(f"✗ Task failed: {result.error_message}")
```

### With Custom Configuration

```python
from fsd.orchestrator.plan_storage import PlanStorage
from fsd.orchestrator.retry_strategy import RetryConfig, RetryStrategy

# Custom retry configuration
retry_config = RetryConfig(
    max_retries=5,                      # Allow more retries
    retry_on_validation_failure=True,
    allow_partial_success=True,         # Accept partial success
)

# Custom plan storage location
plan_storage = PlanStorage(plans_dir=Path(".fsd/custom_plans"))

# Create orchestrator with custom config
orchestrator = PhaseExecutor(
    state_machine=state_machine,
    checkpoint_manager=checkpoint_manager,
    claude_executor=claude_executor,
    plan_storage=plan_storage,
    retry_strategy=RetryStrategy(config=retry_config),
)
```

### Task Execution Result

```python
result = orchestrator.execute_task("add-auth")

# Check result
print(f"Task ID: {result.task_id}")
print(f"Completed: {result.completed}")
print(f"Final State: {result.final_state}")
print(f"Summary: {result.summary}")
print(f"Retry Count: {result.retry_count}")
print(f"Duration: {result.duration_seconds:.1f}s")

if not result.completed:
    print(f"Error: {result.error_message}")
```

### Monitoring Progress

Track state changes throughout execution:

```python
def monitor_progress():
    """Monitor task progress through states."""
    state = state_machine.get_state("add-auth")

    if state == TaskState.PLANNING:
        print("⏳ Planning task...")
    elif state == TaskState.EXECUTING:
        print("🔨 Executing implementation...")
    elif state == TaskState.VALIDATING:
        print("✓ Validating results...")
    elif state == TaskState.COMPLETED:
        print("✓ Task completed!")
    elif state == TaskState.FAILED:
        print("✗ Task failed")
        error = state_machine.get_state_metadata("add-auth").get("error")
        print(f"  Error: {error}")
```

## Plan Storage

Plans are persisted to disk for resumption and analysis.

### Save and Load Plans

```python
from fsd.orchestrator.plan_storage import PlanStorage, ExecutionPlan

storage = PlanStorage()

# Save plan
plan = ExecutionPlan(
    task_id="add-auth",
    analysis="Implement JWT authentication",
    complexity="medium",
    estimated_total_time="3h",
    steps=[...],
    dependencies=["PyJWT"],
    risks=[],
    validation_strategy="Run tests",
)
storage.save_plan(plan)

# Load plan
loaded_plan = storage.load_plan("add-auth")
print(f"Plan has {len(loaded_plan.steps)} steps")

# Check if plan exists
if storage.plan_exists("add-auth"):
    print("Plan found")

# Get summary
summary = storage.get_plan_summary("add-auth")
print(summary)  # "3 steps, complexity: medium, estimated: 3h"
```

### Plan File Structure

Plans are stored as JSON in `.fsd/plans/{task_id}.json`:

```json
{
  "task_id": "add-auth",
  "analysis": "Implement JWT-based authentication...",
  "complexity": "medium",
  "estimated_total_time": "3h",
  "steps": [...],
  "dependencies": ["PyJWT"],
  "risks": ["Token security", "Key management"],
  "validation_strategy": "Run test suite and type checking",
  "created_at": "2025-01-15T10:30:00Z"
}
```

## Checkpoints

Checkpoints are created at key points for rollback capability.

### Checkpoint Types in Workflow

| Checkpoint Type | When Created | Purpose |
|----------------|--------------|---------|
| `PRE_EXECUTION` | Before planning | Save starting state |
| `STEP_COMPLETE` | After each step with `checkpoint: true` | Save progress after step |
| `PRE_VALIDATION` | Before validation | Save state before checking |
| `POST_VALIDATION` | After validation | Save validation results |
| `PRE_RECOVERY` | Before recovery | Save state before fixes |

### Checkpoint Creation

```python
# Checkpoints are created automatically by orchestrator
# Manual checkpoint creation:
checkpoint_manager.create_checkpoint(
    task_id="add-auth",
    checkpoint_type=CheckpointType.STEP_COMPLETE,
    step_number=1,
    description="Completed auth module implementation",
)

# List checkpoints
checkpoints = checkpoint_manager.list_checkpoints("add-auth")
for cp in checkpoints:
    print(f"{cp.checkpoint_type.value}: {cp.description}")
```

## Error Handling

### Exception Types

```python
from fsd.core.exceptions import (
    ClaudeExecutionError,
    ClaudeTimeoutError,
    ClaudeOutputParseError,
)

try:
    result = orchestrator.execute_task("add-auth")
except ClaudeTimeoutError:
    print("Task timed out - consider increasing timeout or breaking into smaller tasks")
except ClaudeOutputParseError:
    print("Could not parse Claude output - check prompt templates")
except ClaudeExecutionError as e:
    print(f"Execution error: {e}")
```

### Handling Failures

```python
result = orchestrator.execute_task("add-auth")

if not result.completed:
    # Check if retries were exhausted
    if result.retry_count >= orchestrator.retry_strategy.config.max_retries:
        print("Max retries exhausted - task needs manual intervention")

        # Rollback to last good checkpoint
        checkpoints = checkpoint_manager.list_checkpoints("add-auth")
        if checkpoints:
            last_good = checkpoints[-2]  # Before failed validation
            checkpoint_manager.rollback_to_checkpoint(last_good.commit_hash)
            print(f"Rolled back to checkpoint: {last_good.description}")

    # Log error for analysis
    with open(".fsd/logs/failures.log", "a") as f:
        f.write(f"{result.task_id}: {result.error_message}\n")
```

## Best Practices

### 1. Break Complex Tasks into Steps

Plans should have 3-7 steps for manageability:

```python
# Good: Manageable steps
steps = [
    "Create auth module structure",
    "Implement token generation",
    "Add token validation",
    "Create auth middleware",
    "Add comprehensive tests",
]

# Too granular: 20+ tiny steps
# Too coarse: 1 step for entire feature
```

### 2. Use Checkpoints Strategically

Enable checkpoints after significant milestones:

```python
{
  "step_number": 1,
  "description": "Create auth module",
  "checkpoint": True,  # Enable - significant milestone
}

{
  "step_number": 2,
  "description": "Add docstrings",
  "checkpoint": False,  # Disable - minor change
}
```

### 3. Set Appropriate Retry Limits

```python
# For stable environments: fewer retries
retry_config = RetryConfig(max_retries=2)

# For flaky tests: more retries
retry_config = RetryConfig(max_retries=5)

# For critical production: no retries
retry_config = RetryConfig(max_retries=0)
```

### 4. Monitor Retry Patterns

```python
# Track retry rates
def analyze_retries():
    """Analyze retry patterns for improvement."""
    results = []  # Collect task results

    total_tasks = len(results)
    tasks_with_retries = sum(1 for r in results if r.retry_count > 0)

    if tasks_with_retries / total_tasks > 0.5:
        print("⚠️  High retry rate - review prompts and test quality")
```

### 5. Preserve Plans for Analysis

```python
# Keep plans for post-mortem analysis
storage = PlanStorage(plans_dir=".fsd/plans/archive")

# After task completion
result = orchestrator.execute_task("add-auth")
if result.completed:
    # Plan automatically saved during execution
    plan = storage.load_plan("add-auth")

    # Analyze accuracy
    actual_duration = result.duration_seconds / 3600  # Convert to hours
    estimated_duration = parse_duration(plan.estimated_total_time)

    accuracy = actual_duration / estimated_duration
    print(f"Estimation accuracy: {accuracy:.1%}")
```

## Troubleshooting

### Task Stuck in Planning

**Symptom**: Task remains in `PLANNING` state

**Possible Causes**:
- Planning prompt too complex
- Claude CLI hanging
- Timeout too short

**Solutions**:
```python
# Increase planning timeout
orchestrator._execute_planning_phase(task)  # Uses 300s default

# Or simplify prompt by reducing context
prompt = load_prompt(
    "planning",
    context=task.context[:500],  # Limit context length
)
```

### Validation Always Fails

**Symptom**: Task exhausts retries with validation failures

**Possible Causes**:
- Success criteria too strict
- Tests flaky or environment-specific
- Recovery prompt ineffective

**Solutions**:
```python
# Enable partial success
retry_config = RetryConfig(allow_partial_success=True)

# Review validation results
result = orchestrator.execute_task("add-auth")
if not result.completed:
    # Check what's failing
    plan = storage.load_plan("add-auth")
    print(f"Validation strategy: {plan.validation_strategy}")

    # Review recovery attempts
    checkpoints = checkpoint_manager.list_checkpoints("add-auth")
    recovery_attempts = [cp for cp in checkpoints if cp.checkpoint_type == CheckpointType.PRE_RECOVERY]
    print(f"Recovery attempted {len(recovery_attempts)} times")
```

### Out of Memory During Execution

**Symptom**: Process killed or hanging during execution

**Possible Causes**:
- Too many concurrent steps
- Large file operations
- Memory leak in Claude CLI

**Solutions**:
```python
# Execute steps with smaller batch size
# (Orchestrator executes steps sequentially by default)

# Or reduce plan complexity
plan = storage.load_plan("add-auth")
if len(plan.steps) > 10:
    print("⚠️  Plan has many steps - consider splitting task")
```

### JSON Parsing Errors

**Symptom**: `ClaudeOutputParseError` during phase execution

**Possible Causes**:
- Prompt doesn't emphasize JSON format
- Claude output includes extra text
- Malformed JSON in response

**Solutions**:
```python
# Check raw output
result = claude_executor.execute(prompt)
print("Raw output:", result.stdout)

# Use non-strict parsing
try:
    data = result.parse_json()
except ClaudeOutputParseError:
    # Fallback to safe parsing
    data = result.parse_json_safe()
    if data is None:
        # Extract manually
        data = OutputParser.extract_json(result.stdout, strict=False)
```

## See Also

- [Prompt Templates](./prompt-templates.md) - Phase-specific prompt design
- [Claude Executor](./claude-executor.md) - CLI execution details
- [State Machine](./architecture.md#state-machine) - Task lifecycle management
- [Checkpoint System](./architecture.md#checkpoint-system) - Git-based rollback
