"""Semantic Cache Service - Tier 1 of the RAG pipeline"""

import json
from typing import Optional, List
from datetime import datetime

from app.config import get_settings
from app.core.database import get_connection
from app.core.embeddings import get_embedding, embedding_to_pgvector
from app.models.schemas import CacheEntry, SourceInfo, SearchResponse, SearchPath
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SemanticCacheService:
    """Handles semantic caching of query-response pairs"""

    def __init__(self):
        self.settings = get_settings()

    async def search(self, query: str) -> Optional[CacheEntry]:
        """
        Search cache for semantically similar query.
        Returns cached entry if similarity >= threshold.
        """
        query_embedding = await get_embedding(query)
        embedding_str = embedding_to_pgvector(query_embedding)

        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    id,
                    query_text,
                    response_text,
                    sources,
                    hit_count,
                    created_at,
                    1 - (query_embedding <=> $1::vector) as similarity
                FROM semantic_cache
                WHERE 1 - (query_embedding <=> $1::vector) >= $2
                ORDER BY similarity DESC
                LIMIT 1
                """,
                embedding_str,
                self.settings.cache_similarity_threshold,
            )

            if row:
                # Increment hit count
                await conn.execute(
                    "UPDATE semantic_cache SET hit_count = hit_count + 1 WHERE id = $1",
                    row["id"],
                )

                sources = [SourceInfo(**s) for s in json.loads(row["sources"] or "[]")]
                entry = CacheEntry(
                    id=row["id"],
                    query_text=row["query_text"],
                    response_text=row["response_text"],
                    sources=sources,
                    hit_count=row["hit_count"] + 1,
                    similarity=float(row["similarity"]),
                    created_at=row["created_at"],
                )
                logger.info(f"Cache hit: similarity={entry.similarity:.4f}")
                return entry

        logger.debug("Cache miss")
        return None

    async def store(
        self,
        query: str,
        response: str,
        sources: List[SourceInfo],
    ) -> int:
        """Store a query-response pair in cache"""
        query_embedding = await get_embedding(query)
        embedding_str = embedding_to_pgvector(query_embedding)
        sources_json = json.dumps([s.model_dump() for s in sources])

        async with get_connection() as conn:
            cache_id = await conn.fetchval(
                """
                INSERT INTO semantic_cache (query_text, query_embedding, response_text, sources)
                VALUES ($1, $2::vector, $3, $4::jsonb)
                RETURNING id
                """,
                query,
                embedding_str,
                response,
                sources_json,
            )

        logger.info(f"Stored response in cache: id={cache_id}")
        return cache_id

    async def get_stats(self) -> dict:
        """Get cache statistics"""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_entries,
                    COALESCE(SUM(hit_count), 0) as total_hits,
                    COALESCE(AVG(hit_count), 0) as avg_hits
                FROM semantic_cache
                """
            )

            return {
                "total_entries": row["total_entries"],
                "total_hits": row["total_hits"],
                "avg_hits_per_entry": float(row["avg_hits"]),
            }

    async def clear(self) -> int:
        """Clear all cache entries (admin operation)"""
        async with get_connection() as conn:
            result = await conn.execute("DELETE FROM semantic_cache")
            count = int(result.split()[-1])
            logger.warning(f"Cache cleared: {count} entries deleted")
            return count


# Global service instance
_cache_service: Optional[SemanticCacheService] = None


def get_cache_service() -> SemanticCacheService:
    """Get or create cache service instance"""
    global _cache_service
    if _cache_service is None:
        _cache_service = SemanticCacheService()
    return _cache_service
