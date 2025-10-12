"""Tests for FSD shell mode."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from fsd.cli.shell import (
    run_shell_mode,
    show_shell_help,
    get_history_file,
    FSDCompleter,
)


class TestShellHelp:
    """Test shell help functionality."""

    @patch("fsd.cli.shell.console.print")
    def test_show_shell_help_includes_features(self, mock_print):
        """Test that shell help includes shell features."""
        show_shell_help()

        # Check that shell features are printed
        output = " ".join(str(call_args) for call_args in mock_print.call_args_list)
        assert "Shell Features" in output
        assert "Navigate command history" in output
        assert "Tab" in output
        assert "Ctrl+R" in output

    @patch("fsd.cli.shell.console.print")
    def test_show_shell_help_includes_commands(self, mock_print):
        """Test that shell help includes built-in commands."""
        show_shell_help()

        # Check that built-in commands are printed
        output = " ".join(str(call_args) for call_args in mock_print.call_args_list)
        assert "Built-in Commands" in output
        assert "help" in output
        assert "?" in output
        assert "clear" in output
        assert "history" in output
        assert "quit" in output


class TestShellMode:
    """Test shell mode functionality."""

    @patch("fsd.cli.shell.create_prompt_session")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    @patch("fsd.cli.shell.console.print")
    def test_question_mark_shows_menu(
        self, mock_console_print, mock_menu, mock_welcome, mock_session
    ):
        """Test that '?' shows the FSD menu, not shell help."""
        # Create a mock session that returns '?' then 'quit'
        mock_prompt_instance = MagicMock()
        mock_prompt_instance.prompt.side_effect = ["?", "quit"]
        mock_session.return_value = mock_prompt_instance

        # Run shell mode
        result = run_shell_mode(continuous=False)

        # Should show menu once for '?'
        mock_menu.assert_called_once()
        assert result is None

    @patch("fsd.cli.shell.create_prompt_session")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    @patch("fsd.cli.shell.console.print")
    def test_help_command_shows_menu(
        self, mock_console_print, mock_menu, mock_welcome, mock_session
    ):
        """Test that 'help' command shows the FSD menu."""
        # Create a mock session that returns 'help' then 'quit'
        mock_prompt_instance = MagicMock()
        mock_prompt_instance.prompt.side_effect = ["help", "quit"]
        mock_session.return_value = mock_prompt_instance

        # Run shell mode
        result = run_shell_mode(continuous=False)

        # Should show menu once for 'help'
        mock_menu.assert_called_once()
        assert result is None

    @patch("fsd.cli.shell.create_prompt_session")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    @patch("fsd.cli.shell.console.print")
    def test_help_and_question_mark_are_equivalent(
        self, mock_console_print, mock_menu, mock_welcome, mock_session
    ):
        """Test that 'help' and '?' behave identically."""
        # Test with '?'
        mock_prompt_instance = MagicMock()
        mock_prompt_instance.prompt.side_effect = ["?", "quit"]
        mock_session.return_value = mock_prompt_instance

        result1 = run_shell_mode(continuous=False)
        menu_call_count_1 = mock_menu.call_count

        # Reset mocks
        mock_menu.reset_mock()
        mock_session.reset_mock()

        # Test with 'help'
        mock_prompt_instance = MagicMock()
        mock_prompt_instance.prompt.side_effect = ["help", "quit"]
        mock_session.return_value = mock_prompt_instance

        result2 = run_shell_mode(continuous=False)
        menu_call_count_2 = mock_menu.call_count

        # Both should have same behavior
        assert result1 == result2
        assert menu_call_count_1 == menu_call_count_2

    @patch("fsd.cli.shell.create_prompt_session")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.shell.console.print")
    def test_quit_command(self, mock_console_print, mock_welcome, mock_session):
        """Test that 'quit' exits shell mode."""
        # Create a mock session that returns 'quit'
        mock_prompt_instance = MagicMock()
        mock_prompt_instance.prompt.return_value = "quit"
        mock_session.return_value = mock_prompt_instance

        # Run shell mode
        result = run_shell_mode(continuous=False)

        # Should return None to indicate quit
        assert result is None

    @patch("fsd.cli.shell.create_prompt_session")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.shell.console.print")
    def test_exit_command(self, mock_console_print, mock_welcome, mock_session):
        """Test that 'exit' exits shell mode."""
        # Create a mock session that returns 'exit'
        mock_prompt_instance = MagicMock()
        mock_prompt_instance.prompt.return_value = "exit"
        mock_session.return_value = mock_prompt_instance

        # Run shell mode
        result = run_shell_mode(continuous=False)

        # Should return None to indicate quit
        assert result is None

    @patch("fsd.cli.shell.create_prompt_session")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.shell.console.print")
    @patch("fsd.cli.shell.clear_screen")
    def test_clear_command(
        self, mock_clear, mock_console_print, mock_welcome, mock_session
    ):
        """Test that 'clear' clears the screen and shows welcome again."""
        # Create a mock session that returns 'clear' then 'quit'
        mock_prompt_instance = MagicMock()
        mock_prompt_instance.prompt.side_effect = ["clear", "quit"]
        mock_session.return_value = mock_prompt_instance

        # Run shell mode
        result = run_shell_mode(continuous=False)

        # Should call clear_screen once
        mock_clear.assert_called_once()
        # Should show welcome twice (initial + after clear)
        assert mock_welcome.call_count == 2
        assert result is None

    @patch("fsd.cli.shell.create_prompt_session")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.shell.console.print")
    @patch("fsd.cli.shell.show_command_history")
    def test_history_command(
        self, mock_show_history, mock_console_print, mock_welcome, mock_session
    ):
        """Test that 'history' shows command history."""
        # Create a mock session that returns 'history' then 'quit'
        mock_prompt_instance = MagicMock()
        mock_prompt_instance.prompt.side_effect = ["history", "quit"]
        mock_session.return_value = mock_prompt_instance

        # Run shell mode
        result = run_shell_mode(continuous=False)

        # Should call show_command_history once with the session
        mock_show_history.assert_called_once()
        assert result is None

    @patch("fsd.cli.shell.create_prompt_session")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.shell.console.print")
    @patch("fsd.cli.interactive._parse_command_input")
    def test_command_with_args(
        self, mock_parse, mock_console_print, mock_welcome, mock_session
    ):
        """Test that commands with arguments are parsed and returned."""
        # Create a mock session that returns 'queue list'
        mock_prompt_instance = MagicMock()
        mock_prompt_instance.prompt.return_value = "queue list"
        mock_session.return_value = mock_prompt_instance
        mock_parse.return_value = ["queue", "list"]

        # Run shell mode in non-continuous mode
        result = run_shell_mode(continuous=False)

        # Should parse the command and return the args
        mock_parse.assert_called_once_with("queue list")
        assert result == ["queue", "list"]


class TestHistoryFile:
    """Test history file path logic."""

    def test_get_history_file_returns_path(self):
        """Test that get_history_file returns a valid Path object."""
        history_file = get_history_file()

        # Should return a Path object
        assert isinstance(history_file, Path)
        # Should end with shell_history
        assert history_file.name == "shell_history"


class TestFSDCompleter:
    """Test FSD command completer."""

    def test_completer_initialization(self):
        """Test that FSD completer initializes correctly."""
        completer = FSDCompleter()

        # Should have command words
        assert len(completer.command_words) > 0
        assert "help" in completer.command_words
        assert "?" in completer.command_words
        assert "queue" in completer.command_words
        assert "status" in completer.command_words

    def test_completer_no_input(self):
        """Test completions with no input."""
        completer = FSDCompleter()
        mock_document = MagicMock()
        mock_document.text_before_cursor = ""

        completions = list(completer.get_completions(mock_document, None))

        # Should suggest all commands
        assert len(completions) > 0
        completion_texts = [c.text for c in completions]
        assert "help" in completion_texts
        assert "?" in completion_texts

    def test_completer_partial_command(self):
        """Test completions with partial command input."""
        completer = FSDCompleter()
        mock_document = MagicMock()
        mock_document.text_before_cursor = "qu"

        completions = list(completer.get_completions(mock_document, None))

        # Should suggest commands starting with 'qu'
        completion_texts = [c.text for c in completions]
        assert "queue" in completion_texts
        assert "quit" in completion_texts
