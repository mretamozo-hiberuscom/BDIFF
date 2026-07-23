"""The Textual App subclass: layout composition, key bindings, reactive
filter state, and widget wiring for the interactive findings browser."""

import io
import sys

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Input, Label, Static, Tree

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
    """Single-screen, findings browser for a `ComparisonResult`
    with enterprise-grade dashboard styling, in-memory exclude editing,
    re-run comparison, and report generation."""

    DEFAULT_CSS = """
    SchemaComparatorApp {
        background: $background;
        color: $text;
    }
    
    #main-body {
        layout: horizontal;
        height: 1fr;
    }
    
    #left-container {
        width: 40%;
        height: 100%;
        layout: vertical;
        border-right: tall $primary-darken-1;
    }
    
    #right-container {
        width: 60%;
        height: 100%;
        layout: vertical;
    }
    
    #filter-input {
        margin: 1 1 0 1;
        border: tall $primary-darken-2;
        background: $surface;
    }
    
    #filter-input:focus {
        border: double $accent;
    }
    
    #findings-tree {
        height: 1fr;
        margin: 0 1 1 1;
        border: round $primary;
        scrollbar-gutter: stable;
    }
    
    #findings-tree:focus {
        border: double $accent;
    }
    
    #detail-panel {
        height: 100%;
        margin: 1;
        padding: 1 2;
        border: round $primary;
        background: $surface;
        scrollbar-gutter: stable;
        overflow-y: auto;
    }
    
    #detail-panel:focus {
        border: double $accent;
    }

    #bottom-container {
        height: 8;
        layout: horizontal;
        border-top: tall $primary-darken-1;
        background: $surface-darken-1;
    }
    
    #exclude-container {
        width: 50%;
        height: 100%;
        layout: vertical;
        padding: 0 1;
        border-right: solid $primary-darken-2;
    }
    
    #exclude-label {
        text-style: bold;
        color: $accent;
        margin: 1 0 0 1;
    }
    
    #exclude-editor {
        margin: 0 1 1 1;
        border: round $primary;
        background: $background;
    }
    
    #exclude-editor:focus {
        border: double $accent;
    }
    
    #log-container {
        width: 50%;
        height: 100%;
        layout: vertical;
        padding: 0 1;
    }
    
    #log-label {
        text-style: bold;
        color: $accent;
        margin: 1 0 0 1;
    }
    
    #status-log {
        height: 1fr;
        margin: 0 1 1 1;
        border: round $primary;
        background: $background;
        scrollbar-gutter: stable;
    }
    
    #status-log:focus {
        border: double $accent;
    }
    
    SummaryHeader {
        background: $primary;
        color: $text;
        text-style: bold;
        height: 3;
        content-align: center middle;
        text-align: center;
        border-bottom: tall $primary-darken-2;
    }

    #no-drift-container {
        align: center middle;
        height: 1fr;
    }
    #no-drift-message {
        text-style: bold;
        color: $success;
        border: double $success;
        padding: 2 4;
        background: $surface;
        content-align: center middle;
        text-align: center;
        height: 7;
        width: 60;
    }
    """

    BINDINGS = [
        Binding("q,Q", "quit", "Quit"),
        Binding("escape", "quit", "Quit", show=False),
        Binding("slash", "focus_filter", "Filter"),
        Binding("e,E", "focus_exclude_editor", "Editar excludes"),
        Binding("r,R", "run_comparison", "Re-ejecutar comparación"),
        Binding("g,G", "generate_reports", "Generar reportes"),
        Binding("d,D", "open_decision_screen", "Consolidar Diferencias"),
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
            with Container(id="no-drift-container"):
                yield Static(_NO_DRIFT_MESSAGE, id="no-drift-message")
        else:
            with Container(id="main-body"):
                with Vertical(id="left-container"):
                    yield Input(
                        placeholder="Filtrar por tabla, columna o tipo de diferencia… (Presiona /)",
                        id="filter-input",
                    )
                    yield FindingsTree(self._tree_data, id="findings-tree")
                with Vertical(id="right-container"):
                    yield DetailPanel(id="detail-panel")
        with Horizontal(id="bottom-container"):
            with Vertical(id="exclude-container"):
                yield Label("Excluir tablas (coincidencia de texto, separadas por espacio):", id="exclude-label")
                yield ExcludeEditor(self._exclude_patterns, id="exclude-editor")
            with Vertical(id="log-container"):
                yield Label("Registro de actividad:", id="log-label")
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
            self.call_from_thread(self.query_one(StatusLog).info, buffer.getvalue())
        except Exception as exc:
            self.call_from_thread(
                self.query_one(StatusLog).error,
                f"Falló la generación de reportes: {exc}",
            )

    def action_open_decision_screen(self) -> None:
        from schema_comparator.tui.decision_screen import DecisionScreen
        from schema_comparator.compare.models import ColumnMismatch, MissingColumn, MissingTable
        from pathlib import Path

        relevant_entries = [
            e for e in self._result.entries
            if isinstance(e, (ColumnMismatch, MissingColumn, MissingTable))
        ]
        if not relevant_entries:
            self.query_one(StatusLog).info("No hay diferencias de tablas, atributos o columnas para consolidar.")
            return

        def handle_decision_screen_result(result) -> None:
            if result is None:
                self.query_one(StatusLog).info("Consolidación cancelada.")
            elif not result:
                self.query_one(StatusLog).info("Consolidación exitosa. No se generaron archivos SQL.")
            else:
                subfolder = Path(result[0]).parent.name
                self.query_one(StatusLog).info(
                    f"Consolidación exitosa. Scripts generados en 'scripts-db/{subfolder}/': "
                    f"{', '.join(Path(f).name for f in result)}"
                )

        # Hallar la raíz del proyecto
        repo_root = Path(__file__).resolve().parents[3]

        profiles_to_pass = self._profiles
        if not profiles_to_pass:
            from schema_comparator.config.models import ConnectionProfile
            profiles_to_pass = [
                ConnectionProfile(name=p, connection_string=f"Database={p};")
                for p in self._result.compared_profiles
            ]

        self.push_screen(
            DecisionScreen(
                entries=tuple(relevant_entries),
                profiles=tuple(profiles_to_pass),
                repo_root=repo_root
            ),
            callback=handle_decision_screen_result
        )


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

