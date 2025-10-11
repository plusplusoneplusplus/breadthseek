"""Tests for AI task parser."""

import os
import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock

from fsd.core.ai_task_parser import AITaskParser, AITaskParserError
from fsd.core.task_schema import Priority


class TestAITaskParser:
    """Tests for AITaskParser class."""

    @patch("fsd.core.ai_task_parser.subprocess.Popen")
    def test_parse_simple_task(self, mock_popen):
        """Test parsing a simple task description."""
        # Mock subprocess response
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            """
{
  "id": "fix-login-bug",
  "description": "Fix login bug in auth.py",
  "priority": "high",
  "estimated_duration": "30m",
  "context": null,
  "focus_files": ["auth.py"],
  "success_criteria": null,
  "pr_title": "fix: Fix login bug in auth.py"
}
""",
            "",
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Parse task
        parser = AITaskParser()
        task = parser.parse_task("HIGH priority: Fix login bug in auth.py. Should take 30m")

        # Verify
        assert task.id == "fix-login-bug"
        assert task.description == "Fix login bug in auth.py"
        assert task.priority == Priority.HIGH
        assert task.estimated_duration == "30m"
        assert task.focus_files == ["auth.py"]

    @patch("fsd.core.ai_task_parser.subprocess.Popen")
    def test_parse_complex_task(self, mock_popen):
        """Test parsing a complex task with context and criteria."""
        # Mock subprocess response
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            """
{
  "id": "implement-caching-layer",
  "description": "Implement caching layer for API with Redis",
  "priority": "medium",
  "estimated_duration": "2h",
  "context": "Should improve performance by 50%",
  "focus_files": ["api/v1/users.py", "cache.py"],
  "success_criteria": "Performance improved by at least 50%, all tests pass",
  "pr_title": "feat: Implement caching layer for API with Redis"
}
""",
            "",
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Parse task
        parser = AITaskParser()
        task = parser.parse_task(
            "Implement a caching layer for the API with Redis. Should improve performance by 50%. "
            "Focus on /api/v1/users endpoint"
        )

        # Verify
        assert task.id == "implement-caching-layer"
        assert task.description == "Implement caching layer for API with Redis"
        assert task.priority == Priority.MEDIUM
        assert task.estimated_duration == "2h"
        assert task.context == "Should improve performance by 50%"
        assert "api/v1/users.py" in task.focus_files
        assert task.success_criteria is not None

    @patch("fsd.core.ai_task_parser.subprocess.Popen")
    def test_parse_invalid_json(self, mock_popen):
        """Test handling of invalid JSON response."""
        # Mock subprocess response with invalid JSON
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("This is not JSON", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Parse task should raise error
        parser = AITaskParser()
        with pytest.raises(AITaskParserError):
            parser.parse_task("Fix authentication bug in login system")

    @patch("fsd.core.ai_task_parser.subprocess.Popen")
    def test_parse_missing_required_fields(self, mock_popen):
        """Test handling of response missing required fields."""
        # Mock subprocess response missing required fields
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            """
{
  "priority": "high",
  "estimated_duration": "30m"
}
""",
            "",
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Parse task should raise error
        parser = AITaskParser()
        with pytest.raises(AITaskParserError):
            parser.parse_task("Fix authentication bug in login system")

    @patch("fsd.core.ai_task_parser.subprocess.Popen")
    def test_parse_with_markdown_code_blocks(self, mock_popen):
        """Test parsing JSON from markdown code blocks."""
        # Mock subprocess response with markdown
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            """
Here's the parsed task:

```json
{
  "id": "fix-authentication-bug",
  "description": "Fix authentication bug in login system",
  "priority": "medium",
  "estimated_duration": "1h",
  "context": null,
  "focus_files": null,
  "success_criteria": null,
  "pr_title": "fix: Fix authentication bug"
}
```
""",
            "",
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Parse task
        parser = AITaskParser()
        task = parser.parse_task("Fix authentication bug in login system")

        # Verify
        assert task.id == "fix-authentication-bug"
        assert task.description == "Fix authentication bug in login system"
        assert task.priority == Priority.MEDIUM

    @patch("fsd.core.ai_task_parser.subprocess.Popen")
    def test_parse_subprocess_timeout(self, mock_popen):
        """Test handling of subprocess timeout."""
        # Mock subprocess that times out
        mock_process = MagicMock()
        mock_process.communicate.side_effect = [
            subprocess.TimeoutExpired("claude", 30),
            ("", ""),  # Return value after kill()
        ]
        mock_popen.return_value = mock_process

        # Parse task should raise AITaskParserError with timeout message
        parser = AITaskParser()
        with pytest.raises(AITaskParserError) as exc_info:
            parser.parse_task("Fix authentication bug", timeout=30)

        # Verify error message mentions timeout
        assert "timed out" in str(exc_info.value).lower()
        assert "30" in str(exc_info.value)

        # Verify process.kill() was called
        mock_process.kill.assert_called_once()
