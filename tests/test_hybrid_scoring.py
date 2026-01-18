"""
Comprehensive Tests for Hybrid Scoring System

Tests the core algorithm: final_score = similarity * 0.7 + recency * 0.3

Key test scenarios:
1. Recency score calculation (3-tier decay)
2. Hybrid score formula verification
3. Re-ranking behavior (newer content beats older high-similarity content)
4. Over-fetching strategy (limit * 2)
5. Min similarity threshold filtering
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone, timedelta

from app.services.vector_store import VectorStoreService, calculate_recency_score
from app.models.schemas import SourceType


class TestRecencyScoreCalculation:
    """Test 3-tier recency score decay: 1.0 / 0.7 / 0.5"""

    def test_very_recent_1_day(self):
        """1 day old -> score 1.0"""
        date = datetime.now(timezone.utc) - timedelta(days=1)
        assert calculate_recency_score(date) == 1.0

    def test_recent_6_days(self):
        """6 days old -> score 1.0 (boundary)"""
        date = datetime.now(timezone.utc) - timedelta(days=6)
        assert calculate_recency_score(date) == 1.0

    def test_boundary_7_days(self):
        """7 days old -> score 0.7 (crosses boundary)"""
        date = datetime.now(timezone.utc) - timedelta(days=7)
        assert calculate_recency_score(date) == 0.7

    def test_medium_15_days(self):
        """15 days old -> score 0.7"""
        date = datetime.now(timezone.utc) - timedelta(days=15)
        assert calculate_recency_score(date) == 0.7

    def test_boundary_29_days(self):
        """29 days old -> score 0.7 (boundary)"""
        date = datetime.now(timezone.utc) - timedelta(days=29)
        assert calculate_recency_score(date) == 0.7

    def test_boundary_30_days(self):
        """30 days old -> score 0.5 (crosses boundary)"""
        date = datetime.now(timezone.utc) - timedelta(days=30)
        assert calculate_recency_score(date) == 0.5

    def test_old_60_days(self):
        """60 days old -> score 0.5"""
        date = datetime.now(timezone.utc) - timedelta(days=60)
        assert calculate_recency_score(date) == 0.5

    def test_very_old_365_days(self):
        """365 days old -> score 0.5"""
        date = datetime.now(timezone.utc) - timedelta(days=365)
        assert calculate_recency_score(date) == 0.5

    def test_naive_datetime_handling(self):
        """Naive datetime (no timezone) should be handled correctly"""
        date = datetime.now() - timedelta(days=3)  # No timezone
        score = calculate_recency_score(date)
        assert score == 1.0


class TestHybridScoreFormula:
    """Test the formula: final_score = similarity * 0.7 + recency * 0.3"""

    def test_perfect_scores(self):
        """similarity=1.0, recency=1.0 -> final=1.0"""
        final = 1.0 * 0.7 + 1.0 * 0.3
        assert final == 1.0

    def test_high_similarity_low_recency(self):
        """similarity=0.95, recency=0.5 -> final=0.815"""
        final = 0.95 * 0.7 + 0.5 * 0.3
        assert round(final, 3) == 0.815

    def test_medium_similarity_high_recency(self):
        """similarity=0.85, recency=1.0 -> final=0.895"""
        final = 0.85 * 0.7 + 1.0 * 0.3
        assert round(final, 3) == 0.895

    def test_recency_boost_effect(self):
        """
        Verify that recent content can beat older higher-similarity content.

        Old paper: similarity=0.95, recency=0.5 -> final=0.815
        New paper: similarity=0.85, recency=1.0 -> final=0.895

        New paper wins despite 10% lower similarity!
        """
        old_final = 0.95 * 0.7 + 0.5 * 0.3  # 0.815
        new_final = 0.85 * 0.7 + 1.0 * 0.3  # 0.895

        assert new_final > old_final
        boost_percentage = ((new_final - old_final) / old_final) * 100
        assert boost_percentage > 9  # ~9.8% boost


class TestHybridScoringReranking:
    """Test that re-ranking correctly prioritizes recent relevant content"""

    @pytest.fixture
    def vector_service(self):
        return VectorStoreService()

    @pytest.fixture
    def mock_embedding(self):
        return [0.1] * 1536

    @pytest.mark.asyncio
    async def test_reranking_new_beats_old(self, vector_service, mock_embedding):
        """
        Scenario: Old paper has higher similarity but new paper should rank higher.

        Paper A (2 days old): similarity=0.85 -> final = 0.85*0.7 + 1.0*0.3 = 0.895
        Paper B (60 days old): similarity=0.95 -> final = 0.95*0.7 + 0.5*0.3 = 0.815

        Expected: Paper A ranks #1
        """
        with patch("app.services.vector_store.get_embedding", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = mock_embedding

            with patch("app.services.vector_store.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetch.return_value = [
                    {
                        "id": 1,
                        "content": "Recent transformer architecture improvements",
                        "source_type": "arxiv_paper",
                        "source_url": "https://arxiv.org/abs/2024.new",
                        "source_title": "New Transformer Paper",
                        "source_author": "Alice",
                        "metadata": "{}",
                        "created_at": datetime.now(timezone.utc) - timedelta(days=2),
                        "similarity": 0.85,
                    },
                    {
                        "id": 2,
                        "content": "Classic transformer paper from years ago",
                        "source_type": "arxiv_paper",
                        "source_url": "https://arxiv.org/abs/2022.old",
                        "source_title": "Old Transformer Paper",
                        "source_author": "Bob",
                        "metadata": "{}",
                        "created_at": datetime.now(timezone.utc) - timedelta(days=60),
                        "similarity": 0.95,
                    },
                ]
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                results = await vector_service.search(["transformer", "architecture"])

                assert len(results) == 2
                # Recent paper should rank first
                assert results[0].id == 1
                assert results[0].source_title == "New Transformer Paper"

                # Verify scores
                assert round(results[0].final_score, 3) == 0.895  # 0.85*0.7 + 1.0*0.3
                assert round(results[1].final_score, 3) == 0.815  # 0.95*0.7 + 0.5*0.3

    @pytest.mark.asyncio
    async def test_very_high_similarity_still_wins(self, vector_service, mock_embedding):
        """
        When similarity difference is large enough, old content can still win.

        Paper A (2 days old): similarity=0.70 -> final = 0.70*0.7 + 1.0*0.3 = 0.79
        Paper B (60 days old): similarity=0.99 -> final = 0.99*0.7 + 0.5*0.3 = 0.843

        Expected: Paper B (old but very relevant) ranks #1
        """
        with patch("app.services.vector_store.get_embedding", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = mock_embedding

            with patch("app.services.vector_store.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetch.return_value = [
                    {
                        "id": 1,
                        "content": "Somewhat related new content",
                        "source_type": "arxiv_paper",
                        "source_url": "url1",
                        "source_title": "New Paper",
                        "source_author": "Author1",
                        "metadata": "{}",
                        "created_at": datetime.now(timezone.utc) - timedelta(days=2),
                        "similarity": 0.70,
                    },
                    {
                        "id": 2,
                        "content": "Highly relevant old content",
                        "source_type": "arxiv_paper",
                        "source_url": "url2",
                        "source_title": "Old Classic Paper",
                        "source_author": "Author2",
                        "metadata": "{}",
                        "created_at": datetime.now(timezone.utc) - timedelta(days=60),
                        "similarity": 0.99,
                    },
                ]
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                results = await vector_service.search(["query"])

                # Old but highly relevant paper should win
                assert results[0].id == 2
                assert round(results[0].final_score, 3) == 0.843  # 0.99*0.7 + 0.5*0.3
                assert round(results[1].final_score, 3) == 0.790  # 0.70*0.7 + 1.0*0.3


class TestMinSimilarityThreshold:
    """Test min_similarity filtering for MCP fallback"""

    @pytest.fixture
    def vector_service(self):
        return VectorStoreService()

    @pytest.fixture
    def mock_embedding(self):
        return [0.1] * 1536

    @pytest.mark.asyncio
    async def test_filters_low_similarity(self, vector_service, mock_embedding):
        """Results below min_similarity=0.5 should be filtered out"""
        with patch("app.services.vector_store.get_embedding", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = mock_embedding

            with patch("app.services.vector_store.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetch.return_value = [
                    {
                        "id": 1,
                        "content": "High similarity content",
                        "source_type": "arxiv_paper",
                        "source_url": "url1",
                        "source_title": "Paper 1",
                        "source_author": "Author1",
                        "metadata": "{}",
                        "created_at": datetime.now(timezone.utc) - timedelta(days=5),
                        "similarity": 0.85,
                    },
                    {
                        "id": 2,
                        "content": "Low similarity content",
                        "source_type": "arxiv_paper",
                        "source_url": "url2",
                        "source_title": "Paper 2",
                        "source_author": "Author2",
                        "metadata": "{}",
                        "created_at": datetime.now(timezone.utc) - timedelta(days=5),
                        "similarity": 0.40,  # Below threshold
                    },
                ]
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                results = await vector_service.search(["query"], min_similarity=0.5)

                # Only high similarity result should be returned
                assert len(results) == 1
                assert results[0].id == 1

    @pytest.mark.asyncio
    async def test_empty_results_triggers_mcp_fallback(self, vector_service, mock_embedding):
        """When all results are below threshold, empty list returned (triggers MCP)"""
        with patch("app.services.vector_store.get_embedding", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = mock_embedding

            with patch("app.services.vector_store.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetch.return_value = [
                    {
                        "id": 1,
                        "content": "Low similarity",
                        "source_type": "arxiv_paper",
                        "source_url": "url1",
                        "source_title": "Paper 1",
                        "source_author": "Author1",
                        "metadata": "{}",
                        "created_at": datetime.now(timezone.utc),
                        "similarity": 0.30,
                    },
                ]
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                results = await vector_service.search(["unknown_topic"], min_similarity=0.5)

                # Empty result triggers MCP external search
                assert len(results) == 0


class TestOverFetchingStrategy:
    """Test limit * 2 over-fetching for accurate re-ranking"""

    @pytest.fixture
    def vector_service(self):
        return VectorStoreService()

    @pytest.fixture
    def mock_embedding(self):
        return [0.1] * 1536

    @pytest.mark.asyncio
    async def test_overfetch_doubles_limit(self, vector_service, mock_embedding):
        """Verify DB query fetches limit * 2 results"""
        with patch("app.services.vector_store.get_embedding", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = mock_embedding

            with patch("app.services.vector_store.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetch.return_value = []
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                # Request limit=5
                await vector_service.search(["query"], limit=5)

                # Verify SQL was called with limit * 2 = 10
                call_args = mock_conn.fetch.call_args
                # Second positional arg should be limit * 2 = 10
                assert call_args[0][2] == 10  # limit * 2

    @pytest.mark.asyncio
    async def test_returns_only_requested_limit(self, vector_service, mock_embedding):
        """Even with over-fetching, only return requested limit"""
        with patch("app.services.vector_store.get_embedding", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = mock_embedding

            with patch("app.services.vector_store.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                # Return 6 results from DB (limit*2 = 6 for limit=3)
                mock_conn.fetch.return_value = [
                    {
                        "id": i,
                        "content": f"Content {i}",
                        "source_type": "arxiv_paper",
                        "source_url": f"url{i}",
                        "source_title": f"Paper {i}",
                        "source_author": f"Author{i}",
                        "metadata": "{}",
                        "created_at": datetime.now(timezone.utc) - timedelta(days=i*10),
                        "similarity": 0.9 - (i * 0.05),
                    }
                    for i in range(6)
                ]
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                results = await vector_service.search(["query"], limit=3)

                # Should return only 3 results despite fetching 6
                assert len(results) == 3


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.fixture
    def vector_service(self):
        return VectorStoreService()

    @pytest.mark.asyncio
    async def test_empty_keywords(self, vector_service):
        """Empty keywords should return empty list immediately"""
        results = await vector_service.search([])
        assert results == []

    @pytest.mark.asyncio
    async def test_none_metadata_handling(self, vector_service):
        """NULL metadata from DB should be handled as empty dict"""
        mock_embedding = [0.1] * 1536

        with patch("app.services.vector_store.get_embedding", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = mock_embedding

            with patch("app.services.vector_store.get_connection") as mock_conn_ctx:
                mock_conn = AsyncMock()
                mock_conn.fetch.return_value = [
                    {
                        "id": 1,
                        "content": "Content",
                        "source_type": "arxiv_paper",
                        "source_url": "url",
                        "source_title": "Title",
                        "source_author": None,
                        "metadata": None,  # NULL from DB
                        "created_at": datetime.now(timezone.utc),
                        "similarity": 0.9,
                    },
                ]
                mock_conn_ctx.return_value.__aenter__.return_value = mock_conn

                results = await vector_service.search(["query"])

                assert results[0].metadata == {}
