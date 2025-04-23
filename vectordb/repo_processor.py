import os
import argparse
from vectordb.code_embeddings import (
    CodeEmbeddings, 
    EMBEDDING_CONFIG_QWEN25_CODER_7B,
    EMBEDDING_CONFIG_DEEPSEEK_CODER_V2_LITE_BASE,
    EMBEDDING_CONFIG_PHI4
)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Generate code embeddings for files in a git repository')
    parser.add_argument('--repo', type=str, required=True, help='Path to the git repository')
    parser.add_argument('--output', type=str, help='Output directory for embeddings', default=None)
    parser.add_argument('--batch-size', type=int, help='Batch size for processing files', default=10)
    parser.add_argument('--device', type=str, help='Device to use (cuda or cpu)', default=None)
    parser.add_argument('--extensions', type=str, help='Comma-separated list of file extensions to include', default=None)
    parser.add_argument('--exclude-dirs', type=str, help='Comma-separated list of directories to exclude', default=None)
    parser.add_argument('--model', type=str, help='Model to use for embeddings (qwen, deepseek, phi4)', default='qwen')
    parser.add_argument('--subdir', type=str, help='Only process files within this subdirectory of the repository', default=None)
    
    return parser.parse_args()

def get_embedding_model(args):
    """Initialize and return the embedding model based on args"""
    # Select model based on args
    model_config = EMBEDDING_CONFIG_QWEN25_CODER_7B  # Default
    if args.model == 'deepseek':
        model_config = EMBEDDING_CONFIG_DEEPSEEK_CODER_V2_LITE_BASE
    elif args.model == 'phi4':
        model_config = EMBEDDING_CONFIG_PHI4
        
    # Initialize the embedding model
    return CodeEmbeddings(
        model_name=model_config["model_name"],
        device=args.device
    )

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
        exclude_dirs=exclude_dirs,
        subdir=args.subdir
    )
    
    print(f"\nProcessing complete!")
    print(f"Generated embeddings for {len(output_files)} directories")
    print(f"Output files:")
    for dir_path, file_path in output_files.items():
        print(f"  - {dir_path}: {file_path}")

def main():
    """Main function for processing git repositories and generating embeddings"""
    args = parse_args()
    embedding_model = get_embedding_model(args)
    process_repository(embedding_model, args)

if __name__ == "__main__":
    main() 