# Task 10: Execution Agent

**ID:** `fsd-execution-agent`
**Priority:** High
**Estimated Duration:** 6 hours

## Description

Implement the Execution Agent that executes plan steps and makes code changes.

The Execution Agent is responsible for:
- **Step execution** - Running each step from the plan sequentially
- **Tool invocation** - Using appropriate tools (file edits, commands, etc.)
- **Code generation** - Using LLM to generate code changes
- **Context management** - Maintaining execution state between steps
- **Progress tracking** - Reporting progress and updating state

Core capabilities:
- Load execution plan from Planning Agent
- Execute steps one by one with checkpoints
- Use Claude CLI or API to generate code changes
- Apply file edits safely with validation
- Run shell commands when needed
- Handle step failures and retry logic
- Update task state in state machine
- Create checkpoints at key points

Execution workflow:
1. Load plan for task
2. For each step:
   - Update state to `executing`
   - Create checkpoint before step
   - Execute step (generate code, apply changes)
   - Verify changes were applied correctly
   - Update progress
3. Transition to `validating` state when done

Tool capabilities needed:
- File read/write operations
- Code editing (search/replace, insertions)
- Shell command execution
- Git operations (status, diff, commit)
- Integration with LLM for code generation

## Context

- Use Claude CLI or Anthropic API for LLM interactions
- Apply defensive checks before file modifications
- Use state machine for tracking execution progress
- Integrate with checkpoint system for safety
- Handle partial failures gracefully
- Log all operations to activity tracker
- Consider using tool use API for structured interactions

## Success Criteria

- ✅ Can execute multi-step plans end-to-end
- ✅ Code changes are applied correctly
- ✅ Checkpoints are created at appropriate points
- ✅ State machine is updated throughout execution
- ✅ Handles file operation errors gracefully
- ✅ Progress is logged and queryable
- ✅ Can resume from checkpoint after failure
- ✅ Unit tests with mocked file operations
- ✅ Integration tests with real file system

## Focus Files

- `fsd/agents/execution_agent.py`
- `fsd/agents/code_editor.py`
- `fsd/agents/tool_executor.py`
- `fsd/agents/shell_runner.py`
- `tests/test_execution_agent.py`

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Execution Agent with code generation and tool execution"
- **Notify Slack:** No
