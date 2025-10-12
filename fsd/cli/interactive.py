"""Interactive mode for FSD CLI."""

import shlex
import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def show_welcome() -> None:
    """Display welcome banner."""
    console.print(
        Panel.fit(
            "[bold cyan]FSD - Autonomous Overnight Coding Agent System[/bold cyan]\n"
            "[dim]Interactive Mode[/dim]",
            border_style="cyan",
        )
    )


def show_menu() -> None:
    """Display main menu options."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Command", style="cyan bold", width=20)
    table.add_column("Description", style="dim")

    table.add_row("init", "Initialize FSD in current project")
    table.add_row("submit", "Submit a new task")
    table.add_row("queue [action]", "Manage task queue")
    table.add_row("  queue list", "List tasks in queue")
    table.add_row("  queue show", "Show task details")
    table.add_row("  queue start", "Start queue execution")
    table.add_row("  queue stop", "Stop queue execution")
    table.add_row("task show <id>", "Show any task (past/present)")
    table.add_row("task list", "List all tasks with filters")
    table.add_row("history", "Show all tasks ever executed")
    table.add_row("status", "Check system status")
    table.add_row("logs [task-id]", "View task logs")
    table.add_row("serve", "Start web interface")
    table.add_row("help [command]", "Show help (e.g., 'help queue')")
    table.add_row("?", "Show this menu")
    table.add_row("quit", "Exit interactive mode")

    console.print("\n[bold]Available commands:[/bold]")
    console.print(table)
    console.print("\n[dim]Tips:[/dim]")
    console.print("[dim]  • Use 'command --help' for detailed help (e.g., 'queue --help')[/dim]")
    console.print("[dim]  • All interactive flows support option '0' to cancel/go back[/dim]")
    console.print()


def handle_init() -> list[str]:
    """Handle init command interactively."""
    console.print("\n[bold cyan]Initialize FSD[/bold cyan]")
    console.print("[dim]This will initialize FSD in your project.[/dim]")
    console.print("  [cyan]1[/cyan] - Continue with initialization")
    console.print("  [cyan]0[/cyan] - Cancel")

    choice = click.prompt("Your choice", type=click.Choice(["0", "1"]), default="1")

    if choice == "0":
        # User wants to cancel
        console.print("[dim]Returning to main menu...[/dim]")
        return []

    project_path = click.prompt(
        "Project path",
        default=".",
        type=str,
    )

    git_auto_commit = click.confirm(
        "Enable automatic git commits?",
        default=True,
    )

    cmd_args = ["init", "--project-path", project_path]
    if git_auto_commit:
        cmd_args.append("--git-auto-commit")

    return cmd_args


def handle_submit() -> list[str]:
    """Handle submit command interactively."""
    console.print("\n[bold cyan]Submit Task[/bold cyan]")
    console.print("Choose submission method:")
    console.print("  [cyan]1[/cyan] - Natural language text")
    console.print("  [cyan]2[/cyan] - YAML file")
    console.print("  [cyan]0[/cyan] - Cancel")

    choice = click.prompt("Your choice", type=click.Choice(["0", "1", "2"]), default="1")

    if choice == "0":
        # User wants to cancel
        console.print("[dim]Returning to main menu...[/dim]")
        return []
    elif choice == "1":
        console.print(
            "\n[dim]Enter your task description. Can include priority and time estimate.[/dim]"
        )
        console.print("[dim]Example: HIGH priority: Fix login bug. Takes 30m[/dim]\n")

        text = click.prompt("Task description", type=str)
        return ["submit", "--text", text]
    else:
        file_path = click.prompt("Path to YAML file", type=str)
        return ["submit", file_path]


def handle_queue() -> list[str]:
    """Handle queue command interactively."""
    console.print("\n[bold cyan]Queue Management[/bold cyan]")
    console.print("Choose action:")
    console.print("  [cyan]1[/cyan] - List tasks")
    console.print("  [cyan]2[/cyan] - Show task details")
    console.print("  [cyan]3[/cyan] - Start execution")
    console.print("  [cyan]4[/cyan] - Stop execution")
    console.print("  [cyan]5[/cyan] - Clear queue")
    console.print("  [cyan]6[/cyan] - Retry task")
    console.print("  [cyan]0[/cyan] - Back to main menu")

    choice = click.prompt(
        "Your choice",
        type=click.Choice(["0", "1", "2", "3", "4", "5", "6"]),
        default="1",
    )

    if choice == "0":
        # User wants to go back to main menu
        console.print("[dim]Returning to main menu...[/dim]")
        return []
    elif choice == "1":
        return ["queue", "list"]
    elif choice == "2":
        task_id = click.prompt("Enter task ID to view", type=str)
        show_checkpoints = click.confirm("Show checkpoint history?", default=False)
        show_logs = click.confirm("Show execution logs?", default=False)

        cmd = ["queue", "show", task_id]
        if show_checkpoints:
            cmd.append("--checkpoints")
        if show_logs:
            cmd.append("--logs")
        return cmd
    elif choice == "3":
        return ["queue", "start"]
    elif choice == "4":
        return ["queue", "stop"]
    elif choice == "5":
        if click.confirm("Are you sure you want to clear the entire queue?", default=False):
            return ["queue", "clear"]
        else:
            console.print("[yellow]Queue clear cancelled[/yellow]")
            return []
    elif choice == "6":
        task_id = click.prompt("Enter task ID to retry", type=str)
        return ["queue", "retry", task_id]

    return []


def handle_status() -> list[str]:
    """Handle status command interactively."""
    console.print("\n[bold cyan]System Status[/bold cyan]")
    console.print("  [cyan]1[/cyan] - Show status")
    console.print("  [cyan]0[/cyan] - Cancel")

    choice = click.prompt("Your choice", type=click.Choice(["0", "1"]), default="1")

    if choice == "0":
        # User wants to cancel
        console.print("[dim]Returning to main menu...[/dim]")
        return []

    watch = click.confirm("Watch mode (auto-refresh)?", default=False)

    cmd_args = ["status"]
    if watch:
        cmd_args.append("--watch")

    return cmd_args


def handle_logs() -> list[str]:
    """Handle logs command interactively."""
    console.print("\n[bold cyan]View Logs[/bold cyan]")
    console.print("  [cyan]1[/cyan] - View logs")
    console.print("  [cyan]0[/cyan] - Cancel")

    choice = click.prompt("Your choice", type=click.Choice(["0", "1"]), default="1")

    if choice == "0":
        # User wants to cancel
        console.print("[dim]Returning to main menu...[/dim]")
        return []

    task_id = click.prompt("Task ID (or press Enter for latest)", default="", type=str)

    follow = click.confirm("Follow mode (tail -f)?", default=False)

    cmd_args = ["logs"]
    if task_id:
        cmd_args.append(task_id)
    if follow:
        cmd_args.append("--follow")

    return cmd_args


def handle_serve() -> list[str]:
    """Handle serve command interactively."""
    console.print("\n[bold cyan]Start Web Interface[/bold cyan]")
    console.print("  [cyan]1[/cyan] - Start web interface")
    console.print("  [cyan]0[/cyan] - Cancel")

    choice = click.prompt("Your choice", type=click.Choice(["0", "1"]), default="1")

    if choice == "0":
        # User wants to cancel
        console.print("[dim]Returning to main menu...[/dim]")
        return []

    port = click.prompt("Port", default=8000, type=int)
    reload = click.confirm("Enable auto-reload?", default=False)

    cmd_args = ["serve", "--port", str(port)]
    if reload:
        cmd_args.append("--reload")

    return cmd_args


def _parse_command_input(input_str: str) -> list[str]:
    """
    Parse user input into command arguments.

    Handles shell-style quoting so that arguments like --text "my text"
    are parsed correctly.

    Args:
        input_str: The full command string from user.

    Returns:
        List of command arguments (e.g., ["queue", "start"]).

    Examples:
        >>> _parse_command_input('submit --text "my task"')
        ['submit', '--text', 'my task']
        >>> _parse_command_input('queue list')
        ['queue', 'list']
    """
    try:
        # Use shlex.split() to properly handle quoted strings
        parts = shlex.split(input_str)
        return parts if parts else []
    except ValueError as e:
        # If shlex fails (e.g., unclosed quote), fall back to simple split
        console.print(f"[yellow]Warning: Failed to parse command (unclosed quote?): {e}[/yellow]")
        parts = input_str.split()
        return parts if parts else []


def _show_command_help(command: str, subcommand: str | None = None) -> None:
    """
    Display help for a specific command by invoking it with --help.

    Args:
        command: The command name (e.g., "queue", "submit", "init").
        subcommand: Optional subcommand (e.g., "list" for "queue list").
    """
    if subcommand:
        cmd = ["fsd", command, subcommand, "--help"]
        help_target = f"{command} {subcommand}"
    else:
        cmd = ["fsd", command, "--help"]
        help_target = command

    console.print(f"\n[dim]Help for '{help_target}' command:[/dim]\n")

    try:
        result = subprocess.run(cmd, capture_output=False)
        if result.returncode != 0:
            console.print(f"\n[yellow]Could not retrieve help for '{help_target}'[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error retrieving help: {e}[/red]")


def _command_requires_args(command: str, args: list[str]) -> tuple[bool, str | None]:
    """
    Check if a command requires additional arguments and is missing them.

    Args:
        command: The base command (e.g., "queue", "logs", "submit").
        args: List of arguments provided after the command.

    Returns:
        Tuple of (requires_help, subcommand):
        - requires_help: True if help should be shown
        - subcommand: The subcommand if this is a group command, None otherwise
    """
    # Commands that require subcommands (command groups)
    subcommand_groups = {
        "queue": ["list", "start", "stop", "clear", "retry"],
    }

    # Check if it's a group command without a subcommand
    if command in subcommand_groups:
        if not args or args[0] not in subcommand_groups[command]:
            # No subcommand or invalid subcommand - show help for the group
            return (True, None)
        # Valid subcommand provided
        subcommand = args[0]

        # Check if the subcommand itself requires arguments
        if command == "queue" and subcommand == "retry":
            # retry requires a task-id unless --all-failed is used
            remaining_args = args[1:]
            if not remaining_args or (
                len(remaining_args) == 1 and remaining_args[0] == "--all-failed"
            ):
                # Has --all-failed or will be handled by the command's own validation
                return (False, None)
            return (False, None)  # Let the actual command handle validation

        return (False, None)

    # For non-group commands, check if they need args
    if command == "submit":
        # submit requires either --text or a file path
        if not args:
            return (True, None)
        # Check if it looks like a valid argument
        has_text_flag = "--text" in args or "-t" in args
        has_file_arg = any(not arg.startswith("-") for arg in args)
        if not has_text_flag and not has_file_arg:
            return (True, None)

    return (False, None)


def run_interactive_mode(
    continuous: bool = False, verbose: bool = False, config: Path | None = None
) -> list[str] | None:
    """
    Run the interactive mode and return the command args to execute.

    Args:
        continuous: If True, loop continuously executing commands until quit.
                   If False, return after first valid command selection.
        verbose: Pass verbose flag to executed commands.
        config: Pass config path to executed commands.

    Returns:
        List of command arguments to execute (when continuous=False),
        or None if user quits.
    """
    show_welcome()
    show_menu()

    while True:
        user_input = click.prompt("Command", type=str).strip()
        choice = user_input.lower()

        # Handle quit
        if choice in ("q", "quit", "exit"):
            console.print("[yellow]Goodbye![/yellow]")
            return None

        # Handle help menu
        if choice == "?":
            show_menu()
            continue

        # Parse the input into command parts
        cmd_parts = _parse_command_input(choice)
        if not cmd_parts:
            continue

        base_cmd = cmd_parts[0]
        has_args = len(cmd_parts) > 1

        # Handle 'help' command (e.g., 'help', 'help queue', 'help submit')
        if base_cmd == "help":
            if has_args:
                # 'help <command>' - show help for specific command
                target_cmd = cmd_parts[1]
                _show_command_help(target_cmd)
            else:
                # Just 'help' - show the main menu
                show_menu()
            continue

        # Handle 'command --help' syntax (e.g., 'queue --help', 'submit --help')
        if has_args and cmd_parts[-1] == "--help":
            # Remove --help and show help for the command
            _show_command_help(base_cmd)
            continue

        # Map command names and numbers to handlers
        handlers = {
            "1": handle_init,
            "init": handle_init,
            "2": handle_submit,
            "submit": handle_submit,
            "3": handle_queue,
            "queue": handle_queue,
            "4": handle_status,
            "status": handle_status,
            "5": handle_logs,
            "logs": handle_logs,
            "6": handle_serve,
            "serve": handle_serve,
        }

        # Get the arguments (everything after the base command)
        cmd_args_only = cmd_parts[1:] if has_args else []

        # Check if this command needs help due to missing required arguments
        needs_help, subcommand = _command_requires_args(base_cmd, cmd_args_only)
        if needs_help:
            # Show help instead of trying to execute
            _show_command_help(base_cmd, subcommand)
            continue

        # If command has arguments, try to execute directly
        if has_args:
            if continuous:
                _execute_command(cmd_parts, verbose, config)
                console.print()  # Add blank line for visual separation
            else:
                return cmd_parts
        # If no arguments and matches a handler, use the handler
        elif base_cmd in handlers:
            handler = handlers[base_cmd]
            cmd_args = handler()
            if cmd_args:  # Only proceed if we have valid command args
                if continuous:
                    # Execute the command and loop back to prompt
                    _execute_command(cmd_args, verbose, config)
                    console.print()  # Add blank line for visual separation
                else:
                    # Return command args for external execution
                    return cmd_args
            # If empty list returned (e.g., cancelled operation), show prompt again
        # Otherwise, try to execute as-is (single word commands like "status")
        else:
            if continuous:
                _execute_command(cmd_parts, verbose, config)
                console.print()
            else:
                return cmd_parts


def _execute_command(cmd_args: list[str], verbose: bool, config: Path | None) -> None:
    """
    Execute a command with the given arguments.

    Args:
        cmd_args: Command arguments to execute.
        verbose: Whether to enable verbose output.
        config: Optional config file path.
    """
    cmd = ["fsd"] + cmd_args
    if verbose:
        cmd.append("--verbose")
    if config:
        cmd.extend(["--config", str(config)])

    console.print(f"\n[dim]Executing: {' '.join(cmd)}[/dim]\n")

    try:
        result = subprocess.run(cmd)
        if result.returncode != 0:
            console.print(f"\n[yellow]Command exited with code {result.returncode}[/yellow]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Command interrupted[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error executing command: {e}[/red]")
