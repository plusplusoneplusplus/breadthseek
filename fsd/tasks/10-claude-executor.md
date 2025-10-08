# Task 10: Claude CLI Executor

**ID:** `fsd-claude-executor`
**Priority:** High
**Estimated Duration:** 3 hours

## Description

Implement a robust subprocess wrapper for executing Claude Code CLI with prompts.

**Key Insight:** Claude Code CLI already handles code generation, file operations, command execution, and testing. We just need a clean interface to invoke it with our prompt templates and capture results.

The Claude CLI Executor provides:
- **Subprocess management** - Spawn and monitor `claude` CLI processes
- **Output streaming** - Real-time capture of stdout/stderr
- **Error handling** - Detect and handle execution failures
- **Timeout management** - Prevent runaway processes
- **Logging integration** - Record all Claude interactions
- **Result parsing** - Extract structured output from Claude responses

Core capabilities:
- Execute `claude --dangerously-skip-permissions -p "<prompt>"`
- Stream output to logs in real-time
- Parse JSON responses from Claude output
- Handle process timeouts (configurable per phase)
- Detect and report execution errors
- Retry logic for transient failures
- Capture exit codes and signals

Execution flow:
```python
# 1. Load prompt template and fill variables
prompt = load_prompt("planning", task=task)

# 2. Execute Claude CLI with prompt
result = execute_claude(
    prompt=prompt,
    timeout="30m",
    working_dir=config.claude.working_dir
)

# 3. Parse output
if result.success:
    plan = parse_json_output(result.stdout)
    save_plan(task.id, plan)
else:
    log_error(result.stderr)
    raise ExecutionError(result.error_message)
```

## Context

- Use Python `subprocess` module for process management
- Execute command from config: `config.claude.command` (e.g., `claude --dangerously-skip-permissions`)
- Stream output using `subprocess.Popen()` with `PIPE`
- Parse structured output (JSON blocks) from Claude responses
- Handle long-running processes (planning: 5m, execution: 30m, validation: 10m)
- Log all stdin/stdout/stderr to activity tracker
- Detect common error patterns (API errors, permission issues, syntax errors)
- No need for Anthropic SDK - direct CLI invocation
- Support both interactive and batch modes

## Success Criteria

- ✅ Can execute Claude CLI with arbitrary prompts
- ✅ Streams output to logs in real-time
- ✅ Correctly handles process timeouts
- ✅ Parses JSON output from Claude responses
- ✅ Detects and reports various error conditions
- ✅ Integrates with activity logging system
- ✅ Handles retries for transient failures (e.g., network issues)
- ✅ Unit tests with mocked subprocess calls
- ✅ Integration tests with real Claude CLI (optional, manual)
- ✅ Documentation on usage and configuration

## Focus Files

- `fsd/core/claude_executor.py` - Main executor implementation
- `fsd/core/output_parser.py` - Parse Claude output (JSON extraction)
- `fsd/core/exceptions.py` - Claude-specific exceptions
- `tests/test_claude_executor.py` - Executor tests
- `docs/claude-executor.md` - Usage documentation

## Example Usage

```python
from fsd.core.claude_executor import ClaudeExecutor
from fsd.core.prompt_loader import load_prompt

executor = ClaudeExecutor()

# Execute planning phase
prompt = load_prompt("planning", task=task)
result = executor.execute(
    prompt=prompt,
    timeout=config.claude.timeout,
    task_id=task.id
)

if result.success:
    plan = result.parse_json()
    print(f"Generated plan with {len(plan['steps'])} steps")
else:
    print(f"Execution failed: {result.error_message}")
```

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Claude CLI executor for subprocess management and output parsing"
- **Notify Slack:** No
