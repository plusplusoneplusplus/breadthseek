# Vector Database Example with ChromaDB and Code Embeddings for C++

This project demonstrates how to use ChromaDB as a vector database with code-optimized embeddings for C++ code snippet searches.

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Run the embedding model example to test it:
```bash
python code_embeddings.py
```

3. Run the vector database example:
```bash
python vector_store_example.py
```

4. For batch processing (useful with large collections):
```bash
# First uncomment the batch_process_example() line in vector_store_example.py
python vector_store_example.py
```

## Features

- Uses transformer-based models from Hugging Face for generating C++ code embeddings
- Implements a custom embedding function for ChromaDB
- Initializes a ChromaDB client with local persistence
- Creates a collection for storing C++ code examples with custom embeddings
- Demonstrates similarity search for C++ code snippets
- Automatically uses GPU if available for faster embedding generation
- Includes batch processing example for large collections

## C++ Examples Included

The project includes examples for various C++ coding patterns and algorithms:
- Template-based QuickSort implementation
- Binary Tree data structure with insertion operations
- Matrix multiplication with vectors
- Fibonacci sequence with memoization

## How It Works

1. `code_embeddings.py` creates a wrapper class for transformer models
   - Automatically detects and uses GPU if available
   - Handles text tokenization and embedding generation
   - Supports multiple pooling strategies (mean, cls, max)
   - Configurable output dimensions for embeddings
2. The model converts C++ code snippets into high-dimensional embeddings
3. `vector_store_example.py` uses these embeddings to power semantic search in ChromaDB
   - Contains example for handling large collections through batch processing

## Performance

The code includes timing metrics to measure:
- Document addition speed
- Query performance
- Batch processing efficiency

On systems with CUDA-compatible GPUs, you should see significant performance improvements compared to CPU-only processing, especially for large collections or complex code snippets.

## Notes

- The vector store data will be saved in the `./vector_store` directory
- The embedding model is downloaded automatically from Hugging Face the first time it's used
- The embedding dimensionality is determined by the model
- For large codebases, the batch processing example demonstrates how to handle many documents efficiently 