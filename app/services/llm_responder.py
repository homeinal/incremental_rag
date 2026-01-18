"""LLM Response Generation Service"""

from typing import List, Optional

from app.config import get_settings
from app.core.embeddings import get_openai_client
from app.models.schemas import KnowledgeItem, MCPSearchResult, SourceInfo
from app.utils.logger import get_logger

logger = get_logger(__name__)

RESPONSE_PROMPT = """You are an AI research assistant. Based on the provided context, answer the user's question accurately and concisely.

Context from knowledge base:
{context}

User question: {query}

Instructions:
1. Synthesize information from the provided sources
2. Be specific and cite relevant details from the context
3. If the context doesn't fully answer the question, acknowledge limitations
4. Keep the response focused and informative
5. Do not make up information not present in the context
6. IMPORTANT: Respond in the same language as the user's question. If the question is in Korean, respond in Korean. If the question is in English, respond in English.

Response:"""


class LLMResponderService:
    """Generates responses using LLM based on retrieved context"""

    def __init__(self):
        self.settings = get_settings()

    async def generate_response(
        self,
        query: str,
        knowledge_items: List[KnowledgeItem] = None,
        mcp_results: List[MCPSearchResult] = None,
    ) -> tuple[str, List[SourceInfo]]:
        """
        Generate a response based on retrieved knowledge.
        Returns (response_text, sources)
        """
        # Build context from knowledge items
        context_parts = []
        sources = []

        if knowledge_items:
            for i, item in enumerate(knowledge_items, 1):
                context_parts.append(f"[Source {i}] ({item.source_type.value})\n{item.content[:1000]}")
                sources.append(SourceInfo(
                    source_type=item.source_type,
                    title=item.source_title,
                    url=item.source_url,
                    author=item.source_author,
                    relevance_score=item.final_score,
                ))

        if mcp_results:
            offset = len(context_parts)
            for i, result in enumerate(mcp_results, offset + 1):
                context_parts.append(f"[Source {i}] ({result.source_type.value})\n{result.content[:1000]}")
                sources.append(SourceInfo(
                    source_type=result.source_type,
                    title=result.source_title,
                    url=result.source_url,
                    author=result.source_author,
                    relevance_score=0.0,
                ))

        if not context_parts:
            return self._not_found_response(query), []

        context = "\n\n---\n\n".join(context_parts)
        client = get_openai_client()

        try:
            response = await client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful AI research assistant with expertise in machine learning, AI, and academic research.",
                    },
                    {
                        "role": "user",
                        "content": RESPONSE_PROMPT.format(context=context, query=query),
                    },
                ],
                temperature=0.7,
                max_tokens=1000,
            )

            response_text = response.choices[0].message.content.strip()
            logger.info(f"Generated response with {len(sources)} sources")
            return response_text, sources

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return f"I encountered an error generating a response: {str(e)}", sources

    def _not_found_response(self, query: str = "") -> str:
        """Generate a not-found response in the appropriate language"""
        # Simple Korean detection: check for Korean characters
        if query and any('\uac00' <= char <= '\ud7a3' for char in query):
            return (
                "질문에 대한 관련 정보를 찾을 수 없습니다. "
                "질문을 다르게 표현하거나 AI 및 머신러닝 연구와 관련된 다른 주제로 질문해 주세요."
            )
        return (
            "I couldn't find relevant information to answer your question. "
            "Try rephrasing your query or asking about a different topic related to AI and machine learning research."
        )


# Global service instance
_responder_service: Optional[LLMResponderService] = None


def get_responder_service() -> LLMResponderService:
    """Get or create LLM responder service instance"""
    global _responder_service
    if _responder_service is None:
        _responder_service = LLMResponderService()
    return _responder_service
