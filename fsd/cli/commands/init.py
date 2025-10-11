"""FSD init command."""

from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console

console = Console()


@click.command()
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force initialization even if .fsd directory already exists",
)
def init_command(force: bool) -> None:
    """Initialize FSD in the current project.

    Creates a .fsd directory with default configuration and sets up
    the project for autonomous task execution.

    Examples:
        fsd init                # Initialize with default settings
        fsd init --force        # Reinitialize existing project
    """
    project_root = Path.cwd()
    fsd_dir = project_root / ".fsd"

    # Check if already initialized
    if fsd_dir.exists() and not force:
        console.print(
            f"[yellow]FSD already initialized in {project_root}[/yellow]\n"
            "Use --force to reinitialize"
        )
        return

    try:
        # Create .fsd directory structure
        fsd_dir.mkdir(exist_ok=True)
        (fsd_dir / "logs").mkdir(exist_ok=True)
        (fsd_dir / "tasks").mkdir(exist_ok=True)
        (fsd_dir / "reports").mkdir(exist_ok=True)
        (fsd_dir / "queue").mkdir(exist_ok=True)
        (fsd_dir / "state").mkdir(exist_ok=True)
        (fsd_dir / "status").mkdir(exist_ok=True)
        (fsd_dir / "checkpoints").mkdir(exist_ok=True)
        (fsd_dir / "plans").mkdir(exist_ok=True)

        # Create default config
        config_path = fsd_dir / "config.yaml"
        if not config_path.exists() or force:
            default_config = _get_default_config()
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(default_config, f, default_flow_style=False, indent=2)

        # Create .gitignore for FSD directory
        gitignore_path = fsd_dir / ".gitignore"
        if not gitignore_path.exists() or force:
            gitignore_content = """# FSD generated files
logs/
reports/
queue/
state/
status/
checkpoints/
plans/
*.tmp
*.lock
"""
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(gitignore_content)

        # Create example task
        example_task_path = fsd_dir / "tasks" / "example.yaml"
        if not example_task_path.exists() or force:
            example_task = _get_example_task()
            with open(example_task_path, "w", encoding="utf-8") as f:
                yaml.dump(example_task, f, default_flow_style=False, indent=2)

        console.print(f"[green]✓[/green] FSD initialized in {project_root}")
        console.print(f"[dim]Configuration:[/dim] {config_path}")
        console.print(f"[dim]Example task:[/dim] {example_task_path}")
        console.print(f"\n[bold]Next steps:[/bold]")
        console.print("1. Review and customize .fsd/config.yaml")
        console.print("2. Create your first task: fsd submit --interactive")
        console.print("3. Start execution: fsd queue start")

    except Exception as e:
        console.print(f"[red]Failed to initialize FSD:[/red] {e}")
        raise click.ClickException(f"Initialization failed: {e}")


def _get_default_config() -> dict:
    """Get default FSD configuration."""
    return {
        "agent": {
            "max_execution_time": "8h",
            "checkpoint_interval": "5m",
            "parallel_tasks": 1,
            "mode": "autonomous",
        },
        "claude": {
            "command": "claude --dangerously-skip-permissions",
            "working_dir": ".",
            "timeout": "30m",
        },
        "safety": {
            "protected_branches": ["main", "master", "production"],
            "require_tests": True,
            "require_type_check": True,
            "secret_scan": True,
            "auto_merge": False,
        },
        "git": {
            "branch_prefix": "fsd/",
            "user": {"name": "FSD Agent", "email": "fsd-agent@example.com"},
        },
        "logging": {
            "level": "INFO",
            "format": "json",
            "output_dir": ".fsd/logs",
            "retention_days": 30,
        },
        "notifications": {
            "enabled": False,
            "slack": {"enabled": False, "webhook_url": "${SLACK_WEBHOOK_URL}"},
        },
    }


def _get_example_task() -> dict:
    """Get example task definition."""
    return {
        "id": "example-task",
        "description": (
            "This is an example task. Replace this with your actual task description.\n\n"
            "Describe what you want the autonomous agent to do in natural language. "
            "Be specific about the requirements, files to focus on, and success criteria."
        ),
        "priority": "medium",
        "estimated_duration": "1h",
        "context": (
            "Add any additional context here that might help the agent understand "
            "the task better, such as relevant files, coding patterns to follow, "
            "or constraints to keep in mind."
        ),
        "success_criteria": (
            "Define what success looks like:\n"
            "- All tests pass\n"
            "- Code follows project conventions\n"
            "- No breaking changes\n"
            "- Documentation is updated if needed"
        ),
        "on_completion": {
            "create_pr": True,
            "pr_title": "feat: Example task implementation",
            "notify_slack": False,
        },
    }
