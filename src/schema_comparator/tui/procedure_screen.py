"""Interactive TUI Screen for verifying procedure dependencies and explicit module refresh."""

import datetime
from pathlib import Path

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.infrastructure.providers.sqlserver import connection
from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
    ModuleRefreshResult,
    RoutineIdentity,
    RoutineValidationResult,
    RoutineValidationStatus,
    SignatureStatus,
    enumerate_routines,
    refresh_modules_mutating,
    validate_routines_read_only,
)


class ConfirmRefreshModal(ModalScreen[bool]):
    """Confirmation modal dialog for mutating sp_refreshsqlmodule operation."""

    DEFAULT_CSS = """
    ConfirmRefreshModal {
        align: center middle;
    }
    #confirm-dialog {
        width: 60;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    #confirm-title {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    #confirm-buttons {
        margin-top: 1;
        horizontal-align: center;
    }
    #confirm-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, routine_count: int) -> None:
        super().__init__()
        self._routine_count = routine_count

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label("⚠️ Operación Mutante: Recompilación de Metadatos", id="confirm-title")
            yield Static(
                f"Estás a punto de ejecutar [bold]sp_refreshsqlmodule[/bold] sobre {self._routine_count} rutinas no firmadas.\n\n"
                "Esta operación modifica metadatos en la base de datos y requiere permisos ALTER.\n"
                "¿Deseas proceder con la recompilación?"
            )
            with Horizontal(id="confirm-buttons"):
                yield Button("Sí, Recompilar", id="btn-confirm", variant="warning")
                yield Button("Cancelar", id="btn-cancel", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)


class ProcedureVerificationScreen(Screen):
    """Interactive screen for checking, validating, and compiling procedures/views."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver", show=True),
        Binding("v,V", "validate_read_only", "Validar dependencias (Lectura)", show=True),
        Binding("r,R", "request_module_refresh", "Actualizar metadatos (Mutante)", show=True),
        Binding("s,S", "generate_script", "Generar Script SQL", show=True),
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
        self._validation_results: dict[str, tuple[RoutineValidationResult, ...]] = {}
        self._refresh_results: dict[str, tuple[ModuleRefreshResult, ...]] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "Verificación de Dependencias y Recompilación de Rutinas SQL Server",
            id="sp-header-container",
        )
        yield DataTable(id="sp-table")
        yield Label("V: Validar dependencias (Solo lectura) | R: Recompilar (Mutante) | S: Guardar script", id="sp-status")
        with Horizontal(id="sp-actions"):
            yield Button("Validar dependencias [V]", id="btn-validate", variant="primary")
            yield Button("Recompilar metadatos [R]", id="btn-refresh", variant="warning")
            yield Button("Generar Script SQL [S]", id="btn-script", variant="success")
            yield Button("Volver [Esc]", id="btn-close")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Perfil", "Esquema", "Rutina / Vista", "Estado Dependencias", "Detalle")
        table.cursor_type = "row"
        self.action_validate_read_only()

    def action_validate_read_only(self) -> None:
        """Run read-only dependency validation across profiles without mutating DB."""
        status_labels = self.query("#sp-status")
        if status_labels:
            status_labels.first().update("🔍 Ejecutando validación de dependencias (solo lectura)...")
        self.run_worker(self._do_validate_read_only, exclusive=True, thread=True)

    def _do_validate_read_only(self) -> tuple[dict[str, tuple[RoutineValidationResult, ...]], int]:
        results_map: dict[str, tuple[RoutineValidationResult, ...]] = {}
        total_count = 0
        for profile in self._profiles:
            provider_name = str(getattr(profile, "provider", "sqlserver")).lower()
            if provider_name == "sqlserver":
                try:
                    with connection.connect(profile) as conn:
                        targets = enumerate_routines(conn)
                        if self._exclude_patterns:
                            targets = tuple(
                                t for t in targets
                                if not any(pat in t.object_name.lower() for pat in self._exclude_patterns)
                            )
                        total_count += len(targets)
                        res = validate_routines_read_only(conn, targets)
                        results_map[profile.name] = res
                except Exception as exc:
                    dummy = RoutineIdentity(schema_name="SYSTEM", object_name="CONNECT")
                    results_map[profile.name] = (
                        RoutineValidationResult(
                            routine=dummy,
                            status=RoutineValidationStatus.UNVERIFIABLE,
                            signature_status=SignatureStatus.UNKNOWN,
                            error_message=f"Error de conexión: {exc}",
                        ),
                    )
        self._validation_results = results_map
        self.app.call_from_thread(self._update_table_view_validation)
        return results_map, total_count

    def _update_table_view_validation(self) -> None:
        tables = self.query(DataTable)
        if not tables:
            return
        table = tables.first()
        table.clear()
        total_objects = 0
        total_invalid = 0

        for profile_name, res_list in sorted(self._validation_results.items()):
            for r in res_list:
                total_objects += 1
                if r.status == RoutineValidationStatus.VALID:
                    status_str = "[green]✅ Dependencias resolubles[/green]"
                    err_str = "-"
                elif r.status == RoutineValidationStatus.INVALID:
                    total_invalid += 1
                    status_str = "[bold red]❌ Dependencia no resuelta[/bold red]"
                    err_str = r.error_message or "Error de referencia"
                else:
                    total_invalid += 1
                    status_str = "[bold yellow]⚠️ No verificable[/bold yellow]"
                    err_str = r.error_message or "Error desconocido"

                table.add_row(
                    escape(profile_name),
                    escape(r.routine.schema_name),
                    escape(r.routine.object_name),
                    status_str,
                    escape(err_str),
                )

        status_labels = self.query("#sp-status")
        if status_labels:
            if total_invalid > 0:
                status_labels.first().update(
                    f"[bold red]❌ {total_invalid} rutina(s) con dependencias no resueltas de {total_objects} evaluadas.[/bold red]"
                )
            else:
                status_labels.first().update(
                    f"[bold green]✅ Todas las dependencias son resolubles ({total_objects} evaluadas).[/bold green]"
                )

    def action_request_module_refresh(self) -> None:
        """Prompt confirmation modal before executing mutating sp_refreshsqlmodule."""
        total_targets = sum(len(res) for res in self._validation_results.values())
        if total_targets == 0:
            status_labels = self.query("#sp-status")
            if status_labels:
                status_labels.first().update("[bold yellow]⚠️ No se han encontrado rutinas para recompilar. Ejecuta primero la validación [V].[/bold yellow]")
            return

        def _on_modal_result(confirmed: bool) -> None:
            if confirmed:
                self._execute_module_refresh()

        self.app.push_screen(ConfirmRefreshModal(total_targets), _on_modal_result)

    def _execute_module_refresh(self) -> None:
        status_labels = self.query("#sp-status")
        if status_labels:
            status_labels.first().update("🔄 Recompilando metadatos en bases de datos con confirmación...")
        self.run_worker(self._do_refresh_modules, exclusive=True, thread=True)

    def _do_refresh_modules(self) -> None:
        results_map: dict[str, tuple[ModuleRefreshResult, ...]] = {}
        for profile in self._profiles:
            provider_name = str(getattr(profile, "provider", "sqlserver")).lower()
            if provider_name == "sqlserver":
                try:
                    with connection.connect(profile) as conn:
                        targets = enumerate_routines(conn)
                        if self._exclude_patterns:
                            targets = tuple(
                                t for t in targets
                                if not any(pat in t.object_name.lower() for pat in self._exclude_patterns)
                            )
                        res = refresh_modules_mutating(conn, targets)
                        results_map[profile.name] = res
                except Exception as exc:
                    dummy = RoutineIdentity(schema_name="SYSTEM", object_name="CONNECT")
                    results_map[profile.name] = (
                        ModuleRefreshResult.failure(
                            dummy,
                            error_message=f"Error de conexión: {exc}",
                            signature_status=SignatureStatus.UNKNOWN,
                        ),
                    )
        self._refresh_results = results_map
        self.app.call_from_thread(self._update_table_view_refresh)

    def _update_table_view_refresh(self) -> None:
        tables = self.query(DataTable)
        if not tables:
            return
        table = tables.first()
        table.clear()
        total_objects = 0
        total_failures = 0

        for profile_name, res_list in sorted(self._refresh_results.items()):
            for r in res_list:
                total_objects += 1
                if r.is_success:
                    status_str = "[green]✅ Recompilado[/green]"
                    err_str = "-"
                else:
                    total_failures += 1
                    status_str = "[bold red]❌ Fallo recompilación[/bold red]"
                    err_str = r.error_message or "Error desconocido"

                table.add_row(
                    escape(profile_name),
                    escape(r.routine.schema_name),
                    escape(r.routine.object_name),
                    status_str,
                    escape(err_str),
                )

        status_labels = self.query("#sp-status")
        if status_labels:
            if total_failures > 0:
                status_labels.first().update(
                    f"[bold red]❌ {total_failures} rutina(s) fallaron durante la recompilación de {total_objects} procesadas.[/bold red]"
                )
            else:
                status_labels.first().update(
                    f"[bold green]✅ Todas las metadatos de rutinas no firmadas fueron recompiladas ({total_objects} procesadas).[/bold green]"
                )

    def action_generate_script(self) -> None:
        """Generate repair T-SQL script in scripts-db folder excluding signed objects."""
        status_labels = self.query("#sp-status")

        if not self._validation_results and not self._refresh_results:
            if status_labels:
                status_labels.first().update("[bold red]❌ Realiza una validación [V] antes de generar el script.[/bold red]")
            return

        ts = datetime.datetime.now()
        folder_name = ts.strftime("%Y%m%d_%H%M%S")
        output_dir = self._repo_root / "scripts-db" / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)

        script_lines = [
            "-- Script de Reparación y Recompilación de Procedimientos Almacenados y Vistas",
            f"-- Generado el {ts.strftime('%Y-%m-%d %H:%M:%S')}",
            "-- NOTA: Excluye automáticamente objetos con firma digital criptográfica",
            "",
        ]

        source_map = self._refresh_results or self._validation_results
        for profile_name, res_list in sorted(source_map.items()):
            script_lines.append(f"-- Perfil / BD: {profile_name}")
            for r in res_list:
                routine = getattr(r, "routine", None)
                if not routine or routine.schema_name == "SYSTEM" or routine.object_name == "CONNECT":
                    continue
                if getattr(r, "signature_status", SignatureStatus.UNSIGNED) != SignatureStatus.UNSIGNED:
                    script_lines.append(f"-- OMITIDO (Firmado): [{routine.schema_name}].[{routine.object_name}]")
                    continue
                # For T-SQL N'...' string literal parameter in sp_refreshsqlmodule:
                # String literals double single-quotes (' -> ''). Do NOT double right-brackets (] -> ]]) inside a string literal.
                safe_sch = routine.schema_name.replace("'", "''")
                safe_obj = routine.object_name.replace("'", "''")
                script_lines.append(f"EXEC sys.sp_refreshsqlmodule @name = N'[{safe_sch}].[{safe_obj}]';")
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
        if event.button.id == "btn-validate":
            self.action_validate_read_only()
        elif event.button.id == "btn-refresh":
            self.action_request_module_refresh()
        elif event.button.id == "btn-script":
            self.action_generate_script()
        elif event.button.id == "btn-close":
            self.app.pop_screen()
