"""FSD status command."""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


@click.command()
@click.option(
    "--watch",
    "-w",
    is_flag=True,
    help="Watch status in real-time (refresh every 5 seconds)",
)
def status_command(watch: bool) -> None:
    """Check current execution status.

    Shows the current state of the FSD system, including running tasks,
    queue status, and recent activity.

    Examples:
        fsd status          # Show current status
        fsd status --watch  # Watch status in real-time
    """
    try:
        if watch:
            _watch_status()
        else:
            _show_status()

    except KeyboardInterrupt:
        console.print("\n[yellow]Status monitoring stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to get status:[/red] {e}")
        raise click.ClickException(f"Status check failed: {e}")


def _show_status() -> None:
    """Show current status once."""
    fsd_dir = Path.cwd() / ".fsd"

    if not fsd_dir.exists():
        console.print("[yellow]FSD not initialized[/yellow]")
        console.print("Run 'fsd init' to initialize FSD in this project")
        return

    # Get system status
    system_status = _get_system_status(fsd_dir)

    # Display status overview
    _display_status_overview(system_status)

    # Display task details if any are running
    if system_status["running_tasks"]:
        _display_running_tasks(system_status["running_tasks"])

    # Display queue summary
    _display_queue_summary(system_status)


def _watch_status() -> None:
    """Watch status in real-time."""
    console.print("[dim]Watching FSD status... Press Ctrl+C to stop[/dim]\n")

    import time

    while True:
        # Clear screen and show status
        console.clear()
        console.print("[bold]FSD Status Monitor[/bold]")
        console.print(
            f"[dim]Last updated: {datetime.now().strftime('%H:%M:%S')}[/dim]\n"
        )

        _show_status()

        # Wait 5 seconds
        time.sleep(5)


def _get_system_status(fsd_dir: Path) -> Dict[str, Any]:
    """Get comprehensive system status."""
    status_dir = fsd_dir / "status"
    queue_dir = fsd_dir / "queue"

    # Count tasks by status
    task_counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0}
    running_tasks = []

    if queue_dir.exists():
        for task_file in queue_dir.glob("*.yaml"):
            task_id = task_file.stem
            status = _get_task_status(status_dir, task_id)

            if status in task_counts:
                task_counts[status] += 1

            if status == "running":
                running_tasks.append({"id": task_id, "file": task_file})

    # Check if execution is active
    execution_active = len(running_tasks) > 0

    # Get recent activity
    recent_activity = _get_recent_activity(fsd_dir)

    return {
        "execution_active": execution_active,
        "task_counts": task_counts,
        "running_tasks": running_tasks,
        "recent_activity": recent_activity,
        "fsd_dir": fsd_dir,
    }


def _get_task_status(status_dir: Path, task_id: str) -> str:
    """Get status of a specific task."""
    status_file = status_dir / f"{task_id}.json"

    if not status_file.exists():
        return "queued"

    try:
        with open(status_file, "r", encoding="utf-8") as f:
            status_data = json.load(f)
        return status_data.get("status", "queued")
    except Exception:
        return "queued"


def _get_recent_activity(fsd_dir: Path) -> list:
    """Get recent activity from logs."""
    logs_dir = fsd_dir / "logs"

    if not logs_dir.exists():
        return []

    # For now, return placeholder activity
    # This will be implemented with actual log parsing later
    return [
        {"time": "12:30:45", "event": "System initialized"},
        {"time": "12:31:20", "event": "Task 'example-task' queued"},
    ]


def _display_status_overview(status: Dict[str, Any]) -> None:
    """Display system status overview."""
    # Execution status
    if status["execution_active"]:
        exec_status = "[yellow]Active[/yellow]"
        exec_icon = "🟡"
    else:
        exec_status = "[green]Idle[/green]"
        exec_icon = "🟢"

    # Create status panel
    status_text = f"""
{exec_icon} [bold]Execution Status:[/bold] {exec_status}

[bold]Task Queue:[/bold]
• Queued: {status['task_counts']['queued']}
• Running: {status['task_counts']['running']}
• Completed: {status['task_counts']['completed']}
• Failed: {status['task_counts']['failed']}

[bold]Total Tasks:[/bold] {sum(status['task_counts'].values())}
"""

    panel = Panel(status_text.strip(), title="FSD System Status", border_style="blue")

    console.print(panel)


def _display_running_tasks(running_tasks: list) -> None:
    """Display details of currently running tasks."""
    if not running_tasks:
        return

    console.print("\n[bold]Running Tasks:[/bold]")

    table = Table()
    table.add_column("Task ID", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Progress", style="green")

    for task_info in running_tasks:
        # For now, show placeholder progress
        # This will be implemented with actual progress tracking later
        table.add_row(task_info["id"], "Executing", "In progress...")

    console.print(table)


def _display_queue_summary(status: Dict[str, Any]) -> None:
    """Display queue summary."""
    if status["task_counts"]["queued"] == 0:
        return

    console.print(f"\n[bold]Next in Queue:[/bold]")

    # Show next few queued tasks
    queue_dir = status["fsd_dir"] / "queue"
    status_dir = status["fsd_dir"] / "status"

    queued_files = []
    for task_file in queue_dir.glob("*.yaml"):
        task_id = task_file.stem
        if _get_task_status(status_dir, task_id) == "queued":
            queued_files.append(task_file)

    # Sort by priority (this is simplified - real implementation would parse YAML)
    queued_files.sort(key=lambda f: f.stat().st_mtime)

    for i, task_file in enumerate(queued_files[:3]):  # Show first 3
        console.print(f"  {i+1}. {task_file.stem}")

    if len(queued_files) > 3:
        console.print(f"  ... and {len(queued_files) - 3} more")


def _display_recent_activity(activity: list) -> None:
    """Display recent activity."""
    if not activity:
        return

    console.print("\n[bold]Recent Activity:[/bold]")

    for event in activity[-5:]:  # Show last 5 events
        console.print(f"  [dim]{event['time']}[/dim] {event['event']}")
