"""Mock helpers for testing Claude AI executor.

This module provides deterministic mock responses and utilities for testing
the Claude executor and AI-powered components without making actual CLI calls.
"""

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union
from unittest.mock import Mock

from fsd.core.claude_executor import ExecutionResult
from fsd.core.task_schema import TaskDefinition, Priority, CompletionActions


@dataclass
class MockResponse:
    """A deterministic mock response for Claude CLI."""

    stdout: str
    stderr: str = ""
    exit_code: int = 0
    duration_seconds: float = 1.0

    def to_execution_result(self) -> ExecutionResult:
        """Convert to ExecutionResult."""
        return ExecutionResult(
            success=self.exit_code == 0,
            stdout=self.stdout,
            stderr=self.stderr,
            exit_code=self.exit_code,
            duration_seconds=self.duration_seconds,
            error_message=self.stderr if self.exit_code != 0 else None,
        )


class MockResponseLibrary:
    """Library of deterministic mock responses for common scenarios."""

    @staticmethod
    def task_parsing_success(
        task_id: str = "fix-login-bug",
        description: str = "Fix login bug in auth.py",
        priority: str = "high",
        duration: str = "30m",
        context: Optional[str] = None,
        focus_files: Optional[List[str]] = None,
        success_criteria: Optional[str] = None,
        pr_title: Optional[str] = None,
    ) -> MockResponse:
        """Create a successful task parsing response."""
        if focus_files is None:
            focus_files = ["auth.py"]
        if pr_title is None:
            pr_title = f"fix: {description}"

        data = {
            "id": task_id,
            "description": description,
            "priority": priority,
            "estimated_duration": duration,
            "context": context,
            "focus_files": focus_files,
            "success_criteria": success_criteria,
            "pr_title": pr_title,
        }

        return MockResponse(
            stdout=json.dumps(data, indent=2),
            exit_code=0,
            duration_seconds=0.5,
        )

    @staticmethod
    def validation_success(
        validation_passed: bool = True,
        tests_passed: int = 10,
        tests_failed: int = 0,
        lint_errors: int = 0,
        type_errors: int = 0,
    ) -> MockResponse:
        """Create a validation result response."""
        data = {
            "validation_passed": validation_passed,
            "tests": {"passed": tests_passed, "failed": tests_failed},
            "lint_errors": lint_errors,
            "type_errors": type_errors,
        }

        output = f"""Validation complete:
- Tests: {tests_passed} passed, {tests_failed} failed
- Lint errors: {lint_errors}
- Type errors: {type_errors}

```json
{json.dumps(data, indent=2)}
```

validation_passed: {str(validation_passed).lower()}
"""

        return MockResponse(
            stdout=output,
            exit_code=0 if validation_passed else 1,
            duration_seconds=2.5,
        )

    @staticmethod
    def code_generation(
        language: str = "python",
        code: str = "def hello():\n    print('Hello, World!')",
        explanation: str = "Simple hello world function",
    ) -> MockResponse:
        """Create a code generation response."""
        output = f"""{explanation}

```{language}
{code}
```

This code provides the requested functionality.
"""

        return MockResponse(
            stdout=output,
            exit_code=0,
            duration_seconds=1.5,
        )

    @staticmethod
    def json_response(data: Dict[str, Any]) -> MockResponse:
        """Create a response with JSON data."""
        return MockResponse(
            stdout=json.dumps(data, indent=2),
            exit_code=0,
            duration_seconds=0.8,
        )

    @staticmethod
    def error_response(
        error_message: str = "Command failed",
        exit_code: int = 1,
    ) -> MockResponse:
        """Create an error response."""
        return MockResponse(
            stdout="",
            stderr=error_message,
            exit_code=exit_code,
            duration_seconds=0.2,
        )

    @staticmethod
    def timeout_response() -> MockResponse:
        """Create a timeout scenario (raises exception in mock)."""
        # This will be handled by the mock executor to raise TimeoutExpired
        return MockResponse(
            stdout="",
            stderr="Timeout",
            exit_code=124,  # Timeout exit code
            duration_seconds=30.0,
        )

    @staticmethod
    def network_error() -> MockResponse:
        """Create a network error response."""
        return MockResponse(
            stdout="",
            stderr="Network connection failed: Unable to reach API server",
            exit_code=1,
            duration_seconds=5.0,
        )

    @staticmethod
    def rate_limit_error() -> MockResponse:
        """Create a rate limit error response."""
        return MockResponse(
            stdout="",
            stderr="Rate limit exceeded. Please try again later.",
            exit_code=1,
            duration_seconds=0.5,
        )


class MockClaudeExecutor:
    """Mock Claude executor for deterministic testing.

    This class mimics the ClaudeExecutor interface but returns predefined
    responses instead of calling the actual Claude CLI.

    Example:
        >>> executor = MockClaudeExecutor()
        >>> executor.add_response("parse task", MockResponseLibrary.task_parsing_success())
        >>> result = executor.execute("parse task for login bug")
        >>> assert result.success
    """

    def __init__(self):
        """Initialize mock executor."""
        self.responses: Dict[str, Union[MockResponse, List[MockResponse]]] = {}
        self.default_response: Optional[MockResponse] = None
        self.call_history: List[Dict[str, Any]] = []
        self.call_count = 0

    def add_response(
        self,
        prompt_pattern: str,
        response: Union[MockResponse, List[MockResponse]],
    ) -> None:
        """Add a mock response for a specific prompt pattern.

        Args:
            prompt_pattern: String to match in the prompt (case-insensitive)
            response: MockResponse or list of MockResponses to return in sequence
        """
        self.responses[prompt_pattern.lower()] = response

    def set_default_response(self, response: MockResponse) -> None:
        """Set the default response when no pattern matches."""
        self.default_response = response

    def execute(
        self,
        prompt: str,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        capture_output: bool = True,
    ) -> ExecutionResult:
        """Execute mock Claude CLI with predefined response.

        Args:
            prompt: Prompt to send to Claude
            timeout: Timeout in seconds (unused in mock)
            task_id: Optional task ID for logging
            capture_output: Whether to capture output (unused in mock)

        Returns:
            ExecutionResult from predefined mock response
        """
        self.call_count += 1
        self.call_history.append({
            "prompt": prompt,
            "timeout": timeout,
            "task_id": task_id,
            "capture_output": capture_output,
        })

        # Find matching response
        prompt_lower = prompt.lower()
        for pattern, response in self.responses.items():
            if pattern in prompt_lower:
                # Handle list of responses (for sequential calls)
                if isinstance(response, list):
                    # Get next response in sequence
                    # Count how many times this pattern was called
                    pattern_calls = sum(
                        1 for call in self.call_history
                        if pattern in call["prompt"].lower()
                    )
                    index = min(pattern_calls - 1, len(response) - 1)
                    return response[index].to_execution_result()
                else:
                    return response.to_execution_result()

        # Use default response if set
        if self.default_response:
            return self.default_response.to_execution_result()

        # No response found - return generic success
        return MockResponseLibrary.json_response(
            {"status": "ok", "message": "Mock response"}
        ).to_execution_result()

    def execute_with_streaming(
        self,
        prompt: str,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        output_callback: Optional[Callable] = None,
    ) -> ExecutionResult:
        """Execute with streaming (mock implementation).

        In mock mode, streaming just calls the callback with all lines at once.
        """
        result = self.execute(prompt, timeout, task_id)

        # Call callback with each line if provided
        if output_callback and result.stdout:
            for line in result.stdout.splitlines():
                output_callback(line)

        return result

    def execute_with_retries(
        self,
        prompt: str,
        max_retries: int = 3,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        retry_delay: int = 5,
    ) -> ExecutionResult:
        """Execute with retries (mock implementation).

        In mock mode, this just calls execute() without actual retries.
        """
        return self.execute(prompt, timeout, task_id)

    def validate_claude_available(self) -> bool:
        """Mock validation - always returns True."""
        return True

    def reset(self) -> None:
        """Reset the mock executor state."""
        self.responses.clear()
        self.default_response = None
        self.call_history.clear()
        self.call_count = 0

    def get_call_history(self) -> List[Dict[str, Any]]:
        """Get history of all execute() calls."""
        return self.call_history.copy()

    def assert_called_with_pattern(self, pattern: str) -> None:
        """Assert that execute was called with a prompt containing pattern."""
        for call in self.call_history:
            if pattern.lower() in call["prompt"].lower():
                return
        raise AssertionError(
            f"No call found with pattern '{pattern}'. "
            f"Calls: {[c['prompt'][:50] for c in self.call_history]}"
        )


class MockSubprocess:
    """Mock subprocess.Popen for testing subprocess-based code."""

    def __init__(self, response: MockResponse):
        """Initialize mock subprocess.

        Args:
            response: MockResponse to return
        """
        self.response = response
        self.returncode = response.exit_code

    def communicate(self, timeout: Optional[int] = None):
        """Mock communicate method."""
        # Handle timeout scenario
        if self.response.exit_code == 124:  # Timeout exit code
            import subprocess
            raise subprocess.TimeoutExpired("claude", timeout or 30)

        return (self.response.stdout, self.response.stderr)

    def kill(self):
        """Mock kill method."""
        pass

    def wait(self, timeout: Optional[int] = None):
        """Mock wait method."""
        return self.returncode


def create_mock_popen(response: MockResponse):
    """Create a mock Popen that returns the specified response.

    This is a helper for patching subprocess.Popen in tests.

    Example:
        >>> response = MockResponseLibrary.task_parsing_success()
        >>> with patch('subprocess.Popen', side_effect=create_mock_popen(response)):
        ...     # Your test code here
        ...     pass
    """
    def mock_popen(*args, **kwargs):
        return MockSubprocess(response)
    return mock_popen


# Pytest fixtures for easy testing
try:
    import pytest

    @pytest.fixture
    def mock_executor():
        """Provide a fresh MockClaudeExecutor for each test."""
        executor = MockClaudeExecutor()
        yield executor
        executor.reset()

    @pytest.fixture
    def mock_responses():
        """Provide the MockResponseLibrary for easy access."""
        return MockResponseLibrary

except ImportError:
    # pytest not available, skip fixture definitions
    pass
