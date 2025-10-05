# FSD: Autonomous Overnight Coding Agent System

A Feature-Sliced Design system that enables a CLI-based coding agent to work autonomously overnight, executing multi-step development tasks with checkpoints, recovery mechanisms, and human-in-the-loop safeguards.

## Features

- **Natural Language Tasks**: Define tasks in plain English
- **Autonomous Execution**: Uses Claude CLI for intelligent code generation
- **Comprehensive Tracking**: Logs every action for full transparency
- **Safety First**: Git-based checkpointing and rollback mechanisms
- **Morning Reports**: Detailed summaries of overnight work

## Quick Start

```bash
# Install FSD
uv add fsd

# Initialize in your project
fsd init

# Submit a task
fsd submit task.yaml

# Start overnight execution
fsd queue start --mode overnight

# Check results in the morning
fsd report --overnight
```

## Development

```bash
# Install development dependencies
uv sync --dev

# Run tests
uv run pytest

# Run linting
uv run ruff check .

# Run type checking
uv run mypy .
```

## License

MIT License - see LICENSE file for details.
