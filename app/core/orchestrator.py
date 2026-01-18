"""Search Orchestrator - Main RAG Pipeline Controller"""

import time
from typing import Optional

from app.config import get_settings
from app.models.schemas import (
    SearchRequest,
    SearchResponse,
    SearchPath,
    SourceInfo,
    MCPSearchResult,
)
from app.services.semantic_cache import get_cache_service
from app.services.vector_store import get_vector_service
from app.services.mcp_client import get_mcp_service
from app.services.keyword_extractor import get_extractor_service
from app.services.llm_responder import get_responder_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SearchOrchestrator:
    """
    Orchestrates the 3-tier RAG search pipeline:
    1. Semantic Cache (≥0.95 similarity)
    2. Vector DB (time-weighted search)
    3. MCP External Search (arXiv, HuggingFace)
    """

    def __init__(self):
        self.settings = get_settings()
        self.cache = get_cache_service()
        self.vector_store = get_vector_service()
        self.mcp_client = get_mcp_service()
        self.extractor = get_extractor_service()
        self.responder = get_responder_service()

    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Execute the 3-tier search pipeline.
        """
        start_time = time.time()
        query = request.query

        # Extract keywords first (needed for logging and vector search)
        keyword_result = await self.extractor.extract(query)
        keywords = keyword_result.keywords

        # Tier 1: Semantic Cache
        logger.info(f"Tier 1: Checking semantic cache for query: {query[:50]}...")
        cached = await self.cache.search(query)
        if cached:
            elapsed_ms = (time.time() - start_time) * 1000
            return SearchResponse(
                query=query,
                response=cached.response_text,
                sources=cached.sources,
                search_path=SearchPath.CACHE,
                processing_time_ms=elapsed_ms,
                keywords=keywords,
            )

        # Tier 2: Vector DB Search
        logger.info(f"Tier 2: Searching vector DB with keywords: {keywords}")
        vector_results = await self.vector_store.search(keywords)

        if vector_results:
            # Generate response from vector results
            response_text, sources = await self.responder.generate_response(
                query=query,
                knowledge_items=vector_results,
            )

            # Store in cache for future queries
            await self.cache.store(query, response_text, sources)

            elapsed_ms = (time.time() - start_time) * 1000
            return SearchResponse(
                query=query,
                response=response_text,
                sources=sources,
                search_path=SearchPath.VECTOR_DB,
                processing_time_ms=elapsed_ms,
                keywords=keywords,
            )

        # Tier 3: MCP External Search
        logger.info(f"Tier 3: Searching external sources (arXiv, HuggingFace)")
        mcp_results = await self.mcp_client.search_all(keywords)

        if mcp_results:
            # Self-learning: ingest MCP results into vector store
            await self.vector_store.ingest_batch(mcp_results)
            logger.info(f"Self-learning: ingested {len(mcp_results)} items from MCP")

            # Generate response from MCP results
            response_text, sources = await self.responder.generate_response(
                query=query,
                mcp_results=mcp_results,
            )

            # Store in cache
            await self.cache.store(query, response_text, sources)

            elapsed_ms = (time.time() - start_time) * 1000
            return SearchResponse(
                query=query,
                response=response_text,
                sources=sources,
                search_path=SearchPath.MCP,
                processing_time_ms=elapsed_ms,
                keywords=keywords,
            )

        # No results found
        elapsed_ms = (time.time() - start_time) * 1000
        return SearchResponse(
            query=query,
            response=(
                "I couldn't find relevant information to answer your question. "
                "Try rephrasing your query or asking about a different topic."
            ),
            sources=[],
            search_path=SearchPath.NOT_FOUND,
            processing_time_ms=elapsed_ms,
            keywords=keywords,
        )


# Global orchestrator instance
_orchestrator: Optional[SearchOrchestrator] = None


def get_orchestrator() -> SearchOrchestrator:
    """Get or create orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SearchOrchestrator()
    return _orchestrator
