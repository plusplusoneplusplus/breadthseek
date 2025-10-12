"""Interactive shell with readline-like features for FSD CLI.

Provides:
- Command history with up/down arrow keys
- Tab completion for commands and options
- Reverse search (Ctrl+R)
- Persistent history across sessions
- Auto-suggestions from history
"""

from pathlib import Path
from typing import List, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter, merge_completers, Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from rich.console import Console

console = Console()


# FSD commands and their common options
FSD_COMMANDS = {
    "init": ["--project-path", "--git-auto-commit", "--no-git-auto-commit", "--help"],
    "submit": ["--interactive", "-i", "--dry-run", "-n", "--text", "-t", "--ai", "--help"],
    "queue": {
        "list": ["--all", "--status", "--help"],
        "start": ["--parallel", "--help"],
        "stop": ["--force", "--help"],
        "clear": ["--help"],
        "retry": ["--all-failed", "--help"],
        "show": ["--checkpoints", "-c", "--logs", "-l", "--help"],
    },
    "status": ["--watch", "-w", "--help"],
    "logs": ["--follow", "-f", "--tail", "-n", "--help"],
    "serve": ["--port", "-p", "--reload", "--help"],
    "help": [],
    "quit": [],
    "exit": [],
    "clear": [],
    "history": [],
    "?": [],
}


class FSDCompleter(Completer):
    """Smart completer for FSD commands with context awareness."""

    def __init__(self):
        """Initialize FSD completer."""
        self.command_words = list(FSD_COMMANDS.keys())

    def get_completions(self, document, complete_event):
        """Get completions based on current input."""
        text_before_cursor = document.text_before_cursor
        words = text_before_cursor.split()

        # No input yet - suggest all commands
        if not words:
            for cmd in self.command_words:
                yield Completion(cmd, start_position=0)
            return

        # Complete first word (command)
        if len(words) == 1 and not text_before_cursor.endswith(' '):
            current_word = words[0]
            for cmd in self.command_words:
                if cmd.startswith(current_word):
                    yield Completion(cmd, start_position=-len(current_word))
            return

        # Complete subcommands and options
        command = words[0]
        current_word = words[-1] if not text_before_cursor.endswith(' ') else ''

        # Handle queue subcommands
        if command == "queue":
            if len(words) == 1 or (len(words) == 2 and not text_before_cursor.endswith(' ')):
                # Complete subcommand
                subcommands = ["list", "start", "stop", "clear", "retry"]
                for subcmd in subcommands:
                    if subcmd.startswith(current_word):
                        yield Completion(subcmd, start_position=-len(current_word))
            elif len(words) >= 2:
                # Complete options for subcommand
                subcommand = words[1]
                if subcommand in FSD_COMMANDS["queue"]:
                    options = FSD_COMMANDS["queue"][subcommand]
                    for opt in options:
                        if opt.startswith(current_word):
                            yield Completion(opt, start_position=-len(current_word))
            return

        # Complete options for regular commands
        if command in FSD_COMMANDS:
            options = FSD_COMMANDS[command]
            if isinstance(options, list):
                for opt in options:
                    if opt.startswith(current_word):
                        yield Completion(opt, start_position=-len(current_word))


def get_history_file() -> Path:
    """Get the path to the command history file.

    Returns:
        Path to history file in .fsd directory or user home
    """
    # Try project-local history first
    local_fsd = Path.cwd() / ".fsd"
    if local_fsd.exists() and local_fsd.is_dir():
        history_file = local_fsd / "shell_history"
        return history_file

    # Fall back to global history in user home
    home_fsd = Path.home() / ".fsd"
    home_fsd.mkdir(exist_ok=True)
    return home_fsd / "shell_history"


def create_prompt_session() -> PromptSession:
    """Create a configured prompt_toolkit session.

    Returns:
        Configured PromptSession with history, completion, and styling
    """
    # Get history file
    history_file = get_history_file()

    # Create custom style
    style = Style.from_dict({
        'prompt': '#00aa00 bold',  # Green prompt
        '': '#ffffff',  # Default text color
    })

    # Create session with all features
    session = PromptSession(
        history=FileHistory(str(history_file)),
        completer=FSDCompleter(),
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,  # Ctrl+R for reverse search
        complete_while_typing=False,  # Only complete on TAB
        style=style,
    )

    return session


def show_shell_help():
    """Display help for shell features."""
    console.print("\n[bold cyan]Shell Features:[/bold cyan]")
    console.print("  [dim]↑↓[/dim]         Navigate command history")
    console.print("  [dim]Tab[/dim]        Auto-complete commands and options")
    console.print("  [dim]Ctrl+R[/dim]     Reverse search through history")
    console.print("  [dim]Ctrl+C[/dim]     Cancel current input")
    console.print("  [dim]Ctrl+D[/dim]     Exit shell")
    console.print()
    console.print("[bold cyan]Built-in Commands:[/bold cyan]")
    console.print("  [cyan]help[/cyan]      Show FSD command menu")
    console.print("  [cyan]?[/cyan]         Show FSD command menu")
    console.print("  [cyan]clear[/cyan]     Clear screen")
    console.print("  [cyan]history[/cyan]   Show command history")
    console.print("  [cyan]quit[/cyan]      Exit shell (also: exit, Ctrl+D)")
    console.print()


def show_command_history(session: PromptSession, limit: int = 20):
    """Display recent command history.

    Args:
        session: The prompt session with history
        limit: Maximum number of commands to show
    """
    history_file = get_history_file()
    if not history_file.exists():
        console.print("[dim]No command history yet[/dim]")
        return

    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            console.print("[dim]No command history yet[/dim]")
            return

        # Show last N commands
        recent = lines[-limit:]
        console.print(f"\n[bold]Recent commands (last {len(recent)}):[/bold]")
        for i, line in enumerate(recent, start=1):
            console.print(f"  [dim]{i:2d}[/dim]  {line.rstrip()}")
        console.print()

    except Exception as e:
        console.print(f"[yellow]Could not read history: {e}[/yellow]")


def clear_screen():
    """Clear the terminal screen."""
    import os
    os.system('clear' if os.name != 'nt' else 'cls')


def get_prompt_text() -> str:
    """Get the prompt text to display.

    Returns:
        Formatted prompt string
    """
    # Check if we're in a FSD project (has .fsd directory)
    if (Path.cwd() / ".fsd").exists():
        return "fsd> "
    else:
        return "fsd (no project)> "


def run_shell_mode(continuous: bool = True, verbose: bool = False, config: Optional[Path] = None):
    """Run the interactive shell with readline-like features.

    Args:
        continuous: If True, loop continuously until quit
        verbose: Enable verbose output for commands
        config: Optional config file path

    Returns:
        List of command args (if continuous=False), or None when quit
    """
    from .interactive import (
        show_welcome,
        show_menu,
        _parse_command_input,
        _execute_command,
    )

    # Show welcome banner
    show_welcome()
    console.print("[dim]Type 'help' for available commands, '?' for shell features[/dim]\n")

    # Create prompt session
    session = create_prompt_session()

    # Show where history is being saved
    history_file = get_history_file()
    console.print(f"[dim]History: {history_file}[/dim]\n")

    while True:
        try:
            # Get input with all the fancy features
            user_input = session.prompt(
                get_prompt_text(),
                # rprompt="Ctrl+R: search | Tab: complete"  # Right-side prompt
            ).strip()

            if not user_input:
                continue

            choice = user_input.lower()

            # Handle built-in shell commands
            if choice in ("quit", "exit"):
                console.print("[yellow]Goodbye![/yellow]")
                return None

            if choice == "?":
                show_shell_help()
                continue

            if choice == "help":
                show_menu()
                continue

            if choice == "clear":
                clear_screen()
                show_welcome()
                continue

            if choice == "history":
                show_command_history(session)
                continue

            # Parse and execute FSD commands
            cmd_parts = _parse_command_input(user_input)
            if not cmd_parts:
                continue

            # Execute the command
            if continuous:
                _execute_command(cmd_parts, verbose, config)
                console.print()  # Blank line for separation
            else:
                return cmd_parts

        except KeyboardInterrupt:
            # Ctrl+C - cancel current line, continue shell
            console.print("^C")
            continue

        except EOFError:
            # Ctrl+D - exit shell
            console.print("\n[yellow]Goodbye![/yellow]")
            return None

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            if verbose:
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
