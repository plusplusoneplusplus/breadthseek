# Vector Database Example with ChromaDB

This is a simple example project demonstrating how to use ChromaDB as a vector database for storing and querying document embeddings.

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Run the example:
```bash
python vector_store_example.py
```

## Features

- Initializes a ChromaDB client with local persistence
- Creates a collection for storing documents
- Adds sample documents to the collection
- Demonstrates similarity search queries
- Shows how to retrieve similar documents based on semantic meaning

## Notes

- The vector store data will be saved in the `./vector_store` directory
- ChromaDB automatically generates embeddings for the documents
- The example uses the default embedding model from ChromaDB 