"""Pure, synchronous formatting helpers for the interactive TUI.

No Textual imports and no widget/App state — every function here takes a
`ComparisonResult` or a single `DiffEntry` and returns plain data or
strings, so this module is testable without the `Pilot` harness.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import groupby

from rich.markup import escape

from schema_comparator.compare.models import (
    ColumnMismatch,
    ComparisonResult,
    DiffEntry,
    MissingColumn,
    MissingProcedure,
    MissingTable,
    ProcedureMismatch,
)
from schema_comparator.domain.comparison.models import column_label, object_label
from schema_comparator.report.attributes import format_attributes
from schema_comparator.report.console import _TYPE_LABELS
from schema_comparator.tui.theme import SEPARATOR, count_label, kind_style, OK


@dataclass(frozen=True, slots=True)
class TableGroup:
    """One qualified-table/procedure's worth of findings, in `console.py`'s
    per-table grouping order."""

    schema_name: str
    table_name: str
    entries: tuple[DiffEntry, ...]

    @property
    def qualified_label(self) -> str:
        return object_label(self.entries[0])


@dataclass(frozen=True, slots=True)
class TreeData:
    """A Textual-independent, plain-data view of a `ComparisonResult`'s
    findings, grouped by table or procedure."""

    groups: tuple[TableGroup, ...]


def build_tree_data(result: ComparisonResult) -> TreeData:
    """Group `result.entries` by qualified table/procedure identity."""
    sorted_entries = sorted(result.entries, key=lambda e: e.qualified_name)
    groups = [
        TableGroup(schema_name=schema, table_name=table, entries=tuple(entries))
        for (schema, table), entries in groupby(
            sorted_entries, key=lambda e: e.qualified_name
        )
    ]
    return TreeData(groups=tuple(groups))


def leaf_parts(entry: DiffEntry) -> tuple[str, str]:
    """A leaf split into its subject (column or routine, empty for a table)
    and what is wrong with it."""
    if isinstance(entry, MissingTable):
        return "", f"tabla faltante (de {entry.missing_from_profile})"
    if isinstance(entry, MissingColumn):
        return column_label(
            entry
        ), f"columna faltante (de {entry.missing_from_profile})"
    if isinstance(entry, MissingProcedure):
        return (
            entry.procedure_name,
            f"rutina/SP faltante (de {entry.missing_from_profile})",
        )
    if isinstance(entry, ProcedureMismatch):
        profiles = ", ".join(p for p, _ in entry.values_by_profile)
        return (
            entry.procedure_name,
            f"discrepancia de código o parámetros entre {profiles}",
        )
    if isinstance(entry, ColumnMismatch):
        profiles = ", ".join(p for p, _ in entry.values_by_profile)
        return column_label(entry), f"discrepancia de atributos entre {profiles}"
    return "", f"{type(entry).__name__}"


def leaf_label(entry: DiffEntry) -> str:
    """Format leaf label text for tree view."""
    subject, description = leaf_parts(entry)
    return f"{subject}: {description}" if subject else description


def _column_heading(entry: MissingColumn | ColumnMismatch) -> str:
    if entry.object_variants or entry.column_variants:
        return f"{object_label(entry)} → {column_label(entry)}"
    schema, table = entry.qualified_name
    return f"{schema}.{table}.{entry.column_name}"


def detail_text(entry: DiffEntry) -> str:
    """Single-dispatch detail-panel content for a selected finding."""
    if isinstance(entry, ColumnMismatch):
        lines = [f"Columna: {_column_heading(entry)}", ""]
        for profile, attrs in entry.values_by_profile:
            lines.append(f"  {profile}: {format_attributes(attrs)}")
        return "\n".join(lines)

    if isinstance(entry, MissingColumn):
        lines = [f"Columna: {_column_heading(entry)}", ""]
        lines.append(f"  Faltante en el perfil '{entry.missing_from_profile}'")
        for profile, attrs in entry.present_attributes:
            lines.append(f"  {profile}: {format_attributes(attrs)}")
        return "\n".join(lines)

    if isinstance(entry, MissingProcedure):
        lines = [f"Procedimiento Almacenado / Rutina: {object_label(entry)}", ""]
        lines.append(f"  Faltante en el perfil '{entry.missing_from_profile}'")
        for profile, p_snap in entry.present_procedures:
            params_str = (
                ", ".join(f"{p.name} {p.data_type}" for p in p_snap.parameters)
                or "sin parámetros"
            )
            lines.append(f"  {profile}: {p_snap.routine_type} ({params_str})")
        return "\n".join(lines)

    if isinstance(entry, ProcedureMismatch):
        lines = [f"Procedimiento Almacenado / Rutina: {object_label(entry)}", ""]
        lines.append("Discrepancias detectadas entre perfiles:")
        for profile, p_snap in entry.values_by_profile:
            params_str = (
                ", ".join(f"{p.name} {p.data_type}" for p in p_snap.parameters)
                or "sin parámetros"
            )
            hash_str = (
                p_snap.definition_hash[:10] if p_snap.definition_hash else "sin hash"
            )
            lines.append(
                f"  {profile}: {p_snap.routine_type} | Params: [{params_str}] | Hash: {hash_str}"
            )
        return "\n".join(lines)

    if isinstance(entry, MissingTable):
        return f"{object_label(entry)}: tabla faltante en el perfil '{entry.missing_from_profile}'"

    return f"{object_label(entry)}: {type(entry).__name__}"


def header_counts(result: ComparisonResult) -> dict[type, int]:
    """Count findings per diff-entry category."""
    counts = {t: 0 for t in _TYPE_LABELS}
    for entry in result.entries:
        if type(entry) in counts:
            counts[type(entry)] += 1
    return counts


def header_text(result: ComparisonResult) -> str:
    """Render the header line: compared profiles plus per-category counts."""
    counts = header_counts(result)
    profiles = ", ".join(result.compared_profiles)
    parts = [f"Perfiles comparados: {profiles}"]
    parts += [
        f"{label}: {counts[t]}"
        for t, label in _TYPE_LABELS.items()
        if counts[t] > 0 or t in (MissingTable, MissingColumn, ColumnMismatch)
    ]
    return " | ".join(parts)


def entry_matches(entry: DiffEntry, filter_text: str) -> bool:
    """Case-insensitive substring match over diff-type label, qualified name, leaf label, and object names."""
    if not filter_text:
        return True
    needle = filter_text.lower()
    schema, table = entry.qualified_name
    haystacks = [type(entry).__name__, leaf_label(entry), schema, table]
    if isinstance(entry, (MissingColumn, ColumnMismatch)):
        haystacks.append(entry.column_name)
    elif isinstance(entry, (MissingProcedure, ProcedureMismatch)):
        haystacks.append(entry.procedure_name)
    return any(needle in haystack.lower() for haystack in haystacks)


def profiles_markup(result: ComparisonResult) -> str:
    """Rich markup naming the compared profiles."""
    names = f" {SEPARATOR} ".join(escape(p) for p in result.compared_profiles)
    return f"{len(result.compared_profiles)} perfiles: {names}"


def summary_markup(result: ComparisonResult) -> str:
    """Rich markup with one coloured chip per kind of finding, or the
    all-clear when there is none."""
    counts = header_counts(result)
    chips = [
        f"[{kind_style(t).color}]{kind_style(t).symbol}[/] "
        f"[bold]{count_label(n, kind_style(t))}[/bold]"
        for t, n in counts.items()
        if n > 0
    ]
    if not chips:
        return f"[green]{OK}[/] [bold]Sin diferencias[/bold]"
    objects = len({entry.qualified_name for entry in result.entries})
    chips.append(
        f"[dim]{SEPARATOR} {len(result.entries)} hallazgos en {objects} objetos[/dim]"
    )
    return "   ".join(chips)


def _group_equal(pairs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Merge profiles that share the same text: `("a, c", text)`."""
    grouped: dict[str, list[str]] = {}
    for profile, text in pairs:
        grouped.setdefault(text, []).append(profile)
    return [(", ".join(profiles), text) for text, profiles in grouped.items()]


def _definition_lines(pairs: Iterable[tuple[str, str]]) -> list[str]:
    return [
        f"  [bold]{escape(profiles)}:[/bold] [green]{escape(text)}[/]"
        for profiles, text in _group_equal(pairs)
    ]


def _routine_text(snapshot) -> str:
    params = (
        ", ".join(f"{p.name} {p.data_type}" for p in snapshot.parameters)
        or "sin parámetros"
    )
    return f"{snapshot.routine_type} ({params})"


def _field(label: str, value: str, color: str | None = None) -> str:
    shown = f"[{color}]{escape(value)}[/]" if color else escape(value)
    return f"[bold]{label}[/bold] {shown}"


def detail_markup(entry: DiffEntry) -> str:
    """Rich markup card of one finding. Profiles that share a definition
    are listed together, so a 2-against-1 split reads at a glance."""
    style = kind_style(entry)
    title = f"[bold {style.color}]{style.symbol} {style.singular.capitalize()}[/]"
    lines = [title, ""]

    if isinstance(entry, ColumnMismatch):
        lines.append(_field("Tabla  ", object_label(entry)))
        lines.append(_field("Columna", column_label(entry), style.color))
        definitions = _definition_lines(
            (profile, format_attributes(attrs))
            for profile, attrs in entry.values_by_profile
        )
        lines += ["", f"[bold underline]Definiciones distintas ({len(definitions)})[/]"]
        lines += definitions
        hint = "Pulsa [bold]c[/bold] para decidir cuál es la correcta."
    elif isinstance(entry, MissingColumn):
        lines.append(_field("Tabla  ", object_label(entry)))
        lines.append(_field("Columna", column_label(entry), style.color))
        lines.append(_field("Falta en", entry.missing_from_profile, "red"))
        lines += ["", "[bold underline]Existe en[/]"]
        lines += _definition_lines(
            (profile, format_attributes(attrs))
            for profile, attrs in entry.present_attributes
        )
        hint = "Pulsa [bold]c[/bold] para agregarla o eliminarla."
    elif isinstance(entry, MissingTable):
        lines.append(_field("Tabla  ", object_label(entry), style.color))
        lines.append(_field("Falta en", entry.missing_from_profile, "red"))
        lines += ["", "[bold underline]Existe en[/]"]
        lines += _definition_lines(
            (profile, f"{len(columns)} columnas")
            for profile, columns in entry.present_columns
        )
        hint = "Pulsa [bold]c[/bold] para crearla o eliminarla."
    elif isinstance(entry, MissingProcedure):
        lines.append(_field("Rutina ", object_label(entry), style.color))
        lines.append(_field("Falta en", entry.missing_from_profile, "red"))
        lines += ["", "[bold underline]Existe en[/]"]
        lines += _definition_lines(
            (profile, _routine_text(snapshot))
            for profile, snapshot in entry.present_procedures
        )
        hint = "Pulsa [bold]v[/bold] para validar y reparar rutinas."
    elif isinstance(entry, ProcedureMismatch):
        lines.append(_field("Rutina ", object_label(entry), style.color))
        lines += ["", "[bold underline]Definiciones distintas[/]"]
        lines += _definition_lines(
            (
                profile,
                f"{_routine_text(snapshot)} | hash "
                f"{snapshot.definition_hash[:10] if snapshot.definition_hash else 'sin hash'}",
            )
            for profile, snapshot in entry.values_by_profile
        )
        hint = "Pulsa [bold]v[/bold] para validar y reparar rutinas."
    else:
        lines.append(_field("Objeto ", object_label(entry)))
        hint = ""

    if hint:
        lines += ["", f"[dim]{hint}[/dim]"]
    return "\n".join(lines)


def group_markup(group: TableGroup) -> str:
    """Rich markup card of every finding of one table or routine."""
    lines = [
        f"[bold]{escape(group.qualified_label)}[/bold]",
        f"[dim]{len(group.entries)} hallazgos[/dim]",
        "",
    ]
    for entry in group.entries:
        style = kind_style(entry)
        subject, description = leaf_parts(entry)
        subject_markup = f"[bold]{escape(subject)}[/bold]: " if subject else ""
        lines.append(
            f"[{style.color}]{style.symbol}[/] {subject_markup}{escape(description)}"
        )
    lines += ["", "[dim]Elige uno para ver su detalle.[/dim]"]
    return "\n".join(lines)
