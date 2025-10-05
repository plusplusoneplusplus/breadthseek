"""FSD submit command."""

from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.prompt import Prompt, Confirm

from fsd.core.task_schema import (
    TaskDefinition,
    Priority,
    CompletionActions,
    load_task_from_yaml,
)

console = Console()


@click.command()
@click.argument(
    "task_file", type=click.Path(exists=True, path_type=Path), required=False
)
@click.option("--interactive", "-i", is_flag=True, help="Create task interactively")
@click.option("--dry-run", "-n", is_flag=True, help="Validate task without submitting")
def submit_command(task_file: Optional[Path], interactive: bool, dry_run: bool) -> None:
    """Submit a task for execution.

    You can either provide a YAML task file or use --interactive mode
    to create a task through a guided wizard.

    Examples:
        fsd submit task.yaml        # Submit from file
        fsd submit --interactive    # Interactive creation
        fsd submit task.yaml --dry-run  # Validate only
    """
    if interactive and task_file:
        raise click.ClickException("Cannot use both task file and --interactive mode")

    if not interactive and not task_file:
        raise click.ClickException(
            "Must provide either a task file or use --interactive mode"
        )

    try:
        if interactive:
            task = _create_task_interactively()
        else:
            task = load_task_from_yaml(task_file)

        # Validate task
        console.print(f"[green]✓[/green] Task validation passed")

        # Display task summary
        _display_task_summary(task)

        if dry_run:
            console.print("[yellow]Dry run mode - task not submitted[/yellow]")
            return

        # Submit task (for now, just save to queue directory)
        _submit_task(task)

        console.print(f"[green]✓[/green] Task '{task.id}' submitted successfully")
        console.print("Use 'fsd queue list' to see queued tasks")
        console.print("Use 'fsd queue start' to begin execution")

    except Exception as e:
        console.print(f"[red]Failed to submit task:[/red] {e}")
        raise click.ClickException(f"Task submission failed: {e}")


def _create_task_interactively() -> TaskDefinition:
    """Create a task through interactive prompts."""
    console.print("[bold]Interactive Task Creation[/bold]")
    console.print("Answer the following questions to create your task:\n")

    # Basic fields
    task_id = Prompt.ask("Task ID (lowercase, hyphens only)", default="my-task")

    description = Prompt.ask("Task description (what should the agent do?)")

    priority = Prompt.ask(
        "Priority", choices=["low", "medium", "high", "critical"], default="medium"
    )

    duration = Prompt.ask("Estimated duration (e.g., '2h', '30m')", default="1h")

    # Optional fields
    add_context = Confirm.ask("Add additional context?", default=False)
    context = None
    if add_context:
        context = Prompt.ask("Context/background information")

    add_focus_files = Confirm.ask("Specify files to focus on?", default=False)
    focus_files = None
    if add_focus_files:
        files_input = Prompt.ask("Focus files (comma-separated)")
        focus_files = [f.strip() for f in files_input.split(",") if f.strip()]

    add_success_criteria = Confirm.ask("Add success criteria?", default=False)
    success_criteria = None
    if add_success_criteria:
        success_criteria = Prompt.ask("Success criteria")

    # Completion actions
    create_pr = Confirm.ask("Create PR when completed?", default=True)
    pr_title = None
    if create_pr:
        pr_title = Prompt.ask("PR title", default=f"feat: {task_id}")

    notify_slack = Confirm.ask("Send Slack notification?", default=False)

    # Build completion actions
    on_completion = None
    if create_pr or notify_slack:
        on_completion = CompletionActions(
            create_pr=create_pr, pr_title=pr_title, notify_slack=notify_slack
        )

    # Create task
    task = TaskDefinition(
        id=task_id,
        description=description,
        priority=Priority(priority),
        estimated_duration=duration,
        context=context,
        focus_files=focus_files,
        success_criteria=success_criteria,
        on_completion=on_completion,
    )

    return task


def _display_task_summary(task: TaskDefinition) -> None:
    """Display a summary of the task."""
    console.print("\n[bold]Task Summary:[/bold]")
    console.print(f"[dim]ID:[/dim] {task.id}")
    console.print(f"[dim]Priority:[/dim] {task.priority.value}")
    console.print(f"[dim]Duration:[/dim] {task.estimated_duration}")
    console.print(f"[dim]Description:[/dim]")

    # Format description with proper indentation
    for line in task.description.split("\n"):
        console.print(f"  {line}")

    if task.context:
        console.print(f"[dim]Context:[/dim] {task.context}")

    if task.focus_files:
        console.print(f"[dim]Focus files:[/dim] {', '.join(task.focus_files)}")

    if task.success_criteria:
        console.print(f"[dim]Success criteria:[/dim] {task.success_criteria}")

    if task.on_completion:
        console.print(f"[dim]On completion:[/dim]")
        if task.on_completion.create_pr:
            console.print(f"  - Create PR: {task.on_completion.pr_title}")
        if task.on_completion.notify_slack:
            console.print(f"  - Notify Slack")


def _submit_task(task: TaskDefinition) -> None:
    """Submit task to the queue."""
    # Ensure .fsd directory exists
    fsd_dir = Path.cwd() / ".fsd"
    if not fsd_dir.exists():
        raise click.ClickException("FSD not initialized. Run 'fsd init' first.")

    # Create queue directory if it doesn't exist
    queue_dir = fsd_dir / "queue"
    queue_dir.mkdir(exist_ok=True)

    # Save task to queue
    task_file = queue_dir / f"{task.id}.yaml"
    if task_file.exists():
        raise click.ClickException(f"Task '{task.id}' already exists in queue")

    # Convert task to dict and save
    task_dict = task.model_dump(exclude_none=True, mode="json")
    with open(task_file, "w", encoding="utf-8") as f:
        yaml.dump(task_dict, f, default_flow_style=False, indent=2)
