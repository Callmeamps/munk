"""
Contextual Enrichment for Chunks

Implements Strategy 4 from all-rag-strategies: Contextual Retrieval.
Adds document-level context to chunk descriptions using LLM analysis.
"""

import json
from typing import List, Optional

from typing import Optional
from munk.models import Chunk, Source
from munk.store import MunkStore


class ContextualEnricher:
    """Enrich chunk descriptions with document-level context."""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.client = None
        if anthropic_api_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=anthropic_api_key)
            except ImportError:
                print("Warning: anthropic package not available. Using mock enrichment.")
    
    async def enrich_chunk(
        self, 
        chunk: Chunk, 
        source: Source, 
        full_document: str
    ) -> Chunk:
        """
        Add contextual prefix to chunk description.
        
        Uses LLM to generate brief context explaining what this chunk
        discusses in relation to the whole document.
        """
        # Truncate document to context window
        document_context = full_document[:4000]
        
        prompt = f"""<document>
Title: {source.path}
{document_context}
</document>

<chunk>
{chunk.content}
</chunk>

Provide brief context explaining what this chunk discusses in relation to the whole document.
Format: "This chunk from '{source.path}' discusses [explanation]."
Keep explanation under 100 words.
"""
        
        if self.client:
            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=150,
                messages=[{
                    "role": "user", 
                    "content": prompt
                }]
            )
            context = response.content[0].text.strip()
        else:
            # Mock enrichment for testing
            context = f"This chunk from '{source.path}' discusses {chunk.title or 'content related to the document'}."
            print("Using mock contextual enrichment")
        enriched_description = f"{context}\n\n{chunk.description}"
        
        # Update chunk with enriched description
        from copy import deepcopy
        updated_chunk = deepcopy(chunk)
        updated_chunk.description = enriched_description
        updated_chunk.updated_at = chunk.updated_at[:19] + ".000000"
        
        return updated_chunk
    
    async def enrich_source_chunks(
        self, 
        source_id: str, 
        store: MunkStore
    ) -> List[Chunk]:
        """
        Enrich all chunks from a source document.
        """
        # Load source and document
        source = store.load_source(source_id)
        document_path = store.root / "sources" / f"{source_id}.json"
        full_document = document_path.read_text(encoding="utf-8")
        
        # Get all chunks for this source
        chunk_ids = store.list_chunks()
        chunks = []
        for chunk_id in chunk_ids:
            chunk = store.load_chunk(chunk_id)
            if chunk.source_id == source_id:
                chunks.append(chunk)
        
        enriched_chunks = []
        for chunk in chunks:
            enriched = await self.enrich_chunk(chunk, source, full_document)
            enriched_chunks.append(enriched)
            store.save_chunk(enriched)
        
        return enriched_chunks