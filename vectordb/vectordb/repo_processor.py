import os
import argparse
from vectordb.code_embeddings import (
    CodeEmbeddings, 
    EMBEDDING_CONFIG_QWEN25_CODER_7B,
    EMBEDDING_CONFIG_DEEPSEEK_CODER_V2_LITE_BASE,
    EMBEDDING_CONFIG_PHI4,
    EMBEDDING_CONFIG_NOMIC_EMBED_CODE_GGUF,
    create_nomic_embed_code
)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Generate code embeddings for files in a git repository',
        epilog='''
Available models:
  qwen     - Qwen2.5-Coder-7B-Instruct (default, 128K context)
  deepseek - DeepSeek-Coder-V2-Lite-Base (128K context)
  phi4     - Microsoft Phi-4 (16K context)
  nomic    - Nomic Embed Code GGUF (8K context, requires llama-cpp-python)

Example usage:
  python repo_processor.py --repo /path/to/repo --model qwen
  python repo_processor.py --repo /path/to/repo --model nomic --model-path ./nomic-embed-code.Q6_K.gguf
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--repo', type=str, required=True, help='Path to the git repository')
    parser.add_argument('--output', type=str, help='Output directory for embeddings', default=None)
    parser.add_argument('--batch-size', type=int, help='Batch size for processing files', default=10)
    parser.add_argument('--device', type=str, help='Device to use (cuda or cpu)', default=None)
    parser.add_argument('--extensions', type=str, help='Comma-separated list of file extensions to include', default=None)
    parser.add_argument('--exclude-dirs', type=str, help='Comma-separated list of directories to exclude', default=None)
    parser.add_argument('--model', type=str, help='Model to use for embeddings (qwen, deepseek, phi4, nomic)', default='qwen')
    parser.add_argument('--model-path', type=str, help='Path to model file (for GGUF models like nomic)', default=None)
    parser.add_argument('--subdir', type=str, help='Only process files within this subdirectory of the repository', default=None)
    
    return parser.parse_args()

def get_embedding_model(args):
    """Initialize and return the embedding model based on args"""
    # Handle Nomic model separately as it uses GGUF format
    if args.model == 'nomic':
        print("Using Nomic Embed Code GGUF model")
        return create_nomic_embed_code(
            model_path=args.model_path,
            device=args.device
        )
    
    # Select transformer model based on args
    model_config = EMBEDDING_CONFIG_QWEN25_CODER_7B  # Default
    if args.model == 'deepseek':
        model_config = EMBEDDING_CONFIG_DEEPSEEK_CODER_V2_LITE_BASE
    elif args.model == 'phi4':
        model_config = EMBEDDING_CONFIG_PHI4
    elif args.model != 'qwen':
        print(f"Warning: Unknown model '{args.model}', using default qwen model")
        
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
    
    # Print model selection info
    print(f"Selected model: {args.model}")
    if args.model == 'nomic' and not args.model_path:
        print("Note: Using default path for Nomic model. Use --model-path to specify a custom location.")
    
    try:
        embedding_model = get_embedding_model(args)
        process_repository(embedding_model, args)
    except FileNotFoundError as e:
        if 'nomic' in str(e).lower():
            print("\nError: Nomic model file not found!")
            print("\nTo use the Nomic Embed Code model:")
            print("1. Install llama-cpp-python: pip install llama-cpp-python")
            print("2. Download the model:")
            print("   wget https://huggingface.co/nomic-ai/nomic-embed-code-GGUF/resolve/main/nomic-embed-code.Q6_K.gguf")
            print("3. Create a 'models' directory next to this script and place the model there")
            print("   OR use --model-path to specify the model location")
        else:
            raise
    except ImportError as e:
        if 'llama_cpp' in str(e):
            print("\nError: llama-cpp-python is not installed!")
            print("Install it with: pip install llama-cpp-python")
            print("\nFor GPU support, use: CMAKE_ARGS=\"-DLLAMA_CUBLAS=on\" pip install llama-cpp-python")
        else:
            raise

if __name__ == "__main__":
    main() 