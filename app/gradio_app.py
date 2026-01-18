"""Standalone Gradio UI Application"""

import gradio as gr
import httpx
from typing import Tuple

from app.config import get_settings

settings = get_settings()
API_BASE_URL = f"http://localhost:{settings.api_port}"


def format_sources(sources: list) -> str:
    """Format sources for display"""
    if not sources:
        return "No sources"

    formatted = []
    for i, source in enumerate(sources, 1):
        title = source.get("title") or "Untitled"
        url = source.get("url")
        source_type = source.get("source_type", "unknown")
        author = source.get("author")
        relevance = source.get("relevance_score", 0)

        parts = [f"**{i}. {title}**"]
        parts.append(f"   - Type: {source_type}")
        if author:
            parts.append(f"   - Author: {author}")
        if url:
            parts.append(f"   - URL: [{url}]({url})")
        if relevance > 0:
            parts.append(f"   - Relevance: {relevance:.2%}")

        formatted.append("\n".join(parts))

    return "\n\n".join(formatted)


def search(query: str) -> Tuple[str, str, str, str]:
    """
    Execute search via FastAPI backend.
    Returns (response, sources, search_path, processing_time)
    """
    if not query.strip():
        return "Please enter a query.", "", "", ""

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{API_BASE_URL}/search",
                json={"query": query},
            )
            response.raise_for_status()
            data = response.json()

        # Extract response components
        answer = data.get("response", "No response")
        sources = format_sources(data.get("sources", []))
        search_path = data.get("search_path", "unknown").upper()
        processing_time = f"{data.get('processing_time_ms', 0):.1f}ms"
        keywords = ", ".join(data.get("keywords", []))

        # Format search path indicator
        path_emoji = {
            "CACHE": "⚡ Cache Hit",
            "VECTOR_DB": "🔍 Vector DB",
            "MCP": "🌐 External Search",
            "NOT_FOUND": "❓ Not Found",
        }.get(search_path, search_path)

        info_line = f"**Search Path:** {path_emoji} | **Time:** {processing_time} | **Keywords:** {keywords}"

        return answer, sources, info_line, ""

    except httpx.ConnectError:
        return (
            "❌ Cannot connect to API server. Please ensure the FastAPI server is running on port 8000.",
            "",
            "",
            "Connection Error",
        )
    except httpx.HTTPStatusError as e:
        return f"❌ API Error: {e.response.status_code}", "", "", str(e)
    except Exception as e:
        return f"❌ Error: {str(e)}", "", "", str(e)


def get_status() -> str:
    """Get system status from API"""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{API_BASE_URL}/status")
            response.raise_for_status()
            data = response.json()

        status_parts = [
            f"**Status:** {data.get('status', 'unknown').upper()}",
            f"**Database:** {'✅ Connected' if data.get('database_connected') else '❌ Disconnected'}",
            f"**Cache Entries:** {data.get('cache_entries', 0)}",
            f"**Knowledge Base Entries:** {data.get('knowledge_entries', 0)}",
        ]

        hit_rate = data.get("cache_hit_rate")
        if hit_rate is not None:
            status_parts.append(f"**Cache Hit Rate:** {hit_rate:.1%}")

        return "\n".join(status_parts)

    except httpx.ConnectError:
        return "❌ Cannot connect to API server"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def clear_cache() -> str:
    """Clear the semantic cache"""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.delete(f"{API_BASE_URL}/admin/cache")
            response.raise_for_status()
            data = response.json()
            return f"✅ {data.get('message', 'Cache cleared')}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


# Build Gradio Interface
with gr.Blocks(title="GuRag - AI Research Assistant", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # 🔬 GuRag - AI Research Assistant

        A 3-tier RAG system connecting AI expert insights with academic research.

        **Search Pipeline:** Semantic Cache → Vector DB → External Search (arXiv, HuggingFace)
        """
    )

    with gr.Row():
        with gr.Column(scale=3):
            query_input = gr.Textbox(
                label="Your Question",
                placeholder="Ask about AI, machine learning, LLMs, research papers...",
                lines=2,
            )
            search_btn = gr.Button("🔍 Search", variant="primary")

        with gr.Column(scale=1):
            status_output = gr.Markdown(label="System Status")
            status_btn = gr.Button("📊 Refresh Status")
            clear_btn = gr.Button("🗑️ Clear Cache", variant="secondary")

    info_output = gr.Markdown(label="Search Info")

    with gr.Row():
        with gr.Column(scale=2):
            response_output = gr.Markdown(label="Response")

        with gr.Column(scale=1):
            sources_output = gr.Markdown(label="Sources")

    error_output = gr.Textbox(label="Errors", visible=False)

    # Example queries
    gr.Examples(
        examples=[
            "What are the latest trends in large language models?",
            "How does RAG improve LLM responses?",
            "Explain transformer architecture and attention mechanisms",
            "What is the difference between GPT and BERT?",
            "Recent advances in multi-agent AI systems",
        ],
        inputs=query_input,
    )

    # Event handlers
    search_btn.click(
        fn=search,
        inputs=[query_input],
        outputs=[response_output, sources_output, info_output, error_output],
    )

    query_input.submit(
        fn=search,
        inputs=[query_input],
        outputs=[response_output, sources_output, info_output, error_output],
    )

    status_btn.click(fn=get_status, outputs=[status_output])
    clear_btn.click(fn=clear_cache, outputs=[status_output])

    # Load status on startup
    demo.load(fn=get_status, outputs=[status_output])


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=settings.gradio_port,
        share=False,
    )
