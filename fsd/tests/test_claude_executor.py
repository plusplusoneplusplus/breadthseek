"""Tests for Claude CLI executor and output parser."""

import json
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from fsd.core.claude_executor import ClaudeExecutor, ExecutionResult
from fsd.core.output_parser import OutputParser
from fsd.core.exceptions import (
    ClaudeExecutionError,
    ClaudeOutputParseError,
    ClaudeTimeoutError,
)


class TestOutputParser:
    """Test output parsing functionality."""

    def test_extract_json_from_code_block(self):
        """Test extracting JSON from markdown code block."""
        output = '''Here is the plan:

```json
{
  "task_id": "test-123",
  "steps": [
    {"step_number": 1, "description": "First step"}
  ]
}
```

That's the plan!'''

        result = OutputParser.extract_json(output)
        assert result["task_id"] == "test-123"
        assert len(result["steps"]) == 1

    def test_extract_json_without_language_tag(self):
        """Test extracting JSON from code block without language tag."""
        output = '''```
{
  "name": "test",
  "value": 42
}
```'''

        result = OutputParser.extract_json(output)
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_extract_json_raw(self):
        """Test extracting raw JSON without code blocks."""
        output = '''The result is:
{
  "status": "success",
  "count": 5
}
Done.'''

        result = OutputParser.extract_json(output)
        assert result["status"] == "success"
        assert result["count"] == 5

    def test_extract_json_strict_failure(self):
        """Test that strict mode raises error when no JSON found."""
        output = "This is just text with no JSON at all."

        with pytest.raises(ClaudeOutputParseError, match="No valid JSON found"):
            OutputParser.extract_json(output, strict=True)

    def test_extract_json_non_strict(self):
        """Test that non-strict mode returns empty dict when no JSON."""
        output = "No JSON here!"

        result = OutputParser.extract_json(output, strict=False)
        assert result == {}

    def test_extract_json_array(self):
        """Test extracting JSON array."""
        output = '''```json
[
  {"id": 1, "name": "first"},
  {"id": 2, "name": "second"}
]
```'''

        result = OutputParser.extract_json(output)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == 1

    def test_extract_json_with_nested_braces(self):
        """Test handling nested braces in JSON."""
        output = '''```json
{
  "outer": {
    "inner": {
      "value": "nested"
    }
  }
}
```'''

        result = OutputParser.extract_json(output)
        assert result["outer"]["inner"]["value"] == "nested"

    def test_extract_json_list(self):
        """Test extract_json_list method."""
        output = '''```json
[{"a": 1}, {"a": 2}]
```'''

        result = OutputParser.extract_json_list(output)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_extract_json_list_from_object(self):
        """Test that single object gets wrapped in list."""
        output = '{"a": 1}'

        result = OutputParser.extract_json_list(output)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["a"] == 1

    def test_extract_code_blocks(self):
        """Test extracting code blocks."""
        output = '''Here's some Python:

```python
def hello():
    print("world")
```

And some JavaScript:

```javascript
console.log("hello");
```'''

        python_blocks = OutputParser.extract_code_blocks(output, language="python")
        assert len(python_blocks) == 1
        assert "def hello()" in python_blocks[0]

        all_blocks = OutputParser.extract_code_blocks(output)
        assert len(all_blocks) == 2

    def test_extract_sections(self):
        """Test extracting markdown sections."""
        output = '''# Title

Preamble content

## Section One

Content of section one

## Section Two

Content of section two'''

        sections = OutputParser.extract_sections(output)
        assert "section_one" in sections
        assert "section_two" in sections
        assert "Content of section one" in sections["section_one"]

    def test_find_validation_result_pass(self):
        """Test detecting validation pass."""
        output = '''Validation complete:
- All tests passed
- No linting errors

validation_passed: true'''

        assert OutputParser.find_validation_result(output) is True

    def test_find_validation_result_fail(self):
        """Test detecting validation failure."""
        output = '''Validation failed:
- 3 tests failed
- Type errors found'''

        assert OutputParser.find_validation_result(output) is False

    def test_find_validation_result_from_json(self):
        """Test detecting validation from JSON output."""
        output = '''```json
{
  "validation_passed": true,
  "tests": {"passed": 10, "failed": 0}
}
```'''

        assert OutputParser.find_validation_result(output) is True

    def test_sanitize_output(self):
        """Test output sanitization."""
        output = "Hello\x1B[31mRed Text\x1B[0m World"

        sanitized = OutputParser.sanitize_output(output)
        assert "Red Text" in sanitized
        assert "\x1B" not in sanitized

    def test_sanitize_output_truncation(self):
        """Test output truncation."""
        output = "A" * 20000

        sanitized = OutputParser.sanitize_output(output, max_length=1000)
        assert len(sanitized) < 1200  # Truncated + message
        assert "truncated" in sanitized


class TestExecutionResult:
    """Test ExecutionResult dataclass."""

    def test_parse_json(self):
        """Test parsing JSON from result."""
        result = ExecutionResult(
            success=True,
            stdout='{"status": "ok"}',
            stderr="",
            exit_code=0,
            duration_seconds=1.5,
        )

        parsed = result.parse_json()
        assert parsed["status"] == "ok"

    def test_parse_json_safe(self):
        """Test safe JSON parsing."""
        result = ExecutionResult(
            success=True,
            stdout="Not JSON",
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
        )

        parsed = result.parse_json_safe()
        assert parsed is None or parsed == {}

    def test_validation_passed(self):
        """Test validation result detection."""
        result = ExecutionResult(
            success=True,
            stdout='{"validation_passed": true}',
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
        )

        assert result.validation_passed() is True


class TestClaudeExecutor:
    """Test Claude executor."""

    @pytest.fixture
    def executor(self):
        """Create Claude executor for testing."""
        return ClaudeExecutor(
            command="claude --dangerously-skip-permissions",
            default_timeout=30,
        )

    @patch("subprocess.Popen")
    def test_execute_success(self, mock_popen, executor):
        """Test successful execution."""
        # Mock process
        mock_process = Mock()
        mock_process.communicate.return_value = ('{"result": "ok"}', "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = executor.execute("Test prompt")

        assert result.success is True
        assert result.exit_code == 0
        assert '{"result": "ok"}' in result.stdout
        assert result.error_message is None

    @patch("subprocess.Popen")
    def test_execute_failure(self, mock_popen, executor):
        """Test execution failure."""
        mock_process = Mock()
        mock_process.communicate.return_value = ("", "Error occurred")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        result = executor.execute("Test prompt")

        assert result.success is False
        assert result.exit_code == 1
        assert result.error_message is not None
        assert "Error occurred" in result.error_message

    @patch("subprocess.Popen")
    def test_execute_timeout(self, mock_popen, executor):
        """Test execution timeout."""
        mock_process = Mock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="claude", timeout=5
        )
        mock_popen.return_value = mock_process

        with pytest.raises(ClaudeTimeoutError, match="timed out"):
            executor.execute("Test prompt", timeout=5)

    @patch("subprocess.Popen")
    def test_execute_with_task_id(self, mock_popen, executor):
        """Test execution with task ID for logging."""
        mock_process = Mock()
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = executor.execute("Test prompt", task_id="test-123")

        assert result.success is True
        # Task ID is used for logging/debugging

    @patch("subprocess.Popen")
    def test_execute_claude_not_found(self, mock_popen, executor):
        """Test handling of Claude CLI not found."""
        mock_popen.side_effect = FileNotFoundError("claude not found")

        with pytest.raises(ClaudeExecutionError, match="not found"):
            executor.execute("Test prompt")

    @patch("subprocess.Popen")
    def test_execute_with_streaming(self, mock_popen, executor):
        """Test execution with output streaming."""
        mock_process = Mock()
        mock_process.stdout = iter(["Line 1\n", "Line 2\n", ""])
        mock_process.stderr = iter([])
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        captured_lines = []

        def callback(line):
            captured_lines.append(line)

        result = executor.execute_with_streaming(
            "Test prompt",
            output_callback=callback,
        )

        assert result.success is True
        assert len(captured_lines) == 2

    @patch("subprocess.Popen")
    def test_execute_with_retries_success_first_try(self, mock_popen, executor):
        """Test retries when first attempt succeeds."""
        mock_process = Mock()
        mock_process.communicate.return_value = ("success", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = executor.execute_with_retries("Test prompt", max_retries=3)

        assert result.success is True
        assert mock_popen.call_count == 1  # Only called once

    @patch("subprocess.Popen")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_execute_with_retries_success_after_failure(
        self, mock_sleep, mock_popen, executor
    ):
        """Test retries after initial failure."""
        # First call fails, second succeeds
        mock_process1 = Mock()
        mock_process1.communicate.return_value = ("", "Temporary network error")
        mock_process1.returncode = 1

        mock_process2 = Mock()
        mock_process2.communicate.return_value = ("success", "")
        mock_process2.returncode = 0

        mock_popen.side_effect = [mock_process1, mock_process2]

        result = executor.execute_with_retries("Test prompt", max_retries=3)

        assert result.success is True
        assert mock_popen.call_count == 2

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_execute_with_retries_all_fail(self, mock_sleep, mock_popen, executor):
        """Test retries when all attempts fail."""
        mock_process = Mock()
        mock_process.communicate.return_value = ("", "Network error")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        with pytest.raises(ClaudeExecutionError, match="Failed after.*retries"):
            executor.execute_with_retries("Test prompt", max_retries=2)

        assert mock_popen.call_count == 3  # Initial + 2 retries

    def test_is_retryable_error(self, executor):
        """Test determining if errors are retryable."""
        # Retryable errors
        assert executor._is_retryable_error(Exception("connection timeout"))
        assert executor._is_retryable_error(Exception("network unreachable"))
        assert executor._is_retryable_error(Exception("rate limit exceeded"))
        assert executor._is_retryable_error(Exception("service unavailable"))

        # Non-retryable errors
        assert not executor._is_retryable_error(Exception("invalid syntax"))
        assert not executor._is_retryable_error(Exception("permission denied"))
        assert not executor._is_retryable_error(Exception("file not found"))

    @patch("subprocess.run")
    def test_validate_claude_available_success(self, mock_run, executor):
        """Test checking if Claude is available."""
        mock_run.return_value = Mock(returncode=0)

        assert executor.validate_claude_available() is True

    @patch("subprocess.run")
    def test_validate_claude_available_failure(self, mock_run, executor):
        """Test checking when Claude is not available."""
        mock_run.side_effect = FileNotFoundError()

        assert executor.validate_claude_available() is False


class TestIntegration:
    """Integration tests (can be skipped in CI)."""

    @pytest.mark.skip(reason="Requires Claude CLI installed")
    def test_real_claude_execution(self):
        """Test with real Claude CLI (manual/optional test)."""
        executor = ClaudeExecutor()

        # Simple test prompt
        result = executor.execute("What is 2+2? Reply with just the number.")

        assert result.success is True
        assert "4" in result.stdout

    @pytest.mark.skip(reason="Requires Claude CLI installed")
    def test_real_claude_json_output(self):
        """Test JSON output parsing with real Claude."""
        executor = ClaudeExecutor()

        prompt = """Please respond with this exact JSON:
{"test": true, "value": 42}"""

        result = executor.execute(prompt)

        parsed = result.parse_json()
        assert parsed["test"] is True
        assert parsed["value"] == 42
