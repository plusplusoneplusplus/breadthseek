# Claude Code Development Guide

## Testing

Run tests: `uv run pytest` or `uv run pytest tests/test_state_machine.py -v`

## AI Interaction Guidelines

**IMPORTANT: Always use the Claude CLI for AI interactions, NOT the Python SDK.**

All AI interactions in this codebase should use the `claude` CLI command via subprocess, not the Anthropic Python SDK. This ensures:

1. **Consistent authentication**: The CLI uses the local authentication (`~/.config/claude/`), so no API keys need to be managed
2. **Unified approach**: All parts of the system use the same method to interact with Claude
3. **Simpler deployment**: No need to set environment variables like `ANTHROPIC_API_KEY`

### Examples

✅ **Correct** - Using CLI via subprocess:
```python
import subprocess

cmd = ["claude", "-p", prompt]
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
stdout, stderr = process.communicate(timeout=30)
```

❌ **Incorrect** - Using Python SDK:
```python
from anthropic import Anthropic

client = Anthropic(api_key="...")
message = client.messages.create(...)
```

### Reference Implementation

See `core/claude_executor.py` and `core/ai_task_parser.py` for reference implementations of how to interact with the Claude CLI.
