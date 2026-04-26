"""
Create test data for contextual enrichment and hierarchical RAG testing.
"""

from munk.models import Source
from munk.store import MunkStore
from munk.chunker import chunkify
from munk.hashing import hash_content

def create_sample_documents():
    """Create sample documents for testing."""
    store = MunkStore("munk_data")
    
    # GDScript file
    gd_content = """# PlayerController.gd
extends CharacterBody2D

@export var speed: float = 200.0
@export var jump_velocity: float = -300.0

func _ready():
    pass

func _physics_process(delta):
    handle_movement(delta)

func handle_movement(delta):
    var direction = Input.get_axis("move_left", "move_right")
    if direction:
        velocity.x = direction * speed
    else:
        velocity.x = move_toward(velocity.x, 0, speed)

func jump():
    if is_on_floor():
        velocity.y = jump_velocity

func attack():
    print("Player attacks!")
"""

    gd_source = Source(
        source_id="src_player_controller",
        path="PlayerController.gd",
        hash=hash_content(gd_content),
        size_bytes=len(gd_content.encode()),
        mime_type="text/x-gdscript",
        created_at="2024-01-01T00:00:00.000000",
        origin="local",
        status="locked"
    )
    
    # Write source content if needed by chunker/store
    (store.root / "sources" / f"{gd_source.source_id}.content").write_text(gd_content)
    
    store.save_source(gd_source)
    chunkify(gd_source, gd_content, store)
    
    print(f"Created GDScript source: {gd_source.source_id}")

if __name__ == "__main__":
    create_sample_documents()
    print("Test data created successfully!")
