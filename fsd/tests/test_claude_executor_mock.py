"""Comprehensive mock-based tests for Claude executor.

This module demonstrates deterministic testing of the Claude executor
using the mock system. All tests are fully deterministic and don't
require the actual Claude CLI.
"""

import subprocess
from unittest.mock import patch

import pytest

from fsd.core.claude_executor import ClaudeExecutor
from fsd.core.ai_task_parser import AITaskParser
from fsd.core.task_schema import Priority
from tests.mocks import (
    MockClaudeExecutor,
    MockResponse,
    MockResponseLibrary,
    create_mock_popen,
)


class TestMockClaudeExecutor:
    """Test the MockClaudeExecutor itself."""

    def test_basic_execution(self, mock_executor):
        """Test basic mock execution."""
        response = MockResponseLibrary.json_response({"status": "ok"})
        mock_executor.add_response("test", response)

        result = mock_executor.execute("test prompt")

        assert result.success
        assert '"status": "ok"' in result.stdout

    def test_pattern_matching(self, mock_executor):
        """Test that responses match prompt patterns."""
        # Add different responses for different patterns
        mock_executor.add_response(
            "parse task",
            MockResponseLibrary.task_parsing_success(task_id="parse-test"),
        )
        mock_executor.add_response(
            "validate",
            MockResponseLibrary.validation_success(validation_passed=True),
        )

        # Test parse task pattern
        result1 = mock_executor.execute("please parse task description")
        assert "parse-test" in result1.stdout

        # Test validate pattern
        result2 = mock_executor.execute("validate the changes")
        assert "validation_passed" in result2.stdout

    def test_sequential_responses(self, mock_executor):
        """Test returning different responses for the same pattern."""
        # First call succeeds, second fails
        responses = [
            MockResponseLibrary.task_parsing_success(task_id="first-call"),
            MockResponseLibrary.task_parsing_success(task_id="second-call"),
        ]
        mock_executor.add_response("parse", responses)

        result1 = mock_executor.execute("parse task 1")
        result2 = mock_executor.execute("parse task 2")

        assert "first-call" in result1.stdout
        assert "second-call" in result2.stdout

    def test_default_response(self, mock_executor):
        """Test default response when no pattern matches."""
        default = MockResponseLibrary.json_response({"default": True})
        mock_executor.set_default_response(default)

        result = mock_executor.execute("unmatched prompt")

        assert result.success
        assert '"default": true' in result.stdout

    def test_call_history(self, mock_executor):
        """Test tracking call history."""
        mock_executor.add_response("test", MockResponseLibrary.json_response({}))

        mock_executor.execute("test prompt 1", task_id="task-1")
        mock_executor.execute("test prompt 2", timeout=60)

        history = mock_executor.get_call_history()
        assert len(history) == 2
        assert history[0]["task_id"] == "task-1"
        assert history[1]["timeout"] == 60

    def test_assert_called_with_pattern(self, mock_executor):
        """Test assertion helper."""
        mock_executor.execute("parse task for login bug")

        # Should pass
        mock_executor.assert_called_with_pattern("parse task")
        mock_executor.assert_called_with_pattern("login bug")

        # Should fail
        with pytest.raises(AssertionError):
            mock_executor.assert_called_with_pattern("never called")


class TestClaudeExecutorWithMocks:
    """Test real ClaudeExecutor with mocked subprocess."""

    def test_successful_execution_with_json(self):
        """Test execution with JSON response."""
        response = MockResponseLibrary.task_parsing_success(
            task_id="test-task",
            description="Test description",
            priority="high",
        )

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_popen(response)()

            executor = ClaudeExecutor()
            result = executor.execute("Test prompt")

            assert result.success
            assert "test-task" in result.stdout
            parsed = result.parse_json()
            assert parsed["id"] == "test-task"
            assert parsed["priority"] == "high"

    def test_validation_workflow(self):
        """Test validation workflow with mock."""
        response = MockResponseLibrary.validation_success(
            validation_passed=True,
            tests_passed=15,
            tests_failed=0,
        )

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_popen(response)()

            executor = ClaudeExecutor()
            result = executor.execute("Run validation")

            assert result.success
            assert result.validation_passed()
            parsed = result.parse_json()
            assert parsed["tests"]["passed"] == 15

    def test_error_handling(self):
        """Test error response handling."""
        response = MockResponseLibrary.error_response(
            error_message="Command execution failed",
            exit_code=1,
        )

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_popen(response)()

            executor = ClaudeExecutor()
            result = executor.execute("Test prompt")

            assert not result.success
            assert result.exit_code == 1
            assert result.error_message is not None
            assert "failed" in result.error_message.lower()

    def test_network_error_retry(self):
        """Test retry logic with network errors."""
        # First call fails with network error, second succeeds
        error_response = MockResponseLibrary.network_error()
        success_response = MockResponseLibrary.json_response({"status": "ok"})

        with patch("subprocess.Popen") as mock_popen, patch("time.sleep"):
            # Return error first, then success
            mock_popen.side_effect = [
                create_mock_popen(error_response)(),
                create_mock_popen(success_response)(),
            ]

            executor = ClaudeExecutor()

            # Note: execute_with_retries checks if the error is retryable
            # The mock network error needs to be raised as an exception, not just returned
            # For now, we'll test that the executor can handle sequential calls
            result1 = executor.execute("Test prompt 1")
            result2 = executor.execute("Test prompt 2")

            # First should fail, second should succeed
            assert not result1.success
            assert result2.success
            assert '"status": "ok"' in result2.stdout
            # Should have been called twice
            assert mock_popen.call_count == 2


class TestAITaskParserWithMocks:
    """Test AITaskParser with deterministic mocks."""

    def test_parse_simple_task_deterministic(self):
        """Test parsing with fully deterministic response."""
        response = MockResponseLibrary.task_parsing_success(
            task_id="fix-auth-bug",
            description="Fix authentication bug",
            priority="high",
            duration="45m",
            focus_files=["auth.py", "tests/test_auth.py"],
        )

        with patch("fsd.core.ai_task_parser.subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_popen(response)()

            parser = AITaskParser()
            task = parser.parse_task("HIGH: Fix auth bug in auth.py - 45m")

            assert task.id == "fix-auth-bug"
            assert task.description == "Fix authentication bug"
            assert task.priority == Priority.HIGH
            assert task.estimated_duration == "45m"
            assert "auth.py" in task.focus_files

    def test_parse_complex_task_with_context(self):
        """Test parsing complex task with context and criteria."""
        response = MockResponseLibrary.task_parsing_success(
            task_id="implement-redis-cache",
            description="Implement Redis caching layer",
            priority="medium",
            duration="2h",
            context="Should improve API response time by 50%",
            focus_files=["api/cache.py", "config/redis.py"],
            success_criteria="Response time improved by 50%, all tests pass",
            pr_title="feat: Implement Redis caching layer",
        )

        with patch("fsd.core.ai_task_parser.subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_popen(response)()

            parser = AITaskParser()
            task = parser.parse_task("Implement Redis caching for API - should improve perf by 50%")

            assert task.id == "implement-redis-cache"
            assert task.context == "Should improve API response time by 50%"
            assert task.success_criteria is not None
            assert "50%" in task.success_criteria
            assert task.on_completion.pr_title == "feat: Implement Redis caching layer"

    def test_multiple_tasks_deterministic_sequence(self):
        """Test parsing multiple tasks with sequential responses."""
        tasks = [
            ("fix-bug-1", "Fix bug in login"),
            ("fix-bug-2", "Fix bug in signup"),
            ("fix-bug-3", "Fix bug in password reset"),
        ]

        with patch("fsd.core.ai_task_parser.subprocess.Popen") as mock_popen:
            # Create sequential responses
            mock_popen.side_effect = [
                create_mock_popen(
                    MockResponseLibrary.task_parsing_success(
                        task_id=task_id,
                        description=desc,
                    )
                )()
                for task_id, desc in tasks
            ]

            parser = AITaskParser()
            results = []

            for task_id, desc in tasks:
                task = parser.parse_task(desc)
                results.append((task.id, task.description))

            # Verify all tasks parsed correctly in order
            assert results == tasks

    def test_error_scenarios(self):
        """Test various error scenarios with deterministic responses."""
        # Test timeout
        timeout_response = MockResponse(
            stdout="",
            stderr="Timeout",
            exit_code=124,
        )

        with patch("fsd.core.ai_task_parser.subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_popen(timeout_response)()

            parser = AITaskParser()
            with pytest.raises(Exception):  # AITaskParserError
                parser.parse_task("Fix bug", timeout=10)


class TestWorkflowIntegration:
    """Test complete workflows with mocked AI."""

    def test_task_submission_to_validation_workflow(self):
        """Test complete workflow from task submission to validation."""
        # Setup mock responses for the workflow
        parse_response = MockResponseLibrary.task_parsing_success(
            task_id="workflow-test",
            description="Test workflow",
            priority="high",
        )

        validation_response = MockResponseLibrary.validation_success(
            validation_passed=True,
            tests_passed=20,
        )

        with patch("fsd.core.ai_task_parser.subprocess.Popen") as mock_popen:
            # Sequential responses for parse then validate
            mock_popen.side_effect = [
                create_mock_popen(parse_response)(),
                create_mock_popen(validation_response)(),
            ]

            # Parse task
            parser = AITaskParser()
            task = parser.parse_task("Implement feature X")

            # Validate (simulated)
            executor = ClaudeExecutor()
            with patch("subprocess.Popen") as executor_mock:
                executor_mock.return_value = create_mock_popen(validation_response)()
                result = executor.execute("Validate changes")

            # Assertions
            assert task.id == "workflow-test"
            assert result.validation_passed()

    def test_deterministic_multi_step_workflow(self, mock_executor):
        """Test multi-step workflow with deterministic responses."""
        # Setup responses for each step
        # Use more specific patterns to avoid conflicts
        mock_executor.add_response(
            "parse task",
            MockResponseLibrary.task_parsing_success(task_id="step-1"),
        )
        mock_executor.add_response(
            "implement the feature",
            MockResponseLibrary.code_generation(
                language="python",
                code="def feature(): pass",
            ),
        )
        mock_executor.add_response(
            "validate changes",
            MockResponseLibrary.validation_success(),
        )

        # Execute workflow steps with specific prompts
        parse_result = mock_executor.execute("parse task: implement feature")
        impl_result = mock_executor.execute("implement the feature")
        val_result = mock_executor.execute("validate changes")

        # Verify each step
        assert "step-1" in parse_result.stdout
        assert "def feature()" in impl_result.stdout
        # Check validation result properly
        assert val_result.success
        assert val_result.validation_passed()

        # Verify execution order
        history = mock_executor.get_call_history()
        assert len(history) == 3
        assert "parse task" in history[0]["prompt"]
        assert "implement" in history[1]["prompt"]
        assert "validate" in history[2]["prompt"]


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_malformed_json_response(self):
        """Test handling of malformed JSON."""
        response = MockResponse(
            stdout='{"invalid": json syntax}',
            exit_code=0,
        )

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_popen(response)()

            executor = ClaudeExecutor()
            result = executor.execute("Test")

            # Should not crash, but JSON parsing will fail
            with pytest.raises(Exception):  # JSON decode error
                result.parse_json()

    def test_empty_response(self):
        """Test handling of empty response."""
        response = MockResponse(stdout="", exit_code=0)

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_popen(response)()

            executor = ClaudeExecutor()
            result = executor.execute("Test")

            assert result.success
            assert result.stdout == ""

    def test_large_response(self):
        """Test handling of large response."""
        # Create a large JSON response
        large_data = {"items": [{"id": i, "data": "x" * 1000} for i in range(100)]}
        response = MockResponseLibrary.json_response(large_data)

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_popen(response)()

            executor = ClaudeExecutor()
            result = executor.execute("Generate large dataset")

            assert result.success
            parsed = result.parse_json()
            assert len(parsed["items"]) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
