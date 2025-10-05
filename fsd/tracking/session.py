"""Session management for FSD activity tracking."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field


class SessionMetadata(BaseModel):
    """Session metadata model."""

    session_id: str = Field(..., description="Unique session identifier")
    start_time: datetime = Field(..., description="Session start time")
    end_time: Optional[datetime] = Field(None, description="Session end time")
    working_directory: str = Field(..., description="Working directory")
    git_branch: Optional[str] = Field(None, description="Git branch at start")

    tasks_submitted: int = Field(default=0, description="Number of tasks submitted")
    tasks_completed: int = Field(default=0, description="Number of tasks completed")
    tasks_failed: int = Field(default=0, description="Number of tasks failed")

    total_commits: int = Field(default=0, description="Total commits created")
    total_files_changed: int = Field(default=0, description="Total files changed")
    total_tests_run: int = Field(default=0, description="Total tests run")
    claude_interactions: int = Field(default=0, description="Claude CLI interactions")

    @property
    def duration(self) -> Optional[float]:
        """Get session duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self.end_time is None


class Session:
    """FSD execution session manager."""

    def __init__(self, session_dir: Path, session_id: Optional[str] = None):
        """Initialize session.

        Args:
            session_dir: Directory to store session data
            session_id: Optional session ID, generates one if not provided
        """
        self.session_dir = session_dir
        self.session_id = session_id or self._generate_session_id()
        self.session_path = session_dir / self.session_id
        self.metadata_file = self.session_path / "session.json"

        self._metadata: Optional[SessionMetadata] = None

    def start(self, working_directory: str, git_branch: Optional[str] = None) -> None:
        """Start a new session.

        Args:
            working_directory: Current working directory
            git_branch: Current git branch
        """
        # Create session directory
        self.session_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.session_path / "tasks").mkdir(exist_ok=True)
        (self.session_path / "artifacts").mkdir(exist_ok=True)

        # Initialize metadata
        self._metadata = SessionMetadata(
            session_id=self.session_id,
            start_time=datetime.now(timezone.utc),
            working_directory=working_directory,
            git_branch=git_branch,
        )

        # Save metadata
        self._save_metadata()

    def end(self) -> None:
        """End the current session."""
        if self._metadata:
            self._metadata.end_time = datetime.now(timezone.utc)
            self._save_metadata()

    def update_stats(self, **kwargs) -> None:
        """Update session statistics.

        Args:
            **kwargs: Statistics to update (e.g., tasks_completed=1)
        """
        if not self._metadata:
            raise RuntimeError("Session not started")

        for key, value in kwargs.items():
            if hasattr(self._metadata, key):
                current_value = getattr(self._metadata, key)
                if isinstance(current_value, int):
                    setattr(self._metadata, key, current_value + value)
                else:
                    setattr(self._metadata, key, value)

        self._save_metadata()

    def get_metadata(self) -> Optional[SessionMetadata]:
        """Get session metadata.

        Returns:
            Session metadata or None if not loaded
        """
        if not self._metadata and self.metadata_file.exists():
            self._load_metadata()

        return self._metadata

    def get_task_dir(self, task_id: str) -> Path:
        """Get directory for task-specific logs.

        Args:
            task_id: Task identifier

        Returns:
            Path to task directory
        """
        task_dir = self.session_path / "tasks" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def get_artifacts_dir(self) -> Path:
        """Get directory for session artifacts.

        Returns:
            Path to artifacts directory
        """
        return self.session_path / "artifacts"

    def list_tasks(self) -> List[str]:
        """List all tasks in this session.

        Returns:
            List of task IDs
        """
        tasks_dir = self.session_path / "tasks"
        if not tasks_dir.exists():
            return []

        return [task_dir.name for task_dir in tasks_dir.iterdir() if task_dir.is_dir()]

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"fsd-{timestamp}-{short_uuid}"

    def _save_metadata(self) -> None:
        """Save session metadata to file."""
        if self._metadata:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(
                    self._metadata.model_dump(mode="json"), f, indent=2, default=str
                )

    def _load_metadata(self) -> None:
        """Load session metadata from file."""
        if self.metadata_file.exists():
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._metadata = SessionMetadata(**data)


class SessionManager:
    """Manages multiple FSD sessions."""

    def __init__(self, logs_dir: Path):
        """Initialize session manager.

        Args:
            logs_dir: Base directory for all session logs
        """
        self.logs_dir = logs_dir
        self.sessions_dir = logs_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, session_id: Optional[str] = None) -> Session:
        """Create a new session.

        Args:
            session_id: Optional session ID

        Returns:
            New session instance
        """
        return Session(self.sessions_dir, session_id)

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get an existing session.

        Args:
            session_id: Session identifier

        Returns:
            Session instance or None if not found
        """
        session_path = self.sessions_dir / session_id
        if session_path.exists():
            session = Session(self.sessions_dir, session_id)
            session._load_metadata()
            return session
        return None

    def list_sessions(self, limit: Optional[int] = None) -> List[SessionMetadata]:
        """List all sessions, most recent first.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session metadata
        """
        sessions = []

        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir():
                metadata_file = session_dir / "session.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        metadata = SessionMetadata(**data)
                        sessions.append(metadata)
                    except Exception:
                        # Skip invalid session files
                        continue

        # Sort by start time, most recent first
        sessions.sort(key=lambda s: s.start_time, reverse=True)

        if limit:
            sessions = sessions[:limit]

        return sessions

    def get_active_session(self) -> Optional[Session]:
        """Get the currently active session.

        Returns:
            Active session or None if no active session
        """
        for metadata in self.list_sessions():
            if metadata.is_active:
                return self.get_session(metadata.session_id)
        return None

    def cleanup_old_sessions(self, retention_days: int) -> int:
        """Clean up old session directories.

        Args:
            retention_days: Number of days to retain sessions

        Returns:
            Number of sessions cleaned up
        """
        cutoff_time = datetime.now(timezone.utc).timestamp() - (
            retention_days * 24 * 3600
        )
        cleaned_count = 0

        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir():
                # Check if session is old enough to clean up
                if session_dir.stat().st_mtime < cutoff_time:
                    try:
                        # Remove entire session directory
                        import shutil

                        shutil.rmtree(session_dir)
                        cleaned_count += 1
                    except Exception:
                        # Skip if cannot remove
                        continue

        return cleaned_count
