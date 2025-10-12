"""Shared pytest fixtures and utilities for FSD tests."""

import tempfile
from pathlib import Path
from typing import Generator
import subprocess

import pytest
import yaml

from fsd.core.task_schema import (
    TaskDefinition,
    Priority,
    CompletionActions,
)
from fsd.core import (
    CheckpointManager,
    GitUtils,
    StatePersistence,
    TaskStateMachine,
)
from tests.mocks import (
    MockClaudeExecutor,
    MockResponseLibrary,
)


# ============================================================================
# Directory and File Fixtures
# ============================================================================


@pytest.fixture
def tmp_fsd_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create temporary .fsd directory structure.

    Yields:
        Path to temporary .fsd directory
    """
    fsd_dir = tmp_path / ".fsd"
    fsd_dir.mkdir(parents=True, exist_ok=True)

    # Create standard subdirectories
    (fsd_dir / "logs").mkdir(exist_ok=True)
    (fsd_dir / "queue").mkdir(exist_ok=True)
    (fsd_dir / "status").mkdir(exist_ok=True)
    (fsd_dir / "state").mkdir(exist_ok=True)
    (fsd_dir / "checkpoints").mkdir(exist_ok=True)
    (fsd_dir / "plans").mkdir(exist_ok=True)
    (fsd_dir / "reports").mkdir(exist_ok=True)

    yield fsd_dir


@pytest.fixture
def git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repository for testing.

    The repository is initialized with:
    - Git config (user.name and user.email)
    - Initial commit with README.md

    Yields:
        Path to the git repository
    """
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir(parents=True, exist_ok=True)

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository\n\nGenerated for testing.\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    yield repo_path


# ============================================================================
# Task Fixtures
# ============================================================================


@pytest.fixture
def sample_task() -> TaskDefinition:
    """Create a sample task with minimal fields.

    Returns:
        Basic task definition for testing
    """
    return TaskDefinition(
        id="sample-task",
        description="This is a sample task for testing purposes",
        priority=Priority.MEDIUM,
        estimated_duration="1h",
    )


@pytest.fixture
def complete_task() -> TaskDefinition:
    """Create a task with all fields populated.

    Returns:
        Complete task definition for testing
    """
    return TaskDefinition(
        id="complete-task",
        description="This is a complete task with all fields populated for comprehensive testing",
        priority=Priority.HIGH,
        estimated_duration="2h30m",
        context="Additional context information about the task requirements and constraints",
        focus_files=["src/main.py", "tests/test_main.py", "docs/README.md"],
        success_criteria=(
            "All tests pass with >80% coverage\n"
            "Code passes type checking\n"
            "No linting errors\n"
            "Documentation is updated"
        ),
        on_completion=CompletionActions(
            create_pr=True,
            pr_title="feat: Complete task implementation",
            notify_slack=True,
        ),
    )


@pytest.fixture
def task_yaml_file(tmp_path: Path, sample_task: TaskDefinition) -> Generator[Path, None, None]:
    """Create a temporary YAML file with a task definition.

    Args:
        tmp_path: Pytest temporary directory
        sample_task: Sample task to save to YAML

    Yields:
        Path to the task YAML file
    """
    task_file = tmp_path / "task.yaml"

    task_data = sample_task.model_dump(exclude_none=True, mode="json")
    with open(task_file, "w", encoding="utf-8") as f:
        yaml.dump(task_data, f, default_flow_style=False, indent=2)

    yield task_file


@pytest.fixture
def multiple_tasks_yaml(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a YAML file with multiple task definitions.

    Yields:
        Path to YAML file containing 3 tasks
    """
    tasks_file = tmp_path / "tasks.yaml"

    yaml_content = """
id: task-1
description: First task for testing multiple task loading
priority: high
estimated_duration: 1h
---
id: task-2
description: Second task for testing multiple task loading
priority: medium
estimated_duration: 30m
---
id: task-3
description: Third task for testing multiple task loading
priority: low
estimated_duration: 45m
"""

    tasks_file.write_text(yaml_content)
    yield tasks_file


# ============================================================================
# Component Fixtures
# ============================================================================


@pytest.fixture
def state_machine() -> TaskStateMachine:
    """Create a state machine without persistence.

    Returns:
        TaskStateMachine instance for testing
    """
    return TaskStateMachine()


@pytest.fixture
def state_machine_with_persistence(tmp_path: Path) -> TaskStateMachine:
    """Create a state machine with persistence enabled.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        TaskStateMachine with persistence handler
    """
    state_dir = tmp_path / "state"
    persistence = StatePersistence(state_dir)
    return TaskStateMachine(persistence_handler=persistence)


@pytest.fixture
def state_persistence(tmp_path: Path) -> StatePersistence:
    """Create a state persistence handler.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        StatePersistence instance
    """
    state_dir = tmp_path / "state"
    return StatePersistence(state_dir)


@pytest.fixture
def git_utils(git_repo: Path) -> GitUtils:
    """Create GitUtils instance for a test repository.

    Args:
        git_repo: Path to test git repository

    Returns:
        GitUtils instance
    """
    return GitUtils(git_repo)


@pytest.fixture
def checkpoint_manager(git_repo: Path, tmp_path: Path) -> CheckpointManager:
    """Create CheckpointManager for testing.

    Args:
        git_repo: Path to test git repository
        tmp_path: Pytest temporary directory

    Returns:
        CheckpointManager instance
    """
    checkpoint_dir = tmp_path / "checkpoints"
    return CheckpointManager(checkpoint_dir=checkpoint_dir, repo_path=git_repo)


# ============================================================================
# Mock Data Fixtures
# ============================================================================


@pytest.fixture
def sample_config_dict() -> dict:
    """Sample configuration dictionary for testing.

    Returns:
        Dictionary with FSD configuration
    """
    return {
        "agent": {
            "max_execution_time": "8h",
            "checkpoint_interval": "5m",
            "parallel_tasks": 1,
            "mode": "autonomous",
        },
        "claude": {
            "command": "claude --dangerously-skip-permissions",
            "working_dir": ".",
            "timeout": "30m",
        },
        "safety": {
            "protected_branches": ["main", "master", "production"],
            "require_tests": True,
            "require_type_check": True,
            "secret_scan": True,
            "auto_merge": False,
        },
        "git": {
            "branch_prefix": "fsd/",
            "user": {
                "name": "FSD Agent",
                "email": "fsd-agent@example.com",
            },
        },
        "logging": {
            "level": "INFO",
            "format": "json",
            "output_dir": ".fsd/logs",
            "retention_days": 30,
        },
        "notifications": {
            "enabled": False,
        },
    }


@pytest.fixture
def sample_task_dict() -> dict:
    """Sample task data as dictionary.

    Returns:
        Dictionary representing a task
    """
    return {
        "id": "test-task",
        "description": "Sample task description for testing purposes",
        "priority": "medium",
        "estimated_duration": "1h",
        "context": "Some additional context",
        "focus_files": ["file1.py", "file2.py"],
        "success_criteria": "All tests pass",
    }


@pytest.fixture
def invalid_task_dict() -> dict:
    """Invalid task data for testing validation.

    Returns:
        Dictionary with invalid task data
    """
    return {
        "id": "ab",  # Too short
        "description": "Short",  # Too short
        "priority": "invalid_priority",
        "estimated_duration": "invalid_duration",
    }


# ============================================================================
# Utility Functions
# ============================================================================


@pytest.fixture
def create_test_file():
    """Factory fixture for creating test files.

    Returns:
        Function that creates a file with given content
    """
    def _create_file(path: Path, content: str = "test content") -> Path:
        """Create a test file with content.

        Args:
            path: Path where file should be created
            content: Content to write to file

        Returns:
            Path to created file
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    return _create_file


@pytest.fixture
def make_git_commit(git_repo: Path):
    """Factory fixture for making git commits in test repo.

    Returns:
        Function that creates a commit
    """
    def _make_commit(message: str, file_path: str = None, content: str = "test") -> str:
        """Create a git commit.

        Args:
            message: Commit message
            file_path: Optional file to create/modify
            content: Content for the file

        Returns:
            Commit hash
        """
        if file_path:
            file = git_repo / file_path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content)
            subprocess.run(
                ["git", "add", file_path],
                cwd=git_repo,
                check=True,
                capture_output=True,
            )

        subprocess.run(
            ["git", "commit", "-m", message] + (["--allow-empty"] if not file_path else []),
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    return _make_commit


# ============================================================================
# Mock AI Fixtures
# ============================================================================


@pytest.fixture
def mock_executor() -> Generator[MockClaudeExecutor, None, None]:
    """Provide a fresh MockClaudeExecutor for each test.

    Yields:
        MockClaudeExecutor instance that is reset after each test
    """
    executor = MockClaudeExecutor()
    yield executor
    executor.reset()


@pytest.fixture
def mock_responses() -> type[MockResponseLibrary]:
    """Provide the MockResponseLibrary for easy access.

    Returns:
        MockResponseLibrary class
    """
    return MockResponseLibrary


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (may be slower)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "git: mark test as requiring git operations"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test (fast, isolated)"
    )
