"""FSD logs command."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


@click.command()
@click.argument("task_id", required=False)
@click.option("--follow", "-f", is_flag=True, help="Follow log output in real-time")
@click.option(
    "--lines", "-n", type=int, default=50, help="Number of lines to show (default: 50)"
)
@click.option(
    "--level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARN", "ERROR"]),
    help="Filter by log level",
)
def logs_command(
    task_id: Optional[str], follow: bool, lines: int, level: Optional[str]
) -> None:
    """View task execution logs.

    Shows detailed logs for a specific task or recent system activity.
    Logs include task execution steps, errors, and system events.

    Examples:
        fsd logs                    # Show recent system logs
        fsd logs my-task           # Show logs for specific task
        fsd logs my-task --follow  # Follow task logs in real-time
        fsd logs --level ERROR     # Show only error logs
    """
    try:
        fsd_dir = Path.cwd() / ".fsd"

        if not fsd_dir.exists():
            console.print("[yellow]FSD not initialized[/yellow]")
            console.print("Run 'fsd init' to initialize FSD in this project")
            return

        if task_id:
            if follow:
                _follow_task_logs(fsd_dir, task_id, level)
            else:
                _show_task_logs(fsd_dir, task_id, lines, level)
        else:
            _show_system_logs(fsd_dir, lines, level)

    except KeyboardInterrupt:
        console.print("\n[yellow]Log viewing stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to show logs:[/red] {e}")
        raise click.ClickException(f"Log viewing failed: {e}")


def _show_task_logs(
    fsd_dir: Path, task_id: str, lines: int, level: Optional[str]
) -> None:
    """Show logs for a specific task."""
    logs_dir = fsd_dir / "logs"
    task_log_file = logs_dir / f"{task_id}.log"

    if not task_log_file.exists():
        console.print(f"[yellow]No logs found for task '{task_id}'[/yellow]")
        console.print(
            "Task may not have been executed yet or logs may have been cleaned up"
        )
        return

    console.print(f"[bold]Logs for task: {task_id}[/bold]\n")

    try:
        log_entries = _read_log_file(task_log_file, lines, level)
        _display_log_entries(log_entries)

    except Exception as e:
        console.print(f"[red]Failed to read task logs:[/red] {e}")


def _show_system_logs(fsd_dir: Path, lines: int, level: Optional[str]) -> None:
    """Show recent system logs."""
    logs_dir = fsd_dir / "logs"

    if not logs_dir.exists():
        console.print("[yellow]No logs directory found[/yellow]")
        console.print("No tasks have been executed yet")
        return

    console.print("[bold]Recent System Activity[/bold]\n")

    # Collect logs from all task files
    all_entries = []

    for log_file in logs_dir.glob("*.log"):
        try:
            entries = _read_log_file(log_file, None, level)
            all_entries.extend(entries)
        except Exception as e:
            console.print(f"[red]Warning: Failed to read {log_file}: {e}[/red]")

    if not all_entries:
        console.print("[yellow]No log entries found[/yellow]")
        return

    # Sort by timestamp and take last N entries
    all_entries.sort(key=lambda e: e.get("timestamp", ""))
    recent_entries = all_entries[-lines:] if lines else all_entries

    _display_log_entries(recent_entries)


def _follow_task_logs(fsd_dir: Path, task_id: str, level: Optional[str]) -> None:
    """Follow task logs in real-time."""
    logs_dir = fsd_dir / "logs"
    task_log_file = logs_dir / f"{task_id}.log"

    console.print(f"[dim]Following logs for task: {task_id}[/dim]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    import time

    # Track file position
    last_position = 0

    while True:
        if task_log_file.exists():
            try:
                with open(task_log_file, "r", encoding="utf-8") as f:
                    f.seek(last_position)
                    new_content = f.read()

                    if new_content:
                        # Parse new log entries
                        for line in new_content.strip().split("\n"):
                            if line.strip():
                                try:
                                    entry = json.loads(line)
                                    if not level or entry.get("level") == level:
                                        _display_log_entry(entry)
                                except json.JSONDecodeError:
                                    # Handle non-JSON log lines
                                    console.print(line)

                    last_position = f.tell()

            except Exception as e:
                console.print(f"[red]Error reading log file:[/red] {e}")

        time.sleep(1)  # Check for new content every second


def _read_log_file(
    log_file: Path, lines: Optional[int], level: Optional[str]
) -> List[Dict[str, Any]]:
    """Read and parse log file."""
    entries = []

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Try to parse as JSON
                    entry = json.loads(line)

                    # Filter by level if specified
                    if level and entry.get("level") != level:
                        continue

                    entries.append(entry)

                except json.JSONDecodeError:
                    # Handle non-JSON log lines
                    entries.append(
                        {
                            "timestamp": "unknown",
                            "level": "INFO",
                            "message": line,
                            "raw": True,
                        }
                    )

    except Exception as e:
        raise Exception(f"Failed to read log file {log_file}: {e}")

    # Return last N entries if lines specified
    if lines:
        return entries[-lines:]

    return entries


def _display_log_entries(entries: List[Dict[str, Any]]) -> None:
    """Display multiple log entries."""
    if not entries:
        console.print("[yellow]No log entries to display[/yellow]")
        return

    for entry in entries:
        _display_log_entry(entry)


def _display_log_entry(entry: Dict[str, Any]) -> None:
    """Display a single log entry."""
    # Handle raw text entries
    if entry.get("raw"):
        console.print(entry["message"])
        return

    # Format structured log entry
    timestamp = entry.get("timestamp", "unknown")
    level = entry.get("level", "INFO")
    message = entry.get("message", "")

    # Color code by level
    level_colors = {
        "DEBUG": "[dim]DEBUG[/dim]",
        "INFO": "[blue]INFO[/blue]",
        "WARN": "[yellow]WARN[/yellow]",
        "ERROR": "[red]ERROR[/red]",
    }

    colored_level = level_colors.get(level, level)

    # Format timestamp (extract time part if full ISO format)
    if "T" in timestamp:
        time_part = timestamp.split("T")[1].split(".")[0]
    else:
        time_part = timestamp

    console.print(f"[dim]{time_part}[/dim] {colored_level} {message}")

    # Show additional fields if present
    for key, value in entry.items():
        if key not in ["timestamp", "level", "message", "raw"]:
            if key == "error" and value:
                # Format error details
                console.print(f"  [red]Error:[/red] {value}")
            elif key == "task_id":
                console.print(f"  [cyan]Task:[/cyan] {value}")
            elif key == "step":
                console.print(f"  [magenta]Step:[/magenta] {value}")
            elif isinstance(value, (dict, list)):
                # Format complex data structures
                console.print(f"  [dim]{key}:[/dim]")
                syntax = Syntax(
                    json.dumps(value, indent=2),
                    "json",
                    theme="monokai",
                    line_numbers=False,
                )
                console.print(syntax)
            else:
                console.print(f"  [dim]{key}:[/dim] {value}")

    console.print()  # Add blank line between entries
