"""The Textual App subclass: layout composition, key bindings, reactive
filter state, and widget wiring for the interactive findings browser."""

import io
import sys

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Footer, Input, Static, Tree

from schema_comparator.compare.models import ComparisonResult
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.report.write import generate_all_reports
from schema_comparator.tui.actions import run_comparison
from schema_comparator.tui.formatting import build_tree_data, header_text
from schema_comparator.tui.widgets import (
    DetailPanel,
    ExcludeEditor,
    FindingsTree,
    StatusLog,
    SummaryHeader,
)

_NO_DRIFT_MESSAGE = "No se detectaron diferencias entre los perfiles comparados."


class SchemaComparatorApp(App):
    """Single-screen, read-only findings browser for a `ComparisonResult`,
    with in-memory exclude editing, re-run comparison, and on-demand
    report generation actions (REQ-interactive-tui-011/012/013)."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit", show=False),
        Binding("slash", "focus_filter", "Filter"),
        Binding("e", "focus_exclude_editor", "Editar excludes"),
        Binding("r", "run_comparison", "Re-ejecutar comparación"),
        Binding("g", "generate_reports", "Generar reportes"),
    ]

    filter_text: reactive[str] = reactive("")

    def __init__(
        self,
        result: ComparisonResult,
        *,
        profiles: list[ConnectionProfile] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._result = result
        self._tree_data = build_tree_data(result)
        self._profiles = profiles or []
        self._exclude_patterns = list(exclude_patterns or [])

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
        yield ExcludeEditor(self._exclude_patterns, id="exclude-editor")
        yield StatusLog(id="status-log")
        yield Footer()

    def action_focus_filter(self) -> None:
        filter_inputs = self.query("#filter-input")
        if filter_inputs:
            filter_inputs.first().focus()

    def action_focus_exclude_editor(self) -> None:
        editors = self.query("#exclude-editor")
        if editors:
            editors.first().focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self.filter_text = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "exclude-editor":
            self._exclude_patterns = event.value.split()
            self.action_run_comparison()

    def watch_filter_text(self, filter_text: str) -> None:
        trees = self.query(FindingsTree)
        if trees:
            trees.first().apply_filter(filter_text)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        detail_panels = self.query(DetailPanel)
        if detail_panels:
            detail_panels.first().show(event.node.data)

    def action_run_comparison(self) -> None:
        if not self._profiles:
            self.query_one(StatusLog).error(
                "No hay perfiles cargados; no se puede ejecutar la comparación."
            )
            return
        self.query_one(StatusLog).info("Ejecutando comparación…")
        self.run_worker(self._do_run_comparison, exclusive=True, thread=True)

    def _do_run_comparison(self) -> None:
        try:
            new_result = run_comparison(self._profiles, self._exclude_patterns)
        except Exception as exc:
            self.call_from_thread(
                self.query_one(StatusLog).error,
                f"Falló la comparación: {exc}",
            )
            return
        self.call_from_thread(self._apply_new_result, new_result)

    def _apply_new_result(self, new_result: ComparisonResult) -> None:
        self._result = new_result
        self._tree_data = build_tree_data(new_result)
        trees = self.query(FindingsTree)
        if trees:
            trees.first().populate(self._tree_data)
        self.query_one(SummaryHeader).update(header_text(new_result))
        self.query_one(StatusLog).info("Comparación actualizada.")

    def action_generate_reports(self) -> None:
        self.query_one(StatusLog).info("Generando reportes…")
        self.run_worker(self._do_generate_reports, exclusive=True, thread=True)

    def _do_generate_reports(self) -> None:
        buffer = io.StringIO()
        try:
            generate_all_reports(self._result, out=buffer)
        finally:
            self.call_from_thread(self.query_one(StatusLog).info, buffer.getvalue())


def run_tui(
    result: ComparisonResult,
    *,
    profiles: list[ConnectionProfile] | None = None,
    exclude_patterns: list[str] | None = None,
) -> None:
    """Launch the interactive TUI. Any exception raised while running is
    caught and reported to stderr rather than propagating as an unhandled
    exception (REQ-interactive-tui-008)."""
    app = SchemaComparatorApp(
        result, profiles=profiles, exclude_patterns=exclude_patterns
    )
    try:
        app.run()
    except Exception as exc:
        print(f"[ERROR] Falló la interfaz interactiva: {exc}", file=sys.stderr)

