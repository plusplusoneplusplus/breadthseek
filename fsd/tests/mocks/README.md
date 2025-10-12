# Mock-Based Testing for AI Executor

This directory provides a comprehensive mock-based testing framework for the Claude AI executor. The mock system allows you to write deterministic, repeatable unit tests without making actual API calls.

## Overview

The mock system provides:

1. **MockClaudeExecutor**: A drop-in replacement for `ClaudeExecutor` that returns predefined responses
2. **MockResponseLibrary**: Pre-built responses for common scenarios
3. **MockSubprocess**: Utilities for mocking subprocess calls
4. **Pytest Fixtures**: Easy-to-use fixtures for testing

## Quick Start

### Basic Usage

```python
from tests.mocks import MockClaudeExecutor, MockResponseLibrary

def test_basic_execution(mock_executor):
    """Test with deterministic response."""
    # Setup: Add a mock response
    response = MockResponseLibrary.task_parsing_success(
        task_id="test-task",
        description="Test description",
        priority="high"
    )
    mock_executor.add_response("parse", response)

    # Execute
    result = mock_executor.execute("parse this task")

    # Verify
    assert result.success
    assert "test-task" in result.stdout
```

### Using Pytest Fixtures

The mock fixtures are available globally via `conftest.py`:

```python
def test_with_fixture(mock_executor, mock_responses):
    """Test using pytest fixtures."""
    # mock_executor is a fresh MockClaudeExecutor
    # mock_responses is the MockResponseLibrary class

    response = mock_responses.validation_success(tests_passed=10)
    mock_executor.add_response("validate", response)

    result = mock_executor.execute("validate the code")
    assert result.validation_passed()
```

## MockClaudeExecutor

### Adding Responses

#### Single Response per Pattern

```python
mock_executor.add_response(
    "pattern",  # String to match in prompt (case-insensitive)
    MockResponseLibrary.json_response({"status": "ok"})
)
```

#### Sequential Responses

Return different responses for the same pattern:

```python
mock_executor.add_response(
    "parse",
    [
        MockResponseLibrary.task_parsing_success(task_id="first"),
        MockResponseLibrary.task_parsing_success(task_id="second"),
    ]
)

# First call returns "first", second call returns "second"
result1 = mock_executor.execute("parse task 1")
result2 = mock_executor.execute("parse task 2")
```

#### Default Response

Set a fallback response when no pattern matches:

```python
mock_executor.set_default_response(
    MockResponseLibrary.json_response({"default": True})
)
```

### Inspecting Call History

```python
# Execute some calls
mock_executor.execute("test 1", task_id="task-1")
mock_executor.execute("test 2", timeout=60)

# Get call history
history = mock_executor.get_call_history()
assert len(history) == 2
assert history[0]["task_id"] == "task-1"
assert history[1]["timeout"] == 60

# Assert a pattern was called
mock_executor.assert_called_with_pattern("test 1")
```

## MockResponseLibrary

Pre-built responses for common scenarios:

### Task Parsing

```python
response = MockResponseLibrary.task_parsing_success(
    task_id="fix-bug",
    description="Fix authentication bug",
    priority="high",
    duration="30m",
    context="User login fails with 500 error",
    focus_files=["auth.py", "tests/test_auth.py"],
    success_criteria="All auth tests pass",
    pr_title="fix: Fix authentication bug"
)
```

### Validation Results

```python
response = MockResponseLibrary.validation_success(
    validation_passed=True,
    tests_passed=15,
    tests_failed=0,
    lint_errors=0,
    type_errors=0
)
```

### Code Generation

```python
response = MockResponseLibrary.code_generation(
    language="python",
    code="def hello():\n    print('world')",
    explanation="Simple greeting function"
)
```

### Generic JSON Response

```python
response = MockResponseLibrary.json_response({
    "status": "success",
    "data": {"key": "value"}
})
```

### Error Responses

```python
# Generic error
error = MockResponseLibrary.error_response(
    error_message="Command failed",
    exit_code=1
)

# Network error (retryable)
network_error = MockResponseLibrary.network_error()

# Rate limit error (retryable)
rate_limit = MockResponseLibrary.rate_limit_error()

# Timeout
timeout = MockResponseLibrary.timeout_response()
```

## Mocking Subprocess Calls

For code that uses `subprocess.Popen` directly (like `AITaskParser`):

```python
from unittest.mock import patch
from tests.mocks import create_mock_popen, MockResponseLibrary

def test_with_subprocess_mock():
    """Test code that uses subprocess directly."""
    response = MockResponseLibrary.task_parsing_success()

    with patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value = create_mock_popen(response)()

        # Your test code here
        parser = AITaskParser()
        task = parser.parse_task("Fix bug")

        assert task.id == "fix-login-bug"
```

## Complete Workflow Examples

### Task Parsing → Validation Workflow

```python
def test_complete_workflow(mock_executor):
    """Test multi-step workflow with deterministic responses."""
    # Setup responses for each step
    mock_executor.add_response(
        "parse",
        MockResponseLibrary.task_parsing_success(task_id="workflow-test")
    )
    mock_executor.add_response(
        "implement",
        MockResponseLibrary.code_generation(code="# implementation")
    )
    mock_executor.add_response(
        "validate",
        MockResponseLibrary.validation_success()
    )

    # Execute workflow
    parse_result = mock_executor.execute("parse: implement feature")
    impl_result = mock_executor.execute("implement the feature")
    val_result = mock_executor.execute("validate changes")

    # Verify each step
    assert "workflow-test" in parse_result.stdout
    assert "implementation" in impl_result.stdout
    assert val_result.validation_passed()

    # Verify execution order
    history = mock_executor.get_call_history()
    assert len(history) == 3
```

### Testing Retry Logic

```python
def test_retry_with_sequential_responses(mock_executor):
    """Test retry logic with sequential responses."""
    # First call fails, second succeeds
    mock_executor.add_response(
        "test",
        [
            MockResponseLibrary.network_error(),
            MockResponseLibrary.json_response({"status": "ok"})
        ]
    )

    # Simulate retry logic
    result1 = mock_executor.execute("test request")
    assert not result1.success  # First fails

    result2 = mock_executor.execute("test request")
    assert result2.success  # Second succeeds
```

## Custom Mock Responses

Create custom responses for specific scenarios:

```python
from tests.mocks import MockResponse

custom_response = MockResponse(
    stdout='{"custom": "response"}',
    stderr="",
    exit_code=0,
    duration_seconds=1.5
)

mock_executor.add_response("custom", custom_response)
```

## Integration with Real ClaudeExecutor

You can patch the real `ClaudeExecutor` to use mock responses:

```python
from unittest.mock import patch
from fsd.core.claude_executor import ClaudeExecutor
from tests.mocks import create_mock_popen, MockResponseLibrary

def test_real_executor_with_mock():
    """Test real ClaudeExecutor with mocked subprocess."""
    response = MockResponseLibrary.validation_success()

    with patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value = create_mock_popen(response)()

        executor = ClaudeExecutor()
        result = executor.execute("Test")

        assert result.success
        assert result.validation_passed()
```

## Best Practices

### 1. Use Fixtures

Always use the `mock_executor` fixture for automatic cleanup:

```python
def test_with_fixture(mock_executor):
    # Executor is automatically reset after test
    pass
```

### 2. Make Responses Deterministic

Ensure responses are predictable:

```python
# Good - Explicit, deterministic
response = MockResponseLibrary.task_parsing_success(
    task_id="specific-id",
    description="Specific description"
)

# Avoid - Uses random/default values
response = MockResponseLibrary.task_parsing_success()
```

### 3. Test Edge Cases

Use mock responses to test edge cases:

```python
def test_edge_cases(mock_executor):
    # Empty response
    mock_executor.add_response("empty", MockResponse(stdout="", exit_code=0))

    # Malformed JSON
    mock_executor.add_response("bad", MockResponse(stdout="{invalid json}", exit_code=0))

    # Large response
    large_data = {"items": [{"id": i} for i in range(1000)]}
    mock_executor.add_response("large", MockResponseLibrary.json_response(large_data))
```

### 4. Verify Call History

Always verify that the right calls were made:

```python
def test_verify_calls(mock_executor):
    mock_executor.add_response("test", MockResponseLibrary.json_response({}))

    mock_executor.execute("test prompt", task_id="task-1")

    # Verify the call
    mock_executor.assert_called_with_pattern("test")

    history = mock_executor.get_call_history()
    assert history[0]["task_id"] == "task-1"
```

## Running Tests

Run all mock-based tests:

```bash
# Run all tests
uv run pytest tests/test_claude_executor_mock.py -v

# Run specific test class
uv run pytest tests/test_claude_executor_mock.py::TestMockClaudeExecutor -v

# Run with coverage
uv run pytest tests/test_claude_executor_mock.py --cov=fsd.core.claude_executor
```

## Troubleshooting

### Issue: Pattern Not Matching

If your pattern isn't matching:

```python
# Check call history
history = mock_executor.get_call_history()
print([call["prompt"] for call in history])

# Patterns are case-insensitive
mock_executor.add_response("TEST", response)  # Matches "test", "Test", "TEST"
```

### Issue: Wrong Response Returned

For sequential responses, verify the order:

```python
responses = [response1, response2, response3]
mock_executor.add_response("pattern", responses)

# First call → response1
# Second call → response2
# Third call → response3
# Fourth+ calls → response3 (last response repeats)
```

### Issue: Import Errors

Ensure the mocks module is importable:

```python
# Add to your test file
import sys
from pathlib import Path

# Ensure tests directory is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.mocks import MockClaudeExecutor
```

## API Reference

### MockClaudeExecutor

- `add_response(pattern: str, response: Union[MockResponse, List[MockResponse]])` - Add mock response for pattern
- `set_default_response(response: MockResponse)` - Set default fallback response
- `execute(prompt: str, **kwargs) -> ExecutionResult` - Execute with mock response
- `get_call_history() -> List[Dict]` - Get all execute calls
- `assert_called_with_pattern(pattern: str)` - Assert pattern was called
- `reset()` - Clear all responses and history

### MockResponseLibrary

- `task_parsing_success(**kwargs) -> MockResponse` - Task parsing response
- `validation_success(**kwargs) -> MockResponse` - Validation result
- `code_generation(**kwargs) -> MockResponse` - Code generation response
- `json_response(data: Dict) -> MockResponse` - Generic JSON response
- `error_response(**kwargs) -> MockResponse` - Error response
- `network_error() -> MockResponse` - Network error (retryable)
- `rate_limit_error() -> MockResponse` - Rate limit error
- `timeout_response() -> MockResponse` - Timeout scenario

### MockResponse

```python
@dataclass
class MockResponse:
    stdout: str
    stderr: str = ""
    exit_code: int = 0
    duration_seconds: float = 1.0

    def to_execution_result() -> ExecutionResult
```

## Contributing

When adding new mock responses:

1. Add the response to `MockResponseLibrary`
2. Add a test demonstrating its use
3. Update this documentation
4. Ensure the response is deterministic
