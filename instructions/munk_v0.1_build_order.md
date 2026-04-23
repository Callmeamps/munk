# Munk v0.1 — Build Order

This document orders every task in the implementation by dependency and importance. Nothing in a later step can be built until everything it depends on is done and tested. Setup and git are treated as first-class steps, not afterthoughts.

---

## Dependency Map

```
git + repo setup
        ↓
pyproject.toml + venv
        ↓
ids.py → hashing.py → models.py → store.py     ← Phase 1 (engine foundation)
                                      ↓
                               chunker_config.py → chunker.py   ← Phase 2
                                      ↓
                        locker.py → editor.py    ← Phase 3
                                      ↓
                        validator.py → assembler.py   ← Phase 4
                                      ↓
                         ┌────────────┴──────────────┐
                       tui/app.py              api/routes.py    ← Phase 5 & 6
                                                     ↓
                                              web/index.html    ← Phase 7
```

Each column in Phase 1 is also a dependency chain left to right: `ids` has no deps, `hashing` has no deps, `models` depends on both, `store` depends on `models`.

---

## Step 0 — Git and Repository Setup

**Why first:** Everything else lives inside the repo. The `.gitignore` determines what never touches version control. Getting this wrong means committing runtime data or secrets.

### 0.1 — Initialise the repo

```bash
mkdir munk
cd munk
git init
git branch -M main
```

### 0.2 — Create `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.eggs/

# Virtual environment
.venv/
venv/
env/

# Munk runtime data — never commit sources, chunks, or exports
munk_data/

# OS
.DS_Store
Thumbs.db

# Editor
.vscode/
.idea/
*.swp

# Test artifacts
.pytest_cache/
.coverage
htmlcov/

# Environment
.env
```

**Why `munk_data/` is gitignored:** It contains user source snapshots, chunk edits, and exports. These are runtime state, not project code. If you want to commit example data for tests, put it in `tests/fixtures/` instead and keep `munk_data/` clean.

### 0.3 — Create the directory skeleton

```bash
mkdir -p munk/api
mkdir -p tui
mkdir -p tests
mkdir -p examples
mkdir -p web/static
touch munk/__init__.py
touch munk/api/__init__.py
touch README.md
```

### 0.4 — First commit

```bash
git add .gitignore README.md
git commit -m "chore: init repo"
```

Commit only the gitignore and README. Nothing else exists yet.

---

## Step 1 — Python Environment and Project Metadata

**Why before any code:** The virtual environment and `pyproject.toml` define what Python version and packages are available. Writing code before this means you cannot run or test anything.

### 1.1 — Create `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "munk"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.29.0",
    "textual>=0.55.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",       # required for FastAPI test client
    "pytest-cov>=5.0",
]

[project.scripts]
munk-api = "munk.api.routes:app"
munk-tui = "tui.app:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### 1.2 — Create and activate the virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

pip install -e ".[dev]"
```

The `-e` flag installs the package in editable mode so `from munk.models import ...` works immediately without reinstalling after every code change.

### 1.3 — Verify

```bash
python --version    # must be 3.11+
pytest --version    # must resolve
uvicorn --version   # must resolve
```

### 1.4 — Commit

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml and dev dependencies"
```

Do not commit `.venv/`. It is already gitignored.

---

## Step 2 — `ids.py` (no dependencies)

**Why here:** Every other module calls `new_id`. It has zero imports from the project and is trivially testable. Build and test it in isolation before anything else touches it.

```bash
# Write munk/ids.py (see implementation guide)
# Then verify manually:
python -c "from munk.ids import new_id; print(new_id('src'))"
# Expected: src_3f2a1b  (six-char hex suffix varies)
```

Commit:

```bash
git add munk/ids.py
git commit -m "feat: add ID generation (ids.py)"
```

---

## Step 3 — `hashing.py` (no dependencies)

**Why here:** `models.py` and `store.py` both need `hash_content` and `verify_content`. Like `ids.py`, this has no internal imports. Build and verify before writing models.

```bash
python -c "
from munk.hashing import hash_content, verify_content
h = hash_content('hello')
print(h)                                # sha256:2cf24d...
print(verify_content('hello', h))       # True
print(verify_content('world', h))       # False
"
```

Commit:

```bash
git add munk/hashing.py
git commit -m "feat: add content hashing (hashing.py)"
```

---

## Step 4 — `models.py` (depends on: ids, hashing)

**Why here:** All five data objects — `Source`, `Chunk`, `Manifest`, `ChunkHistory`, `Lock` — must exist before the store, chunker, editor, or assembler can reference them. Write the dataclasses, `to_dict`, `to_json`, and `from_dict` for each. Add `__post_init__` validation on `Chunk.status` and `Manifest` order consistency.

Write the model tests at the same time:

```bash
# tests/test_models.py — see implementation guide
pytest tests/test_models.py -v
```

All tests must pass before proceeding.

Commit:

```bash
git add munk/models.py tests/test_models.py
git commit -m "feat: add data models and model tests (models.py)"
```

---

## Step 5 — `store.py` (depends on: models)

**Why here:** The store is the I/O layer that everything else sits on top of. The chunker writes chunks through it, the editor reads and writes chunks through it, the assembler reads through it. It must exist and be correct before any of those can work.

Key behaviours to verify manually:

```bash
python -c "
import tempfile, os
from munk.store import MunkStore
from munk.models import Source
from munk.ids import new_id
from munk.hashing import hash_content
from datetime import datetime, timezone

with tempfile.TemporaryDirectory() as tmp:
    store = MunkStore(tmp)

    src = Source(
        source_id=new_id('src'), path='/test.gd',
        hash=hash_content('hello'), size_bytes=5,
        mime_type='text/plain',
        created_at=datetime.now(timezone.utc).isoformat()
    )
    store.save_source(src)

    # Must raise on second save (write-once)
    try:
        store.save_source(src)
        print('ERROR: should have raised')
    except FileExistsError:
        print('OK: write-once enforced')

    loaded = store.load_source(src.source_id)
    print('OK: source roundtrip', loaded.source_id == src.source_id)
"
```

Commit:

```bash
git add munk/store.py
git commit -m "feat: add flat-file JSON store (store.py)"
```

At this point Phase 1 is complete. The engine foundation is done.

---

## Step 6 — `chunker_config.py` (depends on: nothing)

**Why before chunker:** The config is a pure data file — compiled regex patterns keyed by extension. Separating it means the chunker logic and the format definitions can change independently. Add the config, verify the patterns compile, then move on.

```bash
python -c "
from munk.chunker_config import get_boundaries, SUPPORTED_EXTENSIONS
print(SUPPORTED_EXTENSIONS)           # {'gd', 'md', 'txt', 'json'}
b = get_boundaries('gd')
print(b[0].match('func _ready():'))   # Match object
print(b[0].match('var x = 1'))        # None
"
```

Commit:

```bash
git add munk/chunker_config.py
git commit -m "feat: add chunker format config (chunker_config.py)"
```

---

## Step 7 — `chunker.py` (depends on: store, models, ids, hashing, chunker_config)

**Why here:** The chunker is the entry point for all real file content. Without it, the only way to create chunks is by hand. It converts a source + raw file content into a set of Chunk objects and a Manifest.

Write and run the chunker tests before continuing:

```bash
# tests/test_chunker.py — see implementation guide
pytest tests/test_chunker.py -v
```

Also do a live run against the sample files:

```bash
# Create examples/sample.gd with the content from the implementation guide
python -c "
import tempfile
from munk.store import MunkStore
from munk.models import Source
from munk.ids import new_id
from munk.hashing import hash_content, hash_file
from munk.chunker import chunkify
from datetime import datetime, timezone
import os

store = MunkStore('munk_data')
content = open('examples/sample.gd').read()

src = Source(
    source_id  = new_id('src'),
    path       = 'examples/sample.gd',
    hash       = hash_content(content),
    size_bytes = len(content.encode()),
    mime_type  = 'text/x-gdscript',
    created_at = datetime.now(timezone.utc).isoformat(),
)
store.save_source(src)
manifest = chunkify(src, content, store)
print('manifest_id:', manifest.manifest_id)
print('chunks:', manifest.order)
"
```

Inspect the output files in `munk_data/chunks/` to confirm titles and content look correct.

Commit:

```bash
git add munk/chunker.py tests/test_chunker.py examples/
git commit -m "feat: add line-scanning chunker and example files (chunker.py)"
```

---

## Step 8 — `locker.py` (depends on: store, models, ids)

**Why before editor:** The editor checks lock state before allowing edits. `locker.py` must exist and be correct so the editor can import it. It is also simple enough to build and test quickly.

```bash
python -c "
import tempfile
from munk.store import MunkStore
from munk.locker import lock_chunk, unlock_chunk, LockError

with tempfile.TemporaryDirectory() as tmp:
    store = MunkStore(tmp)
    lock = lock_chunk('chk_test', owner='agent_007', store=store)
    print('locked:', lock.lock_id)

    # Double-lock must raise
    try:
        lock_chunk('chk_test', owner='agent_008', store=store)
        print('ERROR: should have raised')
    except LockError as e:
        print('OK: double-lock blocked:', e)

    unlock_chunk('chk_test', owner='agent_007', store=store)
    print('unlocked OK')

    # Wrong owner unlock must raise
    lock_chunk('chk_test', owner='agent_007', store=store)
    try:
        unlock_chunk('chk_test', owner='agent_008', store=store)
        print('ERROR: should have raised')
    except LockError as e:
        print('OK: wrong owner blocked:', e)
"
```

Commit:

```bash
git add munk/locker.py
git commit -m "feat: add lock/unlock (locker.py)"
```

---

## Step 9 — `editor.py` (depends on: store, models, ids, hashing, locker)

**Why here:** The editor is the only legal way for an agent to mutate chunk content. It enforces all the rules: no edits to locked chunks, no edits to archived chunks, version increment, hash update, history record. This is the most safety-critical module in the engine.

Write `tests/test_editor.py` to cover:

- Successful edit increments version and updates hash
- Edit on locked chunk raises `EditError`
- Edit on archived chunk raises `EditError`
- History entry is written after every edit
- Empty content raises `EditError`

```bash
pytest tests/test_editor.py -v
```

Commit:

```bash
git add munk/editor.py tests/test_editor.py
git commit -m "feat: add chunk editor with versioning and history (editor.py)"
```

---

## Step 10 — `validator.py` (depends on: store, models, hashing)

**Why before assembler:** The assembler calls the validator before writing any output. The validator must exist as a separate module so it can also be called independently (e.g. from the API or TUI before export).

The validator checks:

- Source reference exists
- Content hash matches content
- Chunk is not archived
- All chunk IDs in manifest exist
- `chunks` and `order` sets are identical

```bash
pytest tests/test_assembler.py::test_validation -v   # write this test first
```

Commit:

```bash
git add munk/validator.py
git commit -m "feat: add chunk and manifest validation (validator.py)"
```

---

## Step 11 — `assembler.py` (depends on: store, models, validator)

**Why here:** The assembler is the payoff for all previous steps. It proves the full pipeline works end-to-end. The round-trip test (import source → chunkify → edit a chunk → assemble → compare output) is the most important test in the project.

```bash
pytest tests/test_assembler.py -v
```

The round-trip test must pass exactly. If it does not, debug before moving on — the assembler is the correctness proof for everything above it.

Commit:

```bash
git add munk/assembler.py tests/test_assembler.py
git commit -m "feat: add manifest assembler and round-trip test (assembler.py)"
```

**Phase 1–4 (the engine) is now complete.** Run the full test suite:

```bash
pytest --cov=munk tests/ -v
```

All tests must pass. Tag this point:

```bash
git tag v0.1-engine
```

---

## Step 12 — TUI (depends on: store, editor, assembler, locker)

**Why here:** The TUI is the first interface. It is also the first time a human interacts with the engine in real time. Building it before the API means you find UX problems early without needing an HTTP client.

Install `textual` if not already present (it is in `pyproject.toml`, so `pip install -e .` should have covered it):

```bash
python -m textual --version
```

Run the TUI against real data from Step 7:

```bash
python tui/app.py
# Replace manifest_id in tui/app.py __main__ block with the one from Step 7
```

Check that:

- Chunk list renders and is scrollable
- Selecting a chunk shows its content in the diff panel
- Approve changes status to `approved`
- Reject resets status to `draft`
- Export writes to `munk_data/exports/`

No tests are written for the TUI in v0.1. Manual verification is sufficient.

Commit:

```bash
git add tui/app.py
git commit -m "feat: add Textual TUI with chunk list, diff view, approve/reject/export"
```

---

## Step 13 — API (depends on: store, chunker, editor, locker, assembler, validator)

**Why here:** The API wraps the entire engine as an HTTP service. It is the contract that the web app and any external agent will use. Get it right before building the frontend against it.

Start the server:

```bash
uvicorn munk.api.routes:app --reload --port 8000
```

Verify every endpoint manually using the interactive docs at `http://localhost:8000/docs`:

1. `POST /sources` — register a source
2. `POST /sources/{id}/chunkify` — produce chunks and manifest
3. `GET /chunks/{id}` — retrieve a chunk
4. `PATCH /chunks/{id}` — edit a chunk
5. `POST /chunks/{id}/lock` — lock a chunk
6. `POST /chunks/{id}/unlock` — unlock a chunk
7. `GET /manifests/{id}` — retrieve a manifest
8. `POST /manifests/{id}/export` — reconstruct the file

Write an integration test using `httpx` and FastAPI's `TestClient`:

```python
# tests/test_api.py

from fastapi.testclient import TestClient
from munk.api.routes import app
import tempfile, os

client = TestClient(app)

def test_create_source_and_chunkify():
    res = client.post("/sources", json={
        "path": "test.gd",
        "mime_type": "text/x-gdscript",
        "content": "extends Node\n\nfunc _ready():\n    pass\n",
    })
    assert res.status_code == 201
    source_id = res.json()["source_id"]

    res2 = client.post(f"/sources/{source_id}/chunkify", json={})
    assert res2.status_code == 201
    manifest_id = res2.json()["manifest_id"]
    chunk_ids = res2.json()["chunk_ids"]
    assert len(chunk_ids) >= 1

    res3 = client.post(f"/manifests/{manifest_id}/export", json={
        "output_filename": "test_out.gd"
    })
    assert res3.status_code == 201
    assert "output_path" in res3.json()
```

```bash
pytest tests/test_api.py -v
```

Commit:

```bash
git add munk/api/routes.py tests/test_api.py
git commit -m "feat: add FastAPI routes and API integration test (api/routes.py)"
```

---

## Step 14 — Web App (depends on: API)

**Why last:** The web app is a thin frontend over the API. Every feature it exposes already works and is tested. Building it last means there is nothing to debug except presentation.

Serve it from the API:

```bash
# Add static mount to munk/api/routes.py (see implementation guide)
# Create web/index.html and web/static/app.js
uvicorn munk.api.routes:app --reload --port 8000
# Open http://localhost:8000
```

Minimum viable web UI for v0.1:

- Text input for manifest ID → load button
- Chunk list rendered from manifest order
- Click a chunk to see its content
- Approve / Reject buttons per chunk
- Export button that calls `/manifests/{id}/export`

No framework. Plain HTML, CSS, and the fetch calls from the implementation guide.

No automated tests for the web UI in v0.1. Test manually in the browser.

Commit:

```bash
git add web/ munk/api/routes.py
git commit -m "feat: add web UI served from FastAPI (web/)"
```

Tag the full v0.1 release:

```bash
git tag v0.1.0
```

---

## Full Build Order Summary

| Step | Module | Depends On | Phase | Commit Message |
|---|---|---|---|---|
| 0 | git init, `.gitignore` | — | Setup | `chore: init repo` |
| 1 | `pyproject.toml`, venv | git | Setup | `chore: add pyproject.toml and dev dependencies` |
| 2 | `ids.py` | — | 1 | `feat: add ID generation` |
| 3 | `hashing.py` | — | 1 | `feat: add content hashing` |
| 4 | `models.py` + `test_models.py` | ids, hashing | 1 | `feat: add data models and model tests` |
| 5 | `store.py` | models | 1 | `feat: add flat-file JSON store` |
| 6 | `chunker_config.py` | — | 2 | `feat: add chunker format config` |
| 7 | `chunker.py` + `test_chunker.py` + examples | store, models, ids, hashing, chunker_config | 2 | `feat: add line-scanning chunker and example files` |
| 8 | `locker.py` | store, models, ids | 3 | `feat: add lock/unlock` |
| 9 | `editor.py` + `test_editor.py` | store, models, ids, hashing, locker | 3 | `feat: add chunk editor with versioning and history` |
| 10 | `validator.py` | store, models, hashing | 4 | `feat: add chunk and manifest validation` |
| 11 | `assembler.py` + `test_assembler.py` | store, models, validator | 4 | `feat: add manifest assembler and round-trip test` |
| — | **Tag: v0.1-engine** | all above | — | engine complete |
| 12 | `tui/app.py` | store, editor, assembler, locker | 5 | `feat: add Textual TUI` |
| 13 | `api/routes.py` + `test_api.py` | all engine modules | 6 | `feat: add FastAPI routes and API integration test` |
| 14 | `web/` | API | 7 | `feat: add web UI served from FastAPI` |
| — | **Tag: v0.1.0** | all | — | full v0.1 release |

---

## Rules for This Build

- Never skip a step. Every step has a dependency.
- Never start a new step with failing tests from the previous one.
- Commit at the end of every step — not at the end of the day.
- `munk_data/` is always gitignored. Test data lives in `tests/fixtures/` or in `tempfile.TemporaryDirectory()`.
- The engine tag (`v0.1-engine`) is the stability checkpoint. Do not start the TUI or API until that tag is clean.
- The API is the source of truth for the web app. If the API changes, update the web app before tagging.
