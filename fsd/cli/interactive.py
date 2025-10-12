"""Interactive mode for FSD CLI."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

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
    table.add_column("Option", style="cyan bold", width=8)
    table.add_column("Command", style="green")
    table.add_column("Description", style="dim")

    table.add_row("1", "init", "Initialize FSD in current project")
    table.add_row("2", "submit", "Submit a new task")
    table.add_row("3", "queue", "Manage task queue")
    table.add_row("4", "status", "Check system status")
    table.add_row("5", "logs", "View task logs")
    table.add_row("6", "serve", "Start web interface")
    table.add_row("q", "quit", "Exit interactive mode")

    console.print("\n[bold]What would you like to do?[/bold]")
    console.print(table)
    console.print()


def handle_init() -> list[str]:
    """Handle init command interactively."""
    console.print("\n[bold cyan]Initialize FSD[/bold cyan]")

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

    choice = click.prompt("Your choice", type=click.Choice(["1", "2"]), default="1")

    if choice == "1":
        console.print("\n[dim]Enter your task description. Can include priority and time estimate.[/dim]")
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
    console.print("  [cyan]2[/cyan] - Start execution")
    console.print("  [cyan]3[/cyan] - Stop execution")
    console.print("  [cyan]4[/cyan] - Clear queue")
    console.print("  [cyan]5[/cyan] - Retry task")

    choice = click.prompt(
        "Your choice",
        type=click.Choice(["1", "2", "3", "4", "5"]),
        default="1",
    )

    if choice == "1":
        return ["queue", "list"]
    elif choice == "2":
        return ["queue", "start"]
    elif choice == "3":
        return ["queue", "stop"]
    elif choice == "4":
        if click.confirm("Are you sure you want to clear the entire queue?", default=False):
            return ["queue", "clear"]
        else:
            console.print("[yellow]Queue clear cancelled[/yellow]")
            return []
    elif choice == "5":
        task_id = click.prompt("Enter task ID to retry", type=str)
        return ["queue", "retry", task_id]

    return []


def handle_status() -> list[str]:
    """Handle status command interactively."""
    console.print("\n[bold cyan]System Status[/bold cyan]")

    watch = click.confirm("Watch mode (auto-refresh)?", default=False)

    cmd_args = ["status"]
    if watch:
        cmd_args.append("--watch")

    return cmd_args


def handle_logs() -> list[str]:
    """Handle logs command interactively."""
    console.print("\n[bold cyan]View Logs[/bold cyan]")

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

    port = click.prompt("Port", default=8000, type=int)
    reload = click.confirm("Enable auto-reload?", default=False)

    cmd_args = ["serve", "--port", str(port)]
    if reload:
        cmd_args.append("--reload")

    return cmd_args


def run_interactive_mode(
    continuous: bool = False, verbose: bool = False, config: Optional[Path] = None
) -> Optional[list[str]]:
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

    while True:
        show_menu()
        choice = click.prompt("Select option", type=str).lower().strip()

        if choice == "q" or choice == "quit":
            console.print("[yellow]Goodbye![/yellow]")
            return None

        # Map choices to handlers
        handlers = {
            "1": handle_init,
            "2": handle_submit,
            "3": handle_queue,
            "4": handle_status,
            "5": handle_logs,
            "6": handle_serve,
        }

        handler = handlers.get(choice)
        if handler:
            cmd_args = handler()
            if cmd_args:  # Only proceed if we have valid command args
                if continuous:
                    # Execute the command and loop back to menu
                    _execute_command(cmd_args, verbose, config)
                    console.print("\n[dim]Press Enter to continue...[/dim]")
                    input()
                else:
                    # Return command args for external execution
                    return cmd_args
            # If empty list returned (e.g., cancelled operation), show menu again
        else:
            console.print(f"[red]Invalid option: {choice}[/red]")
            console.print("[dim]Press Enter to continue...[/dim]")
            input()


def _execute_command(cmd_args: list[str], verbose: bool, config: Optional[Path]) -> None:
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
