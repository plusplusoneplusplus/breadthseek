# Interactive Mode

The FSD CLI now supports an interactive mode that launches automatically when you run `fsd` without any subcommand.

## Usage

Simply run:

```bash
fsd
```

This will launch an interactive menu that operates in a continuous loop:

1. **Type any command** - Type the full command with arguments (e.g., `queue start`, `logs task-123 --follow`)
2. **Universal support** - ALL commands and arguments are supported - just type what you want!
3. **Interactive fallback** - Commands without arguments will prompt for needed parameters
4. **Or use numbers** - You can also use numbers (1-6) for quick access to common commands
5. **Get help** - Type `?` to see available commands anytime
6. **Seamless execution** - Commands run immediately and return to the prompt
7. **Repeat** - Continue executing commands until you type `quit`

The interactive mode runs continuously with **full command support** - any command that works in `fsd <command>` will work here! Type commands naturally with all their arguments and flags.

## Features

- **Universal command support** - ANY command with arguments works (e.g., `serve --port 3000 --reload`)
- **Full CLI compatibility** - If it works as `fsd <command>`, it works here
- **Natural syntax** - Type commands exactly as you would in the terminal
- **Number shortcuts** - Use numbers (1-6) for quick access to common commands
- **Built-in help** - Type `?` to see all available commands
- **Smart prompts** - Commands without args fall back to interactive prompts
- **Multiple exit options** - Type `quit`, `q`, or `exit` to leave

## Example Session

```
┌────────────────────────────────────────────────────────────────┐
│ FSD - Autonomous Overnight Coding Agent System                 │
│ Interactive Mode                                               │
└────────────────────────────────────────────────────────────────┘

Available commands:
  init              Initialize FSD in current project
  submit            Submit a new task
  queue [action]    Manage task queue
    queue list      List tasks in queue
    queue start     Start queue execution
    queue stop      Stop queue execution
  status            Check system status
  logs [task-id]    View task logs
  serve             Start web interface
  ?                 Show this help
  quit              Exit interactive mode

Command: queue list

Executing: fsd queue list

┌──────────────────────────── Task Queue ─────────────────────────────┐
│ # │ ID          │ Priority │ Duration │ Status │ Description        │
├───┼─────────────┼──────────┼──────────┼────────┼────────────────────┤
│ 1 │ task-123    │ high     │ 30m      │ queued │ Fix authentication │
│ 2 │ task-456    │ medium   │ 1h       │ queued │ Add logging        │
└───┴─────────────┴──────────┴──────────┴────────┴────────────────────┘

Command: queue start

Executing: fsd queue start

[... execution starts ...]

Command: logs task-123

Executing: fsd logs task-123

[... task logs displayed ...]

Command: status

Executing: fsd status

╭─────────────────────── FSD System Status ───────────────────────╮
│ 🟢 Execution Status: Running                                    │
│ Task Queue: 1 queued, 1 running, 0 completed, 0 failed         │
╰─────────────────────────────────────────────────────────────────╯

Command: quit
Goodbye!
```

## Command Examples

**The interactive mode supports ALL commands with full arguments!** Here are some examples:

```bash
# Queue commands - any subcommand works
queue list              # List all tasks
queue start             # Start execution
queue stop              # Stop execution
queue clear             # Clear queue
queue retry task-123    # Retry a specific task

# Logs - with any task ID and flags
logs task-123           # View logs for a task
logs task-456 --follow  # Follow logs in real-time

# Serve - with all options
serve --port 3000       # Custom port
serve --port 8080 --reload  # With auto-reload

# Status - with or without flags
status                  # Basic status
status --watch          # Watch mode (if supported)

# Any other command
init --project-path /path/to/project --git-auto-commit
submit task.yaml
submit --text "HIGH priority: Fix bug. Takes 30m"
```

**Interactive prompts** - When you type commands WITHOUT arguments, you'll get helpful prompts:
- `init` → Asks for project path and git settings
- `submit` → Asks for task text or YAML file
- `queue` → Shows menu of actions
- `logs` → Asks for task ID
- `serve` → Asks for port and reload settings

## Command-Specific Prompts

### Init
- Project path (default: current directory)
- Enable automatic git commits (yes/no)

### Submit
- Submission method (text or YAML file)
- Task description or file path

### Queue
- Action (list, start, stop, clear, retry)
- Additional parameters based on action

### Status
- Watch mode (auto-refresh)

### Logs
- Task ID (optional, defaults to latest)
- Follow mode (tail -f style)

### Serve
- Port (default: 8000)
- Enable auto-reload (yes/no)

## Benefits

- **True CLI compatibility** - Use the full power of `fsd` commands without leaving interactive mode
- **No limitations** - ALL commands, arguments, and flags are supported
- **Natural workflow** - Type commands exactly as you would in the terminal
- **Smart fallback** - Get interactive prompts when you need them, skip them when you don't
- **Discoverable** - Type `?` anytime to see available commands
- **Continuous operation** - Execute multiple commands without restarting the CLI
- **Efficient task management** - Check status, submit tasks, and view logs in a single session
- **Flexible** - Mix command-line style (`queue start`) with interactive prompts (`submit`)
