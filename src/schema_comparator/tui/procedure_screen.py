"""Interactive TUI screen for verifying routine dependencies and explicitly
refreshing their metadata."""

import datetime
from pathlib import Path

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from schema_comparator.compare.consolidation import assign_script_filenames
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.infrastructure.providers.sqlserver.ddl_renderer import (
    SQL_SCRIPT_ENCODING,
    extract_database_name,
)
from schema_comparator.infrastructure.providers.sqlserver.routine_runner import (
    run_routines,
)
from schema_comparator.infrastructure.providers.sqlserver.repair_script import (
    CONNECTION_FAILURE_ROUTINE,
    render_repair_scripts,
)
from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
    ModuleRefreshResult,
    RoutineValidationResult,
    RoutineValidationStatus,
    SignatureStatus,
    refresh_modules_mutating,
    validate_routines_read_only,
)
from schema_comparator.tui.modals import ROUTINES_HELP, ConfirmModal, HelpModal
from schema_comparator.tui.routine_model import (
    RoutineRow,
    detail_markup,
    refresh_confirmation_body,
    refresh_plan,
    refresh_rows,
    summary_markup,
    validation_rows,
)
from schema_comparator.tui.theme import FAIL, OK, SEPARATOR, WARN


class ProcedureVerificationScreen(Screen):
    """Validates routine dependencies (read-only), recompiles metadata after
    an explicit confirmation and saves the repair scripts."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver"),
        Binding("v,V", "validate_read_only", "Validar"),
        Binding("r,R", "request_module_refresh", "Recompilar"),
        Binding("s,S", "generate_script", "Guardar script"),
        Binding("question_mark,f1", "show_help", "Ayuda"),
    ]

    DEFAULT_CSS = """
    ProcedureVerificationScreen {
        background: $background;
        color: $text;
    }

    #routines-header {
        height: auto;
        padding: 0 2;
        background: $panel;
        border-bottom: solid $primary;
    }

    #sp-table {
        height: 1fr;
        margin: 1 1 0 1;
        border: round $primary;
    }

    #routine-detail {
        height: auto;
        min-height: 5;
        max-height: 10;
        margin: 0 1;
        padding: 0 1;
        border: round $primary-darken-2;
        overflow-y: auto;
    }

    #sp-status {
        height: auto;
        min-height: 1;
        margin: 0 2;
    }
    """

    def __init__(
        self,
        profiles: tuple[ConnectionProfile, ...],
        repo_root: Path,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._profiles = profiles
        self._repo_root = repo_root
        self._exclude_patterns = [p.lower() for p in (exclude_patterns or [])]
        self._validation_results: dict[str, tuple[RoutineValidationResult, ...]] = {}
        self._refresh_results: dict[str, tuple[ModuleRefreshResult, ...]] = {}
        self._rows: list[RoutineRow] = []
        # One validation or refresh at a time: results of a mutating refresh
        # must never be overwritten by a validation started meanwhile.
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Static(id="routines-header")
        yield DataTable(id="sp-table", cursor_type="row", zebra_stripes=True)
        yield Static(Text.from_markup(detail_markup(None)), id="routine-detail")
        yield Static(id="sp-status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Perfil", "Rutina / vista", "Estado")
        table.border_title = "Rutinas"
        self._show_header(summary="[dim]Aún sin validar.[/dim]")
        self.action_validate_read_only()

    # -- drawing ---------------------------------------------------------

    def _show_header(self, *, summary: str) -> None:
        names = ", ".join(escape(p.name) for p in self._profiles)
        headers = self.query("#routines-header")
        if headers:
            headers.first().update(
                Text.from_markup(f"[bold]Rutinas[/bold]  [dim]{names}[/dim]\n{summary}")
            )

    def _set_status(self, markup: str) -> None:
        status_labels = self.query("#sp-status")
        if status_labels:
            status_labels.first().update(Text.from_markup(markup))

    def _notify(self, message: str, severity: str = "information") -> None:
        if self.is_attached:
            self.notify(message, severity=severity)

    def _show_rows(
        self, rows: list[RoutineRow], *, title: str, recompiled: bool
    ) -> None:
        self._rows = rows
        self._show_header(summary=summary_markup(rows, recompiled=recompiled))
        tables = self.query(DataTable)
        if not tables:
            return
        table = tables.first()
        table.clear()
        table.border_title = title
        for index, row in enumerate(rows):
            name = Text(
                row.profile if row.is_connection_failure else row.qualified_name
            )
            table.add_row(
                Text(row.profile),
                name if not row.is_connection_failure else Text("—", style="dim"),
                Text.from_markup(row.state_markup),
                key=str(index),
            )
        self._show_detail(rows[0] if rows else None)

    def _show_detail(self, row: RoutineRow | None) -> None:
        panels = self.query("#routine-detail")
        if panels:
            panels.first().update(Text.from_markup(detail_markup(row)))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        index = event.cursor_row
        self._show_detail(self._rows[index] if 0 <= index < len(self._rows) else None)

    # -- busy guard ------------------------------------------------------

    def _refuse_if_busy(self) -> bool:
        if self._busy:
            self._set_status(
                f"[yellow]{WARN} Hay una operación en curso; espera a que termine.[/yellow]"
            )
        return self._busy

    def _start(self, work, status: str) -> None:
        if self._refuse_if_busy():
            return
        self._busy = True
        self._set_status(status)
        self.run_worker(work, exclusive=True, thread=True)

    # -- validation (read-only) ------------------------------------------

    def action_validate_read_only(self) -> None:
        """Run read-only dependency validation across profiles without mutating DB."""
        self._start(
            self._do_validate_read_only,
            f"[dim]{SEPARATOR} Validando dependencias (solo lectura)…[/dim]",
        )

    def _do_validate_read_only(self) -> None:
        results_map: dict[str, tuple[RoutineValidationResult, ...]] = {}
        runs = run_routines(
            self._profiles, self._exclude_patterns, validate_routines_read_only
        )
        for profile_name, run in runs.items():
            results_map[profile_name] = (
                run.results
                if run.error is None
                else (
                    RoutineValidationResult(
                        routine=CONNECTION_FAILURE_ROUTINE,
                        status=RoutineValidationStatus.UNVERIFIABLE,
                        signature_status=SignatureStatus.UNKNOWN,
                        error_message=f"Error de conexión: {run.error}",
                    ),
                )
            )
        self.app.call_from_thread(self._apply_validation, results_map)

    def _apply_validation(
        self, results: dict[str, tuple[RoutineValidationResult, ...]]
    ) -> None:
        self._validation_results = results
        self._busy = False
        self._update_table_view_validation()

    def _update_table_view_validation(self) -> None:
        rows = validation_rows(self._validation_results)
        self._show_rows(rows, title="Validación de dependencias", recompiled=False)
        routines = [row for row in rows if not row.is_connection_failure]
        if not rows:
            self._set_status(
                f"[yellow]{WARN} No hay rutinas que evaluar en los perfiles SQL Server.[/yellow]"
            )
        elif any(row.is_problem for row in rows):
            self._set_status(
                f"[dim]{SEPARATOR} {len(routines)} evaluadas. "
                "Recorre la lista para ver el detalle de cada problema.[/dim]"
            )
        else:
            self._set_status(
                f"[green]{OK} Todas las dependencias son resolubles "
                f"({len(routines)} evaluadas).[/green]"
            )

    # -- refresh (mutating, always confirmed) ----------------------------

    def action_request_module_refresh(self) -> None:
        """Ask for confirmation before executing the mutating sp_refreshsqlmodule."""
        if self._refuse_if_busy():
            return
        if not self._validation_results:
            self._set_status(
                f"[yellow]{WARN} Valida primero con [bold]v[/bold]: así sabrás qué se recompilaría.[/yellow]"
            )
            return
        plan = refresh_plan(self._validation_results)
        if plan.is_empty:
            self._set_status(
                f"[yellow]{WARN} No hay rutinas sin firma que recompilar.[/yellow]"
            )
            return

        def _on_modal_result(confirmed: bool | None) -> None:
            if confirmed:
                self._execute_module_refresh()

        self.app.push_screen(
            ConfirmModal(
                "Recompilar metadatos de rutinas",
                refresh_confirmation_body(plan),
                confirm_label="Recompilar",
                cancel_label="Cancelar",
                severity="warning",
                focus_cancel=True,
            ),
            _on_modal_result,
        )

    def _execute_module_refresh(self) -> None:
        self._start(
            self._do_refresh_modules,
            f"[dim]{SEPARATOR} Recompilando metadatos de las rutinas sin firma…[/dim]",
        )

    def _do_refresh_modules(self) -> None:
        results_map: dict[str, tuple[ModuleRefreshResult, ...]] = {}
        runs = run_routines(
            self._profiles, self._exclude_patterns, refresh_modules_mutating
        )
        for profile_name, run in runs.items():
            results_map[profile_name] = (
                run.results
                if run.error is None
                else (
                    ModuleRefreshResult.failure(
                        CONNECTION_FAILURE_ROUTINE,
                        error_message=f"Error de conexión: {run.error}",
                        signature_status=SignatureStatus.UNKNOWN,
                    ),
                )
            )
        self.app.call_from_thread(self._apply_refresh, results_map)

    def _apply_refresh(
        self, results: dict[str, tuple[ModuleRefreshResult, ...]]
    ) -> None:
        self._refresh_results = results
        self._busy = False
        self._update_table_view_refresh()

    def _update_table_view_refresh(self) -> None:
        rows = refresh_rows(self._refresh_results)
        self._show_rows(rows, title="Recompilación de metadatos", recompiled=True)
        failures = sum(1 for row in rows if row.is_problem)
        if failures:
            self._set_status(
                f"[red]{FAIL} {failures} de {len(rows)} no se pudieron recompilar.[/red] "
                "Guarda el script con [bold]s[/bold] para revisarlas."
            )
        else:
            self._set_status(
                f"[green]{OK} Metadatos recompilados ({len(rows)} procesadas).[/green]"
            )

    # -- script ----------------------------------------------------------

    def action_generate_script(self) -> None:
        """Generate repair T-SQL scripts in scripts-db/<folder>/repair_sps/ separated per database profile."""
        if self._refuse_if_busy():
            return

        if not self._validation_results and not self._refresh_results:
            self._set_status(
                f"[red]{FAIL} Valida primero con [bold]v[/bold] antes de guardar el script.[/red]"
            )
            return

        ts = datetime.datetime.now()
        folder_name = ts.strftime("%Y%m%d_%H%M%S")
        output_dir = self._repo_root / "scripts-db" / folder_name
        repair_dir = output_dir / "repair_sps"
        repair_dir.mkdir(parents=True, exist_ok=True)

        source_map = self._refresh_results or self._validation_results
        databases = {
            p.name: extract_database_name(p.connection_string) for p in self._profiles
        }
        scripts = render_repair_scripts(source_map, databases, ts)
        script_filenames = assign_script_filenames(list(scripts.per_profile))

        written_profile_files: list[str] = []
        for profile_name, content in scripts.per_profile.items():
            safe_filename = script_filenames[profile_name] + ".sql"
            try:
                (repair_dir / safe_filename).write_text(
                    content, encoding=SQL_SCRIPT_ENCODING
                )
                written_profile_files.append(safe_filename)
            except Exception as exc:
                self._set_status(
                    f"[red]{FAIL} Error al escribir el script de {escape(profile_name)}: {escape(str(exc))}[/red]"
                )
                return

        master_script_path = output_dir / "repair_sps.sql"
        try:
            master_script_path.write_text(scripts.master, encoding=SQL_SCRIPT_ENCODING)
        except Exception as exc:
            self._set_status(
                f"[red]{FAIL} Error al escribir el script maestro de reparación: {escape(str(exc))}[/red]"
            )
            return

        location = f"scripts-db/{folder_name}/"
        self._set_status(
            f"[green]{OK} Script guardado en {escape(location)}[/green] "
            f"[dim]({len(written_profile_files)} por base + repair_sps.sql; no se ejecutó nada)[/dim]"
        )
        self._notify(f"Script guardado en {location}")

    def action_show_help(self) -> None:
        self.app.push_screen(HelpModal("Ayuda de rutinas", ROUTINES_HELP))
