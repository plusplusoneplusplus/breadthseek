import chromadb
from chromadb.utils import embedding_functions
from code_embeddings import CodeEmbeddings
import time

def main():
    # Initialize the code embeddings model
    code_embeddings_model = CodeEmbeddings()
    
    # Create a custom embedding function for ChromaDB
    embedding_function = lambda texts: code_embeddings_model(texts).tolist()
    
    # Initialize ChromaDB client with newer API
    client = chromadb.PersistentClient(path="./vector_store")

    # Create or get a collection with our custom embedding function
    collection = client.get_or_create_collection(
        name="cpp_examples",
        metadata={"description": "C++ code examples collection"},
        embedding_function=embedding_function
    )

    # Sample C++ code examples
    cpp_examples = [
        """// QuickSort implementation in C++
template<typename T>
int partition(std::vector<T>& arr, int low, int high) {
    T pivot = arr[high];
    int i = low - 1;
    
    for(int j = low; j < high; j++) {
        if(arr[j] <= pivot) {
            i++;
            std::swap(arr[i], arr[j]);
        }
    }
    std::swap(arr[i + 1], arr[high]);
    return i + 1;
}

template<typename T>
void quickSort(std::vector<T>& arr, int low, int high) {
    if(low < high) {
        int pi = partition(arr, low, high);
        quickSort(arr, low, pi - 1);
        quickSort(arr, pi + 1, high);
    }
}""",
        
        """// Binary Tree implementation in C++
class BinaryTree {
private:
    struct Node {
        int value;
        Node* left;
        Node* right;
        
        Node(int v) : value(v), left(nullptr), right(nullptr) {}
    };
    
    Node* root;
    
    void insertRecursive(Node* &node, int value) {
        if (node == nullptr) {
            node = new Node(value);
            return;
        }
        
        if (value < node->value) {
            insertRecursive(node->left, value);
        } else {
            insertRecursive(node->right, value);
        }
    }
    
public:
    BinaryTree() : root(nullptr) {}
    
    void insert(int value) {
        insertRecursive(root, value);
    }
};""",
                
        """// Matrix multiplication in C++
#include <vector>

std::vector<std::vector<double>> matrixMultiply(
        const std::vector<std::vector<double>>& A,
        const std::vector<std::vector<double>>& B) {
    
    int n = A.size();
    int m = B[0].size();
    int p = A[0].size();
    
    std::vector<std::vector<double>> C(n, std::vector<double>(m, 0));
    
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < m; j++) {
            for (int k = 0; k < p; k++) {
                C[i][j] += A[i][k] * B[k][j];
            }
        }
    }
    
    return C;
}""",
        
        """// Fibonacci implementation with memoization in C++
#include <unordered_map>

class Fibonacci {
private:
    std::unordered_map<int, long long> memo;
    
public:
    long long fib(int n) {
        if (memo.find(n) != memo.end()) {
            return memo[n];
        }
        
        if (n <= 2) {
            return 1;
        }
        
        memo[n] = fib(n-1) + fib(n-2);
        return memo[n];
    }
};"""
    ]

    # Time the document addition
    start_time = time.time()
    
    # Add documents to the collection
    collection.add(
        documents=cpp_examples,
        ids=["cpp_algo1", "cpp_algo2", "cpp_algo3", "cpp_algo4"]
    )
    
    end_time = time.time()
    print(f"Added {len(cpp_examples)} C++ documents in {end_time - start_time:.2f} seconds")

    # Query similar code examples
    print("\n=== Query Results with Code Embeddings ===")
    
    # Time the query process
    start_time = time.time()
    
    # Search for sorting algorithms
    results = collection.query(
        query_texts=["C++ sorting algorithm implementation"],
        n_results=2
    )
    
    end_time = time.time()
    print(f"Query completed in {end_time - start_time:.2f} seconds")
    
    print("\nQuery: 'C++ sorting algorithm implementation'")
    print("Top 2 similar code examples:")
    for idx, doc in enumerate(results['documents'][0]):
        print(f"\n{idx + 1}. {doc}")

    # Search for tree data structures
    start_time = time.time()
    
    results = collection.query(
        query_texts=["C++ binary tree data structure"],
        n_results=2
    )
    
    end_time = time.time()
    print(f"Query completed in {end_time - start_time:.2f} seconds")
    
    print("\nQuery: 'C++ binary tree data structure'")
    print("Top 2 similar code examples:")
    for idx, doc in enumerate(results['documents'][0]):
        print(f"\n{idx + 1}. {doc}")

def batch_process_example(batch_size=32):
    """Example function showing how to process a large collection in batches"""
    print("\n=== Batch Processing Example ===")
    
    # Initialize the code embeddings model
    code_embeddings_model = CodeEmbeddings()
    
    # Create a custom embedding function for ChromaDB
    embedding_function = lambda texts: code_embeddings_model(texts).tolist()
    
    # Initialize ChromaDB client with newer API
    client = chromadb.PersistentClient(path="./vector_store_batch")

    # Create or get a collection with our custom embedding function
    collection = client.get_or_create_collection(
        name="large_cpp_collection",
        metadata={"description": "Large C++ code collection with batch processing"},
        embedding_function=embedding_function
    )
    
    # Generate a larger dataset (for demonstration)
    # In a real scenario, you might load this from files
    large_dataset = []
    ids = []
    
    for i in range(100):  # Generate 100 code snippets
        code = f"""// Function {i} implementation
#include <iostream>

template<typename T>
T multiply_{i}(T x) {{
    return x * {i};
}}

int main() {{
    std::cout << multiply_{i}(5) << std::endl;
    return 0;
}}"""
        large_dataset.append(code)
        ids.append(f"cpp_func_{i}")
    
    # Process in batches
    start_time = time.time()
    
    for i in range(0, len(large_dataset), batch_size):
        batch_docs = large_dataset[i:i+batch_size]
        batch_ids = ids[i:i+batch_size]
        
        print(f"Processing batch {i//batch_size + 1}/{(len(large_dataset)-1)//batch_size + 1}")
        
        # Add batch to collection
        collection.add(
            documents=batch_docs,
            ids=batch_ids
        )
    
    end_time = time.time()
    print(f"Processed {len(large_dataset)} C++ documents in {end_time - start_time:.2f} seconds")
    print(f"Average time per document: {(end_time - start_time) / len(large_dataset):.4f} seconds")
    
    # Example query on the batch processed collection
    start_time = time.time()
    results = collection.query(
        query_texts=["C++ function that multiplies by 50"],
        n_results=2
    )
    end_time = time.time()
    
    print(f"\nQuery completed in {end_time - start_time:.2f} seconds")
    print("\nQuery: 'C++ function that multiplies by 50'")
    print("Top 2 similar code examples:")
    for idx, doc in enumerate(results['documents'][0]):
        print(f"\n{idx + 1}. {doc}")

if __name__ == "__main__":
    main()
    
    # Uncomment to run the batch processing example
    # batch_process_example() 