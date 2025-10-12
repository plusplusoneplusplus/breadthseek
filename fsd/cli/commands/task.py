"""FSD task commands - for viewing and listing tasks (past or present)."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fsd.core.task_schema import TaskDefinition, load_task_from_yaml
from fsd.core.checkpoint_manager import CheckpointManager

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def task_group(ctx: click.Context) -> None:
    """View and manage tasks (past or present).

    Commands for showing task details and listing all tasks with filtering.
    """
    # If no subcommand was provided, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@task_group.command("show")
@click.argument("task_id")
@click.option("--checkpoints", "-c", is_flag=True, help="Show checkpoint history")
@click.option("--logs", "-l", is_flag=True, help="Show execution logs summary")
def show_command(task_id: str, checkpoints: bool, logs: bool) -> None:
    """Show detailed information about any task (past or present).

    This command works for tasks in the queue, completed tasks, and cleared tasks.
    It searches all FSD directories to find task information.

    Examples:
        fsd task show my-task              # Show task details
        fsd task show my-task --checkpoints # Include checkpoint history
        fsd task show my-task --logs       # Include logs summary
        fsd task show my-task -c -l        # Show everything
    """
    try:
        fsd_dir = Path.cwd() / ".fsd"
        if not fsd_dir.exists():
            raise click.ClickException("FSD not initialized. Run 'fsd init' first.")

        # Try to find task data from various sources
        task_info = _find_task_data(task_id, fsd_dir)

        if not task_info:
            raise click.ClickException(
                f"Task '{task_id}' not found. No data exists for this task."
            )

        # Display what we found
        _display_task_overview(task_info)

        # Show checkpoint history if requested
        if checkpoints:
            _display_checkpoint_history(task_id, fsd_dir)

        # Show logs summary if requested
        if logs:
            _display_logs_summary(task_id, fsd_dir)

    except Exception as e:
        console.print(f"[red]Failed to show task:[/red] {e}")
        raise click.ClickException(f"Failed to show task: {e}")


def _find_task_data(task_id: str, fsd_dir: Path) -> Optional[dict]:
    """Find task data from all available sources.

    Returns:
        Dictionary with task information or None if not found
    """
    task_info = {
        "task_id": task_id,
        "task_def": None,
        "state": None,
        "status": None,
        "source": None,
    }

    # 1. Try to load from queue (current tasks)
    queue_file = fsd_dir / "queue" / f"{task_id}.yaml"
    if queue_file.exists():
        try:
            task_info["task_def"] = load_task_from_yaml(queue_file)
            task_info["source"] = "queue"
        except Exception as e:
            console.print(f"[dim]Warning: Could not load task definition: {e}[/dim]")

    # 2. Load state information (if exists)
    state_file = fsd_dir / "state" / f"{task_id}.json"
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                task_info["state"] = json.load(f)
            if not task_info["source"]:
                task_info["source"] = "state"
        except Exception as e:
            console.print(f"[dim]Warning: Could not load state: {e}[/dim]")

    # 3. Load status information
    status_file = fsd_dir / "status" / f"{task_id}.json"
    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status_data = json.load(f)
                task_info["status"] = status_data.get("status", "unknown")
        except Exception:
            pass

    # If we have state but no status, use state's current_state
    if not task_info["status"] and task_info["state"]:
        task_info["status"] = task_info["state"].get("current_state", "unknown")

    # Return None if we found absolutely nothing
    if not task_info["task_def"] and not task_info["state"]:
        return None

    return task_info


def _display_task_overview(task_info: dict) -> None:
    """Display comprehensive task overview."""
    task_def = task_info.get("task_def")
    state = task_info.get("state")
    status = task_info.get("status", "unknown")
    source = task_info.get("source", "unknown")

    # Status colors
    status_colors = {
        "queued": "blue",
        "running": "yellow",
        "completed": "green",
        "failed": "red",
        "planning": "cyan",
        "executing": "yellow",
        "validating": "magenta",
    }
    status_color = status_colors.get(status, "white")

    # Build overview
    overview = []

    # Basic info
    overview.append(f"[bold]Task ID:[/bold] {task_info['task_id']}")
    overview.append(f"[bold]Status:[/bold] [{status_color}]{status}[/{status_color}]")
    overview.append(f"[bold]Data Source:[/bold] {source}")
    overview.append("")

    # Task definition (if available)
    if task_def:
        if task_def.numeric_id:
            overview.append(f"[bold]Numeric ID:[/bold] #{task_def.numeric_id}")
        overview.append(f"[bold]Priority:[/bold] {task_def.priority.value}")
        overview.append(f"[bold]Estimated Duration:[/bold] {task_def.estimated_duration}")
        overview.append("")
        overview.append(f"[bold]Description:[/bold]")
        overview.append(f"  {task_def.description}")

        if task_def.context:
            overview.append("")
            overview.append(f"[bold]Context:[/bold]")
            overview.append(f"  {task_def.context}")

        if task_def.focus_files:
            overview.append("")
            overview.append(f"[bold]Focus Files:[/bold]")
            for file in task_def.focus_files:
                overview.append(f"  • {file}")

        if task_def.success_criteria:
            overview.append("")
            overview.append(f"[bold]Success Criteria:[/bold]")
            overview.append(f"  {task_def.success_criteria}")

        if task_def.on_completion:
            overview.append("")
            overview.append(f"[bold]On Completion:[/bold]")
            if task_def.on_completion.create_pr:
                overview.append(f"  • Create PR: {task_def.on_completion.pr_title}")
            if task_def.on_completion.notify_slack:
                overview.append(f"  • Notify Slack")
    else:
        overview.append("[dim]Task definition not available (task may have been cleared)[/dim]")

    # State information (if available)
    if state:
        overview.append("")
        overview.append("[bold]State Information:[/bold]")
        created_at = state.get("created_at", "N/A")
        updated_at = state.get("updated_at", "N/A")
        overview.append(f"  Created: {created_at}")
        overview.append(f"  Updated: {updated_at}")

        retry_count = state.get("retry_count", 0)
        if retry_count > 0:
            overview.append(f"  Retry Count: {retry_count}")

        error = state.get("error_message")
        if error:
            overview.append(f"  [red]Error: {error}[/red]")

        # State transitions
        history = state.get("history", [])
        if history:
            overview.append("")
            overview.append(f"  [bold]Recent Transitions:[/bold]")
            for entry in history[-5:]:
                from_state = entry.get("from_state", "?")
                to_state = entry.get("to_state", "?")
                timestamp = entry.get("timestamp", "?")
                overview.append(f"    {from_state} → {to_state} [{timestamp}]")

    panel = Panel(
        "\n".join(overview),
        title="[bold cyan]Task Overview[/bold cyan]",
        border_style="cyan",
    )
    console.print(panel)


def _display_checkpoint_history(task_id: str, fsd_dir: Path) -> None:
    """Display checkpoint history for the task."""
    try:
        checkpoint_manager = CheckpointManager(checkpoint_dir=fsd_dir / "checkpoints")
        checkpoints = checkpoint_manager.list_checkpoints(task_id)

        if not checkpoints:
            console.print("\n[dim]No checkpoints found[/dim]")
            return

        console.print()

        # Create checkpoint table
        table = Table(title="Checkpoint History")
        table.add_column("Type", style="cyan")
        table.add_column("Created", style="dim")
        table.add_column("Commit", style="yellow", no_wrap=True)
        table.add_column("Files", style="magenta")
        table.add_column("Description", style="white")

        for checkpoint in checkpoints:
            created = checkpoint.created_at.strftime("%Y-%m-%d %H:%M:%S")
            commit_short = checkpoint.commit_hash[:8]
            files_count = str(len(checkpoint.files_changed))
            desc = checkpoint.description or "-"

            # Truncate long descriptions
            if len(desc) > 40:
                desc = desc[:37] + "..."

            table.add_row(
                checkpoint.checkpoint_type.value,
                created,
                commit_short,
                files_count,
                desc,
            )

        console.print(table)

        # Show summary stats
        stats = checkpoint_manager.get_checkpoint_stats(task_id)
        console.print(f"\n[dim]Total Checkpoints: {stats.total_checkpoints}[/dim]")
        console.print(f"[dim]Total Files Changed: {stats.total_files_changed}[/dim]")
        if stats.average_checkpoint_interval:
            interval_min = stats.average_checkpoint_interval / 60
            console.print(f"[dim]Average Interval: {interval_min:.1f} minutes[/dim]")

    except Exception as e:
        console.print(f"\n[yellow]Could not load checkpoint history: {e}[/yellow]")


def _display_logs_summary(task_id: str, fsd_dir: Path) -> None:
    """Display execution logs summary."""
    log_file = fsd_dir / "logs" / f"{task_id}.jsonl"

    if not log_file.exists():
        console.print("\n[dim]No execution logs found[/dim]")
        return

    try:
        console.print()

        entries = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue

        if not entries:
            console.print("[dim]No log entries found[/dim]")
            return

        # Show summary
        log_info = []
        log_info.append(f"[bold]Total Log Entries:[/bold] {len(entries)}")

        # Count by level
        by_level = {}
        for entry in entries:
            level = entry.get("level", "unknown")
            by_level[level] = by_level.get(level, 0) + 1

        if by_level:
            log_info.append(f"[bold]By Level:[/bold]")
            for level, count in sorted(by_level.items()):
                log_info.append(f"  {level}: {count}")

        # Show first and last entry timestamps
        if entries:
            first_time = entries[0].get("timestamp", "N/A")
            last_time = entries[-1].get("timestamp", "N/A")
            log_info.append(f"[bold]First Entry:[/bold] {first_time}")
            log_info.append(f"[bold]Last Entry:[/bold] {last_time}")

        panel = Panel(
            "\n".join(log_info),
            title="[bold green]Execution Logs Summary[/bold green]",
            border_style="green",
        )
        console.print(panel)

        # Show last few entries
        console.print("\n[bold]Recent Log Entries:[/bold]")
        for entry in entries[-10:]:
            timestamp = entry.get("timestamp", "")[:19]
            level = entry.get("level", "INFO")
            message = entry.get("message", "")

            # Color code by level
            level_colors = {
                "ERROR": "red",
                "WARNING": "yellow",
                "INFO": "blue",
                "DEBUG": "dim",
            }
            level_color = level_colors.get(level, "white")

            # Truncate long messages
            if len(message) > 80:
                message = message[:77] + "..."

            console.print(
                f"[dim]{timestamp}[/dim] [{level_color}]{level:7}[/{level_color}] {message}"
            )

        console.print(f"\n[dim]Full logs: {log_file}[/dim]")

    except Exception as e:
        console.print(f"\n[yellow]Could not load logs: {e}[/yellow]")


@task_group.command("list")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["all", "queued", "planning", "executing", "validating", "completed", "failed"]),
    default="all",
    help="Filter by status",
)
@click.option(
    "--priority",
    "-p",
    type=click.Choice(["all", "low", "medium", "high", "critical"]),
    default="all",
    help="Filter by priority",
)
@click.option(
    "--location",
    type=click.Choice(["all", "queue", "archive"]),
    default="all",
    help="Filter by location (queue=active, archive=cleared)",
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
@click.option(
    "--sort",
    type=click.Choice(["created", "updated", "status", "priority"]),
    default="created",
    help="Sort by field (default: created)",
)
@click.option(
    "--reverse",
    "-r",
    is_flag=True,
    help="Reverse sort order",
)
def list_command(
    status: str,
    priority: str,
    location: str,
    limit: int,
    show_all: bool,
    sort: str,
    reverse: bool,
) -> None:
    """List all tasks with filtering and pagination.

    Shows tasks from queue and historical archives with comprehensive filtering options.

    Examples:
        fsd task list                      # Recent 50 tasks
        fsd task list --all                # All tasks
        fsd task list -s failed            # Only failed tasks
        fsd task list -p high              # Only high priority
        fsd task list --location queue     # Only active tasks
        fsd task list --sort status        # Sort by status
        fsd task list -n 10 --reverse      # Last 10, oldest first
    """
    try:
        fsd_dir = Path.cwd() / ".fsd"
        if not fsd_dir.exists():
            raise click.ClickException("FSD not initialized. Run 'fsd init' first.")

        # Gather all tasks
        tasks = _gather_all_tasks(fsd_dir)

        if not tasks:
            console.print("[yellow]No tasks found[/yellow]")
            console.print("Submit tasks with 'fsd submit' to get started")
            return

        # Apply filters
        original_count = len(tasks)
        tasks = _apply_filters(tasks, status, priority, location)

        if not tasks:
            console.print(f"[yellow]No tasks match the filters[/yellow]")
            return

        # Sort tasks
        tasks = _sort_tasks(tasks, sort, reverse)

        # Apply limit
        if not show_all and len(tasks) > limit:
            tasks_to_show = tasks[:limit]
            remaining = len(tasks) - limit
        else:
            tasks_to_show = tasks
            remaining = 0

        # Show summary
        _display_list_summary(tasks, original_count, status, priority, location)

        # Show task table
        _display_task_list_table(tasks_to_show)

        # Show pagination info
        if remaining > 0:
            console.print(f"\n[dim]Showing {limit} of {len(tasks)} filtered tasks (of {original_count} total).[/dim]")
            console.print(f"[dim]Use --all or -n {len(tasks)} to see all filtered tasks.[/dim]")
        elif len(tasks) < original_count:
            console.print(f"\n[dim]Showing {len(tasks)} filtered tasks (of {original_count} total).[/dim]")

    except Exception as e:
        console.print(f"[red]Failed to list tasks:[/red] {e}")
        raise click.ClickException(f"Failed to list tasks: {e}")


def _gather_all_tasks(fsd_dir: Path) -> List[Dict[str, Any]]:
    """Gather all task information from all sources.

    Returns:
        List of task dictionaries with all available information
    """
    tasks = {}

    # 1. Get tasks from state directory
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
                    "priority": None,
                    "numeric_id": None,
                }
            except Exception:
                pass

    # 2. Get tasks from queue (supplement with task definitions)
    queue_dir = fsd_dir / "queue"
    if queue_dir.exists():
        for queue_file in queue_dir.glob("*.yaml"):
            task_id = queue_file.stem
            try:
                task_def = load_task_from_yaml(queue_file)

                if task_id in tasks:
                    # Enhance existing entry
                    tasks[task_id]["in_queue"] = True
                    tasks[task_id]["priority"] = task_def.priority.value
                    tasks[task_id]["numeric_id"] = task_def.numeric_id
                else:
                    # New entry from queue
                    tasks[task_id] = {
                        "task_id": task_id,
                        "status": "queued",
                        "created_at": datetime.fromtimestamp(queue_file.stat().st_ctime).isoformat(),
                        "updated_at": "",
                        "in_queue": True,
                        "priority": task_def.priority.value,
                        "numeric_id": task_def.numeric_id,
                    }
            except Exception:
                pass

    # 3. Check for logs and checkpoints
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

        # Mark location
        tasks[task_id]["location"] = "queue" if tasks[task_id].get("in_queue") else "archive"

    return list(tasks.values())


def _apply_filters(
    tasks: List[Dict[str, Any]],
    status: str,
    priority: str,
    location: str,
) -> List[Dict[str, Any]]:
    """Apply filters to task list."""
    filtered = tasks

    # Filter by status
    if status != "all":
        filtered = [t for t in filtered if t.get("status") == status]

    # Filter by priority
    if priority != "all":
        filtered = [t for t in filtered if t.get("priority") == priority]

    # Filter by location
    if location != "all":
        filtered = [t for t in filtered if t.get("location") == location]

    return filtered


def _sort_tasks(
    tasks: List[Dict[str, Any]],
    sort_by: str,
    reverse: bool,
) -> List[Dict[str, Any]]:
    """Sort tasks by specified field."""
    # Sort key functions
    def get_sort_key(task: Dict[str, Any]) -> Any:
        if sort_by == "created":
            return task.get("created_at", "")
        elif sort_by == "updated":
            return task.get("updated_at", "")
        elif sort_by == "status":
            # Order: queued, planning, executing, validating, completed, failed
            status_order = {"queued": 0, "planning": 1, "executing": 2, "validating": 3, "completed": 4, "failed": 5}
            return status_order.get(task.get("status", "unknown"), 99)
        elif sort_by == "priority":
            # Order: critical, high, medium, low
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            return priority_order.get(task.get("priority", "medium"), 99)
        else:
            return ""

    # Default sort is newest first for created/updated
    default_reverse = sort_by in ["created", "updated"]

    # If user specified reverse, flip it
    if reverse:
        sort_reverse = not default_reverse
    else:
        sort_reverse = default_reverse

    return sorted(tasks, key=get_sort_key, reverse=sort_reverse)


def _display_list_summary(
    tasks: List[Dict[str, Any]],
    original_count: int,
    status_filter: str,
    priority_filter: str,
    location_filter: str,
) -> None:
    """Display summary for task list."""
    summary = []

    # Show filtering info if any filters applied
    filters_applied = []
    if status_filter != "all":
        filters_applied.append(f"status={status_filter}")
    if priority_filter != "all":
        filters_applied.append(f"priority={priority_filter}")
    if location_filter != "all":
        filters_applied.append(f"location={location_filter}")

    if filters_applied:
        filter_str = ", ".join(filters_applied)
        summary.append(f"[bold]Filters:[/bold] {filter_str}")
        summary.append(f"[bold]Matching Tasks:[/bold] {len(tasks)} of {original_count}")
    else:
        summary.append(f"[bold]Total Tasks:[/bold] {len(tasks)}")

    # Count by status (of filtered tasks)
    if status_filter == "all":
        by_status = {}
        for task in tasks:
            task_status = task.get("status", "unknown")
            by_status[task_status] = by_status.get(task_status, 0) + 1

        if by_status:
            summary.append("")
            summary.append("[bold]By Status:[/bold]")
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

    panel = Panel(
        "\n".join(summary),
        title="[bold cyan]Task List Summary[/bold cyan]",
        border_style="cyan",
    )
    console.print(panel)
    console.print()


def _display_task_list_table(tasks: List[Dict[str, Any]]) -> None:
    """Display tasks in a compact table."""
    table = Table(title="Tasks")
    table.add_column("ID", style="cyan", no_wrap=True, max_width=30)
    table.add_column("#", style="dim", no_wrap=True)
    table.add_column("Status", style="yellow", no_wrap=True)
    table.add_column("Priority", style="magenta", no_wrap=True)
    table.add_column("Created", style="dim", no_wrap=True)
    table.add_column("CP", style="blue", no_wrap=True)  # Checkpoints
    table.add_column("Logs", style="green", no_wrap=True)
    table.add_column("Loc", style="dim", no_wrap=True)

    for task in tasks:
        task_id = task.get("task_id", "")

        # Truncate long task IDs
        if len(task_id) > 28:
            task_id_display = task_id[:25] + "..."
        else:
            task_id_display = task_id

        # Numeric ID
        numeric_id = task.get("numeric_id")
        numeric_display = str(numeric_id) if numeric_id else "-"

        # Status
        status = task.get("status", "unknown")
        status_colors = {
            "queued": "[blue]queued[/blue]",
            "planning": "[cyan]plan[/cyan]",
            "executing": "[yellow]exec[/yellow]",
            "validating": "[magenta]valid[/magenta]",
            "completed": "[green]done[/green]",
            "failed": "[red]failed[/red]",
        }
        status_display = status_colors.get(status, status[:6])

        # Priority
        priority = task.get("priority", "-")
        if priority and priority != "-":
            priority_colors = {
                "critical": "[red bold]CRIT[/red bold]",
                "high": "[red]HIGH[/red]",
                "medium": "[yellow]MED[/yellow]",
                "low": "[dim]LOW[/dim]",
            }
            priority_display = priority_colors.get(priority, priority[:4].upper())
        else:
            priority_display = "-"

        # Created time
        created = task.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created_display = dt.strftime("%m-%d %H:%M")
            except Exception:
                created_display = created[:14] if len(created) > 14 else created
        else:
            created_display = "-"

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
            elif log_kb < 100:
                logs_display = f"{log_kb:.0f}K"
            else:
                logs_display = f"{log_kb/1024:.1f}M"
        else:
            logs_display = "-"

        # Location
        location = task.get("location", "archive")
        location_display = "Q" if location == "queue" else "A"

        table.add_row(
            task_id_display,
            numeric_display,
            status_display,
            priority_display,
            created_display,
            checkpoint_display,
            logs_display,
            location_display,
        )

    console.print(table)
