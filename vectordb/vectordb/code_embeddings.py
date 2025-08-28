from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
import os
import pandas as pd
import git
from pathlib import Path
from tqdm import tqdm
from typing import Optional, List, Dict, Any

# Try to import llama-cpp-python for GGUF support
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    print("Warning: llama-cpp-python not installed. GGUF models will not be available.")
    print("Install with: pip install llama-cpp-python")

# Configuration parameters
EMBEDDING_CONFIG_DEEPSEEK_CODER_V2_LITE_BASE = {
    "model_name": "deepseek-ai/DeepSeek-Coder-V2-Lite-Base",  # Model to use for embeddings
    "max_context_length": 128 * 1024,  # Maximum token length for input text
    "output_dim": None,  # Output embedding dimensionality (None = use model's default)
    "pooling_strategy": "mean",  # Options: "mean", "cls", "max"
    "normalize": True,  # Whether to L2-normalize the output embeddings
}

EMBEDDING_CONFIG_QWEN25_CODER_7B = {
    "model_name": "Qwen/Qwen2.5-Coder-7B-Instruct",
    "max_context_length": 128 * 1024,
    "output_dim": None,
    "pooling_strategy": "mean",
    "normalize": True,
}

EMBEDDING_CONFIG_PHI4 = {
    "model_name": "microsoft/phi-4",
    "max_context_length": 16 * 1024,  # Phi-4 has a 16K token context length
    "output_dim": None,
    "pooling_strategy": "mean",
    "normalize": True,
}

EMBEDDING_CONFIG_NOMIC_EMBED_CODE_GGUF = {
    "model_name": "nomic-embed-code.Q6_K.gguf",  # GGUF model file name
    "model_type": "gguf",  # Indicate this is a GGUF model
    "model_url": "https://huggingface.co/nomic-ai/nomic-embed-code-GGUF/resolve/main/nomic-embed-code.Q6_K.gguf",
    "max_context_length": 8192,  # Nomic embed code context length
    "output_dim": 768,  # Nomic embed code output dimension
    "pooling_strategy": "mean",  # GGUF models typically use mean pooling for embeddings
    "normalize": True,
    "n_ctx": 8192,  # Context window for llama.cpp
    "n_gpu_layers": -1,  # Use all available GPU layers (-1 for all)
    "embedding": True,  # Enable embedding mode for llama.cpp
}

# Default configuration 
EMBEDDING_CONFIG = EMBEDDING_CONFIG_QWEN25_CODER_7B

class CodeEmbeddings:
    def __init__(self, 
                 model_name=EMBEDDING_CONFIG["model_name"], 
                 device=None, 
                 output_dim=EMBEDDING_CONFIG.get("output_dim"),
                 pooling_strategy=EMBEDDING_CONFIG.get("pooling_strategy", "mean"),
                 normalize=EMBEDDING_CONFIG.get("normalize", True),
                 model_type=EMBEDDING_CONFIG.get("model_type", "transformer"),
                 model_config=None):
        self.model_type = model_type
        self.model_name = model_name
        self.pooling_strategy = pooling_strategy
        self.normalize = normalize
        self.model_config = model_config or EMBEDDING_CONFIG
        self.max_length = self.model_config.get("max_context_length", 8192)
        self.output_dim = output_dim
        
        # Automatically determine the device to use
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        print(f"Using device: {self.device}")
        print(f"Model type: {self.model_type}")
        
        if self.model_type == "gguf":
            self._init_gguf_model()
        else:
            self._init_transformer_model()
    
    def _init_gguf_model(self):
        """Initialize a GGUF model using llama-cpp-python."""
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError("llama-cpp-python is required for GGUF models. Install with: pip install llama-cpp-python")
        
        # Check if model file exists locally
        model_path = self.model_name
        if not os.path.exists(model_path):
            # Try to find it in a models directory
            models_dir = os.path.join(os.path.dirname(__file__), "models")
            model_path = os.path.join(models_dir, self.model_name)
            
            if not os.path.exists(model_path):
                print(f"Model file {self.model_name} not found locally.")
                print(f"Please download from: {self.model_config.get('model_url', '')}")
                print(f"And place it in: {models_dir}")
                raise FileNotFoundError(f"GGUF model file not found: {self.model_name}")
        
        # Initialize the GGUF model
        n_gpu_layers = self.model_config.get("n_gpu_layers", -1) if self.device == "cuda" else 0
        
        self.model = Llama(
            model_path=model_path,
            n_ctx=self.model_config.get("n_ctx", 8192),
            n_gpu_layers=n_gpu_layers,
            embedding=True,  # Enable embedding mode
            verbose=False
        )
        
        # Set output dimension from config
        if self.output_dim is None:
            self.output_dim = self.model_config.get("output_dim", 768)
        
        print(f"GGUF model loaded: {model_path}")
        print(f"Embedding dimension: {self.output_dim}")
        
        # GGUF models don't need tokenizer or projection
        self.tokenizer = None
        self.projection = None
    
    def _init_transformer_model(self):
        """Initialize a transformer model using HuggingFace transformers."""
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()
        
        # Get the default embedding dimension from the model
        if self.output_dim is None:
            # Most transformer models have this attribute
            if hasattr(self.model.config, "hidden_size"):
                self.output_dim = self.model.config.hidden_size
            else:
                # Determine from the model's output (fallback)
                dummy_input = self.tokenizer("test", return_tensors="pt").to(self.device)
                with torch.no_grad():
                    dummy_output = self.model(**dummy_input)
                self.output_dim = dummy_output[0].shape[-1]
                
        print(f"Embedding dimension: {self.output_dim}")
        
        # Initialize projection layer if we need a specific output dimension
        # different from the model's default
        if self.output_dim is not None and hasattr(self.model.config, "hidden_size") and self.output_dim != self.model.config.hidden_size:
            self.projection = torch.nn.Linear(self.model.config.hidden_size, self.output_dim).to(self.device)
        else:
            self.projection = None

    def _mean_pooling(self, model_output, attention_mask):
        # Mean pooling - take average of all token embeddings
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    
    def _cls_pooling(self, model_output):
        # CLS token pooling - use the first token's embedding
        return model_output[0][:, 0]
    
    def _max_pooling(self, model_output, attention_mask):
        # Max pooling - take max of all token embeddings
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        # Set padding tokens to large negative value to exclude them from max
        token_embeddings = token_embeddings * input_mask_expanded + -1e9 * (1 - input_mask_expanded)
        return torch.max(token_embeddings, dim=1)[0]

    def __call__(self, texts):
        # Process a list of texts and return their embeddings
        if isinstance(texts, str):
            texts = [texts]

        if self.model_type == "gguf":
            return self._embed_gguf(texts)
        else:
            return self._embed_transformer(texts)
    
    def _embed_gguf(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings using a GGUF model."""
        all_embeddings = []
        
        for text in texts:
            # Truncate text if necessary (character-based for GGUF)
            # Approximate max characters based on typical tokenization
            max_chars = self.max_length * 4  # Rough approximation
            if len(text) > max_chars:
                text = text[:max_chars]
            
            # Get embeddings from GGUF model
            embedding_result = self.model.embed(text)
            
            # Extract embedding vector
            if isinstance(embedding_result, list):
                embedding = np.array(embedding_result)
            else:
                embedding = np.array(embedding_result)
            
            # Ensure correct shape
            if len(embedding.shape) == 1:
                embedding = embedding.reshape(1, -1)
            
            all_embeddings.append(embedding)
        
        # Stack all embeddings
        embeddings = np.vstack(all_embeddings)
        
        # Normalize if requested
        if self.normalize:
            # L2 normalization
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / (norms + 1e-9)
        
        return embeddings
    
    def _embed_transformer(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings using a transformer model."""
        # Tokenize the texts
        encoded_input = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors='pt'
        ).to(self.device)

        # Generate embeddings
        with torch.no_grad():
            model_output = self.model(**encoded_input)

        # Apply pooling strategy
        if self.pooling_strategy == "mean":
            embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
        elif self.pooling_strategy == "cls":
            embeddings = self._cls_pooling(model_output)
        elif self.pooling_strategy == "max":
            embeddings = self._max_pooling(model_output, encoded_input['attention_mask'])
        else:
            raise ValueError(f"Unknown pooling strategy: {self.pooling_strategy}")
        
        # Apply projection if needed
        if self.projection is not None:
            embeddings = self.projection(embeddings)
        
        # Normalize embeddings if requested
        if self.normalize:
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        
        # Convert to numpy array
        return embeddings.cpu().numpy()

    def process_git_repo(self, repo_path, output_dir=None, batch_size=10, 
                         file_extensions=None, exclude_dirs=None, subdir=None):
        """
        Generate embeddings for all tracked files in a git repository.
        
        Args:
            repo_path (str): Path to the git repository
            output_dir (str, optional): Directory to save the output parquet files.
                                      If None, will use repo_path/embeddings
            batch_size (int): Number of files to process in a single batch
            file_extensions (list, optional): List of file extensions to include
                                            If None, all files will be processed
            exclude_dirs (list, optional): List of directories to exclude (relative to repo)
            subdir (str, optional): Only process files within this subdirectory of the repository
        
        Returns:
            dict: Directory paths to the output parquet files
        """
        # Set defaults
        if file_extensions is None:
            file_extensions = ['.py', '.java', '.js', '.ts', '.c', '.cpp', '.h', '.hpp', '.go', '.rs', '.rb', '.php']
        
        if exclude_dirs is None:
            exclude_dirs = ['.git', 'node_modules', 'venv', 'dist', 'build', '__pycache__']
        
        if output_dir is None:
            output_dir = os.path.join(repo_path, "embeddings")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize git repo
        repo = git.Repo(repo_path)
        repo_root = Path(repo_path)
        
        # Set the subdirectory path if provided
        subdir_path = None
        if subdir:
            subdir_path = os.path.normpath(subdir)
            if not os.path.isabs(subdir_path):
                subdir_path = os.path.join(repo_path, subdir_path)
            
            # Verify the subdirectory exists
            if not os.path.isdir(subdir_path):
                raise ValueError(f"Specified subdirectory '{subdir}' does not exist in the repository")
            
            print(f"Only processing files within subdirectory: {subdir}")
        
        print("Scanning repository for tracked files...")
        # Get all tracked files
        tracked_files = []
        for item in tqdm(repo.index.entries.items(), desc="Scanning git index"):
            file_path = os.path.join(repo_path, item[0][0])
            
            # Check if file exists and is not in excluded directories
            if not os.path.exists(file_path):
                continue
            
            # Check if file is within the specified subdirectory
            if subdir_path and not file_path.startswith(subdir_path):
                continue
                
            # Check if file is in excluded directories
            rel_path = os.path.relpath(file_path, repo_path)
            if any(rel_path.startswith(exclude_dir) for exclude_dir in exclude_dirs):
                continue
                
            # Check file extension
            _, ext = os.path.splitext(file_path)
            if ext not in file_extensions:
                continue
                
            tracked_files.append(file_path)
            
        print(f"Found {len(tracked_files)} tracked files with specified extensions")
        
        # Group files by directory
        files_by_dir = {}
        for file_path in tracked_files:
            dir_path = os.path.dirname(file_path)
            if dir_path not in files_by_dir:
                files_by_dir[dir_path] = []
            files_by_dir[dir_path].append(file_path)
        
        output_files = {}
        
        # Process each directory
        for dir_path, files in tqdm(files_by_dir.items(), desc="Processing directories"):
            rel_dir = os.path.relpath(dir_path, repo_path)
            dir_tqdm = tqdm(total=len(files), desc=f"Files in {rel_dir}", leave=False)
            
            all_embeddings = []
            
            # Process files in batches
            for i in range(0, len(files), batch_size):
                batch = files[i:i+batch_size]
                
                # Read file contents
                file_contents = []
                valid_files = []
                
                for file_path in batch:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            file_contents.append(content)
                            valid_files.append(file_path)
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
                        continue
                
                if not file_contents:
                    dir_tqdm.update(len(batch))
                    continue
                    
                # Generate embeddings
                batch_embeddings = self(file_contents)
                
                # Store results
                for j, file_path in enumerate(valid_files):
                    rel_path = os.path.relpath(file_path, repo_path)
                    embedding = batch_embeddings[j]
                    
                    all_embeddings.append({
                        "file_path": rel_path,
                        "embedding": embedding
                    })
                
                dir_tqdm.update(len(batch))
            
            dir_tqdm.close()
            
            if all_embeddings:
                # Create output directory if needed
                output_subdir = os.path.join(output_dir, rel_dir)
                os.makedirs(output_subdir, exist_ok=True)
                
                # Create DataFrame
                df = pd.DataFrame([{
                    "file_path": item["file_path"],
                    "embedding": item["embedding"]
                } for item in all_embeddings])
                
                # Save to parquet
                output_file = os.path.join(output_subdir, "embeddings.parquet")
                df.to_parquet(output_file)
                
                output_files[rel_dir] = output_file
                print(f"Saved embeddings for {len(all_embeddings)} files in {rel_dir}")
            
        return output_files


def create_nomic_embed_code(model_path: Optional[str] = None, device: Optional[str] = None) -> CodeEmbeddings:
    """
    Convenience function to create a CodeEmbeddings instance with Nomic Embed Code GGUF model.
    
    Args:
        model_path (str, optional): Path to the GGUF model file. If None, will look for
                                   'nomic-embed-code.Q6_K.gguf' in the models directory.
        device (str, optional): Device to use ('cuda' or 'cpu'). If None, auto-detect.
    
    Returns:
        CodeEmbeddings: Instance configured for Nomic Embed Code
    
    Example:
        >>> embedder = create_nomic_embed_code()
        >>> embeddings = embedder(["def hello():\n    print('Hello, world!')"])
    """
    config = EMBEDDING_CONFIG_NOMIC_EMBED_CODE_GGUF.copy()
    if model_path:
        config["model_name"] = model_path
    
    return CodeEmbeddings(
        model_name=config["model_name"],
        device=device,
        output_dim=config["output_dim"],
        pooling_strategy=config["pooling_strategy"],
        normalize=config["normalize"],
        model_type=config["model_type"],
        model_config=config
    )