import chromadb

def main():
    # Initialize ChromaDB client with newer API
    client = chromadb.PersistentClient(path="./chroma_db")

    # Create or get a collection
    collection = client.get_or_create_collection(
        name="documents",
        metadata={"description": "Sample document collection"}
    )

    # Sample documents and their embeddings
    documents = [
        "The quick brown fox jumps over the lazy dog",
        "A fast orange fox leaps across a sleepy canine",
        "The weather is sunny and warm today",
        "Climate change affects global temperatures"
    ]

    # Add documents to the collection
    # ChromaDB will automatically generate embeddings
    collection.add(
        documents=documents,
        ids=["doc1", "doc2", "doc3", "doc4"]
    )

    # Query similar documents
    print("\n=== Query Results ===")
    results = collection.query(
        query_texts=["fox jumping over animals"],
        n_results=2
    )
    
    print("\nQuery: 'fox jumping over animals'")
    print("Top 2 similar documents:")
    for idx, doc in enumerate(results['documents'][0]):
        print(f"{idx + 1}. {doc}")

    # Query with different topic
    results = collection.query(
        query_texts=["weather and temperature"],
        n_results=2
    )
    
    print("\nQuery: 'weather and temperature'")
    print("Top 2 similar documents:")
    for idx, doc in enumerate(results['documents'][0]):
        print(f"{idx + 1}. {doc}")

if __name__ == "__main__":
    main() 