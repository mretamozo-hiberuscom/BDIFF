"""Rows, counts and summary text of the routines screen, without Textual.

The screen only draws what this module decides, so the wording, the symbols
and the recompilation plan can be tested without a terminal.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from rich.markup import escape

from schema_comparator.infrastructure.providers.sqlserver.repair_script import (
    CONNECTION_FAILURE_ROUTINE,
)
from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
    ModuleRefreshResult,
    RoutineValidationResult,
    RoutineValidationStatus,
    SignatureStatus,
)
from schema_comparator.tui.theme import FAIL, OK, SEPARATOR, WARN

_CONNECTION_LABEL = "Sin conexión"


@dataclass(frozen=True, slots=True)
class RoutineRow:
    """One routine of one profile, ready to draw."""

    profile: str
    schema: str
    name: str
    symbol: str
    color: str
    state: str
    detail: str
    is_problem: bool
    is_connection_failure: bool = False

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"

    @property
    def state_markup(self) -> str:
        return f"[{self.color}]{self.symbol} {self.state}[/]"


@dataclass(frozen=True, slots=True)
class RefreshPlan:
    """What a recompilation would touch: unsigned routines only, since
    `sp_refreshsqlmodule` is refused on signed or unverifiable ones."""

    recompilable: int
    skipped: int

    @property
    def is_empty(self) -> bool:
        return self.recompilable == 0


def _is_connection_failure(routine) -> bool:
    return routine == CONNECTION_FAILURE_ROUTINE


def validation_rows(
    results: Mapping[str, Sequence[RoutineValidationResult]],
) -> list[RoutineRow]:
    rows: list[RoutineRow] = []
    for profile, items in sorted(results.items()):
        for item in items:
            failed_connection = _is_connection_failure(item.routine)
            if item.status == RoutineValidationStatus.VALID:
                symbol, color, state = OK, "green", "Dependencias resolubles"
                detail = ""
            elif item.status == RoutineValidationStatus.INVALID:
                symbol, color, state = FAIL, "red", "Dependencia no resuelta"
                detail = item.error_message or "Error de referencia"
            else:
                symbol, color, state = WARN, "yellow", "No verificable"
                detail = item.error_message or "Error desconocido"
            if failed_connection:
                state = _CONNECTION_LABEL
            rows.append(
                RoutineRow(
                    profile=profile,
                    schema=item.routine.schema_name,
                    name=item.routine.object_name,
                    symbol=symbol,
                    color=color,
                    state=state,
                    detail=detail,
                    is_problem=item.status != RoutineValidationStatus.VALID,
                    is_connection_failure=failed_connection,
                )
            )
    return rows


def refresh_rows(
    results: Mapping[str, Sequence[ModuleRefreshResult]],
) -> list[RoutineRow]:
    rows: list[RoutineRow] = []
    for profile, items in sorted(results.items()):
        for item in items:
            failed_connection = _is_connection_failure(item.routine)
            if item.is_success:
                symbol, color, state = OK, "green", "Recompilada"
                detail = ""
            else:
                symbol, color, state = FAIL, "red", "Falló la recompilación"
                detail = item.error_message or "Error desconocido"
            if failed_connection:
                state = _CONNECTION_LABEL
            rows.append(
                RoutineRow(
                    profile=profile,
                    schema=item.routine.schema_name,
                    name=item.routine.object_name,
                    symbol=symbol,
                    color=color,
                    state=state,
                    detail=detail,
                    is_problem=not item.is_success,
                    is_connection_failure=failed_connection,
                )
            )
    return rows


def refresh_plan(
    validated: Mapping[str, Sequence[RoutineValidationResult]],
) -> RefreshPlan:
    """Count the validated routines a recompilation would really touch.

    Connection-failure placeholders are not routines; signed or unknown
    ones are skipped by the refresh and reported apart.
    """
    recompilable = skipped = 0
    for items in validated.values():
        for item in items:
            if _is_connection_failure(item.routine):
                continue
            if item.signature_status == SignatureStatus.UNSIGNED:
                recompilable += 1
            else:
                skipped += 1
    return RefreshPlan(recompilable=recompilable, skipped=skipped)


def refresh_confirmation_body(plan: RefreshPlan) -> str:
    """Rich markup for the confirmation modal of the recompilation."""
    lines = [
        f"Se ejecutará [bold]sp_refreshsqlmodule[/bold] sobre "
        f"[bold]{plan.recompilable}[/bold] "
        f"{'rutina' if plan.recompilable == 1 else 'rutinas'} sin firma.",
    ]
    if plan.skipped:
        lines.append(
            f"Se omiten {plan.skipped} firmadas o no verificables, para no perder su firma."
        )
    lines.append("")
    lines.append(
        "Modifica metadatos de las bases (no tablas ni datos) y requiere permiso ALTER."
    )
    return "\n".join(lines)


def summary_markup(rows: Sequence[RoutineRow], *, recompiled: bool) -> str:
    """One line: how many routines are fine and how many are not."""
    if not rows:
        return "[dim]Sin rutinas para mostrar.[/dim]"
    unreachable = sum(1 for row in rows if row.is_connection_failure)
    routines = [row for row in rows if not row.is_connection_failure]
    problems = sum(1 for row in routines if row.is_problem)
    good = len(routines) - problems
    ok_word = "recompiladas" if recompiled else "con dependencias resolubles"
    bad_word = "con fallo" if recompiled else "con problemas"
    parts = [f"[green]{OK} {good}[/] {ok_word}"]
    if problems:
        parts.append(f"[red]{FAIL} {problems}[/] {bad_word}")
    if unreachable:
        parts.append(
            f"[yellow]{WARN} {unreachable}[/] "
            f"{'perfil' if unreachable == 1 else 'perfiles'} sin conexión"
        )
    return f"  {SEPARATOR}  ".join(parts)


def detail_markup(row: RoutineRow | None) -> str:
    """Card of the selected row; the guide when nothing is selected."""
    if row is None:
        return "[dim]Selecciona una rutina para ver su detalle.[/dim]"
    title = (
        f"[bold]{escape(row.profile)}[/bold]"
        if row.is_connection_failure
        else f"[bold]{escape(row.qualified_name)}[/bold]  [dim]{escape(row.profile)}[/dim]"
    )
    body = escape(row.detail) if row.detail else "[dim]Sin observaciones.[/dim]"
    return f"{title}\n{row.state_markup}\n\n{body}"
