"""Tests for task ID resolver functionality."""

import tempfile
from pathlib import Path

import pytest
import yaml

from fsd.core.task_resolver import (
    resolve_task_id,
    _resolve_numeric_id,
    _build_numeric_id_mapping,
    _resolve_partial_id,
    get_task_display_name,
)


class TestResolveTaskId:
    """Test resolve_task_id function."""

    def test_resolve_full_task_id_in_queue(self):
        """Test resolving a full task ID that exists in queue."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            queue_dir.mkdir(parents=True)

            # Create a task file
            task_data = {
                "id": "test-task-123",
                "numeric_id": 1,
                "description": "Test task for resolution",
                "priority": "medium",
                "estimated_duration": "1h",
            }
            task_file = queue_dir / "test-task-123.yaml"
            with open(task_file, "w") as f:
                yaml.dump(task_data, f)

            result = resolve_task_id("test-task-123", fsd_dir)
            assert result == "test-task-123"

    def test_resolve_full_task_id_in_state(self):
        """Test resolving a full task ID that exists in state directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            state_dir = fsd_dir / "state"
            state_dir.mkdir(parents=True)

            # Create a state file
            state_data = {
                "task_id": "test-task-456",
                "current_state": "executing",
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
                "history": [],
            }
            state_file = state_dir / "test-task-456.json"
            with open(state_file, "w") as f:
                import json
                json.dump(state_data, f)

            result = resolve_task_id("test-task-456", fsd_dir)
            assert result == "test-task-456"

    def test_resolve_numeric_id(self):
        """Test resolving a numeric ID to full task ID."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            queue_dir.mkdir(parents=True)

            # Create task files with numeric IDs
            for i, task_id in enumerate(["task-one", "task-two", "task-three"], start=1):
                task_data = {
                    "id": task_id,
                    "numeric_id": i,
                    "description": f"Task {i} for resolution",
                    "priority": "medium",
                    "estimated_duration": "1h",
                }
                task_file = queue_dir / f"{task_id}.yaml"
                with open(task_file, "w") as f:
                    yaml.dump(task_data, f)

            # Test resolving by numeric ID
            assert resolve_task_id("1", fsd_dir) == "task-one"
            assert resolve_task_id("2", fsd_dir) == "task-two"
            assert resolve_task_id("3", fsd_dir) == "task-three"

    def test_resolve_numeric_id_with_hash(self):
        """Test resolving numeric ID with # prefix."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            queue_dir.mkdir(parents=True)

            task_data = {
                "id": "task-with-hash",
                "numeric_id": 42,
                "description": "Task for hash test",
                "priority": "medium",
                "estimated_duration": "1h",
            }
            task_file = queue_dir / "task-with-hash.yaml"
            with open(task_file, "w") as f:
                yaml.dump(task_data, f)

            # Should work with or without #
            assert resolve_task_id("42", fsd_dir) == "task-with-hash"
            assert resolve_task_id("#42", fsd_dir) == "task-with-hash"

    def test_resolve_partial_id_unique(self):
        """Test resolving a partial ID that matches uniquely."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            queue_dir.mkdir(parents=True)

            # Create tasks with different prefixes
            tasks = [
                "fix-auth-bug",
                "add-new-feature",
                "refactor-database",
            ]
            for i, task_id in enumerate(tasks, start=1):
                task_data = {
                    "id": task_id,
                    "numeric_id": i,
                    "description": f"{task_id} task",
                    "priority": "medium",
                    "estimated_duration": "1h",
                }
                task_file = queue_dir / f"{task_id}.yaml"
                with open(task_file, "w") as f:
                    yaml.dump(task_data, f)

            # Test partial matching
            assert resolve_task_id("fix-auth", fsd_dir) == "fix-auth-bug"
            assert resolve_task_id("add-new", fsd_dir) == "add-new-feature"
            assert resolve_task_id("refactor", fsd_dir) == "refactor-database"

    def test_resolve_partial_id_ambiguous(self):
        """Test that partial ID returns None when ambiguous."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            queue_dir.mkdir(parents=True)

            # Create tasks with same prefix
            tasks = ["fix-auth-bug", "fix-auth-issue"]
            for i, task_id in enumerate(tasks, start=1):
                task_data = {
                    "id": task_id,
                    "numeric_id": i,
                    "description": f"{task_id} task",
                    "priority": "medium",
                    "estimated_duration": "1h",
                }
                task_file = queue_dir / f"{task_id}.yaml"
                with open(task_file, "w") as f:
                    yaml.dump(task_data, f)

            # Ambiguous prefix should return None
            assert resolve_task_id("fix-auth", fsd_dir) is None
            # But full ID should work
            assert resolve_task_id("fix-auth-bug", fsd_dir) == "fix-auth-bug"

    def test_resolve_nonexistent_task(self):
        """Test resolving a task that doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            queue_dir.mkdir(parents=True)

            assert resolve_task_id("nonexistent-task", fsd_dir) is None
            assert resolve_task_id("999", fsd_dir) is None

    def test_resolve_with_nonexistent_fsd_dir(self):
        """Test resolving when .fsd directory doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            # Don't create the directory

            assert resolve_task_id("any-task", fsd_dir) is None


class TestBuildNumericIdMapping:
    """Test _build_numeric_id_mapping function."""

    def test_build_mapping_from_queue(self):
        """Test building numeric ID mapping from queue directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            queue_dir.mkdir(parents=True)

            # Create multiple tasks
            tasks = [
                ("task-one", 1),
                ("task-two", 2),
                ("task-three", 3),
            ]
            for task_id, numeric_id in tasks:
                task_data = {
                    "id": task_id,
                    "numeric_id": numeric_id,
                    "description": f"Task {numeric_id} for testing numeric ID resolution",
                    "priority": "medium",
                    "estimated_duration": "1h",
                }
                task_file = queue_dir / f"{task_id}.yaml"
                with open(task_file, "w") as f:
                    yaml.dump(task_data, f)

            mapping = _build_numeric_id_mapping(fsd_dir)
            assert len(mapping) == 3
            assert mapping[1] == "task-one"
            assert mapping[2] == "task-two"
            assert mapping[3] == "task-three"

    def test_build_mapping_skips_malformed_files(self):
        """Test that mapping skips malformed YAML files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            queue_dir.mkdir(parents=True)

            # Create a valid task
            task_data = {
                "id": "valid-task",
                "numeric_id": 1,
                "description": "Valid task",
                "priority": "medium",
                "estimated_duration": "1h",
            }
            task_file = queue_dir / "valid-task.yaml"
            with open(task_file, "w") as f:
                yaml.dump(task_data, f)

            # Create a malformed file
            bad_file = queue_dir / "malformed.yaml"
            with open(bad_file, "w") as f:
                f.write("invalid: yaml: content: :")

            # Should only get the valid task
            mapping = _build_numeric_id_mapping(fsd_dir)
            assert len(mapping) == 1
            assert mapping[1] == "valid-task"

    def test_build_mapping_handles_missing_numeric_id(self):
        """Test that mapping handles tasks without numeric_id."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            queue_dir.mkdir(parents=True)

            # Create task with numeric_id
            task_data_1 = {
                "id": "task-with-id",
                "numeric_id": 1,
                "description": "Task with numeric ID",
                "priority": "medium",
                "estimated_duration": "1h",
            }
            task_file_1 = queue_dir / "task-with-id.yaml"
            with open(task_file_1, "w") as f:
                yaml.dump(task_data_1, f)

            # Create task without numeric_id
            task_data_2 = {
                "id": "task-without-id",
                "description": "Task without numeric ID",
                "priority": "medium",
                "estimated_duration": "1h",
            }
            task_file_2 = queue_dir / "task-without-id.yaml"
            with open(task_file_2, "w") as f:
                yaml.dump(task_data_2, f)

            # Should only include task with numeric_id
            mapping = _build_numeric_id_mapping(fsd_dir)
            assert len(mapping) == 1
            assert mapping[1] == "task-with-id"

    def test_build_mapping_empty_queue(self):
        """Test building mapping with empty queue directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            queue_dir.mkdir(parents=True)

            mapping = _build_numeric_id_mapping(fsd_dir)
            assert len(mapping) == 0


class TestResolvePartialId:
    """Test _resolve_partial_id function."""

    def test_resolve_partial_from_queue(self):
        """Test resolving partial ID from queue directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            queue_dir.mkdir(parents=True)

            task_data = {
                "id": "unique-task-name",
                "description": "Unique task",
                "priority": "medium",
                "estimated_duration": "1h",
            }
            task_file = queue_dir / "unique-task-name.yaml"
            with open(task_file, "w") as f:
                yaml.dump(task_data, f)

            result = _resolve_partial_id("unique-task", fsd_dir)
            assert result == "unique-task-name"

    def test_resolve_partial_from_state(self):
        """Test resolving partial ID from state directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            state_dir = fsd_dir / "state"
            state_dir.mkdir(parents=True)

            import json
            state_data = {
                "task_id": "state-only-task",
                "current_state": "executing",
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
                "history": [],
            }
            state_file = state_dir / "state-only-task.json"
            with open(state_file, "w") as f:
                json.dump(state_data, f)

            result = _resolve_partial_id("state-only", fsd_dir)
            assert result == "state-only-task"

    def test_resolve_partial_prefers_queue_no_duplicates(self):
        """Test that partial resolution doesn't duplicate tasks in both dirs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            state_dir = fsd_dir / "state"
            queue_dir.mkdir(parents=True)
            state_dir.mkdir(parents=True)

            # Create same task in both directories
            task_data = {
                "id": "dual-location-task",
                "description": "Task in both locations",
                "priority": "medium",
                "estimated_duration": "1h",
            }
            task_file = queue_dir / "dual-location-task.yaml"
            with open(task_file, "w") as f:
                yaml.dump(task_data, f)

            import json
            state_data = {
                "task_id": "dual-location-task",
                "current_state": "executing",
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
                "history": [],
            }
            state_file = state_dir / "dual-location-task.json"
            with open(state_file, "w") as f:
                json.dump(state_data, f)

            # Should resolve uniquely (not count as duplicate)
            result = _resolve_partial_id("dual-location", fsd_dir)
            assert result == "dual-location-task"


class TestGetTaskDisplayName:
    """Test get_task_display_name function."""

    def test_display_name_with_numeric_id(self):
        """Test getting display name with numeric ID."""
        result = get_task_display_name("test-task", 42)
        assert result == "#42: test-task"

    def test_display_name_without_numeric_id(self):
        """Test getting display name without numeric ID."""
        result = get_task_display_name("test-task", None)
        assert result == "test-task"

    def test_display_name_with_zero_numeric_id(self):
        """Test getting display name with zero numeric ID."""
        result = get_task_display_name("test-task", 0)
        assert result == "#0: test-task"


class TestNumericIdResolutionForAllStates:
    """Test numeric ID resolution works for tasks in all states."""

    def test_resolve_numeric_id_for_queued_task(self):
        """Test resolving numeric ID for a task in queued state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            state_dir = fsd_dir / "state"
            queue_dir.mkdir(parents=True)
            state_dir.mkdir(parents=True)

            # Task in queue with queued state
            task_data = {
                "id": "queued-task",
                "numeric_id": 10,
                "description": "Queued task",
                "priority": "medium",
                "estimated_duration": "1h",
            }
            task_file = queue_dir / "queued-task.yaml"
            with open(task_file, "w") as f:
                yaml.dump(task_data, f)

            result = resolve_task_id("10", fsd_dir)
            assert result == "queued-task"

    def test_resolve_numeric_id_for_executing_task(self):
        """Test resolving numeric ID for a task in executing state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            state_dir = fsd_dir / "state"
            queue_dir.mkdir(parents=True)
            state_dir.mkdir(parents=True)

            # Task in queue (has numeric_id)
            task_data = {
                "id": "executing-task",
                "numeric_id": 20,
                "description": "Executing task",
                "priority": "medium",
                "estimated_duration": "1h",
            }
            task_file = queue_dir / "executing-task.yaml"
            with open(task_file, "w") as f:
                yaml.dump(task_data, f)

            # Task has state file showing it's executing
            import json
            state_data = {
                "task_id": "executing-task",
                "current_state": "executing",
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
                "history": [
                    {
                        "from_state": "queued",
                        "to_state": "planning",
                        "timestamp": "2025-01-01T00:00:00",
                    },
                    {
                        "from_state": "planning",
                        "to_state": "executing",
                        "timestamp": "2025-01-01T00:01:00",
                    },
                ],
            }
            state_file = state_dir / "executing-task.json"
            with open(state_file, "w") as f:
                json.dump(state_data, f)

            # Should be able to resolve by numeric ID
            result = resolve_task_id("20", fsd_dir)
            assert result == "executing-task"

    def test_resolve_numeric_id_for_failed_task(self):
        """Test resolving numeric ID for a task in failed state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            state_dir = fsd_dir / "state"
            queue_dir.mkdir(parents=True)
            state_dir.mkdir(parents=True)

            # Task in queue (has numeric_id)
            task_data = {
                "id": "failed-task",
                "numeric_id": 30,
                "description": "Failed task",
                "priority": "medium",
                "estimated_duration": "1h",
            }
            task_file = queue_dir / "failed-task.yaml"
            with open(task_file, "w") as f:
                yaml.dump(task_data, f)

            # Task has state file showing it's failed
            import json
            state_data = {
                "task_id": "failed-task",
                "current_state": "failed",
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
                "error_message": "Something went wrong",
                "history": [
                    {
                        "from_state": "queued",
                        "to_state": "planning",
                        "timestamp": "2025-01-01T00:00:00",
                    },
                    {
                        "from_state": "planning",
                        "to_state": "failed",
                        "timestamp": "2025-01-01T00:01:00",
                    },
                ],
            }
            state_file = state_dir / "failed-task.json"
            with open(state_file, "w") as f:
                json.dump(state_data, f)

            # Should be able to resolve by numeric ID
            result = resolve_task_id("30", fsd_dir)
            assert result == "failed-task"

    def test_resolve_numeric_id_multiple_states(self):
        """Test resolving numeric IDs for tasks in various states simultaneously."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fsd_dir = Path(temp_dir) / ".fsd"
            queue_dir = fsd_dir / "queue"
            state_dir = fsd_dir / "state"
            queue_dir.mkdir(parents=True)
            state_dir.mkdir(parents=True)

            # Create tasks in different states
            tasks = [
                ("queued-task-1", 1, "queued"),
                ("planning-task-2", 2, "planning"),
                ("executing-task-3", 3, "executing"),
                ("validating-task-4", 4, "validating"),
                ("failed-task-5", 5, "failed"),
            ]

            import json
            for task_id, numeric_id, state in tasks:
                # All tasks exist in queue with numeric_id
                task_data = {
                    "id": task_id,
                    "numeric_id": numeric_id,
                    "description": f"Task in {state} state",
                    "priority": "medium",
                    "estimated_duration": "1h",
                }
                task_file = queue_dir / f"{task_id}.yaml"
                with open(task_file, "w") as f:
                    yaml.dump(task_data, f)

                # Create state file
                state_data = {
                    "task_id": task_id,
                    "current_state": state,
                    "created_at": "2025-01-01T00:00:00",
                    "updated_at": "2025-01-01T00:00:00",
                    "history": [],
                }
                state_file = state_dir / f"{task_id}.json"
                with open(state_file, "w") as f:
                    json.dump(state_data, f)

            # All numeric IDs should resolve correctly
            assert resolve_task_id("1", fsd_dir) == "queued-task-1"
            assert resolve_task_id("2", fsd_dir) == "planning-task-2"
            assert resolve_task_id("3", fsd_dir) == "executing-task-3"
            assert resolve_task_id("4", fsd_dir) == "validating-task-4"
            assert resolve_task_id("5", fsd_dir) == "failed-task-5"
