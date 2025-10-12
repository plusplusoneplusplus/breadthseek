"""FSD queue commands."""

from pathlib import Path
from typing import List, Dict, Any
import json

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from fsd.core.task_schema import TaskDefinition, load_task_from_yaml
from fsd.core.state_machine import TaskStateMachine
from fsd.core.state_persistence import StatePersistence
from fsd.core.checkpoint_manager import CheckpointManager
from fsd.core.claude_executor import ClaudeExecutor
from fsd.core.task_resolver import resolve_task_id
from fsd.orchestrator.phase_executor import PhaseExecutor
from fsd.tracking.activity_logger import ActivityLogger

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def queue_group(ctx: click.Context) -> None:
    """Manage the task queue.

    Commands for listing, starting, stopping, and managing queued tasks.
    """
    # If no subcommand was provided, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@queue_group.command("list")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["all", "queued", "running", "completed", "failed"]),
    default="all",
    help="Filter tasks by status",
)
def list_command(status: str) -> None:
    """List tasks in the queue.

    Shows all tasks with their current status, priority, and estimated duration.

    Examples:
        fsd queue list              # List all tasks
        fsd queue list --status queued  # Only queued tasks
        fsd queue list -s running   # Only running tasks
    """
    try:
        tasks = _get_all_tasks()

        if not tasks:
            console.print("[yellow]No tasks found[/yellow]")
            console.print("Use 'fsd submit' to add tasks to the queue")
            return

        # Filter by status if requested
        if status != "all":
            tasks = [t for t in tasks if t.get("status", "queued") == status]

        if not tasks:
            console.print(f"[yellow]No {status} tasks found[/yellow]")
            return

        # Create table
        table = Table(title="Task Queue")
        table.add_column("#", style="dim cyan", no_wrap=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Priority", style="magenta")
        table.add_column("Duration", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Description", style="white")

        for task_info in tasks:
            task_status = task_info.get("status", "queued")
            description = task_info["task"].description

            # Truncate long descriptions
            if len(description) > 50:
                description = description[:47] + "..."

            # Color code status
            status_color = {
                "queued": "[blue]queued[/blue]",
                "running": "[yellow]running[/yellow]",
                "completed": "[green]completed[/green]",
                "failed": "[red]failed[/red]",
            }.get(task_status, task_status)

            # Display numeric ID if available
            numeric_id = str(task_info["task"].numeric_id) if task_info["task"].numeric_id else "-"

            table.add_row(
                numeric_id,
                task_info["task"].id,
                task_info["task"].priority.value,
                task_info["task"].estimated_duration,
                status_color,
                description,
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Failed to list tasks:[/red] {e}")
        raise click.ClickException(f"Failed to list tasks: {e}")


@queue_group.command("start")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["interactive", "autonomous", "overnight"]),
    default="interactive",
    help="Execution mode",
)
@click.option("--task-id", "-t", help="Execute specific task (supports numeric ID, e.g., '4')")
def start_command(mode: str, task_id: str) -> None:
    """Start task execution.

    Begins processing tasks in the queue according to their priority
    and dependencies.

    You can specify a task by:
    - Numeric ID (e.g., "4" or "#4")
    - Full task ID (e.g., "fix-login-bug-a1b2c3")
    - Partial task ID (e.g., "fix-login")

    Examples:
        fsd queue start                     # Interactive mode
        fsd queue start --mode autonomous   # Autonomous mode
        fsd queue start --mode overnight    # Overnight mode
        fsd queue start --task-id 4         # Execute task by numeric ID
        fsd queue start --task-id my-task   # Execute specific task
    """
    try:
        fsd_dir = Path.cwd() / ".fsd"
        if not fsd_dir.exists():
            raise click.ClickException("FSD not initialized. Run 'fsd init' first.")

        tasks = _get_queued_tasks()

        if not tasks:
            console.print("[yellow]No queued tasks found[/yellow]")
            return

        if task_id:
            # Resolve task ID (supports numeric IDs, partial IDs, and full IDs)
            resolved_task_id = resolve_task_id(task_id, fsd_dir)
            if not resolved_task_id:
                raise click.ClickException(
                    f"Task '{task_id}' not found. "
                    "Use 'fsd queue list' to see available tasks."
                )

            # Execute specific task
            task_found = False
            for task_info in tasks:
                if task_info["task"].id == resolved_task_id:
                    task_found = True
                    console.print(f"[blue]Executing task:[/blue] {resolved_task_id}")
                    _execute_task(task_info["task"], mode)
                    break

            if not task_found:
                raise click.ClickException(f"Task '{resolved_task_id}' not found in queue")
        else:
            # Execute all queued tasks
            console.print(f"[blue]Starting execution in {mode} mode[/blue]")
            console.print(f"[dim]Found {len(tasks)} queued task(s)[/dim]")

            for task_info in tasks:
                console.print(f"\n[blue]Executing:[/blue] {task_info['task'].id}")
                _execute_task(task_info["task"], mode)

        console.print("\n[green]✓[/green] Execution completed")

    except Exception as e:
        console.print(f"[red]Execution failed:[/red] {e}")
        raise click.ClickException(f"Execution failed: {e}")


@queue_group.command("clear")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["all", "completed", "failed"]),
    default="completed",
    help="Clear tasks with specific status",
)
@click.confirmation_option(prompt="Are you sure you want to clear tasks?")
def clear_command(status: str) -> None:
    """Clear tasks from the queue.

    Removes completed or failed tasks to clean up the queue.

    Examples:
        fsd queue clear                 # Clear completed tasks
        fsd queue clear --status all    # Clear all tasks
        fsd queue clear --status failed # Clear only failed tasks
    """
    try:
        fsd_dir = Path.cwd() / ".fsd"
        queue_dir = fsd_dir / "queue"

        if not queue_dir.exists():
            console.print("[yellow]No queue directory found[/yellow]")
            return

        cleared_count = 0

        for task_file in queue_dir.glob("*.yaml"):
            task_status = _get_task_status(task_file.stem)

            should_clear = (
                status == "all"
                or (status == "completed" and task_status == "completed")
                or (status == "failed" and task_status == "failed")
            )

            if should_clear:
                task_file.unlink()
                cleared_count += 1

        console.print(f"[green]✓[/green] Cleared {cleared_count} task(s)")

    except Exception as e:
        console.print(f"[red]Failed to clear tasks:[/red] {e}")
        raise click.ClickException(f"Failed to clear tasks: {e}")


def _get_all_tasks() -> List[Dict[str, Any]]:
    """Get all tasks with their status."""
    fsd_dir = Path.cwd() / ".fsd"
    queue_dir = fsd_dir / "queue"

    if not queue_dir.exists():
        return []

    tasks = []

    for task_file in queue_dir.glob("*.yaml"):
        try:
            task = load_task_from_yaml(task_file)
            status = _get_task_status(task.id)

            tasks.append({"task": task, "status": status, "file": task_file})
        except Exception as e:
            console.print(f"[red]Warning: Failed to load {task_file}: {e}[/red]")

    # Sort by priority and creation time
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    tasks.sort(
        key=lambda t: (
            priority_order.get(t["task"].priority.value, 99),
            t["file"].stat().st_mtime,
        )
    )

    return tasks


def _get_queued_tasks() -> List[Dict[str, Any]]:
    """Get only queued tasks."""
    all_tasks = _get_all_tasks()
    return [t for t in all_tasks if t["status"] == "queued"]


def _get_task_status(task_id: str) -> str:
    """Get the current status of a task."""
    fsd_dir = Path.cwd() / ".fsd"
    status_file = fsd_dir / "status" / f"{task_id}.json"

    if not status_file.exists():
        return "queued"

    try:
        with open(status_file, "r", encoding="utf-8") as f:
            status_data = json.load(f)
        return status_data.get("status", "queued")
    except Exception:
        return "queued"


def _execute_task(task: TaskDefinition, mode: str) -> None:
    """Execute a single task using the orchestrator."""
    console.print(f"[dim]Mode:[/dim] {mode}")
    console.print(f"[dim]Priority:[/dim] {task.priority.value}")
    console.print(f"[dim]Duration:[/dim] {task.estimated_duration}")
    console.print()

    # Set up directories
    fsd_dir = Path.cwd() / ".fsd"
    state_dir = fsd_dir / "state"
    status_dir = fsd_dir / "status"
    logs_dir = fsd_dir / "logs"
    checkpoints_dir = fsd_dir / "checkpoints"

    state_dir.mkdir(exist_ok=True)
    status_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    checkpoints_dir.mkdir(exist_ok=True)

    # Initialize components
    persistence = StatePersistence(state_dir)
    state_machine = TaskStateMachine(persistence_handler=persistence)
    checkpoint_manager = CheckpointManager()
    claude_executor = ClaudeExecutor()

    # Generate session ID for this execution
    from datetime import datetime
    session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Set up activity logger
    activity_logger = ActivityLogger(session_id=session_id, logs_dir=logs_dir)

    # Set up log file for this task
    log_file = logs_dir / f"{task.id}.jsonl"

    # Define progress callback for step updates
    def progress_callback(step_num: int, total_steps: int, description: str) -> None:
        """Display step progress to console."""
        console.print(f"[cyan]Step {step_num}/{total_steps}:[/cyan] {description[:80]}")

    # Create phase executor
    executor = PhaseExecutor(
        state_machine=state_machine,
        checkpoint_manager=checkpoint_manager,
        claude_executor=claude_executor,
        log_file=log_file,
        progress_callback=progress_callback,
    )

    try:
        # Log task start
        activity_logger.log_task_start(task.id, task.description)

        console.print(f"[blue]Starting execution of task:[/blue] {task.id}")
        console.print(f"[dim]Logs:[/dim] {log_file}")
        console.print()

        # Execute task through all phases
        result = executor.execute_task(task.id)

        if result.completed:
            console.print(f"\n[green]✓ Task completed successfully[/green]")
            if result.retry_count > 0:
                console.print(f"[dim](completed after {result.retry_count} retries)[/dim]")
            console.print(f"[dim]Duration:[/dim] {result.duration_seconds:.1f}s")

            # Log task completion
            activity_logger.log_task_complete(
                task.id,
                duration_ms=int(result.duration_seconds * 1000)
            )

            # Update status to completed
            _update_task_status(task.id, "completed")
        else:
            console.print(f"\n[red]✗ Task failed[/red]")
            console.print(f"[dim]Error:[/dim] {result.error_message}")
            console.print(f"[dim]Duration:[/dim] {result.duration_seconds:.1f}s")

            # Log task failure
            activity_logger.log_task_fail(
                task.id,
                error=result.error_message or "Unknown error",
                duration_ms=int(result.duration_seconds * 1000)
            )

            # Update status to failed
            _update_task_status(task.id, "failed")

    except KeyboardInterrupt:
        console.print("\n[yellow]Task execution interrupted by user[/yellow]")
        _update_task_status(task.id, "failed")
        activity_logger.log_task_fail(task.id, error="Interrupted by user", duration_ms=0)
        raise
    except Exception as e:
        console.print(f"\n[red]Task execution failed with exception:[/red] {e}")
        _update_task_status(task.id, "failed")
        activity_logger.log_task_fail(task.id, error=str(e), duration_ms=0)
        raise


@queue_group.command("show")
@click.argument("task_id_or_number")
@click.option("--checkpoints", "-c", is_flag=True, help="Show checkpoint history")
@click.option("--logs", "-l", is_flag=True, help="Show execution logs summary")
def show_command(task_id_or_number: str, checkpoints: bool, logs: bool) -> None:
    """Show detailed information about a task.

    Displays task definition, current status, checkpoint history,
    and execution logs for the specified task.

    You can specify the task by:
    - Numeric ID (e.g., "4" or "#4")
    - Full task ID (e.g., "fix-login-bug-a1b2c3")
    - Partial task ID (e.g., "fix-login")

    Examples:
        fsd queue show 4                    # Show task by numeric ID
        fsd queue show my-task              # Show task details
        fsd queue show my-task --checkpoints # Include checkpoint history
        fsd queue show my-task --logs       # Include logs summary
        fsd queue show my-task -c -l        # Show everything
    """
    try:
        fsd_dir = Path.cwd() / ".fsd"
        if not fsd_dir.exists():
            raise click.ClickException("FSD not initialized. Run 'fsd init' first.")

        # Resolve task ID (supports numeric IDs, partial IDs, and full IDs)
        task_id = resolve_task_id(task_id_or_number, fsd_dir)
        if not task_id:
            raise click.ClickException(
                f"Task '{task_id_or_number}' not found. "
                "Use 'fsd queue list' to see available tasks."
            )

        # Load task definition
        task_file = fsd_dir / "queue" / f"{task_id}.yaml"
        if not task_file.exists():
            raise click.ClickException(f"Task '{task_id}' not found in queue")

        task = load_task_from_yaml(task_file)
        status = _get_task_status(task_id)

        # Show task details
        _display_task_details(task, status)

        # Show state information
        _display_task_state(task_id, fsd_dir)

        # Show checkpoint history if requested
        if checkpoints:
            _display_checkpoint_history(task_id, fsd_dir)

        # Show logs summary if requested
        if logs:
            _display_logs_summary(task_id, fsd_dir)

    except Exception as e:
        console.print(f"[red]Failed to show task details:[/red] {e}")
        raise click.ClickException(f"Failed to show task: {e}")


@queue_group.command("retry")
@click.argument("task_id_or_number", required=False)
@click.option(
    "--all-failed",
    is_flag=True,
    help="Retry all failed tasks",
)
def retry_command(task_id_or_number: str, all_failed: bool) -> None:
    """Retry failed tasks.

    Resets the status of failed tasks back to queued so they can be executed again.

    You can specify the task by:
    - Numeric ID (e.g., "4" or "#4")
    - Full task ID (e.g., "fix-login-bug-a1b2c3")
    - Partial task ID (e.g., "fix-login")

    Examples:
        fsd queue retry 4               # Retry task by numeric ID
        fsd queue retry my-task         # Retry specific task
        fsd queue retry --all-failed    # Retry all failed tasks
    """
    try:
        if not task_id_or_number and not all_failed:
            raise click.ClickException(
                "Must provide either a task ID or use --all-failed flag"
            )

        if task_id_or_number and all_failed:
            raise click.ClickException(
                "Cannot use both task ID and --all-failed flag"
            )

        fsd_dir = Path.cwd() / ".fsd"
        if not fsd_dir.exists():
            raise click.ClickException("FSD not initialized. Run 'fsd init' first.")

        if all_failed:
            # Retry all failed tasks
            tasks = _get_all_tasks()
            failed_tasks = [t for t in tasks if t["status"] == "failed"]

            if not failed_tasks:
                console.print("[yellow]No failed tasks found[/yellow]")
                return

            console.print(f"[blue]Retrying {len(failed_tasks)} failed task(s)[/blue]")

            retry_count = 0
            for task_info in failed_tasks:
                if _retry_task(task_info["task"].id):
                    console.print(f"[green]✓[/green] Reset {task_info['task'].id} to queued")
                    retry_count += 1
                else:
                    console.print(f"[red]✗[/red] Failed to reset {task_info['task'].id}")

            console.print(f"\n[green]✓[/green] Reset {retry_count} task(s) to queued")

        else:
            # Retry specific task
            # Resolve task ID (supports numeric IDs, partial IDs, and full IDs)
            task_id = resolve_task_id(task_id_or_number, fsd_dir)
            if not task_id:
                raise click.ClickException(
                    f"Task '{task_id_or_number}' not found. "
                    "Use 'fsd queue list' to see available tasks."
                )

            task_status = _get_task_status(task_id)

            if task_status != "failed":
                console.print(
                    f"[yellow]Warning: Task '{task_id}' is not in failed state "
                    f"(current: {task_status})[/yellow]"
                )
                if not click.confirm("Do you want to retry it anyway?"):
                    return

            if _retry_task(task_id):
                console.print(f"[green]✓[/green] Task '{task_id}' reset to queued")
            else:
                raise click.ClickException(f"Failed to retry task '{task_id}'")

    except Exception as e:
        console.print(f"[red]Failed to retry task(s):[/red] {e}")
        raise click.ClickException(f"Retry failed: {e}")


def _retry_task(task_id: str) -> bool:
    """Reset a task's status and state back to queued.

    Args:
        task_id: Task identifier

    Returns:
        True if successful, False otherwise
    """
    try:
        from datetime import datetime

        fsd_dir = Path.cwd() / ".fsd"

        # Reset status file
        status_file = fsd_dir / "status" / f"{task_id}.json"
        if status_file.exists():
            status_data = {
                "status": "queued",
                "updated_at": datetime.utcnow().isoformat(),
                "mode": "auto"
            }
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(status_data, f, indent=2)

        # Reset state file
        state_file = fsd_dir / "state" / f"{task_id}.json"
        if state_file.exists():
            now = datetime.utcnow().isoformat()
            state_data = {
                "task_id": task_id,
                "current_state": "queued",
                "created_at": now,
                "updated_at": now,
                "history": [],
                "error_message": None,
                "retry_count": 0,
                "metadata": {}
            }
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2)

        return True

    except Exception as e:
        console.print(f"[red]Error resetting task {task_id}: {e}[/red]")
        return False


def _update_task_status(task_id: str, status: str) -> None:
    """Update the status of a task."""
    fsd_dir = Path.cwd() / ".fsd"
    status_dir = fsd_dir / "status"
    status_dir.mkdir(exist_ok=True)

    status_file = status_dir / f"{task_id}.json"

    status_data = {
        "status": status,
        "updated_at": "2025-01-04T12:00:00Z",  # Placeholder timestamp
    }

    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2)


def _display_task_details(task: TaskDefinition, status: str) -> None:
    """Display detailed task information."""
    from rich.text import Text

    # Create status badge with color
    status_colors = {
        "queued": "blue",
        "running": "yellow",
        "completed": "green",
        "failed": "red",
    }
    status_color = status_colors.get(status, "white")

    # Build task info panel
    task_info = []
    task_info.append(f"[bold]Task ID:[/bold] {task.id}")
    if task.numeric_id:
        task_info.append(f"[bold]Numeric ID:[/bold] #{task.numeric_id}")
    task_info.append(f"[bold]Status:[/bold] [{status_color}]{status}[/{status_color}]")
    task_info.append(f"[bold]Priority:[/bold] {task.priority.value}")
    task_info.append(f"[bold]Estimated Duration:[/bold] {task.estimated_duration}")
    task_info.append("")
    task_info.append(f"[bold]Description:[/bold]")
    task_info.append(f"  {task.description}")

    if task.context:
        task_info.append("")
        task_info.append(f"[bold]Context:[/bold]")
        task_info.append(f"  {task.context}")

    if task.focus_files:
        task_info.append("")
        task_info.append(f"[bold]Focus Files:[/bold]")
        for file in task.focus_files:
            task_info.append(f"  • {file}")

    if task.success_criteria:
        task_info.append("")
        task_info.append(f"[bold]Success Criteria:[/bold]")
        task_info.append(f"  {task.success_criteria}")

    if task.on_completion:
        task_info.append("")
        task_info.append(f"[bold]On Completion:[/bold]")
        if task.on_completion.create_pr:
            task_info.append(f"  • Create PR: {task.on_completion.pr_title}")
        if task.on_completion.notify_slack:
            task_info.append(f"  • Notify Slack")

    panel = Panel(
        "\n".join(task_info),
        title="[bold cyan]Task Details[/bold cyan]",
        border_style="cyan",
    )
    console.print(panel)


def _display_task_state(task_id: str, fsd_dir: Path) -> None:
    """Display current task state machine information."""
    state_file = fsd_dir / "state" / f"{task_id}.json"

    if not state_file.exists():
        return

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state_data = json.load(f)

        state_info = []
        state_info.append(f"[bold]Current State:[/bold] {state_data.get('current_state', 'unknown')}")

        created_at = state_data.get('created_at', 'N/A')
        updated_at = state_data.get('updated_at', 'N/A')
        state_info.append(f"[bold]Created:[/bold] {created_at}")
        state_info.append(f"[bold]Updated:[/bold] {updated_at}")

        retry_count = state_data.get('retry_count', 0)
        if retry_count > 0:
            state_info.append(f"[bold]Retry Count:[/bold] {retry_count}")

        error = state_data.get('error_message')
        if error:
            state_info.append(f"[bold]Error:[/bold] {error}")

        # Show last few state transitions
        history = state_data.get('history', [])
        if history:
            state_info.append("")
            state_info.append(f"[bold]Recent Transitions:[/bold]")
            for entry in history[-5:]:  # Show last 5 transitions
                from_state = entry.get('from_state', '?')
                to_state = entry.get('to_state', '?')
                timestamp = entry.get('timestamp', '?')
                state_info.append(f"  {from_state} → {to_state} [{timestamp}]")

        panel = Panel(
            "\n".join(state_info),
            title="[bold yellow]State Information[/bold yellow]",
            border_style="yellow",
        )
        console.print(panel)

    except Exception as e:
        console.print(f"[dim]Could not load state information: {e}[/dim]")


def _display_checkpoint_history(task_id: str, fsd_dir: Path) -> None:
    """Display checkpoint history for the task."""
    try:
        checkpoint_manager = CheckpointManager(checkpoint_dir=fsd_dir / "checkpoints")
        checkpoints = checkpoint_manager.list_checkpoints(task_id)

        if not checkpoints:
            console.print("[dim]No checkpoints found[/dim]")
            return

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
        console.print(f"[yellow]Could not load checkpoint history: {e}[/yellow]")


def _display_logs_summary(task_id: str, fsd_dir: Path) -> None:
    """Display execution logs summary."""
    log_file = fsd_dir / "logs" / f"{task_id}.jsonl"

    if not log_file.exists():
        console.print("[dim]No execution logs found[/dim]")
        return

    try:
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
            level = entry.get('level', 'unknown')
            by_level[level] = by_level.get(level, 0) + 1

        if by_level:
            log_info.append(f"[bold]By Level:[/bold]")
            for level, count in sorted(by_level.items()):
                log_info.append(f"  {level}: {count}")

        # Show first and last entry timestamps
        if entries:
            first_time = entries[0].get('timestamp', 'N/A')
            last_time = entries[-1].get('timestamp', 'N/A')
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
        for entry in entries[-10:]:  # Show last 10 entries
            timestamp = entry.get('timestamp', '')[:19]  # Trim to readable length
            level = entry.get('level', 'INFO')
            message = entry.get('message', '')

            # Color code by level
            level_colors = {
                'ERROR': 'red',
                'WARNING': 'yellow',
                'INFO': 'blue',
                'DEBUG': 'dim',
            }
            level_color = level_colors.get(level, 'white')

            # Truncate long messages
            if len(message) > 80:
                message = message[:77] + "..."

            console.print(f"[dim]{timestamp}[/dim] [{level_color}]{level:7}[/{level_color}] {message}")

        console.print(f"\n[dim]Full logs: {log_file}[/dim]")

    except Exception as e:
        console.print(f"[yellow]Could not load logs: {e}[/yellow]")
