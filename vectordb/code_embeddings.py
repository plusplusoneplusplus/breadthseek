from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
import os
import pandas as pd
import git
from pathlib import Path
from tqdm import tqdm

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

# Default configuration 
EMBEDDING_CONFIG = EMBEDDING_CONFIG_QWEN25_CODER_7B

class CodeEmbeddings:
    def __init__(self, 
                 model_name=EMBEDDING_CONFIG["model_name"], 
                 device=None, 
                 output_dim=EMBEDDING_CONFIG["output_dim"],
                 pooling_strategy=EMBEDDING_CONFIG["pooling_strategy"],
                 normalize=EMBEDDING_CONFIG["normalize"]):
        # Automatically determine the device to use
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        print(f"Using device: {self.device}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        self.max_length = EMBEDDING_CONFIG["max_context_length"]
        self.output_dim = output_dim
        self.pooling_strategy = pooling_strategy
        self.normalize = normalize
        
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
        if output_dim is not None and hasattr(self.model.config, "hidden_size") and output_dim != self.model.config.hidden_size:
            self.projection = torch.nn.Linear(self.model.config.hidden_size, output_dim).to(self.device)
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