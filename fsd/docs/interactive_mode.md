# Interactive Mode

The FSD CLI now supports an interactive mode that launches automatically when you run `fsd` without any subcommand.

## Usage

Simply run:

```bash
fsd
```

This will launch an interactive menu that guides you through:

1. **Choosing a command** - Select from available commands (init, submit, queue, status, logs, serve)
2. **Providing parameters** - The CLI will prompt for required parameters based on your selection
3. **Executing the command** - The selected command runs with your provided parameters

## Features

- **User-friendly menu** - Clear numbered options for all available commands
- **Smart prompts** - Context-aware prompts with sensible defaults
- **Validation** - Input validation to ensure correct parameters
- **Graceful exit** - Type 'q' or 'quit' to exit at any time

## Example Session

```
┌───────────────────────────────────────────────────────────────┐
│ FSD - Autonomous Overnight Coding Agent System                │
│ Interactive Mode                                              │
└───────────────────────────────────────────────────────────────┘

What would you like to do?
  1    init     Initialize FSD in current project
  2    submit   Submit a new task
  3    queue    Manage task queue
  4    status   Check system status
  5    logs     View task logs
  6    serve    Start web interface
  q    quit     Exit interactive mode

Select option: 2

Submit Task
Choose submission method:
  1 - Natural language text
  2 - YAML file
Your choice [1]: 1

Enter your task description. Can include priority and time estimate.
Example: HIGH priority: Fix login bug. Takes 30m

Task description: Add user authentication feature
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

- **No need to remember commands** - Browse available options
- **Faster onboarding** - New users can explore features easily
- **Reduced errors** - Guided input with validation
- **Flexible workflow** - Switch between interactive and direct command modes
