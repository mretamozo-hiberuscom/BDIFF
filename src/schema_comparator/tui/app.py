"""The Textual App subclass: layout composition, key bindings, reactive
filter state, and widget wiring for the interactive findings browser."""

import sys

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Footer, Input, Static, Tree

from schema_comparator.compare.models import ComparisonResult
from schema_comparator.tui.formatting import build_tree_data, header_text
from schema_comparator.tui.widgets import DetailPanel, FindingsTree, SummaryHeader

_NO_DRIFT_MESSAGE = "No se detectaron diferencias entre los perfiles comparados."


class SchemaComparatorApp(App):
    """Single-screen, read-only findings browser for a `ComparisonResult`."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit", show=False),
        Binding("slash", "focus_filter", "Filter"),
    ]

    filter_text: reactive[str] = reactive("")

    def __init__(self, result: ComparisonResult) -> None:
        super().__init__()
        self._result = result
        self._tree_data = build_tree_data(result)

    def compose(self) -> ComposeResult:
        yield SummaryHeader(header_text(self._result))
        if not self._tree_data.groups:
            yield Static(_NO_DRIFT_MESSAGE, id="no-drift-message")
        else:
            yield Input(
                placeholder="Filtrar por tabla, columna o tipo de diferencia…",
                id="filter-input",
            )
            yield FindingsTree(self._tree_data, id="findings-tree")
            yield DetailPanel(id="detail-panel")
        yield Footer()

    def action_focus_filter(self) -> None:
        filter_inputs = self.query("#filter-input")
        if filter_inputs:
            filter_inputs.first().focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self.filter_text = event.value

    def watch_filter_text(self, filter_text: str) -> None:
        trees = self.query(FindingsTree)
        if trees:
            trees.first().apply_filter(filter_text)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        detail_panels = self.query(DetailPanel)
        if detail_panels:
            detail_panels.first().show(event.node.data)


def run_tui(result: ComparisonResult) -> None:
    """Launch the interactive TUI. Any exception raised while running is
    caught and reported to stderr rather than propagating as an unhandled
    exception (REQ-interactive-tui-008)."""
    app = SchemaComparatorApp(result)
    try:
        app.run()
    except Exception as exc:
        print(f"[ERROR] Falló la interfaz interactiva: {exc}", file=sys.stderr)
