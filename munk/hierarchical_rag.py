"""
Hierarchical RAG Implementation

Implements Strategy 9 from all-rag-strategies: Hierarchical RAG.
Uses parent-child chunk relationships for multi-scale retrieval.
"""

import json
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from munk.models import Chunk, Source
from munk.store import MunkStore


@dataclass
class HierarchicalChunk:
    """Chunk with hierarchical context."""
    chunk: Chunk
    children: List['HierarchicalChunk'] = None
    parent: Optional['HierarchicalChunk'] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class HierarchicalRetriever:
    """Retrieve chunks using hierarchical relationships."""
    
    def __init__(self, store: MunkStore):
        self.store = store
        self._chunk_cache: Dict[str, HierarchicalChunk] = {}
    
    def build_hierarchy(self, source_id: str) -> HierarchicalChunk:
        """
        Build hierarchical tree for a source document.
        """
        # Get all chunks for this source
        chunk_ids = self.store.list_chunks()
        chunks = []
        for chunk_id in chunk_ids:
            chunk = self.store.load_chunk(chunk_id)
            if chunk.source_id == source_id:
                chunks.append(chunk)
        
        # Build mapping
        chunk_map = {}
        for chunk in chunks:
            chunk_map[chunk.chunk_id] = HierarchicalChunk(chunk=chunk)
        
        # Build parent-child relationships
        for chunk in chunks:
            parent_chunk = chunk_map.get(chunk.parent_chunk_id)
            child_chunk = chunk_map[chunk.chunk_id]
            
            if parent_chunk:
                parent_chunk.children.append(child_chunk)
                child_chunk.parent = parent_chunk
        
        # Find root chunks (no parent)
        root_chunks = [chunk for chunk in chunk_map.values() if chunk.parent is None]
        
        if len(root_chunks) == 1:
            return root_chunks[0]
        else:
            # Multiple root chunks - create virtual parent
            virtual_chunk = Chunk(
                chunk_id=f"virtual_{source_id}",
                source_id=source_id,
                content="",
                content_hash="",
                version=0,
                status="draft",
                created_at="",
                updated_at="",
                title=f"Document: {source_id}",
                description="Document root containing multiple chunks"
            )
            virtual_node = HierarchicalChunk(chunk=virtual_chunk)
            for root in root_chunks:
                virtual_node.children.append(root)
                root.parent = virtual_node
            return virtual_node
    
    def retrieve_context_aware(
        self, 
        source_id: str, 
        query_terms: List[str],
        max_depth: int = 2,
        max_chunks: int = 10
    ) -> List[Chunk]:
        """
        Retrieve chunks with hierarchical context.
        
        Returns chunks sorted by relevance, including parent and child context.
        """
        root = self.build_hierarchy(source_id)
        
        # Find relevant chunks
        relevant_chunks = []
        for chunk in self._flatten_tree(root):
            if any(term.lower() in chunk.content.lower() for term in query_terms):
                relevant_chunks.append(chunk)
        
        # Add parent and child context
        enriched_chunks = self._enrich_with_hierarchy(
            relevant_chunks, 
            max_depth, 
            max_chunks
        )
        
        return enriched_chunks
    
    def _flatten_tree(self, node: HierarchicalChunk, depth: int = 0) -> List[Chunk]:
        """Flatten hierarchy with depth tracking."""
        chunks = []
        chunks.append(node.chunk)
        
        if depth < 3:  # Limit depth to prevent infinite recursion
            for child in node.children:
                chunks.extend(self._flatten_tree(child, depth + 1))
        
        return chunks
    
    def _enrich_with_hierarchy(
        self, 
        chunks: List[Chunk], 
        max_depth: int, 
        max_chunks: int
    ) -> List[Chunk]:
        """Add parent and child context to relevant chunks."""
        enriched = []
        seen = set()
        
        for chunk in chunks:
            if chunk.chunk_id in seen:
                continue
            
            # Add chunk itself
            enriched.append(chunk)
            seen.add(chunk.chunk_id)
            
            # Add parent context
            parent = self._find_parent(chunk)
            if parent and parent.chunk_id not in seen:
                enriched.append(parent)
                seen.add(parent.chunk_id)
            
            # Add child context
            children = self._find_children(chunk)
            for child in children[:max_depth]:  # Limit children per chunk
                if child.chunk_id not in seen:
                    enriched.append(child)
                    seen.add(child.chunk_id)
            
            if len(enriched) >= max_chunks:
                break
        
        return enriched[:max_chunks]
    
    def _find_parent(self, chunk: Chunk) -> Optional[Chunk]:
        """Find parent chunk."""
        if chunk.parent_chunk_id:
            try:
                return self.store.load_chunk(chunk.parent_chunk_id)
            except:
                return None
        return None
    
    def _find_children(self, chunk: Chunk) -> List[Chunk]:
        """Find all direct children of a chunk."""
        children = []
        for child_id in self.store.list_chunks():
            child = self.store.load_chunk(child_id)
            if child.parent_chunk_id == chunk.chunk_id:
                children.append(child)
        return children
    
    def create_parent_chunks(self, source_id: str) -> List[Chunk]:
        """
        Create parent chunks for logical grouping of related chunks.
        Example: Group multiple functions into a "class" chunk.
        """
        chunks = []
        chunk_ids = self.store.list_chunks()
        
        # Get chunks for this source
        source_chunks = []
        for chunk_id in chunk_ids:
            chunk = self.store.load_chunk(chunk_id)
            if chunk.source_id == source_id:
                source_chunks.append(chunk)
        
        # Group by title patterns (simple heuristic)
        groups = self._group_chunks_by_content(source_chunks)
        
        # Create parent chunks
        for group_name, group_chunks in groups.items():
            parent_content = f"# {group_name}\n\n" + "\n\n".join(
                [f"## {chunk.title}\n{chunk.content}" for chunk in group_chunks]
            )
            
            parent_chunk = Chunk(
                chunk_id=f"parent_{source_id}_{group_name}",
                source_id=source_id,
                content=parent_content,
                content_hash="",  # Will be updated
                version=1,
                status="draft",
                created_at=group_chunks[0].created_at,
                updated_at=group_chunks[0].updated_at,
                title=group_name,
                description=f"Parent group containing: {', '.join([c.title for c in group_chunks])}",
                tags=["parent"],
                author_agent="system"
            )
            
            # Update parent IDs for children
            for child in group_chunks:
                child.parent_chunk_id = parent_chunk.chunk_id
                self.store.save_chunk(child)
            
            chunks.append(parent_chunk)
            self.store.save_chunk(parent_chunk)
        
        return chunks
    
    def _group_chunks_by_content(self, chunks: List[Chunk]) -> Dict[str, List[Chunk]]:
        """Group chunks by content patterns (simple heuristic)."""
        groups = {}
        
        for chunk in chunks:
            # Simple grouping by first line or title
            if chunk.title.startswith("func "):
                group_name = "Functions"
            elif chunk.title.startswith("class "):
                group_name = "Classes"
            elif chunk.title.startswith("#"):
                group_name = "Sections"
            else:
                group_name = "Other"
            
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(chunk)
        
        return groups