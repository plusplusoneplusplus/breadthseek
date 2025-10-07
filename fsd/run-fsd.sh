#!/bin/bash
cd "$(dirname "$0")"
PYTHONPATH=.. uv run python -m fsd.cli.main "$@"
