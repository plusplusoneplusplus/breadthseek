import unittest
import numpy as np
from ..code_embeddings import CodeEmbeddings

class TestCodeEmbeddings(unittest.TestCase):
    def setUp(self):
        # Initialize the embedding model for tests
        self.embedding_model = CodeEmbeddings(device="cpu")
        
        # Example C++ code snippets
        self.cpp_code_snippets = [
            """// Recursive Fibonacci implementation in C++
int fibonacci(int n) {
    if (n <= 1)
        return n;
    return fibonacci(n-1) + fibonacci(n-2);
}""",

            """// Simple loop example in C++
#include <iostream>
int main() {
    for (int i = 0; i < 10; i++) {
        std::cout << i << std::endl;
    }
    return 0;
}""",

            """// Node class implementation in C++
class Node {
private:
    int value;
    Node* next;
public:
    Node(int val) : value(val), next(nullptr) {}
    void setNext(Node* node) { next = node; }
    Node* getNext() const { return next; }
    int getValue() const { return value; }
};"""
        ]
    
    def test_embeddings_shape(self):
        """Test that embeddings have the expected shape."""
        embeddings = self.embedding_model(self.cpp_code_snippets)
        
        # Check the shape of the embeddings
        self.assertEqual(embeddings.shape[0], len(self.cpp_code_snippets), 
                         "Number of embeddings should match number of input snippets")
        self.assertEqual(embeddings.shape[1], self.embedding_model.output_dim,
                         "Embedding dimension should match the model's output dimension")
    
    def test_single_embedding(self):
        """Test single string embedding."""
        single_code = self.cpp_code_snippets[0]
        embedding = self.embedding_model(single_code)
        
        # Check that it returns a single embedding (2D array with one row)
        self.assertEqual(embedding.shape[0], 1, 
                         "Single input should produce a single embedding")
        self.assertEqual(embedding.shape[1], self.embedding_model.output_dim,
                         "Embedding dimension should match the model's output dimension")
    
    def test_embeddings_are_normalized(self):
        """Test that embeddings are normalized if normalize=True."""
        embeddings = self.embedding_model(self.cpp_code_snippets)
        
        # Check that each embedding has unit norm (if normalize is True)
        if self.embedding_model.normalize:
            for i in range(embeddings.shape[0]):
                norm = np.linalg.norm(embeddings[i])
                self.assertAlmostEqual(norm, 1.0, places=5, 
                                       msg=f"Embedding {i} should have unit norm")
    
    def test_different_snippets_have_different_embeddings(self):
        """Test that different code snippets have different embeddings."""
        embeddings = self.embedding_model(self.cpp_code_snippets)
        
        # Calculate cosine similarity between the first two embeddings
        similarity = np.dot(embeddings[0], embeddings[1]) / (
            np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]))
        
        # They should be somewhat different (not identical)
        self.assertLess(similarity, 0.99, 
                        "Different code snippets should have distinguishable embeddings")

if __name__ == "__main__":
    unittest.main() 