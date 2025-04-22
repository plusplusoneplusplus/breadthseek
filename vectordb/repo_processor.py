import os
import argparse
from vectordb.code_embeddings import (
    CodeEmbeddings, 
    EMBEDDING_CONFIG_QWEN25_CODER_7B,
    EMBEDDING_CONFIG_DEEPSEEK_CODER_V2_LITE_BASE,
    EMBEDDING_CONFIG_PHI4
)

def main():
    """Main function for processing git repositories and generating embeddings"""
    # Add command line arguments
    parser = argparse.ArgumentParser(description='Generate code embeddings for files in a git repository')
    parser.add_argument('--repo', type=str, help='Path to the git repository')
    parser.add_argument('--output', type=str, help='Output directory for embeddings', default=None)
    parser.add_argument('--batch-size', type=int, help='Batch size for processing files', default=10)
    parser.add_argument('--device', type=str, help='Device to use (cuda or cpu)', default=None)
    parser.add_argument('--extensions', type=str, help='Comma-separated list of file extensions to include', default=None)
    parser.add_argument('--exclude-dirs', type=str, help='Comma-separated list of directories to exclude', default=None)
    parser.add_argument('--model', type=str, help='Model to use for embeddings (qwen, deepseek, phi4)', default='qwen')
    
    # Example mode (for backward compatibility)
    parser.add_argument('--example', action='store_true', help='Run example snippets instead of processing a repo')

    args = parser.parse_args()
    
    # Select model based on args
    model_config = EMBEDDING_CONFIG_QWEN25_CODER_7B  # Default
    if args.model == 'deepseek':
        model_config = EMBEDDING_CONFIG_DEEPSEEK_CODER_V2_LITE_BASE
    elif args.model == 'phi4':
        model_config = EMBEDDING_CONFIG_PHI4
        
    # Initialize the embedding model
    embedding_model = CodeEmbeddings(
        model_name=model_config["model_name"],
        device=args.device
    )
    
    # Run in example mode if requested or if no repo specified
    if args.example or not args.repo:
        run_example_mode(embedding_model)
    else:
        process_repository(embedding_model, args)

def run_example_mode(embedding_model):
    """Run the example snippets mode"""
    # Generate embeddings for some C++ code snippets
    cpp_code_snippets = [
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
    
    embeddings = embedding_model(cpp_code_snippets)
    
    # Print embedding dimensions
    print(f"Embedding shape: {embeddings.shape}")
    print(f"First embedding sample: {embeddings[0][:10]}")  # Show first 10 dimensions of first embedding

def process_repository(embedding_model, args):
    """Process a git repository and generate embeddings"""
    # Process file extensions
    file_extensions = None
    if args.extensions:
        file_extensions = args.extensions.split(',')
        # Add dot if not present
        file_extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in file_extensions]
    
    # Process exclude dirs
    exclude_dirs = None
    if args.exclude_dirs:
        exclude_dirs = args.exclude_dirs.split(',')
    
    # Process repository
    print(f"Processing repository: {args.repo}")
    output_files = embedding_model.process_git_repo(
        repo_path=args.repo,
        output_dir=args.output,
        batch_size=args.batch_size,
        file_extensions=file_extensions,
        exclude_dirs=exclude_dirs
    )
    
    print(f"\nProcessing complete!")
    print(f"Generated embeddings for {len(output_files)} directories")
    print(f"Output files:")
    for dir_path, file_path in output_files.items():
        print(f"  - {dir_path}: {file_path}")

if __name__ == "__main__":
    main() 