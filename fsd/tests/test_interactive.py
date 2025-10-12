"""Tests for FSD interactive mode."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, call

import pytest

from fsd.cli.interactive import (
    run_interactive_mode,
    _parse_command_input,
    _show_command_help,
    _command_requires_args,
    show_menu,
)


class TestInteractiveParsing:
    """Test command input parsing."""

    def test_parse_single_command(self):
        """Test parsing a single command."""
        result = _parse_command_input("status")
        assert result == ["status"]

    def test_parse_command_with_args(self):
        """Test parsing command with arguments."""
        result = _parse_command_input("queue list")
        assert result == ["queue", "list"]

    def test_parse_command_with_help_flag(self):
        """Test parsing command with --help flag."""
        result = _parse_command_input("queue --help")
        assert result == ["queue", "--help"]

    def test_parse_help_command(self):
        """Test parsing help command."""
        result = _parse_command_input("help queue")
        assert result == ["help", "queue"]

    def test_parse_empty_input(self):
        """Test parsing empty input."""
        result = _parse_command_input("")
        assert result == []

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only input."""
        result = _parse_command_input("   ")
        assert result == []


class TestCommandRequiresArgs:
    """Test command argument requirement detection."""

    def test_queue_without_subcommand_requires_help(self):
        """Test that queue without subcommand requires help."""
        needs_help, subcommand = _command_requires_args("queue", [])
        assert needs_help is True
        assert subcommand is None

    def test_queue_with_invalid_subcommand_requires_help(self):
        """Test that queue with invalid subcommand requires help."""
        needs_help, subcommand = _command_requires_args("queue", ["invalid"])
        assert needs_help is True
        assert subcommand is None

    def test_queue_with_valid_subcommand_no_help(self):
        """Test that queue with valid subcommand doesn't require help."""
        needs_help, subcommand = _command_requires_args("queue", ["list"])
        assert needs_help is False
        assert subcommand is None

    def test_queue_start_no_help(self):
        """Test that 'queue start' doesn't require help."""
        needs_help, subcommand = _command_requires_args("queue", ["start"])
        assert needs_help is False
        assert subcommand is None

    def test_queue_retry_with_task_id_no_help(self):
        """Test that 'queue retry' with task ID doesn't require help."""
        needs_help, subcommand = _command_requires_args("queue", ["retry", "task-123"])
        assert needs_help is False
        assert subcommand is None

    def test_queue_retry_with_all_failed_no_help(self):
        """Test that 'queue retry --all-failed' doesn't require help."""
        needs_help, subcommand = _command_requires_args("queue", ["retry", "--all-failed"])
        assert needs_help is False
        assert subcommand is None

    def test_submit_without_args_requires_help(self):
        """Test that submit without args requires help."""
        needs_help, subcommand = _command_requires_args("submit", [])
        assert needs_help is True
        assert subcommand is None

    def test_submit_with_text_flag_no_help(self):
        """Test that submit with --text flag doesn't require help."""
        needs_help, subcommand = _command_requires_args("submit", ["--text", "my task"])
        assert needs_help is False
        assert subcommand is None

    def test_submit_with_file_no_help(self):
        """Test that submit with file path doesn't require help."""
        needs_help, subcommand = _command_requires_args("submit", ["task.yaml"])
        assert needs_help is False
        assert subcommand is None

    def test_status_no_args_no_help(self):
        """Test that status without args doesn't require help."""
        needs_help, subcommand = _command_requires_args("status", [])
        assert needs_help is False
        assert subcommand is None

    def test_init_no_args_no_help(self):
        """Test that init without args doesn't require help."""
        needs_help, subcommand = _command_requires_args("init", [])
        assert needs_help is False
        assert subcommand is None


class TestShowCommandHelp:
    """Test command help display."""

    @patch("fsd.cli.interactive.subprocess.run")
    @patch("fsd.cli.interactive.console.print")
    def test_show_help_for_queue(self, mock_print, mock_run):
        """Test showing help for queue command."""
        mock_run.return_value = Mock(returncode=0)

        _show_command_help("queue")

        # Verify subprocess was called with correct command
        mock_run.assert_called_once_with(
            ["fsd", "queue", "--help"],
            capture_output=False
        )

        # Verify header was printed
        assert any("queue" in str(call_args) for call_args in mock_print.call_args_list)

    @patch("fsd.cli.interactive.subprocess.run")
    @patch("fsd.cli.interactive.console.print")
    def test_show_help_for_queue_with_subcommand(self, mock_print, mock_run):
        """Test showing help for queue subcommand."""
        mock_run.return_value = Mock(returncode=0)

        _show_command_help("queue", "list")

        # Verify subprocess was called with correct command
        mock_run.assert_called_once_with(
            ["fsd", "queue", "list", "--help"],
            capture_output=False
        )

        # Verify header was printed with both command and subcommand
        assert any(
            "queue list" in str(call_args)
            for call_args in mock_print.call_args_list
        )

    @patch("fsd.cli.interactive.subprocess.run")
    @patch("fsd.cli.interactive.console.print")
    def test_show_help_for_submit(self, mock_print, mock_run):
        """Test showing help for submit command."""
        mock_run.return_value = Mock(returncode=0)

        _show_command_help("submit")

        mock_run.assert_called_once_with(
            ["fsd", "submit", "--help"],
            capture_output=False
        )

    @patch("fsd.cli.interactive.subprocess.run")
    @patch("fsd.cli.interactive.console.print")
    def test_show_help_command_not_found(self, mock_print, mock_run):
        """Test showing help for non-existent command."""
        mock_run.return_value = Mock(returncode=1)

        _show_command_help("nonexistent")

        # Should still attempt to show help
        mock_run.assert_called_once()
        # Should print warning about failure
        assert any(
            "Could not retrieve help" in str(call_args)
            for call_args in mock_print.call_args_list
        )

    @patch("fsd.cli.interactive.subprocess.run")
    @patch("fsd.cli.interactive.console.print")
    def test_show_help_exception(self, mock_print, mock_run):
        """Test error handling when subprocess fails."""
        mock_run.side_effect = Exception("Subprocess error")

        _show_command_help("queue")

        # Should print error message
        assert any(
            "Error retrieving help" in str(call_args)
            for call_args in mock_print.call_args_list
        )


class TestInteractiveMode:
    """Test interactive mode functionality."""

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    def test_quit_command(self, mock_menu, mock_welcome, mock_prompt):
        """Test quit command exits interactive mode."""
        mock_prompt.return_value = "quit"

        result = run_interactive_mode(continuous=False)

        assert result is None

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    def test_question_mark_shows_menu(self, mock_menu, mock_welcome, mock_prompt):
        """Test that '?' shows the menu and continues."""
        # First input: '?', second input: 'quit'
        mock_prompt.side_effect = ["?", "quit"]

        result = run_interactive_mode(continuous=False)

        # Menu should be shown twice: once at start, once for '?'
        assert mock_menu.call_count == 2
        assert result is None

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    def test_help_command_shows_menu(self, mock_menu, mock_welcome, mock_prompt):
        """Test that 'help' command shows the menu."""
        mock_prompt.side_effect = ["help", "quit"]

        result = run_interactive_mode(continuous=False)

        # Menu should be shown twice: once at start, once for 'help'
        assert mock_menu.call_count == 2
        assert result is None

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    @patch("fsd.cli.interactive._show_command_help")
    def test_help_with_command_shows_command_help(
        self, mock_help, mock_menu, mock_welcome, mock_prompt
    ):
        """Test that 'help queue' shows help for queue command."""
        mock_prompt.side_effect = ["help queue", "quit"]

        result = run_interactive_mode(continuous=False)

        # Should call _show_command_help with 'queue'
        mock_help.assert_called_once_with("queue")
        assert result is None

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    @patch("fsd.cli.interactive._show_command_help")
    def test_command_with_help_flag_shows_help(
        self, mock_help, mock_menu, mock_welcome, mock_prompt
    ):
        """Test that 'queue --help' shows help for queue command."""
        mock_prompt.side_effect = ["queue --help", "quit"]

        result = run_interactive_mode(continuous=False)

        # Should call _show_command_help with 'queue'
        mock_help.assert_called_once_with("queue")
        assert result is None

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    @patch("fsd.cli.interactive._show_command_help")
    def test_submit_help_flag(self, mock_help, mock_menu, mock_welcome, mock_prompt):
        """Test 'submit --help' shows help for submit command."""
        mock_prompt.side_effect = ["submit --help", "quit"]

        result = run_interactive_mode(continuous=False)

        mock_help.assert_called_once_with("submit")
        assert result is None

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    def test_command_with_args_returns_args(self, mock_menu, mock_welcome, mock_prompt):
        """Test that command with args returns full command args."""
        mock_prompt.return_value = "queue list"

        result = run_interactive_mode(continuous=False)

        assert result == ["queue", "list"]

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    @patch("fsd.cli.interactive._execute_command")
    def test_continuous_mode_executes_commands(
        self, mock_execute, mock_menu, mock_welcome, mock_prompt
    ):
        """Test that continuous mode executes commands with args."""
        # Test command with arguments
        mock_prompt.side_effect = ["queue list", "quit"]

        result = run_interactive_mode(continuous=True, verbose=False, config=None)

        # Should execute the command
        mock_execute.assert_called_once_with(["queue", "list"], False, None)
        assert result is None

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    @patch("fsd.cli.interactive._show_command_help")
    def test_queue_without_subcommand_shows_help(
        self, mock_help, mock_menu, mock_welcome, mock_prompt
    ):
        """Test that 'queue' without subcommand shows help."""
        mock_prompt.side_effect = ["queue", "quit"]

        result = run_interactive_mode(continuous=False)

        # Should show help for queue command
        mock_help.assert_called_once_with("queue", None)
        assert result is None

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    @patch("fsd.cli.interactive._show_command_help")
    def test_submit_without_args_shows_help(
        self, mock_help, mock_menu, mock_welcome, mock_prompt
    ):
        """Test that 'submit' without args shows help."""
        mock_prompt.side_effect = ["submit --verbose", "quit"]

        result = run_interactive_mode(continuous=False)

        # Should show help for submit command since --verbose is not --text or a file
        mock_help.assert_called_once_with("submit", None)
        assert result is None

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    def test_queue_with_subcommand_executes(
        self, mock_menu, mock_welcome, mock_prompt
    ):
        """Test that 'queue list' executes without showing help."""
        mock_prompt.return_value = "queue list"

        result = run_interactive_mode(continuous=False)

        # Should return the command args, not show help
        assert result == ["queue", "list"]


class TestShowMenu:
    """Test menu display."""

    @patch("fsd.cli.interactive.console.print")
    def test_show_menu_includes_help_command(self, mock_print):
        """Test that menu includes help command."""
        show_menu()

        # Check that help command is in the output
        output = " ".join(str(call_args) for call_args in mock_print.call_args_list)
        assert "help" in output.lower()

    @patch("fsd.cli.interactive.console.print")
    def test_show_menu_includes_help_tip(self, mock_print):
        """Test that menu includes tip about --help flag."""
        show_menu()

        # Check that the tip is in the output
        output = " ".join(str(call_args) for call_args in mock_print.call_args_list)
        assert "--help" in output
