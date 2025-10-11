"""AI-powered task parser using Claude CLI.

This module uses the Claude CLI to parse natural language task descriptions
into structured TaskDefinition objects with better understanding than regex.

IMPORTANT: This module uses the `claude` CLI command, NOT the Python SDK.
This ensures we use the same authentication method as the rest of the system.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Optional

from .task_schema import TaskDefinition, Priority, CompletionActions
from .exceptions import ExecutionError


class AITaskParserError(ExecutionError):
    """Raised when AI task parsing fails."""

    pass


class AITaskParser:
    """Parse natural language task descriptions using Claude CLI."""

    def __init__(self, command: str = "claude", working_dir: Optional[Path] = None):
        """Initialize AI task parser.

        Args:
            command: Claude CLI command (default: "claude")
            working_dir: Working directory for command execution
        """
        self.command = command
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()

    def parse_task(self, text: str, timeout: int = 30) -> TaskDefinition:
        """Parse natural language text into a TaskDefinition.

        Args:
            text: Natural language task description
            timeout: Timeout in seconds (default: 30)

        Returns:
            TaskDefinition parsed from text

        Raises:
            AITaskParserError: If parsing fails

        Examples:
            >>> parser = AITaskParser()
            >>> task = parser.parse_task("HIGH priority: Fix login bug in auth.py. Should take 30m")
            >>> task.priority
            Priority.HIGH
            >>> task.estimated_duration
            "30m"
        """
        prompt = self._build_prompt(text)

        try:
            # Execute Claude CLI
            cmd = [self.command, "-p", prompt]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.working_dir),
                text=True,
            )

            # Wait with timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                raise AITaskParserError(
                    f"Claude CLI timed out after {timeout}s"
                )

            # Check exit code
            if process.returncode != 0:
                error_msg = f"Claude CLI failed with exit code {process.returncode}"
                if stderr:
                    error_msg += f": {stderr[:500]}"
                raise AITaskParserError(error_msg)

            # Parse JSON from response
            task_data = self._extract_json(stdout)

            # Convert to TaskDefinition
            return self._build_task_definition(task_data)

        except FileNotFoundError as e:
            raise AITaskParserError(
                f"Claude CLI not found. Is it installed? Command: {self.command}"
            ) from e
        except AITaskParserError:
            raise
        except Exception as e:
            raise AITaskParserError(
                f"Failed to parse task with AI: {str(e)}"
            ) from e

    def _build_prompt(self, text: str) -> str:
        """Build prompt for Claude CLI to parse task.

        Args:
            text: User's natural language task description

        Returns:
            Formatted prompt for Claude CLI
        """
        return f"""You are a task parser for the FSD (Full-Stack Development) system. Parse this natural language task description into structured JSON.

Task description: "{text}"

Parse it into a structured task with these fields:

1. **id**: Generate a short, descriptive task ID (lowercase, hyphens, max 50 chars)
   - Example: "fix-login-bug", "refactor-payment-module"
   - Take significant words, skip stop words like "the", "a", "and"

2. **description**: Clean, complete task description (preserve key details)
   - Remove priority/duration keywords if explicit
   - Keep file mentions and technical details

3. **priority**: One of: "low", "medium", "high", "critical"
   - Look for keywords like HIGH, URGENT, CRITICAL, LOW
   - Default to "medium" if not specified

4. **estimated_duration**: Time estimate (e.g., "30m", "2h", "1h30m")
   - Look for patterns like "30m", "takes 2h", "should take 1h"
   - Estimate based on task complexity if not specified:
     * Simple fixes/updates: "30m"
     * Medium features/refactors: "1h"
     * Large features/migrations: "2h"

5. **context**: Additional background/requirements (optional, null if none)
   - Extract any context that helps understand the task
   - Include requirements, constraints, or background info

6. **focus_files**: Array of file paths mentioned (optional, null if none)
   - Extract any .py, .js, .ts, .yaml, .md files mentioned
   - Example: ["auth.py", "tests/test_auth.py"]

7. **success_criteria**: What defines task completion (optional, null if none)
   - Extract explicit success criteria or quality requirements
   - Example: "Tests pass", "No linting errors", "Performance improved"

8. **pr_title**: Conventional commit PR title
   - Format: "type: description" (max 72 chars)
   - Types: fix, feat, refactor, test, docs, chore
   - Detect from keywords in description

Return ONLY valid JSON in this exact format (no markdown, no explanation):

{{
  "id": "task-id-here",
  "description": "Clean description here",
  "priority": "medium",
  "estimated_duration": "1h",
  "context": null,
  "focus_files": null,
  "success_criteria": null,
  "pr_title": "feat: Task description"
}}

Requirements:
- Return ONLY the JSON, nothing else
- All string values must be properly quoted
- Use null for optional fields that aren't present
- Ensure valid JSON syntax
- Keep descriptions clear and concise"""

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from Claude's response.

        Args:
            text: Response text from Claude

        Returns:
            Parsed JSON dictionary

        Raises:
            AITaskParserError: If JSON cannot be extracted
        """
        # Try to parse the entire response as JSON first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in markdown code blocks
        import re

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find any JSON object
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        raise AITaskParserError(
            f"Could not extract valid JSON from Claude response: {text[:500]}"
        )

    def _build_task_definition(self, data: dict) -> TaskDefinition:
        """Build TaskDefinition from parsed data.

        Args:
            data: Parsed JSON data from Claude

        Returns:
            TaskDefinition object

        Raises:
            AITaskParserError: If data is invalid
        """
        try:
            # Build completion actions
            on_completion = CompletionActions(
                create_pr=True,
                pr_title=data.get("pr_title", "feat: Task completion"),
                notify_slack=False,
            )

            # Create task definition
            return TaskDefinition(
                id=data["id"],
                description=data["description"],
                priority=Priority(data.get("priority", "medium")),
                estimated_duration=data.get("estimated_duration", "1h"),
                context=data.get("context"),
                focus_files=data.get("focus_files"),
                success_criteria=data.get("success_criteria"),
                on_completion=on_completion,
            )

        except KeyError as e:
            raise AITaskParserError(
                f"Missing required field in parsed data: {e}"
            ) from e
        except Exception as e:
            raise AITaskParserError(
                f"Failed to build TaskDefinition: {e}"
            ) from e
