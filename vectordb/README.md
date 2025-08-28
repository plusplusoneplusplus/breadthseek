# BreadthSeek Vector Database

This project provides tools for code embeddings and vector database functionality for code snippets, with a focus on C++ code.

## Overview

BreadthSeek Vector Database consists of two main components:

1. **Code Embeddings Generator** - Tool to generate embeddings for code files in a git repository
2. **ChromaDB Integration** - Vector database with code-optimized embeddings for semantic code search

## Code Embeddings Generator

### Features

- Generates embeddings for all tracked files in a git repository
- Supports multiple embedding models:
  - **Transformer Models (via HuggingFace):**
    - Qwen/Qwen2.5-Coder-7B-Instruct (default, 128K context)
    - deepseek-ai/DeepSeek-Coder-V2-Lite-Base (128K context)
    - microsoft/phi-4 (16K context)
  - **GGUF Models (via llama-cpp-python):**
    - Nomic Embed Code (8K context, optimized for code)
- Organizes embeddings by directory
- Stores embeddings in parquet format for efficient storage and retrieval
- Command-line interface for easy use
- Includes a test suite to validate embedding functionality

### Usage

#### Basic Usage

```bash
python -m vectordb.repo_processor --repo /path/to/your/repository
```

This will:
1. Scan the repository for tracked files with supported extensions
2. Generate embeddings for each file
3. Store embeddings in parquet format in `/path/to/your/repository/embeddings/`

#### Advanced Options

```bash
# Using transformer models
python -m vectordb.repo_processor --repo /path/to/your/repository \
                                 --output /custom/output/path \
                                 --batch-size 20 \
                                 --device cuda \
                                 --model deepseek \
                                 --extensions py,js,ts \
                                 --exclude-dirs node_modules,dist

# Using Nomic GGUF model
python -m vectordb.repo_processor --repo /path/to/your/repository \
                                 --model nomic \
                                 --model-path ./nomic-embed-code.Q6_K.gguf \
                                 --device cuda
```

#### Command Line Arguments

- `--repo`: Path to the git repository
- `--output`: Output directory for embeddings (default: `<repo_path>/embeddings/`)
- `--batch-size`: Number of files to process in a single batch (default: 10)
- `--device`: Device to use for inference (cuda or cpu, default: auto-detect)
- `--model`: Embedding model to use (qwen, deepseek, phi4, nomic, default: qwen)
- `--model-path`: Path to model file (required for GGUF models like nomic)
- `--extensions`: Comma-separated list of file extensions to include (default: common code file extensions)
- `--exclude-dirs`: Comma-separated list of directories to exclude (default: common build/dependency directories)
- `--subdir`: Only process files within this subdirectory of the repository

#### Output Structure

The embeddings are saved in parquet files organized by directory structure:

```
<output_dir>/
  ├── dir1/
  │   └── embeddings.parquet
  ├── dir2/
  │   └── embeddings.parquet
  ├── src/subdir/
  │   └── embeddings.parquet
  └── ...
```

Each parquet file contains:
- `file_path`: Relative path to the file from the repository root
- `embedding`: The embedding vector for the file contents

#### Programmatic Usage

You can also use the embedding functionality in your own Python code:

```python
from vectordb.code_embeddings import CodeEmbeddings, create_nomic_embed_code

# Using transformer models
embedding_model = CodeEmbeddings(device="cuda")

# Using Nomic GGUF model
nomic_embedder = create_nomic_embed_code(
    model_path="./nomic-embed-code.Q6_K.gguf",
    device="cuda"
)

# Generate embeddings for a code snippet
code = """
def hello_world():
    print("Hello, world!")
"""
embeddings = embedding_model(code)
nomic_embeddings = nomic_embedder(code)

# Process a git repository
output_files = embedding_model.process_git_repo(
    repo_path="/path/to/repo",
    output_dir="/path/to/output",
    batch_size=10
)
```

## ChromaDB Vector Database for Code Snippets

This component demonstrates how to use ChromaDB as a vector database with code-optimized embeddings for C++ code snippet searches.

### Features

- Uses transformer-based models from Hugging Face for generating C++ code embeddings
- Implements a custom embedding function for ChromaDB
- Initializes a ChromaDB client with local persistence
- Creates a collection for storing C++ code examples with custom embeddings
- Demonstrates similarity search for C++ code snippets
- Automatically uses GPU if available for faster embedding generation
- Includes batch processing example for large collections

### C++ Examples Included

The project includes examples for various C++ coding patterns and algorithms:
- Template-based QuickSort implementation
- Binary Tree data structure with insertion operations
- Matrix multiplication with vectors
- Fibonacci sequence with memoization

### How It Works

1. `code_embeddings.py` creates a wrapper class for transformer models
   - Automatically detects and uses GPU if available
   - Handles text tokenization and embedding generation
   - Supports multiple pooling strategies (mean, cls, max)
   - Configurable output dimensions for embeddings
2. The model converts C++ code snippets into high-dimensional embeddings
3. `vector_store_example.py` uses these embeddings to power semantic search in ChromaDB
   - Contains example for handling large collections through batch processing

### Performance

The code includes timing metrics to measure:
- Document addition speed
- Query performance
- Batch processing efficiency

On systems with CUDA-compatible GPUs, you should see significant performance improvements compared to CPU-only processing, especially for large collections or complex code snippets.

### Vector Database Examples

```bash
# Run the vector database example:
python vectordb/vector_store_example.py

# For batch processing (useful with large collections):
# First uncomment the batch_process_example() line in vector_store_example.py
python vectordb/vector_store_example.py
```

## Setup and Installation

### Requirements

All dependencies are specified in the `pyproject.toml` file:
- Python 3.12+
- PyTorch
- Transformers
- pandas
- pyarrow
- gitpython
- tqdm
- chromadb
- sentence-transformers
- psutil
- flash-attn
- llama-cpp-python (optional, required for GGUF models)

### Installation Options

#### Using pip

```bash
# Install with pip
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"

# Install llama-cpp-python for GGUF model support (optional)
pip install llama-cpp-python

# For GPU support with GGUF models
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python
```

#### Using uv (recommended for faster installation)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or with pip
pip install uv

# Create and activate virtual environment
uv venv
source .venv/bin/activate  # On Unix/macOS
# OR
.venv\Scripts\activate     # On Windows

# Install torch first (required for flash-attn build)
uv pip install torch

# Install dependencies with build isolation disabled
uv pip install -e . --no-build-isolation

# Install llama-cpp-python for GGUF support (optional)
uv pip install llama-cpp-python
```

### Setting up Nomic Embed Code GGUF Model

To use the Nomic Embed Code GGUF model:

1. **Install llama-cpp-python:**
   ```bash
   pip install llama-cpp-python
   # Or for GPU support:
   CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python
   ```

2. **Download the model:**
   ```bash
   # Create models directory
   mkdir -p vectordb/models
   
   # Download the quantized model (Q6_K variant, ~500MB)
   wget -P vectordb/models https://huggingface.co/nomic-ai/nomic-embed-code-GGUF/resolve/main/nomic-embed-code.Q6_K.gguf
   ```

3. **Use the model:**
   ```bash
   python -m vectordb.repo_processor --repo /path/to/repo --model nomic
   ```

   Or specify a custom path:
   ```bash
   python -m vectordb.repo_processor --repo /path/to/repo --model nomic --model-path /path/to/nomic-embed-code.Q6_K.gguf
   ```

## Project Structure

- `vectordb/code_embeddings.py` - Core embedding functionality
- `vectordb/repo_processor.py` - Command-line tool for repository processing
- `vectordb/vector_store_example.py` - ChromaDB integration example
- `vectordb/tests/` - Unit tests for the package

## Running Tests

Run the test suite to validate the embedding functionality:

```bash
# Run the tests
pytest
```

## Model Comparison

| Model | Type | Context Length | Embedding Dim | Size | Best For |
|-------|------|----------------|---------------|------|----------|
| Qwen2.5-Coder-7B | Transformer | 128K | Variable | ~14GB | Large codebases, high accuracy |
| DeepSeek-Coder-V2-Lite | Transformer | 128K | Variable | ~3GB | Balance of speed and accuracy |
| Phi-4 | Transformer | 16K | Variable | ~14GB | General purpose code |
| Nomic Embed Code | GGUF | 8K | 768 | ~500MB | Fast inference, code-specific |

## Notes

- The vector store data will be saved in the `./vector_store` directory
- Transformer models are downloaded automatically from Hugging Face the first time they're used
- GGUF models must be downloaded manually (see setup instructions)
- The embedding dimensionality is determined by the model
- For large codebases, the batch processing example demonstrates how to handle many documents efficiently
- Nomic Embed Code is specifically optimized for code and provides fast inference with a small model size 