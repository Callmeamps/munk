"""Test munk chunker using real conversation data."""

import json
import tempfile
import pytest
from pathlib import Path
from munk.store import MunkStore
from munk.models import Source
from munk.ids import new_id
from munk.hashing import hash_content
from munk.chunker import chunkify, SEMANTIC_CHUNKER_AVAILABLE
from datetime import datetime, timezone


def _extract_messages(conversation: dict) -> list[str]:
    """Extract all message text from a conversation object."""
    messages = []
    mapping = conversation.get("mapping", {})
    for node in mapping.values():
        msg = node.get("message")
        if not msg:
            continue
        content = msg.get("content", {})
        if content.get("content_type") == "text":
            parts = content.get("parts", [])
            for part in parts:
                if isinstance(part, str) and part.strip():
                    messages.append(part.strip())
    return messages


def _conversations_to_json_dict(conversations: list[dict]) -> str:
    """Convert conversations to a JSON dict format (chunker splits by key)."""
    data = {}
    for i, conv in enumerate(conversations[:10]):  # limit to 10 for test speed
        conv_id = conv.get("conversation_id", f"conv_{i}")
        messages = _extract_messages(conv)
        data[conv_id] = {
            "title": conv.get("title", f"Conversation {i}"),
            "create_time": conv.get("create_time"),
            "messages": messages[:50],  # limit messages per conv
        }
    return json.dumps(data, indent=2)


def _conversations_to_markdown(conversations: list[dict]) -> str:
    """Convert conversations to markdown format."""
    lines = ["# Conversation Data\n"]
    for i, conv in enumerate(conversations[:5]):  # limit for test
        conv_id = conv.get("conversation_id", f"conv_{i}")
        lines.append(f"\n## Conversation {i}: {conv_id}\n")
        messages = _extract_messages(conv)
        for j, msg in enumerate(messages[:20]):  # limit messages
            lines.append(f"### Message {j}\n")
            lines.append(msg[:500])  # truncate long messages
            lines.append("\n")
    return "\n".join(lines)


class TestChunkerWithConversations:
    """Test chunker using real conversation files."""

    @pytest.fixture
    def convo_data(self):
        """Load conversation data from the data directory."""
        data_dir = Path("/home/callmeamps/Desktop/Projects/data")
        all_conversations = []
        for f in sorted(data_dir.glob("conversations-*.json")):
            with open(f) as fp:
                convs = json.load(fp)
                if isinstance(convs, list):
                    all_conversations.extend(convs)
        return all_conversations

    @pytest.fixture
    def store(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield MunkStore(tmp)

    def test_semantic_chunker_on_conversations(self, convo_data, store):
        """Test semantic chunker on conversation text."""
        if not convo_data:
            pytest.skip("No conversation data found")
        
        # Try to import and instantiate semantic chunker
        try:
            from munk.chunkers.semantic_chunker import SemanticChunker, EMBEDDING_AVAILABLE
            if not EMBEDDING_AVAILABLE:
                pytest.skip("Semantic chunker dependencies not installed")
            # Try instantiating to verify deps work
            _ = SemanticChunker(ChunkingConfig())
        except (ImportError, RuntimeError) as e:
            pytest.skip(f"Semantic chunker not available: {e}")

        # Use markdown format for semantic chunking
        content = _conversations_to_markdown(convo_data[:3])  # limit to 3 convs
        src = Source(
            source_id=new_id("src"),
            path="conversations_semantic.md",
            hash=hash_content(content),
            size_bytes=len(content),
            mime_type="text/markdown",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        store.save_source(src)

        manifest = chunkify(src, content, store, strategy="semantic")
        chunks = [store.load_chunk(cid) for cid in manifest.order]

        assert len(manifest.order) > 0, "Semantic chunker should produce chunks"
        assert all(c.content.strip() for c in chunks), "Chunks should not be empty"
        assert all(c.tags and "semantic" in c.tags for c in chunks), "Chunks should be tagged as semantic"

        print(f"✓ Semantic chunking: {len(manifest.order)} chunks from conversations")

    def test_chunk_json_conversations(self, convo_data, store):
        """Test chunking conversation data as JSON dict."""
        if not convo_data:
            pytest.skip("No conversation data found")

        content = _conversations_to_json_dict(convo_data)
        src = Source(
            source_id=new_id("src"),
            path="conversations.json",
            hash=hash_content(content),
            size_bytes=len(content),
            mime_type="application/json",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        store.save_source(src)

        manifest = chunkify(src, content, store, strategy="simple")
        chunks = [store.load_chunk(cid) for cid in manifest.order]

        assert len(manifest.order) > 1, "JSON dict should split into multiple chunks"
        assert all(c.content.strip() for c in chunks), "Chunks should not be empty"

        # Verify each chunk is valid JSON with one key
        for chunk in chunks:
            parsed = json.loads(chunk.content)
            assert isinstance(parsed, dict)
            assert len(parsed) == 1, f"Each chunk should have exactly one key, got {len(parsed)}"

        print(f"✓ JSON chunking: {len(manifest.order)} chunks from {len(convo_data)} conversations")

    def test_chunk_markdown_conversations(self, convo_data, store):
        """Test chunking conversation data as Markdown."""
        if not convo_data:
            pytest.skip("No conversation data found")

        content = _conversations_to_markdown(convo_data)
        src = Source(
            source_id=new_id("src"),
            path="conversations.md",
            hash=hash_content(content),
            size_bytes=len(content),
            mime_type="text/markdown",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        store.save_source(src)

        manifest = chunkify(src, content, store, strategy="simple")
        chunks = [store.load_chunk(cid) for cid in manifest.order]

        assert len(manifest.order) > 0, "Should produce at least one chunk"
        assert all(c.content.strip() for c in chunks), "Chunks should not be empty"

        # Markdown chunks should have headers
        assert any("#" in c.content for c in chunks), "Markdown chunks should contain headers"

        print(f"✓ Markdown chunking: {len(manifest.order)} chunks from conversations")

    def test_chunk_large_conversation_file(self, store):
        """Test chunking a single large conversation file."""
        data_dir = Path("/home/callmeamps/Desktop/Projects/data")
        conv_file = data_dir / "conversations-000.json"

        with open(conv_file) as fp:
            conversations = json.load(fp)

        if not conversations:
            pytest.skip("No conversations in file")

        # Take first conversation, extract all text
        conv = conversations[0]
        messages = _extract_messages(conv)
        content = "\n\n".join(messages)

        src = Source(
            source_id=new_id("src"),
            path="single_conversation.txt",
            hash=hash_content(content),
            size_bytes=len(content),
            mime_type="text/plain",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        store.save_source(src)

        manifest = chunkify(src, content, store, strategy="simple")
        chunks = [store.load_chunk(cid) for cid in manifest.order]

        assert len(manifest.order) > 0
        total_chunked = sum(len(c.content) for c in chunks)
        assert total_chunked <= len(content) + len(chunks) * 2  # allow small overhead

        print(f"✓ Single conv chunking: {len(manifest.order)} chunks, {len(content)} chars → {total_chunked} chunked")

    def test_roundtrip_conversation_chunks(self, convo_data, store):
        """Test that chunked conversation data can be reconstructed."""
        if not convo_data:
            pytest.skip("No conversation data found")

        content = _conversations_to_json_dict(convo_data)
        src = Source(
            source_id=new_id("src"),
            path="conversations.json",
            hash=hash_content(content),
            size_bytes=len(content),
            mime_type="application/json",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        store.save_source(src)

        manifest = chunkify(src, content, store, strategy="simple")

        # Reconstruct by parsing each chunk and merging
        reconstructed = {}
        for cid in manifest.order:
            chunk = store.load_chunk(cid)
            chunk_data = json.loads(chunk.content)
            reconstructed.update(chunk_data)

        original = json.loads(content)

        assert set(reconstructed.keys()) == set(original.keys()), "Keys should match after reconstruction"
        print(f"✓ Roundtrip: {len(manifest.order)} chunks, all {len(original)} keys preserved")
