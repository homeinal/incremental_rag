# GuRag - 3-Tier RAG System

A Retrieval-Augmented Generation (RAG) system connecting AI expert insights with academic research via semantic cache, vector search, and external MCP search.

## Architecture

```
User Query → Keyword Extraction → 3-Tier Search Pipeline → LLM Response
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
              Semantic Cache      Vector DB           MCP Search
              (≥0.95 sim)      (time-weighted)     (arXiv/HuggingFace)
```

### Search Tiers

1. **Semantic Cache** - Exact/near-exact query matching (≥95% similarity)
2. **Vector DB** - Time-weighted semantic search with recency scoring
3. **MCP External Search** - arXiv papers and HuggingFace models

### Self-Learning

When MCP search returns results, they are automatically ingested into the Vector DB for future searches, enabling the system to learn and improve over time.

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL with pgvector extension (e.g., Neon)
- OpenAI API key

### Installation

```bash
# Clone and setup
cd gurag
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL and OPENAI_API_KEY
```

### Database Setup

```bash
# Initialize database schema
psql $DATABASE_URL -f scripts/init_db.sql

# Or via API after starting the server
curl -X POST http://localhost:8000/admin/init-db
```

### Running

```bash
# Start FastAPI backend
uvicorn app.main:app --reload --port 8000

# In another terminal, start Gradio UI
python -m app.gradio_app
```

Access:
- FastAPI: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Gradio UI: http://localhost:7860

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | POST | Main search endpoint |
| `/ingest` | POST | Manual data ingestion |
| `/status` | GET | Health check + cache stats |
| `/admin/cache` | DELETE | Clear semantic cache |
| `/admin/init-db` | POST | Initialize database schema |

### Search Example

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the latest trends in large language models?"}'
```

### Ingest Example

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Expert insight about transformer architectures...",
    "source_type": "expert_insight",
    "source_title": "My Expert Note",
    "source_author": "John Doe"
  }'
```

## Configuration

Environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `EMBEDDING_MODEL` | Embedding model name | text-embedding-3-small |
| `LLM_MODEL` | LLM model for responses | gpt-4o-mini |
| `CACHE_SIMILARITY_THRESHOLD` | Cache hit threshold | 0.95 |
| `VECTOR_SEARCH_LIMIT` | Max vector search results | 10 |

## Time-Weighted Scoring

Vector search uses time-weighted scoring:
```
final_score = similarity * 0.7 + recency_score * 0.3

recency_score:
  - < 7 days: 1.0
  - < 30 days: 0.7
  - older: 0.5
```

## Project Structure

```
gurag/
├── app/
│   ├── main.py              # FastAPI application
│   ├── gradio_app.py        # Gradio UI
│   ├── config.py            # Configuration
│   ├── core/
│   │   ├── database.py      # Async DB pool
│   │   ├── embeddings.py    # OpenAI embeddings
│   │   └── orchestrator.py  # Search pipeline
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   ├── services/
│   │   ├── semantic_cache.py
│   │   ├── vector_store.py
│   │   ├── mcp_client.py
│   │   ├── keyword_extractor.py
│   │   └── llm_responder.py
│   └── utils/
│       └── logger.py
├── scripts/
│   └── init_db.sql          # Database schema
├── tests/
├── requirements.txt
├── Dockerfile
├── render.yaml
└── README.md
```

## Deployment

### Render

1. Connect your repository to Render
2. Set environment variables in Render dashboard
3. Deploy using `render.yaml`

### Docker

```bash
docker build -t gurag .
docker run -p 8000:8000 --env-file .env gurag
```

## Testing

```bash
# Run tests
pytest tests/

# Test the full pipeline
# 1. First query hits MCP (empty cache/vector DB)
curl -X POST http://localhost:8000/search -d '{"query": "LLM trends 2025"}'

# 2. Same query hits cache
curl -X POST http://localhost:8000/search -d '{"query": "LLM trends 2025"}'

# 3. Similar query hits vector DB
curl -X POST http://localhost:8000/search -d '{"query": "Latest LLM developments 2025"}'
```

## License

MIT
