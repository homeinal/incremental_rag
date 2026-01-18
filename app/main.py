"""FastAPI Backend Application"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.core.database import DatabasePool, init_db, health_check
from app.core.orchestrator import get_orchestrator
from app.models.schemas import (
    SearchRequest,
    SearchResponse,
    IngestRequest,
    IngestResponse,
    StatusResponse,
    MCPSearchResult,
)
from app.services.semantic_cache import get_cache_service
from app.services.vector_store import get_vector_service
from app.services.mcp_client import get_mcp_service
from app.utils.logger import get_logger, configure_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("Starting GuRag API server...")

    # Initialize database connection pool
    await DatabasePool.get_pool()
    logger.info("Database connection pool initialized")

    yield

    # Cleanup
    logger.info("Shutting down...")
    await DatabasePool.close_pool()
    mcp_service = get_mcp_service()
    await mcp_service.close()


app = FastAPI(
    title="GuRag API",
    description="3-Tier RAG System connecting AI expert insights with academic research",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for Gradio UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Redirect to API documentation"""
    return RedirectResponse(url="/docs")


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Main search endpoint.
    Executes the 3-tier RAG pipeline: Cache → Vector DB → MCP
    """
    try:
        orchestrator = get_orchestrator()
        response = await orchestrator.search(request)
        return response
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest) -> IngestResponse:
    """
    Manual data ingestion endpoint.
    Adds content directly to the knowledge base.
    """
    try:
        vector_service = get_vector_service()

        item = MCPSearchResult(
            content=request.content,
            source_type=request.source_type,
            source_url=request.source_url,
            source_title=request.source_title,
            source_author=request.source_author,
            metadata=request.metadata,
        )

        knowledge_id = await vector_service.ingest(item)

        return IngestResponse(
            success=True,
            message="Content ingested successfully",
            knowledge_id=knowledge_id,
        )
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    """
    Health check and system status endpoint.
    Returns database connectivity and cache statistics.
    """
    try:
        db_connected = await health_check()
        cache_service = get_cache_service()
        vector_service = get_vector_service()

        cache_stats = await cache_service.get_stats()
        knowledge_count = await vector_service.get_count()

        # Calculate cache hit rate
        total_queries = cache_stats["total_entries"]
        total_hits = cache_stats["total_hits"]
        hit_rate = total_hits / max(total_queries, 1) if total_queries > 0 else None

        return StatusResponse(
            status="healthy" if db_connected else "degraded",
            database_connected=db_connected,
            cache_entries=cache_stats["total_entries"],
            knowledge_entries=knowledge_count,
            cache_hit_rate=hit_rate,
        )
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return StatusResponse(
            status="error",
            database_connected=False,
            cache_entries=0,
            knowledge_entries=0,
        )


@app.delete("/admin/cache")
async def clear_cache():
    """
    Admin endpoint to clear the semantic cache.
    Use with caution in production.
    """
    try:
        cache_service = get_cache_service()
        deleted_count = await cache_service.clear()
        return {"message": f"Cache cleared: {deleted_count} entries deleted"}
    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/init-db")
async def initialize_database():
    """
    Admin endpoint to initialize database schema.
    Creates tables if they don't exist.
    """
    try:
        await init_db()
        return {"message": "Database schema initialized successfully"}
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
