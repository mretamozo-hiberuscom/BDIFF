"""Interactive TUI Screen for verifying and repairing Stored Procedures and Views via sp_refreshsqlmodule."""

import datetime
from pathlib import Path

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.infrastructure.providers.sqlserver import connection
from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
    RefreshResult,
    verify_sps_with_refresh,
)


class ProcedureVerificationScreen(Screen):
    """Interactive screen for checking, compiling, and repairing procedures/views."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver", show=True),
        Binding("r,R", "refresh_sps", "Recompilar / Validar en vivo"),
        Binding("s,S", "generate_script", "Generar Script SQL"),
    ]

    DEFAULT_CSS = """
    ProcedureVerificationScreen {
        background: $background;
        color: $text;
    }

    #sp-header-container {
        height: 3;
        background: $primary-darken-1;
        color: $text;
        content-align: center middle;
        text-style: bold;
    }

    #sp-table {
        height: 1fr;
        margin: 1;
        border: round $primary;
    }

    #sp-actions {
        height: 3;
        margin: 0 1 1 1;
        layout: horizontal;
    }

    #sp-actions Button {
        margin-right: 2;
    }

    #sp-status {
        height: 3;
        margin: 0 1;
        color: $accent;
        text-style: bold;
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
        self._results: dict[str, tuple[RefreshResult, ...]] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "Verificación y Reparación de Procedimientos Almacenados (sp_refreshsqlmodule)",
            id="sp-header-container",
        )
        yield DataTable(id="sp-table")
        yield Label("Presiona R para validar/recompilar en vivo | Presiona S para guardar script SQL", id="sp-status")
        with Horizontal(id="sp-actions"):
            yield Button("Recompilar / Validar en vivo (R)", id="btn-refresh", variant="primary")
            yield Button("Generar Script SQL de Reparación (S)", id="btn-script", variant="success")
            yield Button("Volver (Esc)", id="btn-close")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Perfil", "Esquema", "Procedimiento / Vista", "Estado", "Detalle del Error")
        table.cursor_type = "row"
        self.action_refresh_sps()

    def action_refresh_sps(self) -> None:
        """Run sp_refreshsqlmodule across profiles in a background worker."""
        status_labels = self.query("#sp-status")
        if status_labels:
            status_labels.first().update("🔄 Ejecutando sp_refreshsqlmodule en las bases de datos...")
        self.run_worker(self._do_verify_sps, exclusive=True, thread=True)

    def _do_verify_sps(self) -> None:
        results_map: dict[str, tuple[RefreshResult, ...]] = {}
        for profile in self._profiles:
            provider_name = str(getattr(profile, "provider", "sqlserver")).lower()
            if provider_name == "sqlserver":
                try:
                    with connection.connect(profile) as conn:
                        res = verify_sps_with_refresh(conn)
                        if self._exclude_patterns:
                            res = tuple(
                                r for r in res
                                if not any(pat in r.object_name.lower() for pat in self._exclude_patterns)
                            )
                        results_map[profile.name] = res
                except Exception as exc:
                    results_map[profile.name] = (
                        RefreshResult(
                            schema_name="SYSTEM",
                            object_name="CONNECT",
                            is_success=False,
                            error_message=f"Error de conexión: {exc}",
                        ),
                    )
        self._results = results_map
        self.call_from_thread(self._update_table_view)

    def _update_table_view(self) -> None:
        tables = self.query(DataTable)
        if not tables:
            return
        table = tables.first()
        table.clear()
        total_objects = 0
        total_failures = 0

        for profile_name, res_list in sorted(self._results.items()):
            for r in res_list:
                total_objects += 1
                if r.is_success:
                    status_str = "[green]✅ Válido[/green]"
                    err_str = "-"
                else:
                    total_failures += 1
                    status_str = "[bold red]❌ Error de compilación[/bold red]"
                    err_str = r.error_message or "Error desconocido"

                table.add_row(
                    escape(profile_name),
                    escape(r.schema_name),
                    escape(r.object_name),
                    status_str,
                    escape(err_str),
                )

        status_labels = self.query("#sp-status")
        if status_labels:
            if total_failures > 0:
                status_labels.first().update(
                    f"[bold red]❌ Se encontraron {total_failures} procedimiento(s)/vista(s) con errores de compilación de {total_objects} evaluados.[/bold red]"
                )
            else:
                status_labels.first().update(
                    f"[bold green]✅ Todos los procedimientos y vistas compilaron correctamente ({total_objects} evaluados).[/bold green]"
                )


    def action_generate_script(self) -> None:
        """Generate repair T-SQL script in scripts-db folder."""
        status_labels = self.query("#sp-status")

        if not self._results:
            if status_labels:
                status_labels.first().update("[bold red]❌ No hay resultados para generar el script. Presiona R primero.[/bold red]")
            return

        ts = datetime.datetime.now()
        folder_name = ts.strftime("%Y%m%d_%H%M%S")
        output_dir = self._repo_root / "scripts-db" / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)

        script_lines = [
            "-- Script de Reparación y Recompilación de Procedimientos Almacenados y Vistas",
            f"-- Generado el {ts.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        for profile_name, res_list in sorted(self._results.items()):
            script_lines.append(f"-- Perfil / BD: {profile_name}")
            for r in res_list:
                if r.schema_name == "SYSTEM" or r.object_name == "CONNECT":
                    continue
                safe_sch = r.schema_name.replace("'", "''").replace("]", "]]")
                safe_obj = r.object_name.replace("'", "''").replace("]", "]]")
                script_lines.append(f"EXEC sp_refreshsqlmodule @name = N'[{safe_sch}].[{safe_obj}]';")
            script_lines.append("")

        script_path = output_dir / "repair_sps.sql"
        try:
            script_path.write_text("\n".join(script_lines), encoding="utf-8")
            if status_labels:
                status_labels.first().update(f"✅ Script de reparación generado en: scripts-db/{folder_name}/repair_sps.sql")
        except Exception as exc:
            if status_labels:
                status_labels.first().update(f"[bold red]❌ Error al escribir el script de reparación: {exc}[/bold red]")


    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-refresh":
            self.action_refresh_sps()
        elif event.button.id == "btn-script":
            self.action_generate_script()
        elif event.button.id == "btn-close":
            self.app.pop_screen()
