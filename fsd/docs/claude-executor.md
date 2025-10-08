# Claude CLI Executor

The Claude CLI Executor provides a robust interface for executing Claude Code CLI commands with proper process management, output streaming, timeouts, and error handling.

## Overview

Instead of using the Anthropic SDK directly, FSD leverages the Claude Code CLI tool (`claude`), which is already a full-featured autonomous coding agent. The executor module provides:

- **Subprocess management** - Spawn and monitor CLI processes
- **Output capture** - Real-time streaming and buffered capture
- **Timeout handling** - Prevent runaway processes
- **Error recovery** - Retry logic for transient failures
- **Output parsing** - Extract structured data (JSON) from responses

## Architecture

```
fsd/core/
├── claude_executor.py   # Main executor class
├── output_parser.py     # Parse Claude output
└── exceptions.py        # Claude-specific exceptions
```

## Basic Usage

### Simple Execution

```python
from fsd.core.claude_executor import ClaudeExecutor

# Create executor
executor = ClaudeExecutor(
    command="claude --dangerously-skip-permissions",
    working_dir=".",
    default_timeout=1800  # 30 minutes
)

# Execute a prompt
result = executor.execute(
    prompt="Write a function that checks if a number is prime",
    task_id="test-task"
)

if result.success:
    print("Success!")
    print(result.stdout)
else:
    print(f"Failed: {result.error_message}")
```

### Execution with JSON Output

```python
from fsd.core.prompt_loader import load_prompt

# Load a template that requests JSON output
prompt = load_prompt(
    "planning",
    task_id="add-auth",
    description="Add JWT authentication",
    priority="high",
    estimated_duration="3h"
)

# Execute
result = executor.execute(prompt)

# Parse JSON from output
if result.success:
    plan = result.parse_json()
    print(f"Plan has {len(plan['steps'])} steps")
```

### Streaming Output

```python
def log_output(line):
    """Callback for each line of output."""
    print(f"[Claude] {line}")

# Execute with real-time output streaming
result = executor.execute_with_streaming(
    prompt="Implement the feature...",
    output_callback=log_output
)
```

### Retry on Failures

```python
# Automatic retries for transient errors
result = executor.execute_with_retries(
    prompt="Generate code...",
    max_retries=3,
    retry_delay=5  # seconds between retries
)
```

## API Reference

### ClaudeExecutor

```python
ClaudeExecutor(
    command: str = "claude --dangerously-skip-permissions",
    working_dir: Optional[Path] = None,
    default_timeout: int = 1800
)
```

#### Parameters

- **command** - Claude CLI command to execute
- **working_dir** - Working directory for execution (defaults to current directory)
- **default_timeout** - Default timeout in seconds (default: 1800 = 30 minutes)

#### Methods

##### execute()

```python
execute(
    prompt: str,
    timeout: Optional[int] = None,
    task_id: Optional[str] = None,
    capture_output: bool = True
) -> ExecutionResult
```

Execute Claude CLI with the given prompt.

**Parameters:**
- **prompt** - Prompt text to send to Claude
- **timeout** - Timeout in seconds (uses default if None)
- **task_id** - Optional task ID for logging
- **capture_output** - Whether to capture stdout/stderr

**Returns:** `ExecutionResult` with output and status

**Raises:**
- `ClaudeTimeoutError` - If execution exceeds timeout
- `ClaudeExecutionError` - If execution fails

##### execute_with_streaming()

```python
execute_with_streaming(
    prompt: str,
    timeout: Optional[int] = None,
    task_id: Optional[str] = None,
    output_callback: Optional[callable] = None
) -> ExecutionResult
```

Execute with real-time output streaming.

**Parameters:**
- **output_callback** - Function called for each line of output

##### execute_with_retries()

```python
execute_with_retries(
    prompt: str,
    max_retries: int = 3,
    timeout: Optional[int] = None,
    task_id: Optional[str] = None,
    retry_delay: int = 5
) -> ExecutionResult
```

Execute with automatic retries on transient failures.

**Retryable Errors:**
- Network timeouts
- Connection errors
- Service unavailable
- Rate limits

**Non-Retryable Errors:**
- Syntax errors
- Permission denied
- Invalid prompts

### ExecutionResult

Result object returned by executor methods.

```python
@dataclass
class ExecutionResult:
    success: bool                    # True if exit code 0
    stdout: str                      # Standard output
    stderr: str                      # Standard error
    exit_code: int                   # Process exit code
    duration_seconds: float          # Execution time
    error_message: Optional[str]     # Error description if failed
```

#### Methods

##### parse_json()

```python
result.parse_json() -> Dict[str, Any]
```

Parse JSON from stdout (strict, raises error if not found).

##### parse_json_safe()

```python
result.parse_json_safe() -> Optional[Dict[str, Any]]
```

Parse JSON from stdout (returns None if parsing fails).

##### validation_passed()

```python
result.validation_passed() -> bool
```

Check if validation passed based on output content.

### OutputParser

Utility class for parsing Claude output.

#### Methods

##### extract_json()

```python
OutputParser.extract_json(output: str, strict: bool = True) -> Dict[str, Any]
```

Extract JSON from output, handling code blocks and surrounding text.

**Examples:**

```python
# From code block
output = '''Here's the result:
```json
{"status": "ok"}
```
'''
result = OutputParser.extract_json(output)
# {"status": "ok"}

# From raw output
output = 'The answer is: {"value": 42}'
result = OutputParser.extract_json(output)
# {"value": 42}

# With strict=False
output = "No JSON here"
result = OutputParser.extract_json(output, strict=False)
# {}
```

##### extract_code_blocks()

```python
OutputParser.extract_code_blocks(
    output: str,
    language: Optional[str] = None
) -> List[str]
```

Extract code blocks from output.

```python
output = '''```python
def hello():
    print("world")
```'''

blocks = OutputParser.extract_code_blocks(output, language="python")
# ["def hello():\n    print(\"world\")"]
```

##### find_validation_result()

```python
OutputParser.find_validation_result(output: str) -> bool
```

Determine if validation passed based on output.

Looks for patterns like:
- "validation passed"
- "all tests pass"
- `"validation_passed": true` in JSON
- "recommendation: COMPLETE"

## Configuration

### From Config File

```yaml
claude:
  command: "claude --dangerously-skip-permissions"
  working_dir: "."
  timeout: "30m"
```

```python
from fsd.config.loader import load_config

config = load_config()

executor = ClaudeExecutor(
    command=config.claude.command,
    working_dir=config.claude.working_dir,
    default_timeout=parse_duration(config.claude.timeout)
)
```

### Environment-Specific Commands

```python
import os

# Use different commands for different environments
if os.getenv("CI"):
    command = "claude --ci-mode"
elif os.getenv("DEBUG"):
    command = "claude --verbose"
else:
    command = "claude --dangerously-skip-permissions"

executor = ClaudeExecutor(command=command)
```

## Error Handling

### Exception Hierarchy

```
Exception
└── FSDError
    └── ExecutionError
        └── ClaudeExecutionError
            ├── ClaudeTimeoutError
            └── ClaudeOutputParseError
```

### Handling Errors

```python
from fsd.core.exceptions import (
    ClaudeExecutionError,
    ClaudeTimeoutError,
    ClaudeOutputParseError,
)

try:
    result = executor.execute(prompt, timeout=60)

    if result.success:
        data = result.parse_json()
        # Process data...
    else:
        # Handle non-zero exit code
        log.error(f"Execution failed: {result.error_message}")

except ClaudeTimeoutError as e:
    # Handle timeout specifically
    log.error(f"Timed out after 60s: {e}")
    # Maybe retry with longer timeout or different approach

except ClaudeOutputParseError as e:
    # Handle JSON parsing errors
    log.error(f"Could not parse output: {e}")
    log.debug(f"Raw output: {result.stdout}")

except ClaudeExecutionError as e:
    # Handle other execution errors
    log.error(f"Execution error: {e}")
```

## Examples

### Planning Phase

```python
from fsd.core.prompt_loader import load_prompt
from fsd.core.claude_executor import ClaudeExecutor

executor = ClaudeExecutor(default_timeout=300)  # 5 minutes for planning

# Load planning prompt
prompt = load_prompt(
    "planning",
    task_id="refactor-auth",
    description="Refactor authentication module",
    priority="medium",
    estimated_duration="4h"
)

# Execute
result = executor.execute(prompt, task_id="refactor-auth")

if result.success:
    plan = result.parse_json()

    print(f"Generated plan with {len(plan['steps'])} steps")
    print(f"Estimated time: {plan['estimated_total_time']}")
    print(f"Complexity: {plan['complexity']}")

    # Save plan
    with open(f".fsd/plans/refactor-auth.json", "w") as f:
        json.dump(plan, f, indent=2)
else:
    print(f"Planning failed: {result.error_message}")
```

### Execution Phase

```python
# Execute a specific step
step = plan["steps"][0]

prompt = load_prompt(
    "execution",
    task_id="refactor-auth",
    description=task.description,
    step_number=step["step_number"],
    total_steps=len(plan["steps"]),
    step_description=step["description"],
    step_duration=step["estimated_duration"],
    step_files=", ".join(step["files_to_modify"]),
    step_validation=step["validation"],
    step_checkpoint=step.get("checkpoint", False),
    plan_summary=plan["analysis"]
)

# Execute with longer timeout for code generation
result = executor.execute(prompt, timeout=1800, task_id="refactor-auth")

if result.success:
    print("Step completed successfully")
    # Create checkpoint if specified
    if step.get("checkpoint"):
        checkpoint_manager.create_checkpoint(...)
```

### Validation Phase

```python
# Run validation
prompt = load_prompt(
    "validation",
    task_id="refactor-auth",
    description=task.description,
    priority=task.priority,
    success_criteria=task.success_criteria
)

result = executor.execute(prompt, timeout=600, task_id="refactor-auth")

if result.success:
    validation = result.parse_json()

    if validation["validation_passed"]:
        print("✓ Validation passed!")
        state_machine.transition(task_id, TaskState.COMPLETED)
    else:
        print("✗ Validation failed")
        print(f"Failed checks: {validation['failed_checks']}")

        # Trigger recovery
        if retry_count < max_retries:
            state_machine.transition(task_id, TaskState.EXECUTING)
```

## Best Practices

### 1. Use Appropriate Timeouts

Different phases need different timeouts:

```python
# Planning: 5-10 minutes
planning_result = executor.execute(prompt, timeout=300)

# Execution: 30-60 minutes (depends on complexity)
execution_result = executor.execute(prompt, timeout=1800)

# Validation: 10-15 minutes
validation_result = executor.execute(prompt, timeout=600)
```

### 2. Always Check Success

```python
result = executor.execute(prompt)

if not result.success:
    # Handle failure before trying to parse
    log.error(f"Execution failed: {result.error_message}")
    log.debug(f"stderr: {result.stderr}")
    return

# Safe to parse now
data = result.parse_json()
```

### 3. Use Retries for Network Issues

```python
# Retry automatically for transient failures
result = executor.execute_with_retries(
    prompt=prompt,
    max_retries=3,
    retry_delay=5
)
```

### 4. Stream Output for Long Operations

```python
def progress_logger(line):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {line}")

result = executor.execute_with_streaming(
    prompt=long_running_prompt,
    output_callback=progress_logger
)
```

### 5. Validate Claude Availability

```python
executor = ClaudeExecutor()

if not executor.validate_claude_available():
    raise ConfigurationError(
        "Claude CLI not found. Please install Claude Code."
    )
```

## Troubleshooting

### Claude CLI Not Found

```
ClaudeExecutionError: Claude CLI not found. Is it installed?
```

**Solution:**
- Install Claude Code CLI
- Verify it's in PATH: `which claude`
- Or specify full path in config:
  ```yaml
  claude:
    command: "/usr/local/bin/claude --dangerously-skip-permissions"
  ```

### Timeouts

```
ClaudeTimeoutError: Claude execution timed out after 1800s
```

**Solutions:**
- Increase timeout for complex tasks
- Break task into smaller steps
- Check if Claude is hanging on user input

### JSON Parsing Errors

```
ClaudeOutputParseError: No valid JSON found in output
```

**Solutions:**
- Check prompt asks for JSON explicitly
- Review Claude's output: `print(result.stdout)`
- Try non-strict parsing: `result.parse_json_safe()`
- Update prompt template to be clearer about JSON format

### Permission Errors

```
ClaudeExecutionError: Permission denied
```

**Solutions:**
- Ensure `--dangerously-skip-permissions` flag is used
- Check file permissions in working directory
- Verify Claude has access to project files

## See Also

- [Prompt Templates](./prompt-templates.md)
- [Task Execution Flow](./orchestration.md)
- [Configuration Reference](./example-config.yaml)
- [Claude Code Documentation](https://docs.claude.ai/claude-code)
