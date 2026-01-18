"""Tests for Semantic Cache Service"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.semantic_cache import SemanticCacheService
from app.models.schemas import CacheEntry, SourceInfo, SourceType


@pytest.fixture
def cache_service():
    """Create a cache service instance"""
    return SemanticCacheService()


@pytest.fixture
def mock_embedding():
    """Mock embedding vector"""
    return [0.1] * 1536


@pytest.fixture
def sample_cache_entry():
    """Sample cache entry for testing"""
    return CacheEntry(
        id=1,
        query_text="What is RAG?",
        response_text="RAG stands for Retrieval-Augmented Generation...",
        sources=[
            SourceInfo(
                source_type=SourceType.ARXIV_PAPER,
                title="RAG Paper",
                url="https://arxiv.org/abs/1234.5678",
                relevance_score=0.95,
            )
        ],
        hit_count=5,
        similarity=0.98,
        created_at=datetime.now(),
    )


class TestSemanticCacheService:
    """Tests for SemanticCacheService"""

    @pytest.mark.asyncio
    async def test_search_cache_miss(self, cache_service, mock_embedding):
        """Test cache miss returns None"""
        with patch("app.services.semantic_cache.get_embedding", new_callable=AsyncMock) as mock_get_emb:
            mock_get_emb.return_value = mock_embedding

            with patch("app.services.semantic_cache.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetchrow.return_value = None
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                result = await cache_service.search("test query")

                assert result is None
                mock_get_emb.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_search_cache_hit(self, cache_service, mock_embedding, sample_cache_entry):
        """Test cache hit returns entry and increments hit count"""
        with patch("app.services.semantic_cache.get_embedding", new_callable=AsyncMock) as mock_get_emb:
            mock_get_emb.return_value = mock_embedding

            with patch("app.services.semantic_cache.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetchrow.return_value = {
                    "id": 1,
                    "query_text": "What is RAG?",
                    "response_text": "RAG stands for...",
                    "sources": '[{"source_type": "arxiv_paper", "title": "RAG Paper"}]',
                    "hit_count": 5,
                    "similarity": 0.98,
                    "created_at": datetime.now(),
                }
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                result = await cache_service.search("What is RAG?")

                assert result is not None
                assert result.similarity >= 0.95
                # Verify hit count was incremented
                mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_entry(self, cache_service, mock_embedding):
        """Test storing a new cache entry"""
        with patch("app.services.semantic_cache.get_embedding", new_callable=AsyncMock) as mock_get_emb:
            mock_get_emb.return_value = mock_embedding

            with patch("app.services.semantic_cache.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetchval.return_value = 42
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                sources = [SourceInfo(source_type=SourceType.EXPERT_INSIGHT, title="Test")]
                cache_id = await cache_service.store(
                    query="test query",
                    response="test response",
                    sources=sources,
                )

                assert cache_id == 42

    @pytest.mark.asyncio
    async def test_get_stats(self, cache_service):
        """Test getting cache statistics"""
        with patch("app.services.semantic_cache.get_connection") as mock_conn_ctx:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = {
                "total_entries": 100,
                "total_hits": 500,
                "avg_hits": 5.0,
            }
            mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

            stats = await cache_service.get_stats()

            assert stats["total_entries"] == 100
            assert stats["total_hits"] == 500
            assert stats["avg_hits_per_entry"] == 5.0

    @pytest.mark.asyncio
    async def test_clear_cache(self, cache_service):
        """Test clearing the cache"""
        with patch("app.services.semantic_cache.get_connection") as mock_conn_ctx:
            mock_conn = AsyncMock()
            mock_conn.execute.return_value = "DELETE 50"
            mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

            count = await cache_service.clear()

            assert count == 50
