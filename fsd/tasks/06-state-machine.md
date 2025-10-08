# Task 6: State Machine Implementation

**ID:** `fsd-state-machine`
**Priority:** High
**Estimated Duration:** 4 hours
**Status:** Completed

## Description

Implement the task lifecycle state machine that manages transitions between different task states.

Create a state machine system that handles:
- **Task States:** queued → planning → executing → validating → completed/failed
- **State transitions** with validation and logging
- **State persistence** to survive restarts
- **Event hooks** for state transitions
- **State history** tracking for debugging

The state machine should:
- Enforce valid state transitions only
- Persist state to disk (`.fsd/state/tasks.json`)
- Allow querying current state of all tasks
- Support concurrent task state management
- Emit events on state changes for logging and notifications
- Handle edge cases (crashed tasks, stuck states, etc.)

State transition rules:
- `queued` → `planning` (when task starts)
- `planning` → `executing` (when plan is ready)
- `executing` → `validating` (when code changes complete)
- `validating` → `completed` (tests pass) or `executing` (tests fail, retry)
- Any state → `failed` (on critical errors)

## Context

- Use a formal state machine pattern (consider `python-statemachine` library)
- Store state in JSON format for easy debugging
- Each state transition should be atomic
- State changes should be logged to activity tracker
- Support rollback to previous states for recovery

## Success Criteria

- ✅ State machine correctly enforces all valid transitions
- ✅ Invalid transitions raise clear errors
- ✅ State is persisted and can be restored after restart
- ✅ State history is tracked for each task
- ✅ Concurrent state updates are handled safely
- ✅ Unit tests cover all state transitions and edge cases
- ✅ Integration with activity tracking system

## Focus Files

- `fsd/core/state_machine.py`
- `fsd/core/task_state.py`
- `fsd/core/state_persistence.py`
- `tests/test_state_machine.py`

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Task lifecycle state machine with persistence"
- **Notify Slack:** No
