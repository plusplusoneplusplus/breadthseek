#!/bin/bash
# Bootstrap script for Azure Blob Storage benchmark
# Run this on a fresh VM to set up everything in one command:
#
#   curl -fsSL https://raw.githubusercontent.com/plusplusoneplusplus/breadthseek/main/bench/azure-storage/bootstrap.sh | bash
#
# Or if you have the repo cloned:
#   ./bootstrap.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Navigate to script directory (if running from repo)
if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    cd "$SCRIPT_DIR"
    echo "Working directory: $SCRIPT_DIR"
else
    # If running via curl, clone or download just this directory
    echo "Downloading benchmark files..."
    
    BENCH_DIR="$HOME/azure-storage-bench"
    mkdir -p "$BENCH_DIR"
    cd "$BENCH_DIR"
    
    # Download the necessary files
    BASE_URL="https://raw.githubusercontent.com/plusplusoneplusplus/breadthseek/main/bench/azure-storage"
    curl -fsSL "$BASE_URL/pyproject.toml" -o pyproject.toml
    curl -fsSL "$BASE_URL/bench_read_latency.py" -o bench_read_latency.py
    
    echo "Files downloaded to: $BENCH_DIR"
fi

# Install dependencies
echo ""
echo "Installing Python dependencies..."
uv sync

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Usage:"
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
