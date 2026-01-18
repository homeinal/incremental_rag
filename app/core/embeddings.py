"""OpenAI embedding utilities"""

from typing import List
import numpy as np
from openai import AsyncOpenAI

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Get or create OpenAI client"""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def get_embedding(text: str) -> List[float]:
    """Generate embedding for a single text"""
    settings = get_settings()
    client = get_openai_client()

    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )

    embedding = response.data[0].embedding
    logger.debug(f"Generated embedding for text (length={len(text)})")
    return embedding


async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts"""
    if not texts:
        return []

    settings = get_settings()
    client = get_openai_client()

    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )

    embeddings = [item.embedding for item in response.data]
    logger.debug(f"Generated {len(embeddings)} embeddings")
    return embeddings


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def embedding_to_pgvector(embedding: List[float]) -> str:
    """Convert embedding list to pgvector string format"""
    return "[" + ",".join(str(x) for x in embedding) + "]"
