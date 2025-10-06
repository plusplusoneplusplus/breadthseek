"""Tests for FSD CLI commands."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from fsd.cli.main import cli


class TestCLI:
    """Test CLI commands."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_cli_help(self):
        """Test CLI help output."""
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "FSD: Autonomous Overnight Coding Agent System" in result.output
        assert "init" in result.output
        assert "submit" in result.output
        assert "queue" in result.output
        assert "status" in result.output
        assert "logs" in result.output

    def test_init_command(self):
        """Test init command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("fsd.cli.commands.init.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(cli, ["init"])

                assert result.exit_code == 0
                assert "FSD initialized" in result.output

                # Check that directories were created
                fsd_dir = Path(temp_dir) / ".fsd"
                assert fsd_dir.exists()
                assert (fsd_dir / "logs").exists()
                assert (fsd_dir / "tasks").exists()
                assert (fsd_dir / "reports").exists()
                assert (fsd_dir / "config.yaml").exists()

    def test_init_command_force(self):
        """Test init command with --force flag."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("fsd.cli.commands.init.Path.cwd", return_value=Path(temp_dir)):
                # Initialize once
                result1 = self.runner.invoke(cli, ["init"])
                assert result1.exit_code == 0

                # Try to initialize again without force
                result2 = self.runner.invoke(cli, ["init"])
                assert result2.exit_code == 0
                assert "already initialized" in result2.output

                # Initialize with force
                result3 = self.runner.invoke(cli, ["init", "--force"])
                assert result3.exit_code == 0
                assert "FSD initialized" in result3.output

    def test_submit_command_interactive_dry_run(self):
        """Test submit command in interactive mode with dry run."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("fsd.cli.commands.submit.Path.cwd", return_value=Path(temp_dir)):
                # Create .fsd directory first
                fsd_dir = Path(temp_dir) / ".fsd"
                fsd_dir.mkdir()

                # Mock interactive input
                inputs = [
                    "test-task",  # task ID
                    "Test task description for CLI testing",  # description
                    "medium",  # priority
                    "1h",  # duration
                    "n",  # no context
                    "n",  # no focus files
                    "n",  # no success criteria
                    "y",  # create PR
                    "feat: Test task",  # PR title
                    "n",  # no slack notification
                ]

                result = self.runner.invoke(
                    cli,
                    ["submit", "--interactive", "--dry-run"],
                    input="\n".join(inputs),
                )

                assert result.exit_code == 0
                assert "Task validation passed" in result.output
                assert "Dry run mode" in result.output

    def test_queue_list_empty(self):
        """Test queue list with no tasks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("fsd.cli.commands.queue.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(cli, ["queue", "list"])

                assert result.exit_code == 0
                assert "No tasks found" in result.output

    def test_status_not_initialized(self):
        """Test status command when FSD is not initialized."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("fsd.cli.commands.status.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(cli, ["status"])

                assert result.exit_code == 0
                assert "FSD not initialized" in result.output

    def test_logs_not_initialized(self):
        """Test logs command when FSD is not initialized."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("fsd.cli.commands.logs.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(cli, ["logs"])

                assert result.exit_code == 0
                assert "FSD not initialized" in result.output

    def test_verbose_flag(self):
        """Test verbose flag."""
        result = self.runner.invoke(cli, ["--verbose", "--help"])
        assert result.exit_code == 0
        # Verbose output should be shown in the help

    def test_submit_without_args(self):
        """Test submit command without arguments."""
        result = self.runner.invoke(cli, ["submit"])
        assert result.exit_code != 0
        assert (
            "Must provide either a task file or use --interactive mode" in result.output
        )

    def test_submit_with_both_file_and_interactive(self):
        """Test submit command with both file and interactive mode."""
        with tempfile.NamedTemporaryFile(suffix=".yaml") as temp_file:
            result = self.runner.invoke(
                cli, ["submit", temp_file.name, "--interactive"]
            )
            assert result.exit_code != 0
            assert "Cannot use multiple input methods simultaneously" in result.output

    def test_submit_with_text_basic(self):
        """Test submit command with --text option (basic)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("fsd.cli.commands.submit.Path.cwd", return_value=Path(temp_dir)):
                # Create .fsd directory first
                fsd_dir = Path(temp_dir) / ".fsd"
                fsd_dir.mkdir()

                result = self.runner.invoke(
                    cli,
                    ["submit", "--text", "Fix login bug in auth.py", "--dry-run"],
                )

                if result.exit_code != 0:
                    print(f"Error output: {result.output}")
                    print(f"Exception: {result.exception}")

                assert result.exit_code == 0
                assert "Task validation passed" in result.output
                assert "Dry run mode" in result.output

    def test_submit_with_text_priority_and_duration(self):
        """Test submit command with priority and duration extraction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("fsd.cli.commands.submit.Path.cwd", return_value=Path(temp_dir)):
                # Create .fsd directory first
                fsd_dir = Path(temp_dir) / ".fsd"
                fsd_dir.mkdir()

                result = self.runner.invoke(
                    cli,
                    ["submit", "--text", "HIGH priority: Fix critical bug. Takes 30m", "--dry-run"],
                )

                assert result.exit_code == 0
                assert "Task validation passed" in result.output
                assert "high" in result.output.lower()
                assert "30m" in result.output

    def test_submit_with_text_files_extraction(self):
        """Test submit command with file extraction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("fsd.cli.commands.submit.Path.cwd", return_value=Path(temp_dir)):
                # Create .fsd directory first
                fsd_dir = Path(temp_dir) / ".fsd"
                fsd_dir.mkdir()

                result = self.runner.invoke(
                    cli,
                    ["submit", "--text", "Refactor authentication in auth.py and user.py", "--dry-run"],
                )

                assert result.exit_code == 0
                assert "Task validation passed" in result.output
