"""Execute Claude Code CLI with subprocess management.

This module provides a robust interface for invoking Claude Code CLI,
handling process management, output streaming, timeouts, and error handling.
"""

import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import ClaudeExecutionError, ClaudeOutputParseError, ClaudeTimeoutError
from .output_parser import OutputParser


@dataclass
class ExecutionResult:
    """Result of Claude CLI execution."""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    error_message: Optional[str] = None

    def parse_json(self) -> Dict[str, Any]:
        """Parse JSON from stdout.

        Returns:
            Parsed JSON dictionary

        Raises:
            ClaudeOutputParseError: If JSON cannot be parsed
        """
        return OutputParser.extract_json(self.stdout, strict=True)

    def parse_json_safe(self) -> Optional[Dict[str, Any]]:
        """Parse JSON from stdout, returning None on error.

        Returns:
            Parsed JSON dictionary or None if parsing fails
        """
        try:
            return OutputParser.extract_json(self.stdout, strict=False)
        except ClaudeOutputParseError:
            return None

    def validation_passed(self) -> bool:
        """Check if validation passed based on output.

        Returns:
            True if validation appears to have passed
        """
        return OutputParser.find_validation_result(self.stdout)


class ClaudeExecutor:
    """Execute Claude Code CLI commands with subprocess management."""

    def __init__(
        self,
        command: str = "claude --dangerously-skip-permissions",
        working_dir: Optional[Path] = None,
        default_timeout: int = 1800,  # 30 minutes
    ):
        """Initialize Claude executor.

        Args:
            command: Claude CLI command (e.g., "claude --dangerously-skip-permissions")
            working_dir: Working directory for command execution
            default_timeout: Default timeout in seconds
        """
        self.command = command
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.default_timeout = default_timeout

    def execute(
        self,
        prompt: str,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        capture_output: bool = True,
    ) -> ExecutionResult:
        """Execute Claude CLI with the given prompt.

        Args:
            prompt: Prompt to send to Claude
            timeout: Timeout in seconds (uses default if None)
            task_id: Optional task ID for logging
            capture_output: Whether to capture stdout/stderr

        Returns:
            ExecutionResult with output and status

        Raises:
            ClaudeTimeoutError: If execution times out
            ClaudeExecutionError: If execution fails
        """
        if timeout is None:
            timeout = self.default_timeout

        # Build command
        cmd = self.command.split() + ["-p", prompt]

        # Track start time
        start_time = time.time()

        try:
            # Execute process
            if capture_output:
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
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                    duration = time.time() - start_time
                    raise ClaudeTimeoutError(
                        f"Claude execution timed out after {timeout}s "
                        f"(task: {task_id or 'unknown'})"
                    )
            else:
                # Run without capturing (for interactive mode)
                result = subprocess.run(
                    cmd,
                    cwd=str(self.working_dir),
                    timeout=timeout,
                )
                stdout = ""
                stderr = ""
                exit_code = result.returncode

            # Calculate duration
            duration = time.time() - start_time

            # Determine success
            success = exit_code == 0

            # Build error message if failed
            error_message = None
            if not success:
                error_message = f"Claude exited with code {exit_code}"
                if stderr:
                    error_message += f": {stderr[:500]}"

            return ExecutionResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_seconds=duration,
                error_message=error_message,
            )

        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            raise ClaudeTimeoutError(
                f"Claude execution timed out after {timeout}s "
                f"(task: {task_id or 'unknown'})"
            ) from e

        except FileNotFoundError as e:
            raise ClaudeExecutionError(
                f"Claude CLI not found. Is it installed? Command: {self.command}"
            ) from e

        except Exception as e:
            raise ClaudeExecutionError(
                f"Failed to execute Claude: {e}"
            ) from e

    def execute_with_streaming(
        self,
        prompt: str,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        output_callback: Optional[callable] = None,
    ) -> ExecutionResult:
        """Execute Claude CLI with real-time output streaming.

        Args:
            prompt: Prompt to send to Claude
            timeout: Timeout in seconds
            task_id: Optional task ID for logging
            output_callback: Optional callback for streaming output (receives line strings)

        Returns:
            ExecutionResult with complete output

        Raises:
            ClaudeTimeoutError: If execution times out
            ClaudeExecutionError: If execution fails
        """
        if timeout is None:
            timeout = self.default_timeout

        cmd = self.command.split() + ["-p", prompt]
        start_time = time.time()

        stdout_lines = []
        stderr_lines = []

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.working_dir),
                text=True,
                bufsize=1,  # Line buffered
            )

            # Thread to read stdout
            def read_stdout():
                for line in iter(process.stdout.readline, ""):
                    if line:
                        stdout_lines.append(line)
                        if output_callback:
                            output_callback(line.rstrip("\n"))
                process.stdout.close()

            # Thread to read stderr
            def read_stderr():
                for line in iter(process.stderr.readline, ""):
                    if line:
                        stderr_lines.append(line)
                process.stderr.close()

            # Start reader threads
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()

            # Wait for process with timeout
            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise ClaudeTimeoutError(
                    f"Claude execution timed out after {timeout}s "
                    f"(task: {task_id or 'unknown'})"
                )

            # Wait for threads to finish reading
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)

            duration = time.time() - start_time
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)
            success = exit_code == 0

            error_message = None
            if not success:
                error_message = f"Claude exited with code {exit_code}"
                if stderr:
                    error_message += f": {stderr[:500]}"

            return ExecutionResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_seconds=duration,
                error_message=error_message,
            )

        except Exception as e:
            if isinstance(e, ClaudeTimeoutError):
                raise
            raise ClaudeExecutionError(
                f"Failed to execute Claude with streaming: {e}"
            ) from e

    def execute_with_retries(
        self,
        prompt: str,
        max_retries: int = 3,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        retry_delay: int = 5,
    ) -> ExecutionResult:
        """Execute Claude CLI with automatic retries on transient failures.

        Args:
            prompt: Prompt to send to Claude
            max_retries: Maximum number of retry attempts
            timeout: Timeout in seconds
            task_id: Optional task ID for logging
            retry_delay: Delay between retries in seconds

        Returns:
            ExecutionResult from successful execution

        Raises:
            ClaudeExecutionError: If all retries fail
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = self.execute(
                    prompt=prompt,
                    timeout=timeout,
                    task_id=task_id,
                )

                # Success!
                return result

            except ClaudeTimeoutError:
                # Don't retry timeouts
                raise

            except ClaudeExecutionError as e:
                last_error = e

                # Check if this is a transient error worth retrying
                if self._is_retryable_error(e):
                    if attempt < max_retries:
                        # Wait before retrying
                        time.sleep(retry_delay)
                        continue
                    else:
                        # Out of retries
                        raise ClaudeExecutionError(
                            f"Failed after {max_retries} retries: {e}"
                        ) from e
                else:
                    # Not retryable, fail immediately
                    raise

        # Should not reach here, but just in case
        raise ClaudeExecutionError(
            f"Failed after {max_retries} retries: {last_error}"
        ) from last_error

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        """Determine if an error is worth retrying.

        Args:
            error: Exception to check

        Returns:
            True if error is likely transient and worth retrying
        """
        error_msg = str(error).lower()

        # Network-related errors
        network_patterns = [
            "connection",
            "network",
            "timeout",
            "unavailable",
            "unreachable",
            "temporary",
        ]

        for pattern in network_patterns:
            if pattern in error_msg:
                return True

        # API rate limits or service issues
        service_patterns = [
            "rate limit",
            "too many requests",
            "overloaded",
            "service unavailable",
        ]

        for pattern in service_patterns:
            if pattern in error_msg:
                return True

        return False

    def validate_claude_available(self) -> bool:
        """Check if Claude CLI is available.

        Returns:
            True if Claude CLI can be executed
        """
        try:
            # Try to run claude --version or similar
            cmd = self.command.split()[0]  # Just the binary name
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
