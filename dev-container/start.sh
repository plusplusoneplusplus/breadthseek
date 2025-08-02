#!/bin/bash
# This script keeps the dev container alive by launching an interactive shell if possible, or falling back to tail.

if command -v zsh >/dev/null 2>&1; then
  exec zsh
else
  exec tail -f /dev/null
fi