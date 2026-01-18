"""Tests for Vector Store Service"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone, timedelta

from app.services.vector_store import VectorStoreService, calculate_recency_score
from app.models.schemas import KnowledgeItem, MCPSearchResult, SourceType


@pytest.fixture
def vector_service():
    """Create a vector store service instance"""
    return VectorStoreService()


@pytest.fixture
def mock_embedding():
    """Mock embedding vector"""
    return [0.1] * 1536


class TestRecencyScore:
    """Tests for recency score calculation"""

    def test_recent_content(self):
        """Content < 7 days old should have score 1.0"""
        recent_date = datetime.now(timezone.utc) - timedelta(days=3)
        score = calculate_recency_score(recent_date)
        assert score == 1.0

    def test_medium_age_content(self):
        """Content 7-30 days old should have score 0.7"""
        medium_date = datetime.now(timezone.utc) - timedelta(days=15)
        score = calculate_recency_score(medium_date)
        assert score == 0.7

    def test_old_content(self):
        """Content > 30 days old should have score 0.5"""
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        score = calculate_recency_score(old_date)
        assert score == 0.5


class TestVectorStoreService:
    """Tests for VectorStoreService"""

    @pytest.mark.asyncio
    async def test_search_empty_keywords(self, vector_service):
        """Test search with empty keywords returns empty list"""
        result = await vector_service.search([])
        assert result == []

    @pytest.mark.asyncio
    async def test_search_with_keywords(self, vector_service, mock_embedding):
        """Test search returns time-weighted results"""
        with patch("app.services.vector_store.get_embedding", new_callable=AsyncMock) as mock_get_emb:
            mock_get_emb.return_value = mock_embedding

            with patch("app.services.vector_store.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetch.return_value = [
                    {
                        "id": 1,
                        "content": "Test content about LLMs",
                        "source_type": "arxiv_paper",
                        "source_url": "https://arxiv.org/abs/1234",
                        "source_title": "LLM Paper",
                        "source_author": "John Doe",
                        "metadata": "{}",
                        "created_at": datetime.now(timezone.utc) - timedelta(days=1),
                        "similarity": 0.92,
                    },
                    {
                        "id": 2,
                        "content": "Old content about neural nets",
                        "source_type": "expert_insight",
                        "source_url": None,
                        "source_title": "Expert Note",
                        "source_author": None,
                        "metadata": "{}",
                        "created_at": datetime.now(timezone.utc) - timedelta(days=45),
                        "similarity": 0.95,
                    },
                ]
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                results = await vector_service.search(["LLM", "transformer"])

                assert len(results) == 2
                # Recent content should rank higher due to recency bonus
                # Item 1: 0.92 * 0.7 + 1.0 * 0.3 = 0.944
                # Item 2: 0.95 * 0.7 + 0.5 * 0.3 = 0.815
                assert results[0].id == 1

    @pytest.mark.asyncio
    async def test_ingest_single_item(self, vector_service, mock_embedding):
        """Test ingesting a single item"""
        with patch("app.services.vector_store.get_embedding", new_callable=AsyncMock) as mock_get_emb:
            mock_get_emb.return_value = mock_embedding

            with patch("app.services.vector_store.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetchval.return_value = 123
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                item = MCPSearchResult(
                    content="Test content",
                    source_type=SourceType.ARXIV_PAPER,
                    source_title="Test Paper",
                )

                knowledge_id = await vector_service.ingest(item)

                assert knowledge_id == 123

    @pytest.mark.asyncio
    async def test_ingest_batch(self, vector_service, mock_embedding):
        """Test batch ingestion"""
        with patch("app.services.vector_store.get_embedding", new_callable=AsyncMock) as mock_get_emb:
            mock_get_emb.return_value = mock_embedding

            with patch("app.services.vector_store.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetchval.side_effect = [1, 2, 3]
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                items = [
                    MCPSearchResult(content=f"Content {i}", source_type=SourceType.ARXIV_PAPER)
                    for i in range(3)
                ]

                ids = await vector_service.ingest_batch(items)

                assert ids == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_count(self, vector_service):
        """Test getting knowledge base count"""
        with patch("app.services.vector_store.get_connection") as mock_conn_ctx:
            mock_conn = AsyncMock()
            mock_conn.fetchval.return_value = 42
            mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

            count = await vector_service.get_count()

            assert count == 42
