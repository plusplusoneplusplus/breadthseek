"""FSD history command - list all tasks ever executed."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from fsd.core.task_schema import load_task_from_yaml

console = Console()


@click.command()
@click.option(
    "--status",
    "-s",
    type=click.Choice(["all", "queued", "running", "completed", "failed"]),
    default="all",
    help="Filter tasks by status",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=50,
    help="Maximum number of tasks to show (default: 50)",
)
@click.option(
    "--all",
    "-a",
    "show_all",
    is_flag=True,
    help="Show all tasks (no limit)",
)
def history_command(status: str, limit: int, show_all: bool) -> None:
    """List all tasks ever executed in this project.

    Shows historical view of all tasks including completed and cleared tasks.
    Data is pulled from state files, logs, and queue.

    Examples:
        fsd history                    # Show recent 50 tasks
        fsd history --all              # Show all tasks
        fsd history --status completed # Only completed tasks
        fsd history --status failed    # Only failed tasks
        fsd history -n 10              # Show last 10 tasks
    """
    try:
        fsd_dir = Path.cwd() / ".fsd"
        if not fsd_dir.exists():
            raise click.ClickException("FSD not initialized. Run 'fsd init' first.")

        # Gather all task data
        tasks = _gather_all_tasks(fsd_dir)

        if not tasks:
            console.print("[yellow]No tasks found in history[/yellow]")
            console.print("Submit tasks with 'fsd submit' to get started")
            return

        # Filter by status if requested
        if status != "all":
            tasks = [t for t in tasks if t.get("status") == status]

        if not tasks:
            console.print(f"[yellow]No {status} tasks found[/yellow]")
            return

        # Sort by creation time (newest first)
        tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)

        # Apply limit
        if not show_all and len(tasks) > limit:
            tasks_to_show = tasks[:limit]
            remaining = len(tasks) - limit
        else:
            tasks_to_show = tasks
            remaining = 0

        # Show summary
        _display_summary(tasks, status)

        # Show task table
        _display_task_table(tasks_to_show)

        # Show note about remaining tasks
        if remaining > 0:
            console.print(f"\n[dim]Showing {limit} of {len(tasks)} tasks. Use --all to see all tasks.[/dim]")
            console.print(f"[dim]Or use: fsd history -n {len(tasks)}[/dim]")

    except Exception as e:
        console.print(f"[red]Failed to show history:[/red] {e}")
        raise click.ClickException(f"Failed to show history: {e}")


def _gather_all_tasks(fsd_dir: Path) -> List[Dict[str, Any]]:
    """Gather all task information from all sources.

    Returns:
        List of task dictionaries with all available information
    """
    tasks = {}

    # 1. Get tasks from state directory (most comprehensive for historical data)
    state_dir = fsd_dir / "state"
    if state_dir.exists():
        for state_file in state_dir.glob("*.json"):
            task_id = state_file.stem
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state_data = json.load(f)

                tasks[task_id] = {
                    "task_id": task_id,
                    "status": state_data.get("current_state", "unknown"),
                    "created_at": state_data.get("created_at", ""),
                    "updated_at": state_data.get("updated_at", ""),
                    "retry_count": state_data.get("retry_count", 0),
                    "error": state_data.get("error_message"),
                    "state_transitions": len(state_data.get("history", [])),
                    "numeric_id": None,
                    "source": "state",
                }
            except Exception as e:
                console.print(f"[dim]Warning: Could not load state for {task_id}: {e}[/dim]")

    # 2. Supplement with status information
    status_dir = fsd_dir / "status"
    if status_dir.exists():
        for status_file in status_dir.glob("*.json"):
            task_id = status_file.stem
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    status_data = json.load(f)

                if task_id in tasks:
                    # Update status if available
                    tasks[task_id]["status"] = status_data.get("status", tasks[task_id]["status"])
                else:
                    # Create minimal entry
                    tasks[task_id] = {
                        "task_id": task_id,
                        "status": status_data.get("status", "unknown"),
                        "created_at": "",
                        "updated_at": status_data.get("updated_at", ""),
                        "source": "status",
                    }
            except Exception:
                pass

    # 3. Check which tasks are still in queue and load numeric IDs
    queue_dir = fsd_dir / "queue"
    if queue_dir.exists():
        for queue_file in queue_dir.glob("*.yaml"):
            task_id = queue_file.stem
            try:
                task_def = load_task_from_yaml(queue_file)
                if task_id in tasks:
                    tasks[task_id]["in_queue"] = True
                    tasks[task_id]["numeric_id"] = task_def.numeric_id
                else:
                    # Task in queue but no state yet
                    tasks[task_id] = {
                        "task_id": task_id,
                        "status": "queued",
                        "created_at": datetime.fromtimestamp(queue_file.stat().st_ctime).isoformat(),
                        "updated_at": "",
                        "numeric_id": task_def.numeric_id,
                        "in_queue": True,
                        "source": "queue",
                    }
            except Exception:
                # If we can't load the YAML, just mark as in queue without numeric_id
                if task_id in tasks:
                    tasks[task_id]["in_queue"] = True
                else:
                    tasks[task_id] = {
                        "task_id": task_id,
                        "status": "queued",
                        "created_at": datetime.fromtimestamp(queue_file.stat().st_ctime).isoformat(),
                        "updated_at": "",
                        "numeric_id": None,
                        "in_queue": True,
                        "source": "queue",
                    }

    # 4. Check for logs and checkpoints to enrich data
    logs_dir = fsd_dir / "logs"
    checkpoints_dir = fsd_dir / "checkpoints"

    for task_id in tasks:
        # Check for logs
        log_file = logs_dir / f"{task_id}.jsonl"
        if log_file.exists():
            tasks[task_id]["has_logs"] = True
            tasks[task_id]["log_size"] = log_file.stat().st_size
        else:
            tasks[task_id]["has_logs"] = False

        # Check for checkpoints
        checkpoint_dir = checkpoints_dir / task_id
        if checkpoint_dir.exists():
            checkpoint_count = len(list(checkpoint_dir.glob("*.json")))
            tasks[task_id]["checkpoint_count"] = checkpoint_count
        else:
            tasks[task_id]["checkpoint_count"] = 0

    return list(tasks.values())


def _display_summary(tasks: List[Dict[str, Any]], status_filter: str) -> None:
    """Display summary statistics."""
    # Count by status
    by_status = {}
    for task in tasks:
        task_status = task.get("status", "unknown")
        by_status[task_status] = by_status.get(task_status, 0) + 1

    # Build summary
    summary = []
    summary.append(f"[bold]Total Tasks:[/bold] {len(tasks)}")

    if status_filter == "all" and by_status:
        summary.append("")
        summary.append("[bold]By Status:[/bold]")
        # Order: queued, planning, executing, validating, completed, failed
        status_order = ["queued", "planning", "executing", "validating", "completed", "failed"]
        for status in status_order:
            if status in by_status:
                count = by_status[status]
                status_colors = {
                    "queued": "blue",
                    "planning": "cyan",
                    "executing": "yellow",
                    "validating": "magenta",
                    "completed": "green",
                    "failed": "red",
                }
                color = status_colors.get(status, "white")
                summary.append(f"  [{color}]{status}[/{color}]: {count}")

        # Show any other statuses
        for status in sorted(by_status.keys()):
            if status not in status_order:
                summary.append(f"  {status}: {by_status[status]}")

    # Show tasks with logs/checkpoints
    tasks_with_logs = sum(1 for t in tasks if t.get("has_logs"))
    tasks_with_checkpoints = sum(1 for t in tasks if t.get("checkpoint_count", 0) > 0)

    if tasks_with_logs or tasks_with_checkpoints:
        summary.append("")
        summary.append(f"[dim]Tasks with logs: {tasks_with_logs}[/dim]")
        summary.append(f"[dim]Tasks with checkpoints: {tasks_with_checkpoints}[/dim]")

    panel = Panel(
        "\n".join(summary),
        title="[bold cyan]Task History Summary[/bold cyan]",
        border_style="cyan",
    )
    console.print(panel)
    console.print()


def _display_task_table(tasks: List[Dict[str, Any]]) -> None:
    """Display tasks in a table."""
    table = Table(title="Task History")
    table.add_column("#", style="dim cyan", no_wrap=True)
    table.add_column("Task ID", style="cyan", no_wrap=True)
    table.add_column("Status", style="yellow")
    table.add_column("Created", style="dim")
    table.add_column("Retries", style="magenta")
    table.add_column("Checkpoints", style="blue")
    table.add_column("Logs", style="green")
    table.add_column("Location", style="dim")

    for task in tasks:
        task_id = task.get("task_id", "")

        # Numeric ID
        numeric_id = task.get("numeric_id")
        numeric_display = str(numeric_id) if numeric_id else "-"

        status = task.get("status", "unknown")

        # Color code status
        status_colors = {
            "queued": "[blue]queued[/blue]",
            "planning": "[cyan]planning[/cyan]",
            "executing": "[yellow]executing[/yellow]",
            "validating": "[magenta]validating[/magenta]",
            "completed": "[green]completed[/green]",
            "failed": "[red]failed[/red]",
        }
        status_display = status_colors.get(status, status)

        # Format created time
        created = task.get("created_at", "")
        if created:
            try:
                # Parse ISO format and display nicely
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created_display = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                created_display = created[:16] if len(created) > 16 else created
        else:
            created_display = "-"

        # Retry count
        retry_count = task.get("retry_count", 0)
        retry_display = str(retry_count) if retry_count > 0 else "-"

        # Checkpoints
        checkpoint_count = task.get("checkpoint_count", 0)
        checkpoint_display = str(checkpoint_count) if checkpoint_count > 0 else "-"

        # Logs
        has_logs = task.get("has_logs", False)
        log_size = task.get("log_size", 0)
        if has_logs and log_size > 0:
            log_kb = log_size / 1024
            if log_kb < 1:
                logs_display = f"{log_size}B"
            elif log_kb < 1024:
                logs_display = f"{log_kb:.1f}KB"
            else:
                logs_display = f"{log_kb/1024:.1f}MB"
        else:
            logs_display = "-"

        # Location
        in_queue = task.get("in_queue", False)
        location = "queue" if in_queue else "archive"

        table.add_row(
            numeric_display,
            task_id,
            status_display,
            created_display,
            retry_display,
            checkpoint_display,
            logs_display,
            location,
        )

    console.print(table)


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"
