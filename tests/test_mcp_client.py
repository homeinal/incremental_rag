"""Tests for MCP Client Service"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.mcp_client import MCPClientService
from app.models.schemas import SourceType


@pytest.fixture
def mcp_service():
    """Create an MCP client service instance"""
    return MCPClientService()


SAMPLE_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.12345v1</id>
    <title>Test Paper on Large Language Models</title>
    <summary>This paper explores advances in LLMs...</summary>
    <author>
      <name>John Doe</name>
    </author>
    <author>
      <name>Jane Smith</name>
    </author>
    <arxiv:primary_category term="cs.CL"/>
  </entry>
</feed>
"""

SAMPLE_HF_RESPONSE = [
    {
        "modelId": "test-org/test-model",
        "description": "A test model for NLP tasks",
        "author": "test-org",
        "downloads": 1000,
        "likes": 50,
        "tags": ["nlp", "transformers"],
    }
]


class TestMCPClientService:
    """Tests for MCPClientService"""

    @pytest.mark.asyncio
    async def test_search_arxiv_empty_keywords(self, mcp_service):
        """Test arXiv search with empty keywords returns empty list"""
        results = await mcp_service.search_arxiv([])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_arxiv_success(self, mcp_service):
        """Test successful arXiv search"""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_ARXIV_XML
        mock_response.raise_for_status = MagicMock()

        with patch.object(mcp_service.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            results = await mcp_service.search_arxiv(["LLM", "transformers"])

            assert len(results) == 1
            assert results[0].source_type == SourceType.ARXIV_PAPER
            assert "Large Language Models" in results[0].source_title
            assert "John Doe" in results[0].source_author

    @pytest.mark.asyncio
    async def test_search_arxiv_error(self, mcp_service):
        """Test arXiv search handles errors gracefully"""
        with patch.object(mcp_service.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection failed")

            results = await mcp_service.search_arxiv(["test"])

            assert results == []

    @pytest.mark.asyncio
    async def test_search_huggingface_empty_keywords(self, mcp_service):
        """Test HuggingFace search with empty keywords returns empty list"""
        results = await mcp_service.search_huggingface([])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_huggingface_success(self, mcp_service):
        """Test successful HuggingFace search"""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_HF_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch.object(mcp_service.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            results = await mcp_service.search_huggingface(["NLP", "model"])

            assert len(results) == 1
            assert results[0].source_type == SourceType.HUGGINGFACE
            assert "test-org/test-model" in results[0].source_title

    @pytest.mark.asyncio
    async def test_search_huggingface_error(self, mcp_service):
        """Test HuggingFace search handles errors gracefully"""
        with patch.object(mcp_service.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection failed")

            results = await mcp_service.search_huggingface(["test"])

            assert results == []

    @pytest.mark.asyncio
    async def test_search_all_combines_results(self, mcp_service):
        """Test search_all combines results from all sources"""
        with patch.object(mcp_service, "search_arxiv", new_callable=AsyncMock) as mock_arxiv:
            with patch.object(mcp_service, "search_huggingface", new_callable=AsyncMock) as mock_hf:
                from app.models.schemas import MCPSearchResult

                mock_arxiv.return_value = [
                    MCPSearchResult(
                        content="arXiv paper",
                        source_type=SourceType.ARXIV_PAPER,
                    )
                ]
                mock_hf.return_value = [
                    MCPSearchResult(
                        content="HuggingFace model",
                        source_type=SourceType.HUGGINGFACE,
                    )
                ]

                results = await mcp_service.search_all(["test"])

                assert len(results) == 2
                assert any(r.source_type == SourceType.ARXIV_PAPER for r in results)
                assert any(r.source_type == SourceType.HUGGINGFACE for r in results)

    @pytest.mark.asyncio
    async def test_parse_arxiv_response_invalid_xml(self, mcp_service):
        """Test parsing invalid XML returns empty list"""
        results = mcp_service._parse_arxiv_response("not valid xml")
        assert results == []

    def test_parse_arxiv_response_extracts_metadata(self, mcp_service):
        """Test XML parsing extracts all metadata"""
        results = mcp_service._parse_arxiv_response(SAMPLE_ARXIV_XML)

        assert len(results) == 1
        result = results[0]
        assert result.metadata["arxiv_id"] == "2301.12345v1"
        assert "cs.CL" in result.metadata["categories"]
        assert len(result.metadata["all_authors"]) == 2
