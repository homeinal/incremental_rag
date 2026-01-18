-- GuRag Database Schema
-- Requires PostgreSQL with pgvector extension

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Semantic Cache Table
-- Stores query-response pairs for exact/near-exact query matching
CREATE TABLE IF NOT EXISTS semantic_cache (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_embedding vector(1536) NOT NULL,
    response_text TEXT NOT NULL,
    sources JSONB DEFAULT '[]',
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Knowledge Base Table
-- Stores AI expert insights and research content for vector search
CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    content_embedding vector(1536) NOT NULL,
    source_type VARCHAR(50) NOT NULL,  -- 'expert_insight', 'arxiv_paper', 'huggingface', 'manual'
    source_url TEXT,
    source_title TEXT,
    source_author TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for fast similarity search
CREATE INDEX IF NOT EXISTS idx_cache_embedding ON semantic_cache
    USING ivfflat (query_embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_knowledge_embedding ON knowledge_base
    USING ivfflat (content_embedding vector_cosine_ops) WITH (lists = 100);

-- Create index for source_type filtering
CREATE INDEX IF NOT EXISTS idx_knowledge_source_type ON knowledge_base(source_type);

-- Create index for timestamp-based queries
CREATE INDEX IF NOT EXISTS idx_knowledge_created_at ON knowledge_base(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cache_created_at ON semantic_cache(created_at DESC);

-- Function to update timestamp on cache update
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS update_semantic_cache_updated_at ON semantic_cache;
CREATE TRIGGER update_semantic_cache_updated_at
    BEFORE UPDATE ON semantic_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Sample query to test similarity search (for reference)
-- SELECT id, query_text, 1 - (query_embedding <=> '[...]'::vector) as similarity
-- FROM semantic_cache
-- WHERE 1 - (query_embedding <=> '[...]'::vector) >= 0.95
-- ORDER BY similarity DESC
-- LIMIT 1;
