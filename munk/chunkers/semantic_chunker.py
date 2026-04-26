# munk/chunkers/semantic_chunker.py
"""
Semantic chunker for intelligent document splitting using embeddings.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from munk.models import Source, Manifest, Chunk
from munk.store import MunkStore
from munk.ids import new_id
from munk.hashing import hash_content
from munk.chunker_config import ChunkingConfig

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False


@dataclass
class SemanticChunk:
    """Represents a semantically coherent document chunk."""
    content: str
    index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]


class SemanticChunker:
    """Semantic document chunker using embeddings for intelligent splitting."""

    def __init__(self, config: ChunkingConfig):
        """
        Initialize the semantic chunker.
        Args:
            config: Chunking configuration.
        """
        self.config = config
        if not EMBEDDING_AVAILABLE:
            raise ImportError(
                "SemanticChunker requires `sentence-transformers` and `scikit-learn`. "
                "Install with: pip install sentence-transformers scikit-learn"
            )
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

    def chunkify(self, source: Source, content: str, store: MunkStore) -> Manifest:
        """
        Chunk a document into semantically coherent pieces using embeddings.
        Args:
            source: Source document.
            content: Document content.
            store: MunkStore instance.
        Returns:
            Manifest for the chunks.
        """
        if not content.strip():
            return self._empty_manifest(source)

        # Split content into sentences
        sentences = self._split_into_sentences(content)
        if not sentences:
            return self._empty_manifest(source)

        # Generate embeddings for each sentence
        embeddings = self.embedding_model.encode(sentences)

        # Calculate similarity between consecutive sentences
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = cosine_similarity(
                [embeddings[i]],
                [embeddings[i + 1]],
            )[0][0]
            similarities.append(sim)

        # Group sentences into chunks based on similarity
        chunks = []
        current_chunk = [sentences[0]]
        current_similarity = []
        for i, sim in enumerate(similarities):
            if sim > self.config.semantic_similarity_threshold:
                # High similarity = same topic
                current_chunk.append(sentences[i + 1])
                current_similarity.append(sim)
            else:
                # Low similarity = new topic
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [sentences[i + 1]]
                current_similarity = []
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        # Remove empty chunks
        chunks = [chunk for chunk in chunks if chunk.strip()]

        # Save chunks to store and return Manifest
        return self._save_chunks(source, content, chunks, store)

    def _split_into_sentences(self, content: str) -> List[str]:
        """
        Split content into sentences using simple heuristics.
        Args:
            content: Document content.
        Returns:
            List of sentences.
        """
        import re
        # Split on sentence boundaries (., !, ?, followed by whitespace)
        sentences = re.split(r'(?<=[.!?])\s+', content)
        return [s.strip() for s in sentences if s.strip()]

    def _empty_manifest(self, source: Source) -> Manifest:
        """Return an empty manifest for edge cases."""
        from datetime import datetime, timezone
        return Manifest(
            manifest_id=new_id("man"),
            source_id=source.source_id,
            chunks=[],
            order=[],
            export_mode="rebuild",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _save_chunks(
        self, source: Source, original_content: str, chunks: List[str], store: MunkStore
    ) -> Manifest:
        """
        Save chunks to the store and return a Manifest.
        Args:
            source: Source document.
            original_content: Original document content.
            chunks: List of chunk texts.
            store: MunkStore instance.
        Returns:
            Manifest for the chunks.
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        chunk_ids: List[str] = []
        chunk_objs: List[Chunk] = []

        for i, text in enumerate(chunks):
            chunk_id = new_id("chk")
            chunk = Chunk(
                chunk_id=chunk_id,
                source_id=source.source_id,
                content=text,
                content_hash=hash_content(text),
                version=1,
                status="draft",
                created_at=now,
                updated_at=now,
                parent_chunk_id=None,
                title=f"Semantic Chunk {i+1}",
                description="",
                tags=["semantic"],
                author_agent="semantic-chunker",
            )
            chunk_objs.append(chunk)
            chunk_ids.append(chunk_id)

        # Save chunks to store
        for chunk in chunk_objs:
            store.save_chunk(chunk)

        # Create and save manifest
        manifest = Manifest(
            manifest_id=new_id("man"),
            source_id=source.source_id,
            chunks=chunk_ids,
            order=chunk_ids,
            export_mode="rebuild",
            created_at=now,
        )
        store.save_manifest(manifest)
        return manifest