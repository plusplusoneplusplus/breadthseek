# Task 3: Basic CLI Interface

**ID:** `fsd-basic-cli`
**Priority:** High
**Estimated Duration:** 3 hours

## Description

Create the basic command-line interface for FSD using Click.

Implement these core commands:
- `fsd init` - Initialize FSD in the current project (create .fsd/ directory, config)
- `fsd submit <task-file>` - Submit a task from a YAML file
- `fsd submit --interactive` - Interactive task creation wizard
- `fsd queue list` - List all queued/running/completed tasks
- `fsd status` - Show current execution status
- `fsd logs <task-id>` - View logs for a specific task

The CLI should:
- Use Click for command structure and argument parsing
- Have proper help text and examples for each command
- Support `--verbose` flag for detailed output
- Use rich/colorama for nice terminal output with colors
- Handle errors gracefully with user-friendly messages

For now, just implement the command structure and basic functionality.
Don't worry about the actual task execution yet - that comes later.

## Context

- Use Click for CLI framework
- Use rich for terminal formatting and colors
- Store FSD data in `.fsd/` directory in project root
- Commands should be intuitive and follow common CLI patterns
- Include bash completion support if possible

## Success Criteria

- ✅ All basic commands are implemented and functional
- ✅ Help text is clear and includes examples
- ✅ Error handling is user-friendly
- ✅ CLI has nice formatting with colors
- ✅ Can initialize FSD in a project and submit tasks
- ✅ Queue listing shows task status properly

## Focus Files

- `fsd/cli/`
- `fsd/cli/main.py`
- `fsd/cli/commands/`
- `tests/test_cli.py`

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Basic CLI interface with core commands"
- **Notify Slack:** No
