"""Tests for FSD configuration system."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from fsd.config.models import (
    FSDConfig,
    AgentConfig,
    ClaudeConfig,
    SafetyConfig,
    GitConfig,
    LoggingConfig,
    NotificationConfig,
    SlackConfig,
    EmailConfig,
)
from fsd.config.loader import (
    load_config,
    save_config,
    create_default_config,
    validate_config_file,
    get_config_paths,
)
from fsd.core.exceptions import ConfigurationError


class TestConfigModels:
    """Test configuration model validation."""

    def test_default_config(self):
        """Test creating default configuration."""
        config = FSDConfig()

        assert config.agent.max_execution_time == "8h"
        assert config.agent.parallel_tasks == 1
        assert config.claude.command == "claude --dangerously-skip-permissions"
        assert config.safety.require_tests is True
        assert config.git.branch_prefix == "fsd/"
        assert config.logging.level == "INFO"
        assert config.notifications.enabled is False

    def test_agent_config_validation(self):
        """Test agent configuration validation."""
        # Valid config
        config = AgentConfig(
            max_execution_time="4h",
            checkpoint_interval="10m",
            parallel_tasks=2,
            mode="autonomous",
        )
        assert config.max_execution_time == "4h"
        assert config.parallel_tasks == 2

        # Invalid duration format
        with pytest.raises(ValueError, match="Duration must be in format"):
            AgentConfig(max_execution_time="invalid")

        # Invalid parallel tasks
        with pytest.raises(ValueError, match="parallel_tasks must be at least 1"):
            AgentConfig(parallel_tasks=0)

        with pytest.raises(ValueError, match="parallel_tasks cannot exceed 10"):
            AgentConfig(parallel_tasks=11)

        # Invalid mode
        with pytest.raises(ValueError, match="mode must be one of"):
            AgentConfig(mode="invalid")

    def test_claude_config_validation(self):
        """Test Claude configuration validation."""
        # Valid config
        config = ClaudeConfig(command="claude --help", working_dir="/tmp", timeout="1h")
        assert config.command == "claude --help"
        assert config.timeout == "1h"

        # Invalid timeout format
        with pytest.raises(ValueError, match="Timeout must be in format"):
            ClaudeConfig(timeout="invalid")

    def test_safety_config_validation(self):
        """Test safety configuration validation."""
        # Valid config
        config = SafetyConfig(
            protected_branches=["main", "develop"],
            max_files_per_commit=25,
            max_lines_per_file=1000,
        )
        assert config.protected_branches == ["main", "develop"]
        assert config.max_files_per_commit == 25

        # Invalid values
        with pytest.raises(ValueError, match="Value must be positive"):
            SafetyConfig(max_files_per_commit=0)

    def test_git_config_validation(self):
        """Test Git configuration validation."""
        # Valid config
        config = GitConfig(
            branch_prefix="feature/",
            user={"name": "Test User", "email": "test@example.com"},
        )
        assert config.branch_prefix == "feature/"
        assert config.user.name == "Test User"

        # Invalid email
        with pytest.raises(ValueError, match="Invalid email format"):
            GitConfig(user={"name": "Test", "email": "invalid-email"})

    def test_logging_config_validation(self):
        """Test logging configuration validation."""
        # Valid config
        config = LoggingConfig(level="DEBUG", format="text", retention_days=7)
        assert config.level == "DEBUG"
        assert config.format == "text"

        # Invalid level
        with pytest.raises(ValueError, match="level must be one of"):
            LoggingConfig(level="INVALID")

        # Invalid format
        with pytest.raises(ValueError, match="format must be one of"):
            LoggingConfig(format="invalid")

        # Invalid retention
        with pytest.raises(ValueError, match="retention_days must be at least 1"):
            LoggingConfig(retention_days=0)

    def test_notification_config_validation(self):
        """Test notification configuration validation."""
        # Valid config
        config = NotificationConfig(
            enabled=True,
            events=["task_completed", "task_failed"],
            slack={"enabled": True, "webhook_url": "https://hooks.slack.com/test"},
        )
        assert config.enabled is True
        assert len(config.events) == 2

        # Invalid event
        with pytest.raises(ValueError, match="Invalid event"):
            NotificationConfig(events=["invalid_event"])

        # Slack enabled without webhook
        with pytest.raises(ValueError, match="webhook_url is required"):
            NotificationConfig(slack={"enabled": True})

    def test_env_var_resolution(self):
        """Test environment variable resolution."""
        # Set test environment variables
        os.environ["TEST_WEBHOOK"] = "https://test.webhook.com"

        try:
            # Create config with valid values first, then test resolution on dict level
            config_dict = {
                "notifications": {"slack": {"webhook_url": "${TEST_WEBHOOK}"}},
                "claude": {
                    "command": "${TEST_WEBHOOK}"  # Use webhook URL as command for testing
                },
            }

            # Test the environment variable resolution function directly
            from fsd.config.models import _resolve_env_vars_recursive

            resolved_dict = _resolve_env_vars_recursive(config_dict)

            assert (
                resolved_dict["notifications"]["slack"]["webhook_url"]
                == "https://test.webhook.com"
            )
            assert resolved_dict["claude"]["command"] == "https://test.webhook.com"

        finally:
            # Clean up environment variables
            os.environ.pop("TEST_WEBHOOK", None)

    def test_env_var_with_defaults(self):
        """Test environment variable resolution with default values."""
        config = FSDConfig(
            notifications={
                "slack": {
                    "webhook_url": "${NONEXISTENT_VAR:https://default.webhook.com}"
                }
            }
        )

        resolved = config.resolve_env_vars()
        assert resolved.notifications.slack.webhook_url == "https://default.webhook.com"


class TestConfigLoader:
    """Test configuration loading functionality."""

    def test_create_default_config(self):
        """Test creating default configuration."""
        config = create_default_config()

        assert isinstance(config, FSDConfig)
        assert config.agent.max_execution_time == "8h"
        assert config.claude.command == "claude --dangerously-skip-permissions"

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"

            # Create test configuration
            original_config = FSDConfig(
                agent={"max_execution_time": "4h", "parallel_tasks": 2},
                claude={"timeout": "15m"},
                logging={"level": "DEBUG"},
            )

            # Save configuration
            save_config(original_config, config_path)

            # Verify file was created
            assert config_path.exists()

            # Load configuration back
            with patch(
                "fsd.config.loader._get_project_config_path", return_value=config_path
            ):
                loaded_config = load_config()

            # Verify loaded configuration matches
            assert loaded_config.agent.max_execution_time == "4h"
            assert loaded_config.agent.parallel_tasks == 2
            assert loaded_config.claude.timeout == "15m"
            assert loaded_config.logging.level == "DEBUG"

    def test_config_merging(self):
        """Test configuration merging from multiple sources."""
        with tempfile.TemporaryDirectory() as temp_dir:
            global_config_path = Path(temp_dir) / "global.yaml"
            project_config_path = Path(temp_dir) / "project.yaml"

            # Create global configuration
            global_config = {
                "agent": {"max_execution_time": "6h", "parallel_tasks": 1},
                "logging": {"level": "INFO"},
            }

            with open(global_config_path, "w") as f:
                yaml.dump(global_config, f)

            # Create project configuration (overrides some values)
            project_config = {
                "agent": {"parallel_tasks": 3},  # Override this value
                "claude": {"timeout": "45m"},  # Add new value
            }

            with open(project_config_path, "w") as f:
                yaml.dump(project_config, f)

            # Load merged configuration
            config = load_config(
                global_config_path=global_config_path,
                project_config_path=project_config_path,
            )

            # Verify merging worked correctly
            assert config.agent.max_execution_time == "6h"  # From global
            assert config.agent.parallel_tasks == 3  # Overridden by project
            assert config.claude.timeout == "45m"  # From project
            assert config.logging.level == "INFO"  # From global

    def test_validate_config_file(self):
        """Test configuration file validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Valid configuration file
            valid_config_path = Path(temp_dir) / "valid.yaml"
            valid_config = {"agent": {"max_execution_time": "4h", "parallel_tasks": 2}}

            with open(valid_config_path, "w") as f:
                yaml.dump(valid_config, f)

            result = validate_config_file(valid_config_path)
            assert result["valid"] is True
            assert len(result["errors"]) == 0

            # Invalid configuration file
            invalid_config_path = Path(temp_dir) / "invalid.yaml"
            invalid_config = {"agent": {"parallel_tasks": -1}}  # Invalid value

            with open(invalid_config_path, "w") as f:
                yaml.dump(invalid_config, f)

            result = validate_config_file(invalid_config_path)
            assert result["valid"] is False
            assert len(result["errors"]) > 0

    def test_nonexistent_config_file(self):
        """Test handling of nonexistent configuration files."""
        # Should not raise error, just use defaults
        with patch("fsd.config.loader._get_global_config_path", return_value=None):
            with patch("fsd.config.loader._get_project_config_path", return_value=None):
                config = load_config()

                # Should get default configuration
                assert config.agent.max_execution_time == "8h"

    def test_invalid_yaml_file(self):
        """Test handling of invalid YAML files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content:")
            invalid_path = Path(f.name)

        try:
            with pytest.raises(ConfigurationError, match="Invalid YAML"):
                validate_config_file(invalid_path)
        finally:
            invalid_path.unlink()

    def test_get_config_paths(self):
        """Test getting configuration file paths."""
        paths = get_config_paths()

        assert "global" in paths
        assert "project" in paths

        # Global path should be in user's config directory
        if paths["global"]:
            assert ".config" in str(paths["global"]) or "XDG_CONFIG_HOME" in os.environ

    def test_config_directory_creation(self):
        """Test that save_config creates parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "subdir" / "config.yaml"

            config = create_default_config()
            save_config(config, config_path)

            assert config_path.exists()
            assert config_path.parent.exists()
