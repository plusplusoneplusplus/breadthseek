# Cursor Rules for BreadthSeek Project

This directory contains linting rules for the BreadthSeek project that will help maintain consistent coding practices.

## Dependency Management Rules

These rules ensure that we use `uv` instead of `pip` throughout the project for better performance and dependency resolution.

### Rule Descriptions

1. **Use uv instead of pip**
   - Replaces `pip install`, `pip uninstall`, `pip freeze`, and `pip list` with `uv` equivalents
   - Example: `pip install torch` → `uv install torch`

2. **Use uv pip with requirements.txt**
   - Replaces `pip install -r requirements.txt` with `uv pip install -r requirements.txt`
   - Example: `pip install -r requirements.txt` → `uv pip install -r requirements.txt`

3. **Use uv with editable installs**
   - Replaces `pip install -e .` with `uv pip install -e .`
   - Example: `pip install -e .` → `uv pip install -e .`

4. **Always install with --no-build-isolation**
   - Ensures that editable installs of the current project use `--no-build-isolation` flag
   - Example: `uv pip install -e .` → `uv pip install -e . --no-build-isolation`

## Why Use uv?

`uv` offers several advantages over `pip`:

1. **Speed**: uv is significantly faster than pip
2. **Better dependency resolution**: uv has improved dependency resolution algorithms
3. **Consistent environment management**: Better integration with virtual environments
4. **Faster builds**: The `--no-build-isolation` flag can significantly speed up local development

## How to Use

These rules will automatically highlight in Cursor IDE when you use pip instead of uv in your code, docs, or scripts. You can:

1. Hover over the highlighted code to see the suggested fix
2. Use the "Quick Fix" feature to automatically apply the suggested change
3. Manually edit to follow the rules

## Installation

To use `uv`, install it with:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv
``` 