"""Tests for FSD activity tracking system."""

import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from fsd.tracking.session import Session, SessionManager, SessionMetadata
from fsd.tracking.activity_logger import (
    ActivityLogger,
    ActivityEvent,
    EventType,
    FileChangeEvent,
    CommandExecutionEvent,
    calculate_file_checksum,
    count_file_lines,
)


class TestSessionMetadata:
    """Test session metadata model."""

    def test_session_metadata_creation(self):
        """Test creating session metadata."""
        start_time = datetime.now(timezone.utc)

        metadata = SessionMetadata(
            session_id="test-session",
            start_time=start_time,
            working_directory="/test/dir",
            git_branch="main",
        )

        assert metadata.session_id == "test-session"
        assert metadata.start_time == start_time
        assert metadata.working_directory == "/test/dir"
        assert metadata.git_branch == "main"
        assert metadata.is_active is True
        assert metadata.duration is None

    def test_session_metadata_with_end_time(self):
        """Test session metadata with end time."""
        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)

        metadata = SessionMetadata(
            session_id="test-session",
            start_time=start_time,
            end_time=end_time,
            working_directory="/test/dir",
        )

        assert metadata.is_active is False
        assert metadata.duration is not None
        assert metadata.duration >= 0


class TestSession:
    """Test session management."""

    def test_session_creation(self):
        """Test creating a new session."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir)
            session = Session(session_dir, "test-session")

            assert session.session_id == "test-session"
            assert session.session_dir == session_dir
            assert session.session_path == session_dir / "test-session"

    def test_session_start(self):
        """Test starting a session."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir)
            session = Session(session_dir, "test-session")

            session.start("/test/working/dir", "main")

            # Check that directories were created
            assert session.session_path.exists()
            assert (session.session_path / "tasks").exists()
            assert (session.session_path / "artifacts").exists()

            # Check metadata
            metadata = session.get_metadata()
            assert metadata is not None
            assert metadata.session_id == "test-session"
            assert metadata.working_directory == "/test/working/dir"
            assert metadata.git_branch == "main"
            assert metadata.is_active is True

    def test_session_end(self):
        """Test ending a session."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir)
            session = Session(session_dir, "test-session")

            session.start("/test/dir")
            time.sleep(0.01)  # Small delay to ensure duration > 0
            session.end()

            metadata = session.get_metadata()
            assert metadata is not None
            assert metadata.is_active is False
            assert metadata.duration is not None
            assert metadata.duration > 0

    def test_session_update_stats(self):
        """Test updating session statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir)
            session = Session(session_dir, "test-session")

            session.start("/test/dir")

            # Update stats
            session.update_stats(tasks_completed=2, total_commits=5)

            metadata = session.get_metadata()
            assert metadata.tasks_completed == 2
            assert metadata.total_commits == 5

            # Update again (should add to existing values)
            session.update_stats(tasks_completed=1, total_commits=3)

            metadata = session.get_metadata()
            assert metadata.tasks_completed == 3
            assert metadata.total_commits == 8

    def test_session_task_directory(self):
        """Test getting task directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir)
            session = Session(session_dir, "test-session")

            session.start("/test/dir")

            task_dir = session.get_task_dir("my-task")
            assert task_dir.exists()
            assert task_dir == session.session_path / "tasks" / "my-task"

    def test_session_list_tasks(self):
        """Test listing tasks in session."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir)
            session = Session(session_dir, "test-session")

            session.start("/test/dir")

            # Create some task directories
            session.get_task_dir("task-1")
            session.get_task_dir("task-2")

            tasks = session.list_tasks()
            assert len(tasks) == 2
            assert "task-1" in tasks
            assert "task-2" in tasks

    def test_session_persistence(self):
        """Test session metadata persistence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir)

            # Create and start session
            session1 = Session(session_dir, "test-session")
            session1.start("/test/dir", "main")
            session1.update_stats(tasks_completed=3)

            # Create new session instance with same ID
            session2 = Session(session_dir, "test-session")
            metadata = session2.get_metadata()

            assert metadata is not None
            assert metadata.session_id == "test-session"
            assert metadata.working_directory == "/test/dir"
            assert metadata.git_branch == "main"
            assert metadata.tasks_completed == 3


class TestSessionManager:
    """Test session manager."""

    def test_session_manager_creation(self):
        """Test creating session manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            manager = SessionManager(logs_dir)

            assert manager.logs_dir == logs_dir
            assert manager.sessions_dir.exists()

    def test_create_session(self):
        """Test creating a session through manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            manager = SessionManager(logs_dir)

            session = manager.create_session("test-session")
            assert session.session_id == "test-session"

    def test_get_session(self):
        """Test getting an existing session."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            manager = SessionManager(logs_dir)

            # Create and start a session
            session1 = manager.create_session("test-session")
            session1.start("/test/dir")

            # Get the session through manager
            session2 = manager.get_session("test-session")
            assert session2 is not None
            assert session2.session_id == "test-session"

            # Try to get non-existent session
            session3 = manager.get_session("non-existent")
            assert session3 is None

    def test_list_sessions(self):
        """Test listing sessions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            manager = SessionManager(logs_dir)

            # Create multiple sessions
            session1 = manager.create_session("session-1")
            session1.start("/test/dir1")

            time.sleep(0.01)  # Ensure different timestamps

            session2 = manager.create_session("session-2")
            session2.start("/test/dir2")

            # List sessions
            sessions = manager.list_sessions()
            assert len(sessions) == 2

            # Should be sorted by start time, most recent first
            assert sessions[0].session_id == "session-2"
            assert sessions[1].session_id == "session-1"

    def test_get_active_session(self):
        """Test getting active session."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            manager = SessionManager(logs_dir)

            # No active sessions initially
            active = manager.get_active_session()
            assert active is None

            # Create active session
            session = manager.create_session("active-session")
            session.start("/test/dir")

            active = manager.get_active_session()
            assert active is not None
            assert active.session_id == "active-session"

            # End session
            session.end()

            active = manager.get_active_session()
            assert active is None


class TestActivityLogger:
    """Test activity logging."""

    def test_activity_logger_creation(self):
        """Test creating activity logger."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            logger = ActivityLogger("test-session", logs_dir)

            assert logger.session_id == "test-session"
            assert logger.session_log_dir.exists()

    def test_log_basic_event(self):
        """Test logging basic events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            logger = ActivityLogger("test-session", logs_dir)

            logger.log_event(EventType.INFO, "Test message", task_id="test-task")

            # Check that event was written
            assert logger.main_log_file.exists()

            with open(logger.main_log_file, "r") as f:
                line = f.readline()
                event_data = json.loads(line)

                assert event_data["event_type"] == "info"
                assert event_data["message"] == "Test message"
                assert event_data["session_id"] == "test-session"
                assert event_data["task_id"] == "test-task"

    def test_log_session_events(self):
        """Test logging session start/end events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            logger = ActivityLogger("test-session", logs_dir)

            logger.log_session_start("/test/dir", "main")
            logger.log_session_end(5000, {"tasks_completed": 2})

            events = logger.get_recent_events()
            assert len(events) == 2

            start_event = events[0]
            assert start_event.event_type == EventType.SESSION_START
            assert start_event.working_directory == "/test/dir"
            assert start_event.git_branch == "main"

            end_event = events[1]
            assert end_event.event_type == EventType.SESSION_END
            assert end_event.duration_ms == 5000

    def test_log_task_events(self):
        """Test logging task events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            logger = ActivityLogger("test-session", logs_dir)

            logger.log_task_start("my-task", "Test task description")
            logger.log_task_complete("my-task", 3000, files_changed_count=5)

            task_events = logger.get_task_events("my-task")
            assert len(task_events) == 2

            start_event = task_events[0]
            assert start_event.event_type == EventType.TASK_START
            assert start_event.task_id == "my-task"

            complete_event = task_events[1]
            assert complete_event.event_type == EventType.TASK_COMPLETE
            assert complete_event.duration_ms == 3000

    def test_log_command_execution(self):
        """Test logging command execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            logger = ActivityLogger("test-session", logs_dir)

            cmd_event = CommandExecutionEvent(
                command="pytest",
                args=["tests/"],
                working_directory="/test/dir",
                exit_code=0,
                duration_ms=2500,
                stdout="All tests passed",
                stderr="",
            )

            logger.log_command_execution(cmd_event, "test-task")

            # Check main log
            events = logger.get_recent_events()
            assert len(events) == 1
            assert events[0].event_type == EventType.COMMAND_EXECUTE

            # Check detailed command log
            assert logger.commands_log_file.exists()

    def test_log_file_change(self):
        """Test logging file changes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            logger = ActivityLogger("test-session", logs_dir)

            change_event = FileChangeEvent(
                file_path="test.py",
                operation="modify",
                size_before=100,
                size_after=150,
                lines_added=5,
                lines_removed=2,
            )

            logger.log_file_change(change_event, "test-task")

            # Check main log
            events = logger.get_recent_events()
            assert len(events) == 1
            assert events[0].event_type == EventType.FILE_CHANGE
            assert events[0].files_changed == ["test.py"]

            # Check detailed file changes log
            assert logger.file_changes_log_file.exists()

    def test_log_claude_interaction(self):
        """Test logging Claude interactions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            logger = ActivityLogger("test-session", logs_dir)

            logger.log_claude_interaction(
                prompt="Fix the bug in main.py",
                response_summary="Fixed syntax error on line 42",
                duration_ms=15000,
                tools_used=["read_file", "search_replace"],
                files_accessed=["main.py"],
                task_id="test-task",
            )

            # Check main log
            events = logger.get_recent_events()
            assert len(events) == 1
            assert events[0].event_type == EventType.CLAUDE_INTERACTION

            # Check detailed Claude log
            assert logger.claude_log_file.exists()

    def test_log_test_run(self):
        """Test logging test runs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            logger = ActivityLogger("test-session", logs_dir)

            logger.log_test_run(
                command="pytest tests/",
                exit_code=0,
                duration_ms=3500,
                tests_run=25,
                tests_passed=24,
                tests_failed=1,
                coverage=85.5,
                task_id="test-task",
            )

            events = logger.get_recent_events()
            assert len(events) == 1

            event = events[0]
            assert event.event_type == EventType.TEST_RUN
            assert event.data["tests_run"] == 25
            assert event.data["tests_passed"] == 24
            assert event.data["coverage"] == 85.5

    def test_thread_safety(self):
        """Test thread safety of logging."""
        import threading

        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            logger = ActivityLogger("test-session", logs_dir)

            def log_events():
                for i in range(10):
                    logger.log_info(f"Message {i}")

            # Create multiple threads
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=log_events)
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Check that all events were logged
            events = logger.get_recent_events()
            assert len(events) == 50  # 5 threads * 10 messages each


class TestUtilityFunctions:
    """Test utility functions."""

    def test_calculate_file_checksum(self):
        """Test file checksum calculation."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_path = Path(f.name)

        try:
            checksum = calculate_file_checksum(temp_path)
            assert len(checksum) == 32  # MD5 hex string length
            assert checksum != ""

            # Same content should produce same checksum
            checksum2 = calculate_file_checksum(temp_path)
            assert checksum == checksum2

        finally:
            temp_path.unlink()

    def test_calculate_file_checksum_nonexistent(self):
        """Test checksum of non-existent file."""
        checksum = calculate_file_checksum(Path("nonexistent.txt"))
        assert checksum == ""

    def test_count_file_lines(self):
        """Test counting file lines."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("line 1\nline 2\nline 3\n")
            temp_path = Path(f.name)

        try:
            line_count = count_file_lines(temp_path)
            assert line_count == 3

        finally:
            temp_path.unlink()

    def test_count_file_lines_nonexistent(self):
        """Test counting lines in non-existent file."""
        line_count = count_file_lines(Path("nonexistent.txt"))
        assert line_count == 0
