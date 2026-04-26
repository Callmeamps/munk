# munk/adapters/contextual_enrichment_adapter.py
"""
Contextual Enrichment Adapter - a seam with behavior-focused interface.

Provides enrich_chunk() and enrich_source() methods.
Centralizes enrichment logic for munk and all-rag-strategies.
"""
import json
from typing import List, Optional
from munk.models import Chunk, Source
from munk.store import MunkStore


class ContextualEnrichmentAdapter:
    """
    Adapter for contextual enrichment with behavior-focused methods.
    
    Hides implementation details (LLM client, prompt construction) from callers.
    """
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        self._enricher = self._create_enricher(anthropic_api_key)
    
    def _create_enricher(self, api_key: Optional[str]):
        """Create the underlying enricher. Import here to avoid circular imports."""
        from munk.contextual_enrichment import ContextualEnricher
        return ContextualEnricher(anthropic_api_key=api_key)
    
    async def enrich_chunk(
        self, 
        chunk: Chunk, 
        source: Source, 
        full_document: str
    ) -> Chunk:
        """
        Enrich a single chunk with document-level context.
        Returns the enriched chunk (original unchanged - uses copy).
        """
        return await self._enricher.enrich_chunk(chunk, source, full_document)
    
    async def enrich_source(
        self, 
        source_id: str, 
        store: MunkStore
    ) -> List[Chunk]:
        """
        Enrich all chunks from a source.
        Returns list of enriched chunks.
        Saves enriched chunks to store.
        """
        return await self._enricher.enrich_source_chunks(source_id, store)
