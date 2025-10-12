"""FSD task commands - for viewing any task (past or present)."""

import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fsd.core.task_schema import TaskDefinition, load_task_from_yaml
from fsd.core.checkpoint_manager import CheckpointManager

console = Console()


@click.command()
@click.argument("task_id")
@click.option("--checkpoints", "-c", is_flag=True, help="Show checkpoint history")
@click.option("--logs", "-l", is_flag=True, help="Show execution logs summary")
def task_command(task_id: str, checkpoints: bool, logs: bool) -> None:
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
