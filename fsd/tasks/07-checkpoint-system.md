# Task 7: Checkpoint System

**ID:** `fsd-checkpoint-system`
**Priority:** High
**Estimated Duration:** 4 hours

## Description

Implement a Git-based checkpoint system to enable rollback and resume capabilities.

Create a checkpoint manager that:
- Creates **Git commits** at key execution points
- Stores **metadata** for each checkpoint (step, timestamp, status, task context)
- Provides **rollback** functionality to any previous checkpoint
- Enables **resume** from failed or interrupted execution
- Manages **checkpoint cleanup** to avoid cluttering Git history

Checkpoint creation points:
- Before starting task execution
- After each major step completion
- Before running validation/tests
- After successful validation
- Before attempting error recovery

Metadata to store:
- Task ID and step number
- Timestamp and execution duration
- Files changed since last checkpoint
- Test results (if applicable)
- Error information (if failed)
- State machine state

## Context

- Use Git commits with special tags or refs for checkpoints
- Store metadata in `.fsd/checkpoints/<task-id>/` as JSON files
- Consider using `git worktree` for isolation if needed
- Checkpoints should be lightweight and fast
- Support both automatic and manual checkpoint creation
- Don't checkpoint files in `.fsd/` directory itself

## Success Criteria

- ✅ Can create checkpoints at any point during execution
- ✅ Metadata is stored with each checkpoint
- ✅ Can list all checkpoints for a task
- ✅ Rollback restores working directory to checkpoint state
- ✅ Resume can continue from any checkpoint
- ✅ Checkpoint cleanup works without breaking history
- ✅ Unit and integration tests cover all scenarios
- ✅ Performance is acceptable (checkpoint creation < 1s)

## Focus Files

- `fsd/core/checkpoint.py`
- `fsd/core/checkpoint_manager.py`
- `fsd/core/git_utils.py`
- `tests/test_checkpoint.py`

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Git-based checkpoint system for rollback and resume"
- **Notify Slack:** No
