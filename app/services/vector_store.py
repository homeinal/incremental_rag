"""Vector Store Service - Tier 2 of the RAG pipeline"""

import json
from typing import List, Optional
from datetime import datetime, timezone

from app.config import get_settings
from app.core.database import get_connection
from app.core.embeddings import get_embedding, embedding_to_pgvector
from app.models.schemas import KnowledgeItem, SourceType, MCPSearchResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_recency_score(created_at: datetime) -> float:
    """
    Calculate recency score based on age:
    - < 7 days: 1.0
    - < 30 days: 0.7
    - older: 0.5
    """
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    age_days = (now - created_at).days

    if age_days < 7:
        return 1.0
    elif age_days < 30:
        return 0.7
    else:
        return 0.5


class VectorStoreService:
    """Handles vector-based knowledge retrieval with time weighting"""

    def __init__(self):
        self.settings = get_settings()

    async def search(
        self,
        keywords: List[str],
        limit: Optional[int] = None,
        min_similarity: float = 0.5,  # Minimum similarity threshold
    ) -> List[KnowledgeItem]:
        """
        Search knowledge base using keyword embeddings with time-weighted scoring.
        Final score = similarity * 0.7 + recency_score * 0.3

        Returns empty list if no results meet min_similarity threshold,
        allowing fallback to MCP external search.
        """
        if not keywords:
            return []

        limit = limit or self.settings.vector_search_limit

        # Combine keywords into search text
        search_text = " ".join(keywords)
        query_embedding = await get_embedding(search_text)
        embedding_str = embedding_to_pgvector(query_embedding)

        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    content,
                    source_type,
                    source_url,
                    source_title,
                    source_author,
                    metadata,
                    created_at,
                    1 - (content_embedding <=> $1::vector) as similarity
                FROM knowledge_base
                ORDER BY similarity DESC
                LIMIT $2
                """,
                embedding_str,
                limit * 2,  # Fetch more for re-ranking
            )

        # Calculate time-weighted scores and re-rank
        items = []
        for row in rows:
            similarity = float(row["similarity"])

            # Skip results below minimum similarity threshold
            if similarity < min_similarity:
                continue

            recency = calculate_recency_score(row["created_at"])
            final_score = similarity * 0.7 + recency * 0.3

            item = KnowledgeItem(
                id=row["id"],
                content=row["content"],
                source_type=SourceType(row["source_type"]),
                source_url=row["source_url"],
                source_title=row["source_title"],
                source_author=row["source_author"],
                metadata=json.loads(row["metadata"] or "{}"),
                similarity=similarity,
                recency_score=recency,
                final_score=final_score,
                created_at=row["created_at"],
            )
            items.append(item)

        # Sort by final score and return top results
        items.sort(key=lambda x: x.final_score, reverse=True)
        results = items[:limit]

        logger.info(f"Vector search found {len(results)} results (min_sim={min_similarity}) for keywords: {keywords}")
        return results

    async def ingest(self, item: MCPSearchResult) -> int:
        """Ingest a single item into the knowledge base"""
        content_embedding = await get_embedding(item.content)
        embedding_str = embedding_to_pgvector(content_embedding)
        metadata_json = json.dumps(item.metadata)

        async with get_connection() as conn:
            knowledge_id = await conn.fetchval(
                """
                INSERT INTO knowledge_base
                    (content, content_embedding, source_type, source_url, source_title, source_author, metadata)
                VALUES ($1, $2::vector, $3, $4, $5, $6, $7::jsonb)
                RETURNING id
                """,
                item.content,
                embedding_str,
                item.source_type.value,
                item.source_url,
                item.source_title,
                item.source_author,
                metadata_json,
            )

        logger.info(f"Ingested item into knowledge base: id={knowledge_id}")
        return knowledge_id

    async def ingest_batch(self, items: List[MCPSearchResult]) -> List[int]:
        """Ingest multiple items into the knowledge base"""
        ids = []
        for item in items:
            knowledge_id = await self.ingest(item)
            ids.append(knowledge_id)
        return ids

    async def get_count(self) -> int:
        """Get total number of items in knowledge base"""
        async with get_connection() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_base")
            return count


# Global service instance
_vector_service: Optional[VectorStoreService] = None


def get_vector_service() -> VectorStoreService:
    """Get or create vector store service instance"""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorStoreService()
    return _vector_service
