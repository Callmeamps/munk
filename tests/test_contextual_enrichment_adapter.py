# tests/test_contextual_enrichment_adapter.py
"""Tests for ContextualEnrichmentAdapter - verify behavior, not internals."""
import pytest
import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from munk.adapters.contextual_enrichment_adapter import ContextualEnrichmentAdapter
from munk.models import Chunk, Source
from munk.store import MunkStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def sample_chunk():
    return Chunk(
        chunk_id="chk_1",
        source_id="src_1",
        content="This is chunk content about neural networks.",
        content_hash="sha256:abc123",
        version=1,
        status="draft",
        created_at=_now(),
        updated_at=_now(),
        title="Neural Networks",
        description="Original description",
        tags=["ai"],
        author_agent="user",
    )


@pytest.fixture
def sample_source():
    return Source(
        source_id="src_1",
        path="doc.md",
        hash="sha256:def456",
        size_bytes=1000,
        mime_type="text/markdown",
        created_at=_now(),
    )


@pytest.fixture
def mock_enricher():
    """Mock the underlying ContextualEnricher."""
    with patch("munk.adapters.contextual_enrichment_adapter.ContextualEnrichmentAdapter._create_enricher") as mock:
        enricher = MagicMock()
        enricher.enrich_chunk = AsyncMock()
        enricher.enrich_source_chunks = AsyncMock()
        mock.return_value = enricher
        yield enricher


@pytest.mark.anyio
async def test_enrich_chunk_returns_enriched_chunk(mock_enricher, sample_chunk, sample_source):
    """enrich_chunk() should return a chunk with enriched description."""
    from copy import deepcopy
    enriched = deepcopy(sample_chunk)
    enriched.description = "This chunk from 'doc.md' discusses neural networks.\n\nOriginal description"
    mock_enricher.enrich_chunk.return_value = enriched

    adapter = ContextualEnrichmentAdapter()
    result = await adapter.enrich_chunk(sample_chunk, sample_source, "Full document content")

    assert result.description != sample_chunk.description
    assert "neural networks" in result.description.lower() or result.description != "Original description"


@pytest.mark.anyio
async def test_enrich_chunk_preserves_original(mock_enricher, sample_chunk, sample_source):
    """Original chunk should not be modified (enrich_chunk returns a copy)."""
    enriched = deepcopy(sample_chunk)
    enriched.description = "New description"
    mock_enricher.enrich_chunk.return_value = enriched

    adapter = ContextualEnrichmentAdapter()
    result = await adapter.enrich_chunk(sample_chunk, sample_source, "Full document")

    # Original unchanged
    assert sample_chunk.description == "Original description"
    # Result is different
    assert result.description == "New description"


@pytest.mark.anyio
async def test_enrich_source_enriches_all_chunks(mock_enricher, sample_source):
    """enrich_source() should enrich all chunks for a source."""
    enriched_list = [MagicMock(), MagicMock()]
    mock_enricher.enrich_source_chunks.return_value = enriched_list

    adapter = ContextualEnrichmentAdapter()
    result = await adapter.enrich_source("src_1", MagicMock())

    assert len(result) == 2
    mock_enricher.enrich_source_chunks.assert_called_once()


@pytest.mark.anyio
async def test_enrich_chunk_calls_underlying_enricher(mock_enricher, sample_chunk, sample_source):
    """Verify the adapter delegates to the underlying enricher."""
    mock_enricher.enrich_chunk.return_value = sample_chunk

    adapter = ContextualEnrichmentAdapter()
    await adapter.enrich_chunk(sample_chunk, sample_source, "Full doc")

    mock_enricher.enrich_chunk.assert_called_once_with(sample_chunk, sample_source, "Full doc")
