#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$(dirname "$SCRIPT_DIR")/models"

echo "Model Download Script"
echo "===================="
echo "Models will be downloaded to: $MODELS_DIR"
echo

mkdir -p "$MODELS_DIR"

declare -A MODELS=(
    ["nomic-embed-code.Q6_K.gguf"]="https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q6_K.gguf"
    ["codellama-7b-instruct.Q4_K_M.gguf"]="https://huggingface.co/TheBloke/CodeLlama-7B-Instruct-GGUF/resolve/main/codellama-7b-instruct.Q4_K_M.gguf"
    ["deepseek-coder-6.7b-instruct.Q4_K_M.gguf"]="https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF/resolve/main/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
)

function download_model() {
    local name=$1
    local url=$2
    local filepath="$MODELS_DIR/$name"
    
    if [ -f "$filepath" ]; then
        echo "✓ $name already exists, skipping..."
    else
        echo "↓ Downloading $name..."
        if command -v wget &> /dev/null; then
            wget -q --show-progress -O "$filepath" "$url"
        elif command -v curl &> /dev/null; then
            curl -L --progress-bar -o "$filepath" "$url"
        else
            echo "Error: Neither wget nor curl is installed. Please install one of them."
            exit 1
        fi
        echo "✓ Downloaded $name successfully"
    fi
}

if [ $# -eq 0 ]; then
    echo "Available models:"
    echo "-----------------"
    for model in "${!MODELS[@]}"; do
        echo "  - $model"
    done
    echo
    echo "Usage: $0 <model-name|all>"
    echo "Example: $0 nomic-embed-code.Q6_K.gguf"
    echo "Example: $0 all  (downloads all models)"
    exit 0
fi

if [ "$1" == "all" ]; then
    echo "Downloading all models..."
    echo
    for model in "${!MODELS[@]}"; do
        download_model "$model" "${MODELS[$model]}"
    done
    echo
    echo "All models downloaded successfully!"
elif [ -n "${MODELS[$1]}" ]; then
    download_model "$1" "${MODELS[$1]}"
else
    echo "Error: Unknown model '$1'"
    echo
    echo "Available models:"
    for model in "${!MODELS[@]}"; do
        echo "  - $model"
    done
    exit 1
fi

echo
echo "Models are stored in: $MODELS_DIR"