import numpy as np
from sentence_transformers import SentenceTransformer
import asyncio
from typing import List, Union
from src.utils.logger import get_logger

logger = get_logger(__name__)

class EmbeddingEngine:
    """Local embedding engine using sentence-transformers (zero API cost)"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingEngine, cls).__new__(cls)
            cls._instance.model_name = "sentence-transformers/all-MiniLM-L6-v2"
            cls._instance.model = None
            cls._instance.dimension = 384
        return cls._instance
    
    def load(self) -> None:
        """Load the model synchronously. Should be called on app startup."""
        if self.model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            # Loading model. By default uses GPU if available, else CPU.
            self.model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully")

    def _normalize_text(self, text: str) -> str:
        """Basic normalization to improve match consistency"""
        return text.strip().lower()

    async def embed(self, text: str) -> np.ndarray:
        """
        Embed a single text string asynchronously.
        Returns a 1D numpy array of float32, L2-normalized.
        """
        if self.model is None:
            self.load()
            
        normalized_text = self._normalize_text(text)
        
        # Run in a threadpool to not block the async event loop
        vector = await asyncio.to_thread(self.model.encode, normalized_text, normalize_embeddings=True)
        return vector

    async def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Embed a list of text strings asynchronously.
        Returns a 2D numpy array of float32, L2-normalized.
        """
        if self.model is None:
            self.load()
            
        normalized_texts = [self._normalize_text(t) for t in texts]
        
        vectors = await asyncio.to_thread(self.model.encode, normalized_texts, normalize_embeddings=True)
        return vectors

# Global instance
embedding_engine = EmbeddingEngine()