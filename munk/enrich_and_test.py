"""
Test script for contextual enrichment and hierarchical RAG.
Demonstrates integration with munk project.
"""

import asyncio
from pathlib import Path
from munk.contextual_enrichment import ContextualEnricher
from munk.hierarchical_rag import HierarchicalRetriever
from munk.models import Source
from munk.store import MunkStore


async def test_contextual_enrichment():
    """Test contextual enrichment of chunks."""
    print("=== Testing Contextual Enrichment ===")
    
    # Initialize
    store = MunkStore("munk_data")
    enricher = ContextualEnricher("test-key")  # Replace with real API key
    
    # Get first source
    # Only use supported extension sources (gd, md, txt, json)
    SUPPORTED = {".gd", ".md", ".txt", ".json"}
    source_ids = []
    for sid in store.list_sources():
        src = store.load_source(sid)
        if any(src.path.endswith(ext) for ext in SUPPORTED):
            source_ids.append(sid)
            
    if not source_ids:
        print("No supported sources found. Please run chunking first.")
        return
    
    source_id = source_ids[0]
    print(f"Enriching source: {source_id} ({store.load_source(source_id).path})")
    
    try:
        enriched_chunks = await enricher.enrich_source_chunks(source_id, store)
        print(f"Enriched {len(enriched_chunks)} chunks")
        
        # Show example
        if enriched_chunks:
            chunk = enriched_chunks[0]
            print(f"\nExample chunk enrichment:")
            print(f"Title: {chunk.title}")
            print(f"Description: {chunk.description[:200]}...")
    
    except Exception as e:
        print(f"Enrichment failed (expected without real API key): {e}")


def test_hierarchical_rag():
    """Test hierarchical retrieval."""
    print("\n=== Testing Hierarchical RAG ===")
    
    store = MunkStore("munk_data")
    retriever = HierarchicalRetriever(store)
    
    # Get first source
    # Only use supported extension sources (gd, md, txt, json)
    SUPPORTED = {".gd", ".md", ".txt", ".json"}
    source_ids = []
    try:
        for sid in store.list_sources():
            src = store.load_source(sid)
            if any(src.path.endswith(ext) for ext in SUPPORTED):
                source_ids.append(sid)
    except:
        pass
    
    if not source_ids:
        print("No supported sources found.")
        return
    
    source_id = source_ids[0]
    print(f"Testing hierarchical retrieval for: {source_id} ({store.load_source(source_id).path})")
    
    try:
        # Build hierarchy
        root = retriever.build_hierarchy(source_id)
        print(f"Built hierarchy with {len(retriever._flatten_tree(root))} chunks")
        
        # Test context-aware retrieval
        query_terms = ["function", "class"]
        results = retriever.retrieve_context_aware(source_id, query_terms)
        print(f"Retrieved {len(results)} chunks with hierarchical context")
        
        # Show example
        if results:
            chunk = results[0]
            print(f"\nExample retrieved chunk:")
            print(f"Title: {chunk.title}")
            print(f"Content preview: {chunk.content[:100]}...")
        
        # Test parent chunk creation
        parent_chunks = retriever.create_parent_chunks(source_id)
        print(f"Created {len(parent_chunks)} parent chunks")
        
    except Exception as e:
        print(f"Hierarchical retrieval failed: {e}")


async def main():
    """Run all tests."""
    print("Testing munk integration with all-rag-strategies")
    print("=" * 50)
    
    test_hierarchical_rag()
    await test_contextual_enrichment()
    
    print("\n" + "=" * 50)
    print("Integration complete!")
    print("Next steps:")
    print("1. Add real API key for contextual enrichment")
    print("2. Test with actual document data")
    print("3. Integrate with retrieval API")


if __name__ == "__main__":
    asyncio.run(main())