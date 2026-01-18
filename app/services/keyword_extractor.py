"""Keyword Extraction Service using LLM"""

import json
from typing import List, Optional

from openai import AsyncOpenAI

from app.config import get_settings
from app.core.embeddings import get_openai_client
from app.models.schemas import KeywordResult, SourceType
from app.utils.logger import get_logger

logger = get_logger(__name__)

EXTRACTION_PROMPT = """Extract technical keywords from the following query for searching a knowledge base about AI, machine learning, and research papers.

Rules:
1. Extract 3-7 specific technical keywords or phrases
2. Convert abstract concepts to technical terms (e.g., "AI trends" → "large language models", "transformers", "AI")
3. Keep keywords concise but specific
4. Include relevant acronyms if applicable (e.g., "LLM", "RAG", "NLP")
5. Identify if the query is asking about: expert_insight, arxiv_paper, huggingface, or general

Query: {query}

Respond in JSON format:
{{
    "keywords": ["keyword1", "keyword2", ...],
    "source_type_hint": "expert_insight" | "arxiv_paper" | "huggingface" | null
}}"""


class KeywordExtractorService:
    """Extracts technical keywords from natural language queries"""

    def __init__(self):
        self.settings = get_settings()

    async def extract(self, query: str) -> KeywordResult:
        """Extract keywords from a query using LLM"""
        client = get_openai_client()

        try:
            response = await client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a keyword extraction assistant. Always respond with valid JSON.",
                    },
                    {
                        "role": "user",
                        "content": EXTRACTION_PROMPT.format(query=query),
                    },
                ],
                temperature=0.3,
                max_tokens=200,
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON response
            # Handle potential markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            keywords = data.get("keywords", [])
            source_hint = data.get("source_type_hint")

            # Map source hint to SourceType
            source_type = None
            if source_hint:
                type_map = {
                    "expert_insight": SourceType.EXPERT_INSIGHT,
                    "arxiv_paper": SourceType.ARXIV_PAPER,
                    "huggingface": SourceType.HUGGINGFACE,
                }
                source_type = type_map.get(source_hint)

            result = KeywordResult(keywords=keywords, source_type_hint=source_type)
            logger.info(f"Extracted keywords: {keywords}")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse keyword extraction response: {e}")
            # Fallback: split query into words
            words = query.lower().split()
            keywords = [w for w in words if len(w) > 2][:5]
            return KeywordResult(keywords=keywords)

        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}")
            # Fallback
            words = query.lower().split()
            keywords = [w for w in words if len(w) > 2][:5]
            return KeywordResult(keywords=keywords)


# Global service instance
_extractor_service: Optional[KeywordExtractorService] = None


def get_extractor_service() -> KeywordExtractorService:
    """Get or create keyword extractor service instance"""
    global _extractor_service
    if _extractor_service is None:
        _extractor_service = KeywordExtractorService()
    return _extractor_service
