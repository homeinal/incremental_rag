"""MCP Client Service - Tier 3 of the RAG pipeline (External Search)"""

import httpx
import xml.etree.ElementTree as ET
from typing import List, Optional
from urllib.parse import quote

from app.models.schemas import MCPSearchResult, SourceType
from app.utils.logger import get_logger

logger = get_logger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"


class MCPClientService:
    """
    Handles external search via arXiv API and HuggingFace.
    In production, this wraps external APIs.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def search_arxiv(
        self,
        keywords: List[str],
        max_results: int = 5,
    ) -> List[MCPSearchResult]:
        """Search arXiv for papers matching keywords"""
        if not keywords:
            return []

        # Build search query
        query_parts = [f'all:"{kw}"' for kw in keywords]
        query = " OR ".join(query_parts)

        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        try:
            response = await self.client.get(ARXIV_API_URL, params=params)
            response.raise_for_status()

            results = self._parse_arxiv_response(response.text)
            logger.info(f"arXiv search returned {len(results)} results for: {keywords}")
            return results

        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return []

    def _parse_arxiv_response(self, xml_text: str) -> List[MCPSearchResult]:
        """Parse arXiv API XML response"""
        results = []

        # Define namespaces
        namespaces = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        try:
            root = ET.fromstring(xml_text)

            for entry in root.findall("atom:entry", namespaces):
                title_elem = entry.find("atom:title", namespaces)
                summary_elem = entry.find("atom:summary", namespaces)
                id_elem = entry.find("atom:id", namespaces)

                # Get authors
                authors = []
                for author in entry.findall("atom:author", namespaces):
                    name = author.find("atom:name", namespaces)
                    if name is not None and name.text:
                        authors.append(name.text)

                # Get categories
                categories = []
                for category in entry.findall("arxiv:primary_category", namespaces):
                    if "term" in category.attrib:
                        categories.append(category.attrib["term"])

                title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                summary = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ""
                arxiv_id = id_elem.text if id_elem is not None and id_elem.text else ""

                # Clean up whitespace in title and summary
                title = " ".join(title.split())
                summary = " ".join(summary.split())

                # Create content combining title and abstract
                content = f"Title: {title}\n\nAbstract: {summary}"

                result = MCPSearchResult(
                    content=content,
                    source_type=SourceType.ARXIV_PAPER,
                    source_url=arxiv_id,
                    source_title=title,
                    source_author=", ".join(authors[:3]),  # First 3 authors
                    metadata={
                        "arxiv_id": arxiv_id.split("/")[-1] if arxiv_id else "",
                        "categories": categories,
                        "all_authors": authors,
                    },
                )
                results.append(result)

        except ET.ParseError as e:
            logger.error(f"Failed to parse arXiv XML: {e}")

        return results

    async def search_huggingface(
        self,
        keywords: List[str],
        max_results: int = 5,
    ) -> List[MCPSearchResult]:
        """
        Search HuggingFace Hub for models/datasets.
        Uses the HuggingFace API.
        """
        if not keywords:
            return []

        query = " ".join(keywords)
        results = []

        # Search models
        try:
            model_url = f"https://huggingface.co/api/models?search={quote(query)}&limit={max_results}"
            response = await self.client.get(model_url)
            response.raise_for_status()

            models = response.json()
            for model in models[:max_results]:
                model_id = model.get("modelId", "")
                result = MCPSearchResult(
                    content=f"HuggingFace Model: {model_id}\n\nDescription: {model.get('description', 'No description available')}",
                    source_type=SourceType.HUGGINGFACE,
                    source_url=f"https://huggingface.co/{model_id}",
                    source_title=model_id,
                    source_author=model.get("author", ""),
                    metadata={
                        "downloads": model.get("downloads", 0),
                        "likes": model.get("likes", 0),
                        "tags": model.get("tags", []),
                    },
                )
                results.append(result)

            logger.info(f"HuggingFace search returned {len(results)} results for: {keywords}")

        except Exception as e:
            logger.error(f"HuggingFace search failed: {e}")

        return results

    async def search_all(
        self,
        keywords: List[str],
        max_results_per_source: int = 3,
    ) -> List[MCPSearchResult]:
        """Search all external sources and combine results"""
        all_results = []

        # Search arXiv
        arxiv_results = await self.search_arxiv(keywords, max_results_per_source)
        all_results.extend(arxiv_results)

        # Search HuggingFace
        hf_results = await self.search_huggingface(keywords, max_results_per_source)
        all_results.extend(hf_results)

        logger.info(f"Combined external search: {len(all_results)} total results")
        return all_results

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Global service instance
_mcp_service: Optional[MCPClientService] = None


def get_mcp_service() -> MCPClientService:
    """Get or create MCP client service instance"""
    global _mcp_service
    if _mcp_service is None:
        _mcp_service = MCPClientService()
    return _mcp_service
