#!/bin/bash
# Bootstrap script for Azure Blob Storage benchmark
#
# Quick install (fresh VM):
#   curl -fsSL https://raw.githubusercontent.com/plusplusoneplusplus/breadthseek/main/bench/azure-storage/bootstrap.sh | bash
#
# Update to latest:
#   curl -fsSL https://raw.githubusercontent.com/plusplusoneplusplus/breadthseek/main/bench/azure-storage/bootstrap.sh | bash -s -- --update
#
# Or if you have the repo cloned:
#   ./bootstrap.sh [--update]

set -e

BASE_URL="https://raw.githubusercontent.com/plusplusoneplusplus/breadthseek/main/bench/azure-storage"
BENCH_DIR="$HOME/azure-storage-bench"

# Parse arguments
UPDATE_MODE=false
for arg in "$@"; do
    case $arg in
        --update|-u)
            UPDATE_MODE=true
            shift
            ;;
    esac
done

echo "=== Azure Blob Storage Benchmark Setup ==="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Add uv to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"
    
    echo "uv installed successfully"
else
    echo "uv is already installed"
fi

# Determine working directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" 2>/dev/null)" && pwd 2>/dev/null || echo "")"

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/pyproject.toml" ] && [ "$UPDATE_MODE" = false ]; then
    # Running from cloned repo (not update mode)
    cd "$SCRIPT_DIR"
    echo "Working directory: $SCRIPT_DIR"
else
    # Running via curl or update mode - download files
    if [ "$UPDATE_MODE" = true ]; then
        echo "Updating benchmark files..."
    else
        echo "Downloading benchmark files..."
    fi
    
    mkdir -p "$BENCH_DIR"
    cd "$BENCH_DIR"
    
    # Download the necessary files
    curl -fsSL "$BASE_URL/pyproject.toml" -o pyproject.toml
    curl -fsSL "$BASE_URL/bench_read_latency.py" -o bench_read_latency.py
    
    echo "Files downloaded to: $BENCH_DIR"
fi

# Install/update dependencies
echo ""
echo "Installing Python dependencies..."
uv sync

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Working directory: $(pwd)"
echo ""
echo "Usage:"
echo "  cd $BENCH_DIR"
echo ""
echo "  # Set your SAS URL"
echo "  export SAS_URL='https://<account>.blob.core.windows.net/<container>?<sas_token>'"
echo ""
echo "  # Prepare test data"
echo "  uv run python bench_read_latency.py prepare --sas-url \"\$SAS_URL\""
echo ""
echo "  # Run benchmark"
echo "  uv run python bench_read_latency.py run --sas-url \"\$SAS_URL\""
echo ""
echo "  # Clean up"
echo "  uv run python bench_read_latency.py cleanup --sas-url \"\$SAS_URL\""
echo ""
echo "To update to latest version:"
echo "  curl -fsSL $BASE_URL/bootstrap.sh | bash -s -- --update"
echo ""
