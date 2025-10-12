"""AI-powered task parser using Claude CLI.

This module uses the Claude CLI to parse natural language task descriptions
into structured TaskDefinition objects with better understanding than regex.

IMPORTANT: This module uses the `claude` CLI command, NOT the Python SDK.
This ensures we use the same authentication method as the rest of the system.
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from .task_schema import TaskDefinition, Priority, CompletionActions
from .exceptions import ExecutionError


class AITaskParserError(ExecutionError):
    """Raised when AI task parsing fails."""

    pass


class AITaskParser:
    """Parse natural language task descriptions using Claude CLI."""

    def __init__(
        self,
        command: str = "claude",
        working_dir: Optional[Path] = None,
        log_file: Optional[Path] = None,
    ):
        """Initialize AI task parser.

        Args:
            command: Claude CLI command (default: "claude")
            working_dir: Working directory for command execution
            log_file: Optional log file to record CLI interactions
        """
        self.command = command
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.log_file = Path(log_file) if log_file else None

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
        start_time = datetime.now()

        # Log the request
        self._log_interaction("REQUEST", {
            "timestamp": start_time.isoformat(),
            "input_text": text,
            "prompt": prompt,
            "command": self.command,
        })

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

                # Log timeout
                self._log_interaction("ERROR", {
                    "timestamp": datetime.now().isoformat(),
                    "error": "timeout",
                    "duration_seconds": timeout,
                })

                raise AITaskParserError(
                    f"Claude CLI timed out after {timeout}s"
                )

            duration = (datetime.now() - start_time).total_seconds()

            # Log the response
            self._log_interaction("RESPONSE", {
                "timestamp": datetime.now().isoformat(),
                "exit_code": process.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "duration_seconds": duration,
            })

            # Check exit code
            if process.returncode != 0:
                error_msg = f"Claude CLI failed with exit code {process.returncode}"
                if stderr:
                    error_msg += f": {stderr[:500]}"
                raise AITaskParserError(error_msg)

            # Parse JSON from response
            task_data = self._extract_json(stdout)

            # Log successful parsing
            self._log_interaction("SUCCESS", {
                "timestamp": datetime.now().isoformat(),
                "task_id": task_data.get("id"),
                "parsed_data": task_data,
            })

            # Convert to TaskDefinition
            return self._build_task_definition(task_data)

        except FileNotFoundError as e:
            self._log_interaction("ERROR", {
                "timestamp": datetime.now().isoformat(),
                "error": "command_not_found",
                "message": str(e),
            })
            raise AITaskParserError(
                f"Claude CLI not found. Is it installed? Command: {self.command}"
            ) from e
        except AITaskParserError:
            # Already logged
            raise
        except Exception as e:
            self._log_interaction("ERROR", {
                "timestamp": datetime.now().isoformat(),
                "error": "unexpected_error",
                "message": str(e),
            })
            raise AITaskParserError(
                f"Failed to parse task with AI: {str(e)}"
            ) from e

    def _log_interaction(self, level: str, data: dict) -> None:
        """Log CLI interaction to file.

        Args:
            level: Log level (REQUEST, RESPONSE, SUCCESS, ERROR)
            data: Data to log
        """
        if not self.log_file:
            return

        try:
            # Ensure log directory exists
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

            # Append log entry
            log_entry = {
                "level": level,
                **data,
            }

            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")

        except Exception as e:
            # Don't fail task creation if logging fails
            print(f"Warning: Failed to log AI task parser interaction: {e}")

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

1. **id**: Generate a short, descriptive task ID with random suffix (lowercase, hyphens, max 50 chars)
   - Example: "fix-login-bug-1234", "refactor-payment-module-5678"
   - Take significant words, skip stop words like "the", "a", "and"
   - MUST include a 4-digit random suffix (1000-9999) at the end to prevent collisions

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
  "id": "task-id-here-1234",
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
            # Ensure task ID has a random suffix for uniqueness
            task_id = data["id"]
            task_id = self._ensure_unique_suffix(task_id)

            # Build completion actions
            on_completion = CompletionActions(
                create_pr=True,
                pr_title=data.get("pr_title", "feat: Task completion"),
                notify_slack=False,
            )

            # Create task definition
            return TaskDefinition(
                id=task_id,
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

    def _ensure_unique_suffix(self, task_id: str) -> str:
        """Ensure task ID has a 4-digit random suffix for uniqueness.

        Args:
            task_id: Original task ID

        Returns:
            Task ID with suffix (adds one if not present)
        """
        import random
        import re

        # Check if ID already ends with -XXXX pattern (4 digits)
        if re.search(r'-\d{4}$', task_id):
            return task_id

        # Add random suffix
        random_suffix = random.randint(1000, 9999)

        # Truncate base if needed to keep total length <= 50
        if len(task_id) + 5 > 50:  # 5 = len("-XXXX")
            task_id = task_id[:45].rstrip('-')

        return f"{task_id}-{random_suffix}"
