# FSD: Autonomous Overnight Coding Agent System

A Feature-Sliced Design system that enables a CLI-based coding agent to work autonomously overnight, executing multi-step development tasks with checkpoints, recovery mechanisms, and human-in-the-loop safeguards.

## Features

- **Natural Language Tasks**: Define tasks in plain English
- **Autonomous Execution**: Uses Claude CLI for intelligent code generation
- **Comprehensive Tracking**: Logs every action for full transparency
- **Safety First**: Git-based checkpointing and rollback mechanisms
- **Morning Reports**: Detailed summaries of overnight work
- **Web Interface**: Beautiful web dashboard for monitoring tasks and system status

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

# Launch web interface (optional)
fsd serve
# Then open http://127.0.0.1:10010 in your browser
```

## Web Interface

FSD includes a modern web interface for easier monitoring and management of your tasks.

```bash
# Start the web server
fsd serve

# Custom port
fsd serve --port 3000

# Allow external connections
fsd serve --host 0.0.0.0

# Development mode with auto-reload
fsd serve --reload
```

The web interface provides:
- Real-time system status monitoring
- Task queue visualization
- Activity logs and timeline
- Task filtering and search
- Auto-refresh every 5 seconds
- REST API documentation at `/docs`

## Development

### Running the CLI (No Installation Required!)

From within the `fsd/` directory:

```bash
# Using the convenience script:
./run-fsd.sh --help

# All commands work the same way:
./run-fsd.sh init
./run-fsd.sh submit task.yaml
./run-fsd.sh queue list
./run-fsd.sh status
```

### Running Tests

```bash
# Run tests
uv run pytest

# Run linting
uv run ruff check .

# Run type checking
uv run mypy .
```

### Installing (Optional)

If you want to install it globally:

```bash
# Install in development mode
./install-dev.sh

# Or manually:
uv pip install -e .
```

## License

MIT License - see LICENSE file for details.
