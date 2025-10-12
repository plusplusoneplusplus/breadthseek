"""Tests for FSD interactive mode."""

from unittest.mock import Mock, patch

from fsd.cli.interactive import (
    _command_requires_args,
    _parse_command_input,
    _show_command_help,
    run_interactive_mode,
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
        mock_run.assert_called_once_with(["fsd", "queue", "--help"], capture_output=False)

        # Verify header was printed
        assert any("queue" in str(call_args) for call_args in mock_print.call_args_list)

    @patch("fsd.cli.interactive.subprocess.run")
    @patch("fsd.cli.interactive.console.print")
    def test_show_help_for_queue_with_subcommand(self, mock_print, mock_run):
        """Test showing help for queue subcommand."""
        mock_run.return_value = Mock(returncode=0)

        _show_command_help("queue", "list")

        # Verify subprocess was called with correct command
        mock_run.assert_called_once_with(["fsd", "queue", "list", "--help"], capture_output=False)

        # Verify header was printed with both command and subcommand
        assert any("queue list" in str(call_args) for call_args in mock_print.call_args_list)

    @patch("fsd.cli.interactive.subprocess.run")
    @patch("fsd.cli.interactive.console.print")
    def test_show_help_for_submit(self, mock_print, mock_run):
        """Test showing help for submit command."""
        mock_run.return_value = Mock(returncode=0)

        _show_command_help("submit")

        mock_run.assert_called_once_with(["fsd", "submit", "--help"], capture_output=False)

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
            "Could not retrieve help" in str(call_args) for call_args in mock_print.call_args_list
        )

    @patch("fsd.cli.interactive.subprocess.run")
    @patch("fsd.cli.interactive.console.print")
    def test_show_help_exception(self, mock_print, mock_run):
        """Test error handling when subprocess fails."""
        mock_run.side_effect = Exception("Subprocess error")

        _show_command_help("queue")

        # Should print error message
        assert any(
            "Error retrieving help" in str(call_args) for call_args in mock_print.call_args_list
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
    def test_submit_without_args_shows_help(self, mock_help, mock_menu, mock_welcome, mock_prompt):
        """Test that 'submit' without args shows help."""
        mock_prompt.side_effect = ["submit --verbose", "quit"]

        result = run_interactive_mode(continuous=False)

        # Should show help for submit command since --verbose is not --text or a file
        mock_help.assert_called_once_with("submit", None)
        assert result is None

    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.show_welcome")
    @patch("fsd.cli.interactive.show_menu")
    def test_queue_with_subcommand_executes(self, mock_menu, mock_welcome, mock_prompt):
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


class TestHandleQueue:
    """Test queue handler functionality."""

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    def test_queue_back_option(self, mock_prompt, mock_print):
        """Test that selecting '0' in queue menu returns empty list (go back)."""
        from fsd.cli.interactive import handle_queue

        # User selects option '0' (Back)
        mock_prompt.return_value = "0"

        result = handle_queue()

        # Should return empty list to indicate going back to main menu
        assert result == []

        # Should print message about returning to main menu
        assert any(
            "Returning to main menu" in str(call_args) for call_args in mock_print.call_args_list
        )

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    def test_queue_list_option(self, mock_prompt, mock_print):
        """Test that selecting '1' in queue menu returns queue list command."""
        from fsd.cli.interactive import handle_queue

        # User selects option '1' (List tasks)
        mock_prompt.return_value = "1"

        result = handle_queue()

        # Should return command to list tasks
        assert result == ["queue", "list"]

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    def test_queue_start_option(self, mock_prompt, mock_print):
        """Test that selecting '2' in queue menu returns queue start command."""
        from fsd.cli.interactive import handle_queue

        # User selects option '2' (Start execution)
        mock_prompt.return_value = "2"

        result = handle_queue()

        # Should return command to start queue
        assert result == ["queue", "start"]

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_queue_clear_confirmed(self, mock_confirm, mock_prompt, mock_print):
        """Test that selecting '4' and confirming clears the queue."""
        from fsd.cli.interactive import handle_queue

        # User selects option '4' (Clear queue) and confirms
        mock_prompt.return_value = "4"
        mock_confirm.return_value = True

        result = handle_queue()

        # Should return command to clear queue
        assert result == ["queue", "clear"]

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_queue_clear_cancelled(self, mock_confirm, mock_prompt, mock_print):
        """Test that cancelling clear returns to menu."""
        from fsd.cli.interactive import handle_queue

        # User selects option '4' (Clear queue) but cancels
        mock_prompt.return_value = "4"
        mock_confirm.return_value = False

        result = handle_queue()

        # Should return empty list
        assert result == []

        # Should print cancellation message
        assert any("cancelled" in str(call_args).lower() for call_args in mock_print.call_args_list)

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    def test_queue_retry_option(self, mock_prompt, mock_print):
        """Test that selecting '5' prompts for task ID and returns retry command."""
        from fsd.cli.interactive import handle_queue

        # Mock two prompts: first for menu choice, second for task ID
        mock_prompt.side_effect = ["5", "task-123"]

        result = handle_queue()

        # Should return command to retry task
        assert result == ["queue", "retry", "task-123"]


class TestHandleInit:
    """Test init handler functionality."""

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    def test_init_cancel_option(self, mock_prompt, mock_print):
        """Test that selecting '0' in init menu returns empty list (cancel)."""
        from fsd.cli.interactive import handle_init

        # User selects option '0' (Cancel)
        mock_prompt.return_value = "0"

        result = handle_init()

        # Should return empty list to indicate cancellation
        assert result == []

        # Should print message about returning to main menu
        assert any(
            "Returning to main menu" in str(call_args) for call_args in mock_print.call_args_list
        )

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_init_continue_option(self, mock_confirm, mock_prompt, mock_print):
        """Test that selecting '1' and providing inputs returns init command."""
        from fsd.cli.interactive import handle_init

        # Mock prompts: choice '1', project path '.', and confirm for git
        mock_prompt.side_effect = ["1", "."]
        mock_confirm.return_value = True

        result = handle_init()

        # Should return command to init with auto-commit enabled
        assert result == ["init", "--project-path", ".", "--git-auto-commit"]

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_init_custom_path_no_git(self, mock_confirm, mock_prompt, mock_print):
        """Test init with custom project path and git auto-commit disabled."""
        from fsd.cli.interactive import handle_init

        # Mock prompts: choice '1', custom path, and decline git
        mock_prompt.side_effect = ["1", "/custom/path"]
        mock_confirm.return_value = False

        result = handle_init()

        # Should return command to init without auto-commit
        assert result == ["init", "--project-path", "/custom/path"]


class TestHandleSubmit:
    """Test submit handler functionality."""

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    def test_submit_cancel_option(self, mock_prompt, mock_print):
        """Test that selecting '0' in submit menu returns empty list (cancel)."""
        from fsd.cli.interactive import handle_submit

        # User selects option '0' (Cancel)
        mock_prompt.return_value = "0"

        result = handle_submit()

        # Should return empty list to indicate cancellation
        assert result == []

        # Should print message about returning to main menu
        assert any(
            "Returning to main menu" in str(call_args) for call_args in mock_print.call_args_list
        )

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    def test_submit_text_option(self, mock_prompt, mock_print):
        """Test that selecting '1' prompts for text and returns submit command."""
        from fsd.cli.interactive import handle_submit

        # Mock two prompts: first for menu choice, second for task description
        mock_prompt.side_effect = ["1", "Fix the login bug"]

        result = handle_submit()

        # Should return command to submit via text
        assert result == ["submit", "--text", "Fix the login bug"]

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    def test_submit_yaml_option(self, mock_prompt, mock_print):
        """Test that selecting '2' prompts for file path and returns submit command."""
        from fsd.cli.interactive import handle_submit

        # Mock two prompts: first for menu choice, second for file path
        mock_prompt.side_effect = ["2", "task.yaml"]

        result = handle_submit()

        # Should return command to submit via YAML file
        assert result == ["submit", "task.yaml"]


class TestHandleStatus:
    """Test status handler functionality."""

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    def test_status_cancel_option(self, mock_prompt, mock_print):
        """Test that selecting '0' in status menu returns empty list (cancel)."""
        from fsd.cli.interactive import handle_status

        # User selects option '0' (Cancel)
        mock_prompt.return_value = "0"

        result = handle_status()

        # Should return empty list to indicate cancellation
        assert result == []

        # Should print message about returning to main menu
        assert any(
            "Returning to main menu" in str(call_args) for call_args in mock_print.call_args_list
        )

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_status_show_without_watch(self, mock_confirm, mock_prompt, mock_print):
        """Test that selecting '1' and declining watch returns status command."""
        from fsd.cli.interactive import handle_status

        # User selects option '1' (Show status) and declines watch mode
        mock_prompt.return_value = "1"
        mock_confirm.return_value = False

        result = handle_status()

        # Should return command to show status without watch
        assert result == ["status"]

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_status_show_with_watch(self, mock_confirm, mock_prompt, mock_print):
        """Test that selecting '1' and enabling watch returns status command with --watch."""
        from fsd.cli.interactive import handle_status

        # User selects option '1' (Show status) and enables watch mode
        mock_prompt.return_value = "1"
        mock_confirm.return_value = True

        result = handle_status()

        # Should return command to show status with watch
        assert result == ["status", "--watch"]


class TestHandleLogs:
    """Test logs handler functionality."""

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    def test_logs_cancel_option(self, mock_prompt, mock_print):
        """Test that selecting '0' in logs menu returns empty list (cancel)."""
        from fsd.cli.interactive import handle_logs

        # User selects option '0' (Cancel)
        mock_prompt.return_value = "0"

        result = handle_logs()

        # Should return empty list to indicate cancellation
        assert result == []

        # Should print message about returning to main menu
        assert any(
            "Returning to main menu" in str(call_args) for call_args in mock_print.call_args_list
        )

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_logs_view_with_task_id_no_follow(self, mock_confirm, mock_prompt, mock_print):
        """Test that selecting '1' with task ID and no follow returns logs command."""
        from fsd.cli.interactive import handle_logs

        # User selects option '1' (View logs), provides task ID, and declines follow mode
        mock_prompt.side_effect = ["1", "task-123"]
        mock_confirm.return_value = False

        result = handle_logs()

        # Should return command to view logs for task-123
        assert result == ["logs", "task-123"]

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_logs_view_with_task_id_with_follow(self, mock_confirm, mock_prompt, mock_print):
        """Test that selecting '1' with task ID and follow returns logs command with --follow."""
        from fsd.cli.interactive import handle_logs

        # User selects option '1' (View logs), provides task ID, and enables follow mode
        mock_prompt.side_effect = ["1", "task-123"]
        mock_confirm.return_value = True

        result = handle_logs()

        # Should return command to view logs for task-123 with follow
        assert result == ["logs", "task-123", "--follow"]

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_logs_view_latest_no_follow(self, mock_confirm, mock_prompt, mock_print):
        """Test that selecting '1' with empty task ID (latest) and no follow returns logs command."""
        from fsd.cli.interactive import handle_logs

        # User selects option '1' (View logs), presses Enter for latest, and declines follow mode
        mock_prompt.side_effect = ["1", ""]
        mock_confirm.return_value = False

        result = handle_logs()

        # Should return command to view logs without task ID (latest)
        assert result == ["logs"]

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_logs_view_latest_with_follow(self, mock_confirm, mock_prompt, mock_print):
        """Test that selecting '1' with empty task ID and follow returns logs command with --follow."""
        from fsd.cli.interactive import handle_logs

        # User selects option '1' (View logs), presses Enter for latest, and enables follow mode
        mock_prompt.side_effect = ["1", ""]
        mock_confirm.return_value = True

        result = handle_logs()

        # Should return command to view logs with follow
        assert result == ["logs", "--follow"]


class TestHandleServe:
    """Test serve handler functionality."""

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    def test_serve_cancel_option(self, mock_prompt, mock_print):
        """Test that selecting '0' in serve menu returns empty list (cancel)."""
        from fsd.cli.interactive import handle_serve

        # User selects option '0' (Cancel)
        mock_prompt.return_value = "0"

        result = handle_serve()

        # Should return empty list to indicate cancellation
        assert result == []

        # Should print message about returning to main menu
        assert any(
            "Returning to main menu" in str(call_args) for call_args in mock_print.call_args_list
        )

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_serve_start_without_reload(self, mock_confirm, mock_prompt, mock_print):
        """Test that selecting '1' and declining reload returns serve command."""
        from fsd.cli.interactive import handle_serve

        # User selects option '1' (Start), provides port, and declines reload
        mock_prompt.side_effect = ["1", 8080]
        mock_confirm.return_value = False

        result = handle_serve()

        # Should return command to start serve on port 8080 without reload
        assert result == ["serve", "--port", "8080"]

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_serve_start_with_reload(self, mock_confirm, mock_prompt, mock_print):
        """Test that selecting '1' and enabling reload returns serve command with --reload."""
        from fsd.cli.interactive import handle_serve

        # User selects option '1' (Start), provides port, and enables reload
        mock_prompt.side_effect = ["1", 3000]
        mock_confirm.return_value = True

        result = handle_serve()

        # Should return command to start serve on port 3000 with reload
        assert result == ["serve", "--port", "3000", "--reload"]

    @patch("fsd.cli.interactive.console.print")
    @patch("fsd.cli.interactive.click.prompt")
    @patch("fsd.cli.interactive.click.confirm")
    def test_serve_start_default_port_no_reload(self, mock_confirm, mock_prompt, mock_print):
        """Test that selecting '1' with default port and no reload returns serve command."""
        from fsd.cli.interactive import handle_serve

        # User selects option '1' (Start), uses default port 8000, and declines reload
        mock_prompt.side_effect = ["1", 8000]
        mock_confirm.return_value = False

        result = handle_serve()

        # Should return command to start serve on default port 8000
        assert result == ["serve", "--port", "8000"]
