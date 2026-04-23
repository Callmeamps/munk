# tui/app.py

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, TextArea, Button
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
import difflib
import sys

from munk.store import MunkStore
from munk.editor import edit_chunk
from munk.assembler import assemble


class MunkTUI(App):
    """
    Munk TUI — three-panel layout:
    Chunk List | Diff/Content View | Actions
    """

    CSS = """
    #chunk-list  { width: 30%; border: solid green; }
    #diff-view   { width: 50%; border: solid blue; }
    #actions     { width: 20%; border: solid yellow; }
    Button       { margin: 1 0; width: 100%; }
    Label        { padding: 1; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("a", "approve_chunk", "Approve"),
        ("r", "reject_chunk", "Reject"),
        ("e", "export", "Export"),
    ]

    selected_chunk_id: reactive[str | None] = reactive(None)

    def __init__(self, store: MunkStore, manifest_id: str):
        super().__init__()
        self.store = store
        self.manifest_id = manifest_id

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ListView(id="chunk-list")
            yield TextArea(id="diff-view", read_only=True)
            with Vertical(id="actions"):
                yield Button("Approve (A)", id="btn-approve", variant="success")
                yield Button("Reject (R)",  id="btn-reject",  variant="error")
                yield Button("Export (E)",  id="btn-export",  variant="primary")
        yield Footer()

    def on_mount(self):
        self._refresh_chunk_list()

    def _refresh_chunk_list(self):
        manifest = self.store.load_manifest(self.manifest_id)
        list_view = self.query_one("#chunk-list", ListView)
        list_view.clear()
        for chunk_id in manifest.order:
            chunk = self.store.load_chunk(chunk_id)
            status_char = chunk.status[:1].upper()
            label = f"[{status_char}] {chunk.title or chunk_id}"
            list_view.append(ListItem(Label(label), id=chunk_id))

    def on_list_view_selected(self, event: ListView.Selected):
        if event.item and event.item.id:
            self.selected_chunk_id = str(event.item.id)
            self._show_content(self.selected_chunk_id)

    def _show_content(self, chunk_id: str):
        """Show the current content of the chunk."""
        chunk = self.store.load_chunk(chunk_id)
        text_area = self.query_one("#diff-view", TextArea)
        text_area.load_text(chunk.content)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-approve":
            self.action_approve_chunk()
        elif event.button.id == "btn-reject":
            self.action_reject_chunk()
        elif event.button.id == "btn-export":
            self.action_export()

    def action_approve_chunk(self):
        if self.selected_chunk_id:
            chunk = self.store.load_chunk(self.selected_chunk_id)
            edit_chunk(
                chunk_id    = self.selected_chunk_id,
                new_content = chunk.content,
                store       = self.store,
                status      = "approved",
                note        = "Approved via TUI",
            )
            self._refresh_chunk_list()
            self.notify(f"Approved {self.selected_chunk_id}")

    def action_reject_chunk(self):
        if self.selected_chunk_id:
            chunk = self.store.load_chunk(self.selected_chunk_id)
            edit_chunk(
                chunk_id    = self.selected_chunk_id,
                new_content = chunk.content,
                store       = self.store,
                status      = "draft",
                note        = "Rejected via TUI",
            )
            self._refresh_chunk_list()
            self.notify(f"Rejected {self.selected_chunk_id}")

    def action_export(self):
        try:
            path = assemble(self.manifest_id, "export_output.txt", self.store)
            self.notify(f"Exported to {path.name}")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

def main():
    if len(sys.argv) < 2:
        print("Usage: python tui/app.py <manifest_id>")
        sys.exit(1)
    
    store = MunkStore("munk_data")
    app = MunkTUI(store=store, manifest_id=sys.argv[1])
    app.run()

if __name__ == "__main__":
    main()
