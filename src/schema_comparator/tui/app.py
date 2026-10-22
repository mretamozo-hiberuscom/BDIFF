"""The Textual App subclass: layout composition, key bindings, reactive
filter state, and widget wiring for the interactive findings browser."""

import io
import sys

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.events import Resize
from textual.reactive import reactive
from textual.widgets import Footer, Input, Label, Static, Tree

from schema_comparator.compare.models import ComparisonResult
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ComparisonFilters
from schema_comparator.domain.errors import describe_error
from schema_comparator.report.write import generate_all_reports
from schema_comparator.tui.actions import run_comparison
from schema_comparator.tui.formatting import build_tree_data
from schema_comparator.tui.modals import HelpModal, QuitModal
from schema_comparator.tui.theme import OK
from schema_comparator.tui.widgets import (
    DetailPanel,
    ExcludeEditor,
    FindingsTree,
    StatusLog,
    SummaryHeader,
)

_NO_DRIFT_MESSAGE = (
    f"{OK} No se detectaron diferencias entre los perfiles comparados.\n\n"
    "r  volver a comparar      e  ajustar exclusiones      g  generar reportes"
)

# Below this width the findings and their detail stack instead of sitting
# side by side.
_NARROW_WIDTH = 110


class SchemaComparatorApp(App):
    """Single-screen findings browser for a `ComparisonResult`: summary,
    findings tree with its detail card, and a drawer with the exclude
    editor and the activity log. Re-runs the comparison, generates reports
    and opens the consolidation and routines screens."""

    TITLE = "BDIFF"

    DEFAULT_CSS = """
    SchemaComparatorApp {
        background: $background;
        color: $text;
    }

    SummaryHeader {
        height: auto;
        padding: 0 2;
        background: $panel;
        border-bottom: solid $primary;
    }

    #content {
        height: 1fr;
    }

    #main-body {
        layout: horizontal;
        height: 1fr;
    }

    #left-container {
        width: 5fr;
        height: 100%;
    }

    #right-container {
        width: 4fr;
        height: 100%;
    }

    SchemaComparatorApp.-narrow #main-body {
        layout: vertical;
    }

    SchemaComparatorApp.-narrow #left-container,
    SchemaComparatorApp.-narrow #right-container {
        width: 100%;
        height: 1fr;
    }

    #filter-input {
        margin: 1 1 0 1;
    }

    #findings-tree {
        height: 1fr;
        margin: 0 1 1 1;
        border: round $primary-darken-1;
        border-title-color: $text;
        border-subtitle-color: $warning;
        scrollbar-gutter: stable;
        scrollbar-size-horizontal: 0;
    }

    #findings-tree:focus {
        border: round $accent;
    }

    #detail-panel {
        height: 100%;
        margin: 1;
        padding: 1 2;
        border: round $primary-darken-1;
        background: $surface;
        scrollbar-gutter: stable;
        overflow-y: auto;
    }

    #drawer {
        display: none;
        height: 11;
        background: $panel;
        border-top: solid $primary;
    }

    #drawer.-open {
        display: block;
    }

    #exclude-container, #log-container {
        width: 1fr;
        height: 100%;
        padding: 0 1;
    }

    #exclude-container {
        border-right: solid $primary-darken-2;
    }

    .drawer-title {
        text-style: bold;
        color: $accent;
        margin: 1 0 0 1;
    }

    .drawer-hint {
        color: $text-muted;
        margin: 0 0 0 1;
    }

    #exclude-editor {
        margin: 1 1 0 1;
    }

    #status-log {
        height: 1fr;
        margin: 0 1 1 1;
        border: round $primary-darken-1;
        background: $background;
        scrollbar-gutter: stable;
    }

    #no-drift-container {
        align: center middle;
        height: 1fr;
    }

    #no-drift-message {
        color: $success;
        border: round $success;
        padding: 2 4;
        background: $surface;
        text-align: center;
        height: auto;
        width: 76;
        max-width: 95%;
    }
    """

    BINDINGS = [
        Binding("c,C", "open_decision_screen", "Consolidar"),
        Binding("d,D", "open_decision_screen", "Consolidar", show=False),
        Binding("r,R", "run_comparison", "Recomparar"),
        Binding("g,G", "generate_reports", "Reportes"),
        Binding("v,V", "open_sp_verification", "Rutinas"),
        Binding("e,E", "focus_exclude_editor", "Excluir"),
        Binding("l,L", "toggle_drawer", "Registro"),
        Binding("slash", "focus_filter", "Filtrar"),
        Binding("question_mark,f1", "show_help", "Ayuda"),
        Binding("q,Q", "request_quit", "Salir"),
        Binding("escape", "dismiss_open", "Cerrar", show=False),
    ]

    filter_text: reactive[str] = reactive("")

    def __init__(
        self,
        result: ComparisonResult,
        *,
        profiles: list[ConnectionProfile] | None = None,
        exclude_patterns: list[str] | None = None,
        exclude_routines: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._result = result
        self._tree_data = build_tree_data(result)
        self._profiles = profiles or []
        self._exclude_patterns = list(exclude_patterns or [])
        self._exclude_routines = list(exclude_routines or [])
        # Identifies the latest re-run; results of superseded runs are dropped.
        self._run_id = 0

    def _body(self) -> Container:
        """Findings browser, or the no-drift message when there is nothing."""
        if not self._tree_data.groups:
            return Container(
                Static(_NO_DRIFT_MESSAGE, id="no-drift-message"),
                id="no-drift-container",
            )
        return Container(
            Vertical(
                Input(
                    placeholder="Filtrar por tabla, columna o tipo de diferencia  ( / )",
                    id="filter-input",
                ),
                FindingsTree(self._tree_data, id="findings-tree"),
                id="left-container",
            ),
            Vertical(DetailPanel(id="detail-panel"), id="right-container"),
            id="main-body",
        )

    def compose(self) -> ComposeResult:
        yield SummaryHeader(id="summary-header")
        yield Container(self._body(), id="content")
        with Horizontal(id="drawer"):
            with Vertical(id="exclude-container"):
                yield Label("Excluir tablas", classes="drawer-title")
                yield Label(
                    "Enter aplica y recompara  ·  Esc cierra el cajón",
                    classes="drawer-hint",
                )
                yield ExcludeEditor(self._exclude_patterns, id="exclude-editor")
            with Vertical(id="log-container"):
                yield Label("Registro de actividad", classes="drawer-title")
                yield StatusLog(id="status-log")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(SummaryHeader).show(self._result)
        self._focus_findings()

    def on_resize(self, event: Resize) -> None:
        self.set_class(event.size.width < _NARROW_WIDTH, "-narrow")

    def _focus_findings(self) -> None:
        trees = self.query(FindingsTree)
        if trees:
            trees.first().focus()

    def _drawer_open(self) -> bool:
        return self.query_one("#drawer").has_class("-open")

    def _set_drawer(self, is_open: bool) -> None:
        self.query_one("#drawer").set_class(is_open, "-open")

    def action_toggle_drawer(self) -> None:
        if self._drawer_open():
            self._close_drawer()
        else:
            self._set_drawer(True)

    def _close_drawer(self) -> None:
        self._set_drawer(False)
        self._focus_findings()

    def action_focus_filter(self) -> None:
        filter_inputs = self.query("#filter-input")
        if filter_inputs:
            filter_inputs.first().focus()

    def action_focus_exclude_editor(self) -> None:
        self._set_drawer(True)
        self.query_one(ExcludeEditor).focus()

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    def action_request_quit(self) -> None:
        def _leave(confirmed: bool | None) -> None:
            if confirmed:
                self.exit()

        self.push_screen(QuitModal(), _leave)

    def action_dismiss_open(self) -> None:
        """Esc closes what is open, from the inside out; it never quits."""
        focused = self.focused
        if isinstance(focused, Input) and focused.id == "filter-input":
            if focused.value:
                focused.value = ""
            else:
                self._focus_findings()
        elif self._drawer_open():
            self._close_drawer()
        else:
            self.notify("Pulsa q para salir.", timeout=2)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self.filter_text = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "exclude-editor":
            self._exclude_patterns = event.value.split()
            self.action_run_comparison()
        elif event.input.id == "filter-input":
            self._focus_findings()

    def watch_filter_text(self, filter_text: str) -> None:
        trees = self.query(FindingsTree)
        if trees:
            trees.first().apply_filter(filter_text)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        detail_panels = self.query(DetailPanel)
        if detail_panels:
            detail_panels.first().show(event.node.data)

    def _set_busy(self, busy: bool) -> None:
        self.query_one("#content").loading = busy

    def action_run_comparison(self) -> None:
        if not self._profiles:
            self._log_error(
                "No hay perfiles cargados; no se puede ejecutar la comparación."
            )
            return
        self.query_one(StatusLog).info("Ejecutando comparación…")
        self._set_busy(True)
        self._run_id += 1
        run_id = self._run_id
        self.run_worker(
            lambda: self._do_run_comparison(run_id), exclusive=True, thread=True
        )

    def _log_info(self, message: str, *, toast: str | None = None) -> None:
        """Write to the log and raise a toast; `toast` replaces the toast text
        when the log message is long."""
        self.query_one(StatusLog).info(message)
        self.notify(toast or message, timeout=4)

    def _log_error(self, message: str) -> None:
        self.query_one(StatusLog).error(message)
        self.notify(message, severity="error", timeout=10)

    def _do_run_comparison(self, run_id: int) -> None:
        # Worker thread: the UI is only touched through call_from_thread.
        try:
            new_result = run_comparison(
                self._profiles,
                ComparisonFilters(
                    excluded_tables=tuple(self._exclude_patterns),
                    excluded_routines=tuple(self._exclude_routines),
                ),
            )
        except Exception as exc:
            self.call_from_thread(
                self._report_run_failure,
                f"Falló la comparación: {describe_error(exc)}",
                run_id,
            )
            return
        self.call_from_thread(self._apply_new_result, new_result, run_id)

    def _report_run_failure(self, message: str, run_id: int) -> None:
        if run_id == self._run_id:
            self._set_busy(False)
            self._focus_findings()
        self._log_error(message)

    def _apply_new_result(
        self, new_result: ComparisonResult, run_id: int | None = None
    ) -> None:
        if run_id is not None and run_id != self._run_id:
            return
        had_findings = bool(self._tree_data.groups)
        self._result = new_result
        self._tree_data = build_tree_data(new_result)
        if had_findings != bool(self._tree_data.groups):
            self.query_one("#main-body, #no-drift-container").remove()
            self.query_one("#content").mount(self._body())
            self.filter_text = ""
        else:
            trees = self.query(FindingsTree)
            if trees:
                trees.first().populate(self._tree_data)
        self.query_one(SummaryHeader).show(new_result)
        self._set_busy(False)
        self.call_after_refresh(self._focus_findings)
        total = len(new_result.entries)
        self._log_info(
            "Comparación actualizada.",
            toast=f"Comparación actualizada: {total} hallazgos."
            if total
            else "Comparación actualizada: sin diferencias.",
        )

    def action_generate_reports(self) -> None:
        self.query_one(StatusLog).info("Generando reportes…")
        self.run_worker(self._do_generate_reports, exclusive=True, thread=True)

    def _do_generate_reports(self) -> None:
        buffer = io.StringIO()
        try:
            generate_all_reports(self._result, out=buffer)
        except Exception as exc:
            self.call_from_thread(
                self._log_error, f"Falló la generación de reportes: {exc}"
            )
            return
        self.call_from_thread(self._report_generated, buffer.getvalue())

    def _report_generated(self, output: str) -> None:
        self.query_one(StatusLog).info(output)
        if "[ERROR]" in output:
            self.notify(
                "Algún reporte falló; revisa el registro (l).",
                severity="warning",
                timeout=8,
            )
        else:
            self.notify("Reportes generados; las rutas están en el registro (l).")

    def action_open_decision_screen(self) -> None:
        from schema_comparator.tui.decision_screen import DecisionScreen
        from schema_comparator.compare.consolidation import (
            ConsolidationNotSupportedError,
            unsupported_consolidation_profiles,
        )
        from schema_comparator.compare.models import (
            ColumnMismatch,
            MissingColumn,
            MissingTable,
        )
        from pathlib import Path

        unsupported = unsupported_consolidation_profiles(self._profiles)
        if unsupported:
            self._log_error(
                str(ConsolidationNotSupportedError.for_profiles(unsupported))
            )
            return

        relevant_entries = [
            e
            for e in self._result.entries
            if isinstance(e, (ColumnMismatch, MissingColumn, MissingTable))
        ]
        if not relevant_entries:
            self._log_info(
                "No hay diferencias de tablas, atributos o columnas para consolidar."
            )
            return

        def handle_decision_screen_result(result) -> None:
            if result is None:
                self._log_info("Consolidación cancelada.")
            elif not result:
                self._log_info("Consolidación exitosa. No se generaron archivos SQL.")
            else:
                subfolder = Path(result[0]).parent.name
                self._log_info(
                    f"Consolidación exitosa. Scripts generados en 'scripts-db/{subfolder}/': "
                    f"{', '.join(Path(f).name for f in result)}",
                    toast=f"Scripts generados en scripts-db/{subfolder}/",
                )

        # Los scripts van al directorio de trabajo, igual que reportes/.
        repo_root = Path.cwd()

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
                repo_root=repo_root,
            ),
            callback=handle_decision_screen_result,
        )

    def action_open_sp_verification(self) -> None:
        from schema_comparator.tui.procedure_screen import ProcedureVerificationScreen
        from pathlib import Path
        from schema_comparator.config.models import ConnectionProfile

        repo_root = Path.cwd()
        profiles_to_pass = self._profiles
        if not profiles_to_pass:
            profiles_to_pass = [
                ConnectionProfile(name=p, connection_string=f"Database={p};")
                for p in self._result.compared_profiles
            ]

        self.push_screen(
            ProcedureVerificationScreen(
                profiles=tuple(profiles_to_pass),
                repo_root=repo_root,
                exclude_patterns=self._exclude_routines,
            )
        )


def run_tui(
    result: ComparisonResult,
    *,
    profiles: list[ConnectionProfile] | None = None,
    exclude_patterns: list[str] | None = None,
    exclude_routines: list[str] | None = None,
) -> None:
    """Launch the interactive TUI. Any exception raised while running is
    caught and reported to stderr rather than propagating as an unhandled
    exception (REQ-interactive-tui-008)."""
    app = SchemaComparatorApp(
        result,
        profiles=profiles,
        exclude_patterns=exclude_patterns,
        exclude_routines=exclude_routines,
    )
    try:
        app.run()
    except Exception as exc:
        print(
            f"[ERROR] Falló la interfaz interactiva: {describe_error(exc)}",
            file=sys.stderr,
        )
