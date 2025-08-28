#!/bin/bash

set -e

echo "Installing uv - Python package and project manager"
echo "=================================================="

# Detect OS and architecture
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

# Map architecture names
case "$ARCH" in
    x86_64)
        ARCH="x86_64"
        ;;
    aarch64|arm64)
        ARCH="aarch64"
        ;;
    *)
        echo "Error: Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Install using curl (recommended method)
if command -v curl &> /dev/null; then
    echo "Installing uv using curl..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
elif command -v wget &> /dev/null; then
    echo "Installing uv using wget..."
    wget -qO- https://astral.sh/uv/install.sh | sh
else
    echo "Error: Neither curl nor wget is installed. Please install one of them first."
    exit 1
fi

# Add to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.cargo/bin:"* ]]; then
    echo ""
    echo "Adding ~/.cargo/bin to PATH..."
    
    # Detect shell and update appropriate config file
    if [[ "$SHELL" == */bash ]]; then
        echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
        echo "Added to ~/.bashrc"
    elif [[ "$SHELL" == */zsh ]]; then
        echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.zshrc
        echo "Added to ~/.zshrc"
    else
        echo "Please manually add the following to your shell configuration:"
        echo 'export PATH="$HOME/.cargo/bin:$PATH"'
    fi
    
    echo ""
    echo "To use uv immediately, run:"
    echo '  source ~/.bashrc  # or ~/.zshrc if using zsh'
fi

# Verify installation
echo ""
if ~/.cargo/bin/uv --version &> /dev/null; then
    echo "✓ uv successfully installed!"
    ~/.cargo/bin/uv --version
else
    echo "⚠ Installation complete but uv not found in expected location."
    echo "Please restart your terminal or run: source ~/.bashrc"
fi

echo ""
echo "For more information, visit: https://github.com/astral-sh/uv"