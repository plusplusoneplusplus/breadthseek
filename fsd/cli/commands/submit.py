"""FSD submit command."""

import re
from pathlib import Path
from typing import Optional, Tuple, List

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
from fsd.core.ai_task_parser import AITaskParser, AITaskParserError

console = Console()


@click.command()
@click.argument(
    "task_file", type=click.Path(exists=True, path_type=Path), required=False
)
@click.option("--interactive", "-i", is_flag=True, help="Create task interactively")
@click.option("--dry-run", "-n", is_flag=True, help="Validate task without submitting")
@click.option("--text", "-t", "task_text", type=str, help="Create task from natural language text")
@click.option("--ai", is_flag=True, help="Use AI (Claude CLI) to parse natural language")
def submit_command(task_file: Optional[Path], interactive: bool, dry_run: bool, task_text: Optional[str], ai: bool) -> None:
    """Submit a task for execution.

    You can either provide a YAML task file, use --interactive mode,
    or use --text to create a task from natural language.

    Examples:
        fsd submit task.yaml        # Submit from file
        fsd submit --interactive    # Interactive creation
        fsd submit --text "HIGH priority: Fix login bug in auth.py. Should take 30m"
        fsd submit --text "Fix login bug" --ai  # Use AI parsing (better understanding)
        fsd submit task.yaml --dry-run  # Validate only
    """
    # Validate mutually exclusive options
    options_count = sum([bool(task_file), interactive, bool(task_text)])
    if options_count > 1:
        raise click.ClickException("Cannot use multiple input methods simultaneously")

    if options_count == 0:
        raise click.ClickException(
            "Must provide either a task file, use --interactive mode, or use --text"
        )

    # Validate --ai flag usage
    if ai and not task_text:
        raise click.ClickException("--ai flag can only be used with --text")

    try:
        if interactive:
            task = _create_task_interactively()
        elif task_text:
            if ai:
                task = _create_task_from_text_ai(task_text)
            else:
                task = _create_task_from_text(task_text)
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


def _create_task_from_text(text: str) -> TaskDefinition:
    """Create a task from natural language text.

    Parses text to extract:
    - Priority (HIGH, MEDIUM, LOW, CRITICAL keywords)
    - Duration (e.g., "30m", "2h", "1h30m")
    - Focus files (file paths mentioned)
    - Core description

    Args:
        text: Natural language task description

    Returns:
        TaskDefinition created from parsed text

    Examples:
        "HIGH priority: Fix login bug in auth.py. Should take 30m"
        "Refactor the payment module. Takes 2h. Files: payment.py, utils.py"
        "CRITICAL: Database migration issue. 1h"
    """
    # Extract priority
    priority, text_without_priority = _extract_priority(text)

    # Extract duration
    duration, text_without_duration = _extract_duration(text_without_priority)

    # Extract focus files
    focus_files, clean_description = _extract_focus_files(text_without_duration)

    # Generate task ID from description
    task_id = _generate_task_id(clean_description)

    # Build task
    task = TaskDefinition(
        id=task_id,
        description=clean_description.strip(),
        priority=priority,
        estimated_duration=duration,
        focus_files=focus_files if focus_files else None,
        on_completion=CompletionActions(
            create_pr=True,
            pr_title=_generate_pr_title(clean_description)
        )
    )

    return task


def _create_task_from_text_ai(text: str) -> TaskDefinition:
    """Create a task from natural language text using AI (Claude).

    Args:
        text: Natural language task description

    Returns:
        TaskDefinition created from parsed text using AI

    Raises:
        click.ClickException: If AI parsing fails

    Examples:
        "Fix the login authentication bug that happens when users have special characters in passwords"
        "Implement a caching layer for the API with Redis. Should improve performance by 50%. Focus on /api/v1/users endpoint"
    """
    console.print("[dim]Using AI to parse task...[/dim]")

    try:
        # Set up logging for AI task parsing
        fsd_dir = Path.cwd() / ".fsd"
        if fsd_dir.exists():
            logs_dir = fsd_dir / "logs"
            logs_dir.mkdir(exist_ok=True)
            log_file = logs_dir / "task-creation.log"
            parser = AITaskParser(log_file=log_file)
            console.print(f"[dim]Logging to: {log_file}[/dim]")
        else:
            parser = AITaskParser()

        task = parser.parse_task(text)
        console.print("[green]✓[/green] AI parsing successful")
        return task

    except AITaskParserError as e:
        console.print(f"[red]AI parsing failed:[/red] {e}")
        console.print("[yellow]Tip:[/yellow] Make sure 'claude' CLI is installed and authenticated")
        raise click.ClickException(f"AI task parsing failed: {e}")


def _extract_priority(text: str) -> Tuple[Priority, str]:
    """Extract priority from text.

    Args:
        text: Input text

    Returns:
        Tuple of (priority, text with priority removed)
    """
    text_upper = text.upper()

    # Check for priority keywords
    priority_patterns = [
        (r'\b(CRITICAL|CRIT)\b[:\s]?', Priority.CRITICAL),
        (r'\b(HIGH|URGENT)\b[:\s]?', Priority.HIGH),
        (r'\b(MEDIUM|MED|NORMAL)\b[:\s]?', Priority.MEDIUM),
        (r'\b(LOW)\b[:\s]?', Priority.LOW),
    ]

    for pattern, priority in priority_patterns:
        match = re.search(pattern, text_upper)
        if match:
            # Remove priority keyword from text
            text = text[:match.start()] + text[match.end():]
            return priority, text.strip()

    # Default to medium priority
    return Priority.MEDIUM, text


def _extract_duration(text: str) -> Tuple[str, str]:
    """Extract duration from text.

    Args:
        text: Input text

    Returns:
        Tuple of (duration string, text with duration removed)
    """
    # Patterns for duration: "30m", "2h", "1h30m", "takes 2h", "should take 30m"
    duration_patterns = [
        r'\b(?:takes?|should take|needs?|requires?)\s+(\d+h(?:\d+m)?|\d+m)\b',
        r'\b(\d+h(?:\d+m)?|\d+m)\b',
    ]

    for pattern in duration_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            duration = match.group(1) if match.lastindex else match.group(0)
            # Clean up duration to just the time part
            duration = re.search(r'(\d+h(?:\d+m)?|\d+m)', duration).group(1)
            # Remove duration from text
            text = text[:match.start()] + text[match.end():]
            return duration.lower(), text.strip()

    # Default duration estimation based on text length
    return _estimate_duration(text), text


def _estimate_duration(text: str) -> str:
    """Estimate duration based on text complexity.

    Args:
        text: Task description

    Returns:
        Estimated duration string
    """
    word_count = len(text.split())

    # Simple heuristic based on word count and keywords
    keywords_long = ['implement', 'refactor', 'migrate', 'design', 'architecture']
    keywords_short = ['fix', 'update', 'change', 'add']

    text_lower = text.lower()

    if any(keyword in text_lower for keyword in keywords_long) or word_count > 30:
        return "2h"
    elif any(keyword in text_lower for keyword in keywords_short) or word_count > 15:
        return "1h"
    else:
        return "30m"


def _extract_focus_files(text: str) -> Tuple[Optional[List[str]], str]:
    """Extract file paths from text.

    Args:
        text: Input text

    Returns:
        Tuple of (list of file paths or None, text with files removed)
    """
    # Pattern for files: explicit "files:" or common extensions
    files = []

    # Check for explicit "files:" mentions
    files_pattern = r'(?:files?)\s*[:\s]\s*([a-zA-Z0-9_/\-.,\s]+\.(?:py|js|ts|tsx|jsx|java|go|rs|yaml|yml|json|md)(?:\s*,\s*[a-zA-Z0-9_/\-]+\.(?:py|js|ts|tsx|jsx|java|go|rs|yaml|yml|json|md))*)'
    match = re.search(files_pattern, text, re.IGNORECASE)

    if match:
        files_str = match.group(1)
        # Split by comma and clean up
        files = [f.strip() for f in re.split(r'[,\s]+', files_str) if '.' in f]
        # Remove from text
        text = text[:match.start()] + text[match.end():]
    else:
        # Look for file mentions with common extensions (but keep them in description)
        file_pattern = r'\b([a-zA-Z0-9_/\-]+\.(?:py|js|ts|tsx|jsx|java|go|rs|yaml|yml|json|md))\b'
        matches = re.finditer(file_pattern, text)

        for match in matches:
            files.append(match.group(1))

        # Don't remove file mentions from text - they're part of the description
        # Just clean up extra spaces
        text = re.sub(r'\s+', ' ', text)

    return files if files else None, text.strip()


def _generate_task_id(description: str) -> str:
    """Generate a task ID from description.

    Args:
        description: Task description

    Returns:
        Generated task ID (lowercase, hyphens, max 50 chars)
    """
    # Take first significant words (up to 5)
    words = re.findall(r'\b[a-zA-Z]+\b', description.lower())

    # Filter out common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    significant_words = [w for w in words if w not in stop_words][:5]

    # Join with hyphens
    task_id = '-'.join(significant_words)

    # Ensure minimum length
    if len(task_id) < 3:
        task_id = 'task-' + task_id

    # Truncate if too long
    if len(task_id) > 50:
        task_id = task_id[:50].rstrip('-')

    return task_id


def _generate_pr_title(description: str) -> str:
    """Generate a PR title from description.

    Args:
        description: Task description

    Returns:
        PR title (max 72 chars)
    """
    # Take first sentence or first 60 chars
    first_sentence = description.split('.')[0].strip()

    # Detect conventional commit type
    text_lower = first_sentence.lower()
    if 'fix' in text_lower or 'bug' in text_lower:
        prefix = "fix: "
    elif 'refactor' in text_lower:
        prefix = "refactor: "
    elif 'test' in text_lower:
        prefix = "test: "
    elif 'doc' in text_lower:
        prefix = "docs: "
    else:
        prefix = "feat: "

    title = prefix + first_sentence

    # Truncate if too long
    if len(title) > 72:
        title = title[:69] + "..."

    return title
