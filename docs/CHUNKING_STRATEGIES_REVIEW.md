# Chunking Strategies Review

## Overview
This document reviews the chunking strategies implemented in:
- `munk/chunker.py` (current)
- `all-rag-strategies/` (reference)

It identifies **gaps**, **opportunities**, and **proposed updates** to align `munk` with best practices for **Retrieval-Augmented Generation (RAG)** and **version control**.

---

## 1. Chunking Strategies in `all-rag-strategies`

### 1.1 Context-Aware Chunking
- **Description**: Splits text based on **semantic similarity** (embeddings) rather than fixed sizes.
- **Pros**: Preserves topic coherence; improves embedding quality.
- **Cons**: Computationally expensive; requires embeddings for every sentence.
- **Use Case**: Heterogeneous documents with mixed topics.

### 1.2 Late Chunking
- **Description**: Processes entire documents through the **transformer** before splitting into chunks.
- **Pros**: Maintains long-distance context; leverages long-context models.
- **Cons**: Requires models with high token limits; complex implementation.
- **Use Case**: Documents where meaning depends on distant context (e.g., legal contracts).

### 1.3 Docling HybridChunker
- **Description**: Combines **token-aware**, **structure-preserving**, and **semantic** chunking.
- **Pros**: Token-precise; preserves document structure; includes heading context.
- **Cons**: Requires Docling; slower than simple chunking.
- **Use Case**: High-quality RAG on structured documents (e.g., Markdown, code).

### 1.4 Semantic Chunker (LLM)
- **Description**: Uses LLMs to split long sections at **semantic boundaries**.
- **Pros**: Highly accurate; respects document structure.
- **Cons**: Slow; expensive; risk of hallucination.
- **Use Case**: Critical applications where accuracy outweighs cost.

### 1.5 Simple Chunker
- **Description**: Rule-based splitting (e.g., paragraphs, fixed size).
- **Pros**: Fast; lightweight; easy to implement.
- **Cons**: May split unrelated content; poor embedding quality.
- **Use Case**: Low-priority or homogeneous documents.

---

## 2. Current Implementation in `munk/chunker.py`

### 2.1 Strategy
- **Rule-based splitting** (lines, JSON keys).
- **Strengths**: Lightweight, fast, and works without embeddings.
- **Weaknesses**: No semantic awareness; may split unrelated content.

### 2.2 Supported Formats
- GDScript, Markdown, TXT, JSON (top-level keys).
- **Strengths**: Supports multiple formats with simple rules.
- **Weaknesses**: No support for advanced formats (e.g., PDF, DOCX).

### 2.3 Structure Preservation
- Splits on boundaries (e.g., functions in GDScript, headings in Markdown).
- **Strengths**: Preserves logical structure for supported formats.
- **Weaknesses**: No semantic grouping; no heading context.

### 2.4 Context Awareness
- **None**: No long-distance context; may split semantically related content.

### 2.5 Performance
- Fast; no external dependencies.
- **Strengths**: Ideal for lightweight or real-time use cases.

### 2.6 Use Case
- Designed for **version control** and **collaborative editing** (e.g., splitting code into functions).
- **Misalignment**: Lacks RAG-specific optimizations (e.g., semantic coherence, heading context).

---

## 3. Gaps and Opportunities

| **Gap**                          | **Opportunity**                                                                                     |
|-----------------------------------|---------------------------------------------------------------------------------------------------|
| No semantic chunking              | Integrate **context-aware chunking** or **Docling HybridChunker** for RAG use cases.             |
| No late chunking                  | Add **late chunking** for documents requiring long-distance context (e.g., legal contracts).    |
| No heading context                | Use **Docling HybridChunker** to include heading/hierarchy context in chunks.                    |
| Limited to simple formats         | Add support for PDF, DOCX, and other formats via Docling or Unstructured.                       |
| No token precision                | Replace character-based logic with **token-aware chunking** (e.g., `transformers` library).     |
| Narrow use case                   | Align `munk` with `all-rag-strategies` to support **both version control and RAG**.               |

---

## 4. Proposed Updates

### 4.1 Short-Term
1. **Add `SemanticChunker` to `munk`**:
   - Integrate **context-aware chunking** for Markdown/JSON files.
   - Use embeddings to group semantically related content.

2. **Upgrade `JSONChunker`**:
   - Use **token-aware splitting** instead of top-level keys.
   - Preserve JSON structure (e.g., `"nested": { "keys": ... }`).

3. **Update `UBIQUITOUS_LANGUAGE.md`**:
   - Add terms like **"Semantic Chunk"**, **"Late Chunking"**, and **"Structure-Preserving Chunk"**.
   - Clarify when to use each strategy.

### 4.2 Medium-Term
4. **Add `LateChunker`**:
   - Support for documents requiring long-distance context (e.g., contracts, research papers).

5. **Add `DoclingHybridChunker`**:
   - Replace the current GDScript/Markdown chunker with **structure-preserving** logic.
   - Include **heading context** in chunks.

### 4.3 Long-Term
6. **Create a `ChunkStrategy` Interface**:
   - Abstract chunking logic behind a **seam** (e.g., `ChunkStrategy.chunk(source, content)`).
   - Allow swapping strategies at runtime (e.g., `HybridStrategy`, `LateStrategy`, `SimpleStrategy`).

---

## 5. Example Implementation

### 5.1 Adding a `SemanticChunker`
```python
from munk.adapters.embedding_client import EmbeddingClient

class SemanticChunker:
    def __init__(self, embedding_client: EmbeddingClient):
        self.embedding_client = embedding_client

    def chunkify(self, source: Source, content: str, store: MunkStore) -> Manifest:
        # Split content into sentences
        sentences = self._split_into_sentences(content)
        # Generate embeddings for each sentence
        embeddings = [self.embedding_client.encode(s) for s in sentences]
        # Calculate similarity between consecutive sentences
        similarities = [
            cosine_similarity(embeddings[i], embeddings[i+1])
            for i in range(len(embeddings)-1)
        ]
        # Group sentences where similarity > threshold
        chunks = []
        current_chunk = [sentences[0]]
        for i, sim in enumerate(similarities):
            if sim > 0.8:  # High similarity = same topic
                current_chunk.append(sentences[i+1])
            else:  # Low similarity = new topic
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentences[i+1]]
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        # Save chunks to store and return Manifest
        ...
```

### 5.2 Adding a `ChunkStrategy` Interface
```python
from typing import Protocol

@runtime_checkable
class ChunkStrategy(Protocol):
    def chunkify(self, source: Source, content: str, store: MunkStore) -> Manifest:
        ...

def create_chunker(strategy: str = "simple") -> ChunkStrategy:
    if strategy == "semantic":
        return SemanticChunker(embedding_client=get_embedding_client())
    elif strategy == "late":
        return LateChunker(transformer_model=get_transformer_model())
    elif strategy == "docling":
        return DoclingHybridChunker(docling_chunker=HybridChunker())
    else:
        return SimpleChunker()
```

---

## 6. Next Steps

1. **Implement short-term updates** (e.g., `SemanticChunker`, `JSONChunker` improvements).
2. **Create GitHub issues** for medium/long-term updates.
3. **Update documentation** to reflect new strategies and use cases.
4. **Test new strategies** with real-world documents (e.g., code, Markdown, contracts).