# Interactive Mode

The FSD CLI now supports an interactive mode that launches automatically when you run `fsd` without any subcommand.

## Usage

Simply run:

```bash
fsd
```

This will launch an interactive menu that operates in a continuous loop:

1. **Type a command** - Simply type the command name (e.g., `status`, `submit`, `queue list`)
2. **Add arguments** - Many commands support arguments (e.g., `queue start`, `logs task-123`)
3. **Or use numbers** - You can also use numbers (1-6) for quick access
4. **Get help** - Type `?` to see available commands anytime
5. **Interactive prompts** - Commands without full args will prompt for needed parameters
6. **Executing the command** - The command runs with your provided parameters
7. **Seamless return** - Immediately returns to the command prompt for the next command
8. **Repeat** - Continue executing commands until you type `quit`

The interactive mode runs continuously, allowing you to execute multiple commands in sequence without re-launching the CLI. Type commands naturally with arguments!

## Features

- **Natural command input** - Type command names directly (e.g., `status`, `queue list`)
- **Command arguments** - Pass arguments inline (e.g., `queue start`, `logs task-123`)
- **Number shortcuts** - Use numbers (1-6) for quick access
- **Built-in help** - Type `?` to see all available commands
- **Smart prompts** - Context-aware prompts when needed
- **Input validation** - Ensures correct parameters before execution
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

## Quick Command Reference

Commands you can type with arguments for instant execution:

```bash
# Queue commands
queue list              # List all tasks
queue start             # Start execution
queue stop              # Stop execution
queue clear             # Clear queue (with confirmation)
queue retry task-123    # Retry a specific task

# Log commands
logs task-123           # View logs for a task
logs task-123 --follow  # Follow logs in real-time

# Status command
status                  # Check system status
```

Commands that will prompt for parameters:
- `init` - Prompts for project path and git settings
- `submit` - Prompts for task text or YAML file
- `queue` - Prompts for action selection
- `logs` - Prompts for task ID
- `serve` - Prompts for port and reload settings

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

- **Intuitive input** - Type command names naturally or use number shortcuts
- **Discoverable** - Type `?` anytime to see available commands
- **No memorization** - Browse available options as you work
- **Faster onboarding** - New users can explore features easily
- **Reduced errors** - Guided input with validation
- **Flexible workflow** - Switch between interactive and direct command modes
- **Continuous operation** - Execute multiple commands without restarting the CLI
- **Efficient task management** - Check status, submit tasks, and view logs in a single session
