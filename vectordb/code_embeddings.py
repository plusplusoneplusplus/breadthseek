from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np

# Configuration parameters
EMBEDDING_CONFIG = {
    "model_name": "deepseek-ai/DeepSeek-Coder-V2-Lite-Base",  # Model to use for embeddings
    "max_context_length": 128 * 1024,  # Maximum token length for input text
    "output_dim": None,  # Output embedding dimensionality (None = use model's default)
    "pooling_strategy": "mean",  # Options: "mean", "cls", "max"
    "normalize": True,  # Whether to L2-normalize the output embeddings
}

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

# Example usage
if __name__ == "__main__":
    # Initialize the embedding model
    embedding_model = CodeEmbeddings()
    
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