# Interactive Mode

The FSD CLI now supports an interactive mode that launches automatically when you run `fsd` without any subcommand.

## Usage

Simply run:

```bash
fsd
```

This will launch an interactive menu that operates in a continuous loop:

1. **Type a command** - Simply type the command name (e.g., `status`, `submit`, `queue`)
2. **Or use numbers** - You can also use numbers (1-6) for quick access
3. **Get help** - Type `?` to see available commands anytime
4. **Providing parameters** - The CLI will prompt for required parameters based on your command
5. **Executing the command** - The selected command runs with your provided parameters
6. **Return to prompt** - After command completion, press Enter to continue
7. **Repeat** - Continue executing commands until you type `quit`

The interactive mode runs continuously, allowing you to execute multiple commands in sequence without re-launching the CLI. Just type what you want!

## Features

- **Natural command input** - Type command names directly (e.g., `status`, `submit`)
- **Number shortcuts** - Use numbers (1-6) for quick access
- **Built-in help** - Type `?` to see all available commands
- **Smart prompts** - Context-aware prompts with sensible defaults
- **Input validation** - Ensures correct parameters before execution
- **Multiple exit options** - Type `quit`, `q`, or `exit` to leave

## Example Session

```
┌────────────────────────────────────────────────────────────────┐
│ FSD - Autonomous Overnight Coding Agent System                 │
│ Interactive Mode                                               │
└────────────────────────────────────────────────────────────────┘

Available commands:
  init          Initialize FSD in current project
  submit        Submit a new task
  queue         Manage task queue
  status        Check system status
  logs          View task logs
  serve         Start web interface
  ?             Show this help
  quit          Exit interactive mode

Command: status

Executing: fsd status

╭─────────────────────── FSD System Status ───────────────────────╮
│ 🟢 Execution Status: Idle                                       │
│ Task Queue: 0 queued, 0 running, 5 completed, 0 failed         │
╰─────────────────────────────────────────────────────────────────╯

Press Enter to continue...

Command: ?

Available commands:
  init          Initialize FSD in current project
  submit        Submit a new task
  queue         Manage task queue
  status        Check system status
  logs          View task logs
  serve         Start web interface
  ?             Show this help
  quit          Exit interactive mode

Command: submit

Submit Task
Choose submission method:
  1 - Natural language text
  2 - YAML file
Your choice [1]: 1

Task description: Add user authentication feature

Executing: fsd submit --text "Add user authentication feature"

[... command output ...]

Press Enter to continue...

Command: quit
Goodbye!
```

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
