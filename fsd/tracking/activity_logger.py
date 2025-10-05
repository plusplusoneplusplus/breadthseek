"""Activity logging for FSD operations."""

import json
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import hashlib

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events that can be logged."""

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_FAIL = "task_fail"
    COMMAND_EXECUTE = "command_execute"
    FILE_CHANGE = "file_change"
    GIT_OPERATION = "git_operation"
    TEST_RUN = "test_run"
    CLAUDE_INTERACTION = "claude_interaction"
    ERROR = "error"
    INFO = "info"
    DEBUG = "debug"


class ActivityEvent(BaseModel):
    """Activity event model."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: EventType = Field(..., description="Type of event")
    session_id: str = Field(..., description="Session identifier")
    task_id: Optional[str] = Field(None, description="Task identifier")
    message: str = Field(..., description="Event message")

    # Additional event data
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Additional event data"
    )

    # Execution context
    working_directory: Optional[str] = Field(None, description="Working directory")
    git_branch: Optional[str] = Field(None, description="Git branch")

    # Performance data
    duration_ms: Optional[int] = Field(None, description="Duration in milliseconds")
    exit_code: Optional[int] = Field(None, description="Exit code for commands")

    # File operation data
    files_changed: Optional[List[str]] = Field(None, description="Files changed")
    lines_added: Optional[int] = Field(None, description="Lines added")
    lines_removed: Optional[int] = Field(None, description="Lines removed")


class FileChangeEvent(BaseModel):
    """File change event details."""

    file_path: str = Field(..., description="Path to changed file")
    operation: str = Field(..., description="Operation type (create, modify, delete)")
    size_before: Optional[int] = Field(None, description="File size before change")
    size_after: Optional[int] = Field(None, description="File size after change")
    checksum_before: Optional[str] = Field(None, description="Checksum before change")
    checksum_after: Optional[str] = Field(None, description="Checksum after change")
    lines_added: int = Field(default=0, description="Lines added")
    lines_removed: int = Field(default=0, description="Lines removed")


class CommandExecutionEvent(BaseModel):
    """Command execution event details."""

    command: str = Field(..., description="Command executed")
    args: List[str] = Field(default_factory=list, description="Command arguments")
    working_directory: str = Field(..., description="Working directory")
    exit_code: int = Field(..., description="Exit code")
    duration_ms: int = Field(..., description="Execution duration in milliseconds")
    stdout: Optional[str] = Field(None, description="Standard output")
    stderr: Optional[str] = Field(None, description="Standard error")


class ActivityLogger:
    """Thread-safe activity logger for FSD operations."""

    def __init__(self, session_id: str, logs_dir: Path):
        """Initialize activity logger.

        Args:
            session_id: Current session identifier
            logs_dir: Directory to store log files
        """
        self.session_id = session_id
        self.logs_dir = logs_dir
        self.session_log_dir = logs_dir / "sessions" / session_id

        # Create log directories
        self.session_log_dir.mkdir(parents=True, exist_ok=True)

        # Log files
        self.main_log_file = self.session_log_dir / "activity.jsonl"
        self.commands_log_file = self.session_log_dir / "commands.jsonl"
        self.file_changes_log_file = self.session_log_dir / "file_changes.jsonl"
        self.claude_log_file = self.session_log_dir / "claude_interactions.jsonl"

        # Thread lock for safe concurrent logging
        self._lock = threading.Lock()

    def log_event(
        self,
        event_type: EventType,
        message: str,
        task_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Log a general activity event.

        Args:
            event_type: Type of event
            message: Event message
            task_id: Optional task identifier
            **kwargs: Additional event data
        """
        # Separate ActivityEvent fields from data fields
        event_fields = {
            "event_type": event_type,
            "session_id": self.session_id,
            "task_id": task_id,
            "message": message,
        }

        # Extract known ActivityEvent fields from kwargs
        activity_event_field_names = {
            "working_directory",
            "git_branch",
            "duration_ms",
            "exit_code",
            "files_changed",
            "lines_added",
            "lines_removed",
        }

        data_fields = {}
        for key, value in kwargs.items():
            if key in activity_event_field_names:
                event_fields[key] = value
            else:
                data_fields[key] = value

        # Add remaining data to the data field
        if data_fields:
            event_fields["data"] = data_fields

        event = ActivityEvent(**event_fields)
        self._write_event(self.main_log_file, event)

    def log_session_start(
        self, working_directory: str, git_branch: Optional[str] = None
    ) -> None:
        """Log session start event.

        Args:
            working_directory: Current working directory
            git_branch: Current git branch
        """
        self.log_event(
            EventType.SESSION_START,
            f"FSD session started: {self.session_id}",
            working_directory=working_directory,
            git_branch=git_branch,
        )

    def log_session_end(self, duration_ms: int, stats: Dict[str, Any]) -> None:
        """Log session end event.

        Args:
            duration_ms: Session duration in milliseconds
            stats: Session statistics
        """
        self.log_event(
            EventType.SESSION_END,
            f"FSD session ended: {self.session_id}",
            duration_ms=duration_ms,
            **stats,
        )

    def log_task_start(self, task_id: str, task_description: str) -> None:
        """Log task start event.

        Args:
            task_id: Task identifier
            task_description: Task description
        """
        self.log_event(
            EventType.TASK_START, f"Task started: {task_description}", task_id=task_id
        )

    def log_task_complete(self, task_id: str, duration_ms: int, **kwargs) -> None:
        """Log task completion event.

        Args:
            task_id: Task identifier
            duration_ms: Task duration in milliseconds
            **kwargs: Additional completion data
        """
        self.log_event(
            EventType.TASK_COMPLETE,
            f"Task completed successfully",
            task_id=task_id,
            duration_ms=duration_ms,
            **kwargs,
        )

    def log_task_fail(self, task_id: str, error: str, duration_ms: int) -> None:
        """Log task failure event.

        Args:
            task_id: Task identifier
            error: Error message
            duration_ms: Task duration in milliseconds
        """
        self.log_event(
            EventType.TASK_FAIL,
            f"Task failed: {error}",
            task_id=task_id,
            duration_ms=duration_ms,
            error=error,
        )

    def log_command_execution(
        self, cmd_event: CommandExecutionEvent, task_id: Optional[str] = None
    ) -> None:
        """Log command execution event.

        Args:
            cmd_event: Command execution details
            task_id: Optional task identifier
        """
        # Log to main activity log
        self.log_event(
            EventType.COMMAND_EXECUTE,
            f"Executed command: {cmd_event.command}",
            task_id=task_id,
            exit_code=cmd_event.exit_code,
            duration_ms=cmd_event.duration_ms,
            working_directory=cmd_event.working_directory,
        )

        # Log detailed command info to separate file
        self._write_event(self.commands_log_file, cmd_event, task_id=task_id)

    def log_file_change(
        self, change_event: FileChangeEvent, task_id: Optional[str] = None
    ) -> None:
        """Log file change event.

        Args:
            change_event: File change details
            task_id: Optional task identifier
        """
        # Log to main activity log
        self.log_event(
            EventType.FILE_CHANGE,
            f"File {change_event.operation}: {change_event.file_path}",
            task_id=task_id,
            files_changed=[change_event.file_path],
            lines_added=change_event.lines_added,
            lines_removed=change_event.lines_removed,
        )

        # Log detailed file change info to separate file
        self._write_event(self.file_changes_log_file, change_event, task_id=task_id)

    def log_claude_interaction(
        self,
        prompt: str,
        response_summary: str,
        duration_ms: int,
        tools_used: List[str],
        files_accessed: List[str],
        task_id: Optional[str] = None,
    ) -> None:
        """Log Claude CLI interaction.

        Args:
            prompt: Prompt sent to Claude
            response_summary: Summary of Claude's response
            duration_ms: Interaction duration
            tools_used: List of tools Claude used
            files_accessed: List of files Claude accessed
            task_id: Optional task identifier
        """
        interaction_data = {
            "prompt": prompt,
            "response_summary": response_summary,
            "duration_ms": duration_ms,
            "tools_used": tools_used,
            "files_accessed": files_accessed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Log to main activity log
        self.log_event(
            EventType.CLAUDE_INTERACTION,
            f"Claude interaction: {len(tools_used)} tools used, {len(files_accessed)} files accessed",
            task_id=task_id,
            duration_ms=duration_ms,
            tools_used=tools_used,
            files_accessed=files_accessed,
        )

        # Log detailed interaction to separate file
        self._write_event(self.claude_log_file, interaction_data, task_id=task_id)

    def log_git_operation(
        self, operation: str, details: Dict[str, Any], task_id: Optional[str] = None
    ) -> None:
        """Log git operation.

        Args:
            operation: Git operation (commit, branch, merge, etc.)
            details: Operation details
            task_id: Optional task identifier
        """
        self.log_event(
            EventType.GIT_OPERATION,
            f"Git {operation}",
            task_id=task_id,
            git_operation=operation,
            **details,
        )

    def log_test_run(
        self,
        command: str,
        exit_code: int,
        duration_ms: int,
        tests_run: int,
        tests_passed: int,
        tests_failed: int,
        coverage: Optional[float] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Log test execution.

        Args:
            command: Test command executed
            exit_code: Exit code
            duration_ms: Execution duration
            tests_run: Number of tests run
            tests_passed: Number of tests passed
            tests_failed: Number of tests failed
            coverage: Code coverage percentage
            task_id: Optional task identifier
        """
        self.log_event(
            EventType.TEST_RUN,
            f"Tests: {tests_passed}/{tests_run} passed",
            task_id=task_id,
            command=command,
            exit_code=exit_code,
            duration_ms=duration_ms,
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            coverage=coverage,
        )

    def log_error(self, error: str, task_id: Optional[str] = None, **kwargs) -> None:
        """Log error event.

        Args:
            error: Error message
            task_id: Optional task identifier
            **kwargs: Additional error context
        """
        self.log_event(EventType.ERROR, error, task_id=task_id, error=error, **kwargs)

    def log_info(self, message: str, task_id: Optional[str] = None, **kwargs) -> None:
        """Log info event.

        Args:
            message: Info message
            task_id: Optional task identifier
            **kwargs: Additional context
        """
        self.log_event(EventType.INFO, message, task_id=task_id, **kwargs)

    def get_task_events(self, task_id: str) -> List[ActivityEvent]:
        """Get all events for a specific task.

        Args:
            task_id: Task identifier

        Returns:
            List of events for the task
        """
        events = []

        if self.main_log_file.exists():
            with open(self.main_log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        event = ActivityEvent(**data)
                        if event.task_id == task_id:
                            events.append(event)
                    except (json.JSONDecodeError, ValueError):
                        continue

        return events

    def get_recent_events(self, limit: int = 100) -> List[ActivityEvent]:
        """Get recent events from the session.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent events
        """
        events = []

        if self.main_log_file.exists():
            with open(self.main_log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

                # Get last N lines
                for line in lines[-limit:]:
                    try:
                        data = json.loads(line.strip())
                        event = ActivityEvent(**data)
                        events.append(event)
                    except (json.JSONDecodeError, ValueError):
                        continue

        return events

    def _write_event(
        self,
        log_file: Path,
        event: Union[ActivityEvent, BaseModel, Dict[str, Any]],
        task_id: Optional[str] = None,
    ) -> None:
        """Write event to log file in a thread-safe manner.

        Args:
            log_file: Log file to write to
            event: Event to write
            task_id: Optional task identifier to add
        """
        with self._lock:
            try:
                # Convert event to dict
                if isinstance(event, BaseModel):
                    event_dict = event.model_dump(mode="json")
                elif isinstance(event, dict):
                    event_dict = event.copy()
                else:
                    event_dict = {"data": str(event)}

                # Add task_id if provided and not already present
                if task_id and "task_id" not in event_dict:
                    event_dict["task_id"] = task_id

                # Add timestamp if not present
                if "timestamp" not in event_dict:
                    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()

                # Write as JSON line
                with open(log_file, "a", encoding="utf-8") as f:
                    json.dump(event_dict, f, default=str, separators=(",", ":"))
                    f.write("\n")

            except Exception as e:
                # Fallback: write error to main log if possible
                try:
                    error_event = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "event_type": "error",
                        "message": f"Failed to write log event: {e}",
                        "session_id": self.session_id,
                    }

                    with open(self.main_log_file, "a", encoding="utf-8") as f:
                        json.dump(error_event, f, separators=(",", ":"))
                        f.write("\n")
                except Exception:
                    # If we can't even write the error, give up silently
                    pass


def calculate_file_checksum(file_path: Path) -> str:
    """Calculate MD5 checksum of a file.

    Args:
        file_path: Path to file

    Returns:
        MD5 checksum as hex string
    """
    if not file_path.exists():
        return ""

    try:
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


def count_file_lines(file_path: Path) -> int:
    """Count lines in a text file.

    Args:
        file_path: Path to file

    Returns:
        Number of lines in file
    """
    if not file_path.exists():
        return 0

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0
