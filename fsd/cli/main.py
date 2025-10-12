"""Main CLI entry point for FSD."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from fsd.cli.commands.init import init_command
from fsd.cli.commands.submit import submit_command
from fsd.cli.commands.queue import queue_group
from fsd.cli.commands.status import status_command
from fsd.cli.commands.logs import logs_command
from fsd.cli.commands.serve import serve_command
from fsd.cli.interactive import run_interactive_mode
from fsd.core.exceptions import FSDError

console = Console()


@click.group(invoke_without_command=True)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config: Optional[Path]) -> None:
    """FSD: Autonomous Overnight Coding Agent System.

    A Feature-Sliced Design system that enables a CLI-based coding agent to work
    autonomously overnight, executing multi-step development tasks with checkpoints,
    recovery mechanisms, and human-in-the-loop safeguards.

    \b
    Examples:
        fsd init                    # Initialize FSD in current project
        fsd submit task.yaml        # Submit a task from YAML file
        fsd submit --text "HIGH priority: Fix login bug. Takes 30m"  # Natural language task
        fsd queue list              # List queued tasks
        fsd queue start             # Start execution
        fsd status                  # Check status
        fsd logs task-123           # View task logs
        fsd serve                   # Start web interface
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Store global options in context
    ctx.obj["verbose"] = verbose
    ctx.obj["config"] = config

    # Set up console for verbose mode
    if verbose:
        console.print("[dim]FSD CLI starting with verbose output enabled[/dim]")

    # If no subcommand was provided, enter interactive mode
    if ctx.invoked_subcommand is None:
        # Check if we're already in a re-invocation (for nested command execution)
        if not os.environ.get("FSD_INTERACTIVE_MODE"):
            # Set environment variable to prevent nested interactive modes
            os.environ["FSD_INTERACTIVE_MODE"] = "1"

            # Run in continuous mode - loops until user quits
            run_interactive_mode(continuous=True, verbose=verbose, config=config)

            # Clean up and exit
            sys.exit(0)


# Add command groups and commands
cli.add_command(init_command, name="init")
cli.add_command(submit_command, name="submit")
cli.add_command(queue_group, name="queue")
cli.add_command(status_command, name="status")
cli.add_command(logs_command, name="logs")
cli.add_command(serve_command, name="serve")


def main() -> None:
    """Main entry point for the CLI."""
    try:
        cli()
    except FSDError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        if "--verbose" in sys.argv or "-v" in sys.argv:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
