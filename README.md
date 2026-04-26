# Munk

File versioning system. Split files into editable chunks, track changes, rebuild.

## Install

```bash
pip install -e .
```

Dev deps:
```bash
pip install -e ".[dev]"
```

## Usage

### API
```bash
export MUNK_DATA_ROOT=munk_data
munk-api
# → http://localhost:8000
```

### TUI
```bash
munk-tui
```

### Python
```python
from munk.store import MunkStore
from munk.models import Source
from munk.chunker import chunkify

store = MunkStore("munk_data")
# Create source, chunkify, edit chunks, assemble...
```

## Core Concepts

- **Source**: Immutable file snapshot. Never changes.
- **Chunk**: Mutable working unit derived from source. Edit these.
- **Manifest**: Reconstruction plan. Defines which chunks + order for export.
- **Lock**: Exclusive write access to a chunk.

See [UBIQUITOUS_LANGUAGE.md](UBIQUITOUS_LANGUAGE.md) for full domain glossary.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sources` | Create source |
| POST | `/sources/{id}/chunkify` | Split source into chunks |
| GET | `/chunks/{id}` | Get chunk |
| PATCH | `/chunks/{id}` | Edit chunk |
| POST | `/chunks/{id}/lock` | Lock chunk |
| POST | `/chunks/{id}/unlock` | Unlock chunk |
| POST | `/manifests/{id}/export` | Assemble + export |

## Development

```bash
pytest                    # Run tests
pytest --cov=munk        # Coverage
bd list                  # View issues (beads tracker)
```

## Project Structure

```
munk/          # Core engine
├── models.py     # Domain models
├── store.py      # JSON file store
├── chunker.py    # File → chunks
├── editor.py     # Edit chunks
├── assembler.py  # Chunks → file
├── api/          # FastAPI routes
tests/         # Test suite
tui/           # Textual TUI
web/           # Web frontend
```

## License

MIT
