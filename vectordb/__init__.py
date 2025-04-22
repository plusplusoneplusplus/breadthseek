"""BreadthSeek Vector Database Package

This package provides tools for generating and storing code embeddings.
"""

from .code_embeddings import (
    CodeEmbeddings,
    EMBEDDING_CONFIG,
    EMBEDDING_CONFIG_QWEN25_CODER_7B,
    EMBEDDING_CONFIG_DEEPSEEK_CODER_V2_LITE_BASE,
    EMBEDDING_CONFIG_PHI4,
)

__version__ = "0.1.0"
__all__ = [
    "CodeEmbeddings",
    "EMBEDDING_CONFIG",
    "EMBEDDING_CONFIG_QWEN25_CODER_7B",
    "EMBEDDING_CONFIG_DEEPSEEK_CODER_V2_LITE_BASE",
    "EMBEDDING_CONFIG_PHI4",
] 