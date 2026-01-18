"""Pydantic models for API I/O"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Types of knowledge sources"""
    EXPERT_INSIGHT = "expert_insight"
    ARXIV_PAPER = "arxiv_paper"
    HUGGINGFACE = "huggingface"
    MANUAL = "manual"


class SearchPath(str, Enum):
    """Search path indicator"""
    CACHE = "cache"
    VECTOR_DB = "vector_db"
    MCP = "mcp"
    NOT_FOUND = "not_found"


# Request Models
class SearchRequest(BaseModel):
    """Search query request"""
    query: str = Field(..., min_length=1, max_length=1000)


class IngestRequest(BaseModel):
    """Manual data ingestion request"""
    content: str = Field(..., min_length=1)
    source_type: SourceType = SourceType.MANUAL
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    source_author: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Response Models
class SourceInfo(BaseModel):
    """Information about a knowledge source"""
    source_type: SourceType
    title: Optional[str] = None
    url: Optional[str] = None
    author: Optional[str] = None
    relevance_score: float = 0.0


class KeywordResult(BaseModel):
    """Extracted keywords from query"""
    keywords: List[str]
    source_type_hint: Optional[SourceType] = None


class SearchResponse(BaseModel):
    """Search result response"""
    query: str
    response: str
    sources: List[SourceInfo] = Field(default_factory=list)
    search_path: SearchPath
    processing_time_ms: float
    keywords: List[str] = Field(default_factory=list)


class StatusResponse(BaseModel):
    """System status response"""
    status: str
    database_connected: bool
    cache_entries: int
    knowledge_entries: int
    cache_hit_rate: Optional[float] = None


class IngestResponse(BaseModel):
    """Ingestion result response"""
    success: bool
    message: str
    knowledge_id: Optional[int] = None


# Internal Models
class CacheEntry(BaseModel):
    """Semantic cache entry"""
    id: int
    query_text: str
    response_text: str
    sources: List[SourceInfo] = Field(default_factory=list)
    hit_count: int = 0
    similarity: float = 0.0
    created_at: datetime


class KnowledgeItem(BaseModel):
    """Knowledge base item"""
    id: int
    content: str
    source_type: SourceType
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    source_author: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    similarity: float = 0.0
    recency_score: float = 0.0
    final_score: float = 0.0
    created_at: datetime


class MCPSearchResult(BaseModel):
    """Result from MCP external search"""
    content: str
    source_type: SourceType
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    source_author: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
