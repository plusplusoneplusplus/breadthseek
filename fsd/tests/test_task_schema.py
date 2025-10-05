"""Tests for task schema and validation."""

import tempfile
from pathlib import Path
from datetime import timedelta

import pytest
import yaml

from fsd.core.task_schema import (
    TaskDefinition,
    Priority,
    CompletionActions,
    load_task_from_yaml,
    load_tasks_from_yaml,
    validate_task,
    save_task,
    _parse_duration,
)


class TestTaskDefinition:
    """Test TaskDefinition model."""

    def test_valid_task_minimal(self):
        """Test creating a task with minimal required fields."""
        task = TaskDefinition(
            id="test-task",
            description="This is a test task description",
            priority=Priority.MEDIUM,
            estimated_duration="2h",
        )

        assert task.id == "test-task"
        assert task.description == "This is a test task description"
        assert task.priority == Priority.MEDIUM
        assert task.estimated_duration == "2h"
        assert task.context is None
        assert task.focus_files is None
        assert task.success_criteria is None
        assert task.on_completion is None

    def test_valid_task_complete(self):
        """Test creating a task with all fields."""
        completion = CompletionActions(
            create_pr=True,
            pr_title="feat: Test task implementation",
            notify_slack=True,
        )

        task = TaskDefinition(
            id="complete-task",
            description="This is a complete test task",
            priority=Priority.HIGH,
            estimated_duration="1h30m",
            context="Additional context information",
            focus_files=["src/main.py", "tests/test_main.py"],
            success_criteria="All tests pass and code is clean",
            on_completion=completion,
        )

        assert task.id == "complete-task"
        assert task.priority == Priority.HIGH
        assert task.estimated_duration == "1h30m"
        assert task.context == "Additional context information"
        assert task.focus_files == ["src/main.py", "tests/test_main.py"]
        assert task.success_criteria == "All tests pass and code is clean"
        assert task.on_completion.create_pr is True
        assert task.on_completion.pr_title == "feat: Test task implementation"

    def test_invalid_task_id(self):
        """Test task ID validation."""
        # Too short
        with pytest.raises(ValueError, match="at least 3 characters"):
            TaskDefinition(
                id="ab",
                description="Test description",
                priority=Priority.MEDIUM,
                estimated_duration="1h",
            )

        # Invalid characters
        with pytest.raises(ValueError, match="lowercase letters, numbers, and hyphens"):
            TaskDefinition(
                id="Invalid_ID",
                description="Test description",
                priority=Priority.MEDIUM,
                estimated_duration="1h",
            )

        # Too long
        with pytest.raises(ValueError, match="no more than 50 characters"):
            TaskDefinition(
                id="a" * 51,
                description="Test description",
                priority=Priority.MEDIUM,
                estimated_duration="1h",
            )

    def test_invalid_description(self):
        """Test description validation."""
        # Empty description
        with pytest.raises(ValueError, match="cannot be empty"):
            TaskDefinition(
                id="test-task",
                description="",
                priority=Priority.MEDIUM,
                estimated_duration="1h",
            )

        # Too short
        with pytest.raises(ValueError, match="at least 10 characters"):
            TaskDefinition(
                id="test-task",
                description="Short",
                priority=Priority.MEDIUM,
                estimated_duration="1h",
            )

    def test_invalid_duration(self):
        """Test duration validation."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            TaskDefinition(
                id="test-task",
                description="Test description",
                priority=Priority.MEDIUM,
                estimated_duration="invalid",
            )

    def test_completion_actions_validation(self):
        """Test completion actions validation."""
        # create_pr=True but no pr_title
        with pytest.raises(ValueError, match="PR title is required"):
            TaskDefinition(
                id="test-task",
                description="Test description",
                priority=Priority.MEDIUM,
                estimated_duration="1h",
                on_completion=CompletionActions(create_pr=True),
            )

    def test_get_duration_methods(self):
        """Test duration conversion methods."""
        task = TaskDefinition(
            id="test-task",
            description="Test description",
            priority=Priority.MEDIUM,
            estimated_duration="2h30m",
        )

        assert task.get_duration_seconds() == 9000  # 2.5 hours * 3600
        assert task.get_duration_timedelta() == timedelta(hours=2, minutes=30)


class TestDurationParsing:
    """Test duration parsing function."""

    def test_valid_durations(self):
        """Test parsing valid duration strings."""
        assert _parse_duration("1h") == timedelta(hours=1)
        assert _parse_duration("30m") == timedelta(minutes=30)
        assert _parse_duration("2h30m") == timedelta(hours=2, minutes=30)
        assert _parse_duration("45m") == timedelta(minutes=45)
        assert _parse_duration("10h") == timedelta(hours=10)

    def test_invalid_durations(self):
        """Test parsing invalid duration strings."""
        assert _parse_duration("") is None
        assert _parse_duration("invalid") is None
        assert _parse_duration("1x") is None
        assert _parse_duration("h30m") is None
        assert _parse_duration("0h0m") is None


class TestTaskLoading:
    """Test task loading from YAML files."""

    def test_load_single_task(self):
        """Test loading a single task from YAML."""
        task_data = {
            "id": "yaml-task",
            "description": "Task loaded from YAML",
            "priority": "high",
            "estimated_duration": "1h",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(task_data, f)
            temp_path = Path(f.name)

        try:
            task = load_task_from_yaml(temp_path)
            assert task.id == "yaml-task"
            assert task.description == "Task loaded from YAML"
            assert task.priority == Priority.HIGH
        finally:
            temp_path.unlink()

    def test_load_multiple_tasks(self):
        """Test loading multiple tasks from YAML."""
        yaml_content = """
id: task-1
description: First task description
priority: high
estimated_duration: 1h
---
id: task-2
description: Second task description
priority: medium
estimated_duration: 30m
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            tasks = load_tasks_from_yaml(temp_path)
            assert len(tasks) == 2
            assert tasks[0].id == "task-1"
            assert tasks[1].id == "task-2"
        finally:
            temp_path.unlink()

    def test_load_nonexistent_file(self):
        """Test loading from nonexistent file."""
        with pytest.raises(FileNotFoundError):
            load_task_from_yaml("nonexistent.yaml")

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content:")
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid YAML"):
                load_task_from_yaml(temp_path)
        finally:
            temp_path.unlink()

    def test_load_invalid_task_data(self):
        """Test loading YAML with invalid task data."""
        task_data = {
            "id": "ab",  # Too short
            "description": "Test",  # Too short
            "priority": "invalid",
            "estimated_duration": "invalid",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(task_data, f)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid task definition"):
                load_task_from_yaml(temp_path)
        finally:
            temp_path.unlink()


class TestTaskSaving:
    """Test task saving to YAML files."""

    def test_save_task(self):
        """Test saving a task to YAML."""
        task = TaskDefinition(
            id="save-test",
            description="Task to be saved",
            priority=Priority.MEDIUM,
            estimated_duration="2h",
            context="Test context",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_task.yaml"
            save_task(task, file_path)

            # Load it back and verify
            loaded_task = load_task_from_yaml(file_path)
            assert loaded_task.id == task.id
            assert loaded_task.description == task.description
            assert loaded_task.priority == task.priority
            assert loaded_task.context == task.context

    def test_save_task_creates_directory(self):
        """Test that save_task creates parent directories."""
        task = TaskDefinition(
            id="save-test",
            description="Task to be saved",
            priority=Priority.MEDIUM,
            estimated_duration="2h",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "subdir" / "test_task.yaml"
            save_task(task, file_path)

            assert file_path.exists()
            loaded_task = load_task_from_yaml(file_path)
            assert loaded_task.id == task.id


class TestValidateTask:
    """Test task validation from dictionary."""

    def test_validate_valid_task(self):
        """Test validating a valid task dictionary."""
        task_data = {
            "id": "valid-task",
            "description": "Valid task description",
            "priority": "medium",
            "estimated_duration": "1h",
        }

        task = validate_task(task_data)
        assert task.id == "valid-task"
        assert task.priority == Priority.MEDIUM

    def test_validate_invalid_task(self):
        """Test validating an invalid task dictionary."""
        task_data = {
            "id": "ab",  # Too short
            "description": "Test",
            "priority": "medium",
            "estimated_duration": "1h",
        }

        with pytest.raises(ValueError, match="Invalid task definition"):
            validate_task(task_data)
