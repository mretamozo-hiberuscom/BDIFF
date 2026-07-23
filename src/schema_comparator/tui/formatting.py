"""Pure, synchronous formatting helpers for the interactive TUI.

No Textual imports and no widget/App state — every function here takes a
`ComparisonResult` or a single `DiffEntry` and returns plain data or
strings, so this module is testable without the `Pilot` harness.
"""

from dataclasses import dataclass
from itertools import groupby

from schema_comparator.compare.models import (
    ColumnMismatch,
    ComparisonResult,
    DiffEntry,
    ForeignKeyMismatch,
    IndexMismatch,
    MissingColumn,
    MissingProcedure,
    MissingTable,
    PrimaryKeyMismatch,
    ProcedureMismatch,
)
from schema_comparator.report.attributes import format_attributes
from schema_comparator.report.console import _TYPE_LABELS


@dataclass(frozen=True, slots=True)
class TableGroup:
    """One qualified-table/procedure's worth of findings, in `console.py`'s
    per-table grouping order."""

    schema_name: str
    table_name: str
    entries: tuple[DiffEntry, ...]

    @property
    def qualified_label(self) -> str:
        return f"{self.schema_name}.{self.table_name}"


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



def leaf_label(entry: DiffEntry) -> str:
    """Format leaf label text for tree view."""
    if isinstance(entry, MissingTable):
        return f"tabla faltante (de {entry.missing_from_profile})"
    if isinstance(entry, MissingColumn):
        return f"{entry.column_name}: columna faltante (de {entry.missing_from_profile})"
    if isinstance(entry, MissingProcedure):
        return f"{entry.procedure_name}: rutina/SP faltante (de {entry.missing_from_profile})"
    if isinstance(entry, ProcedureMismatch):
        profiles = ", ".join(p for p, _ in entry.values_by_profile)
        return f"{entry.procedure_name}: discrepancia de código o parámetros entre {profiles}"
    if isinstance(entry, ColumnMismatch):
        profiles = ", ".join(p for p, _ in entry.values_by_profile)
        return f"{entry.column_name}: discrepancia de atributos entre {profiles}"
    return f"{type(entry).__name__}"


def detail_text(entry: DiffEntry) -> str:
    """Single-dispatch detail-panel content for a selected finding."""
    if isinstance(entry, ColumnMismatch):
        schema, table = entry.qualified_name
        lines = [f"Columna: {schema}.{table}.{entry.column_name}", ""]
        for profile, attrs in entry.values_by_profile:
            lines.append(f"  {profile}: {format_attributes(attrs)}")
        return "\n".join(lines)

    if isinstance(entry, MissingColumn):
        schema, table = entry.qualified_name
        lines = [f"Columna: {schema}.{table}.{entry.column_name}", ""]
        lines.append(f"  Faltante en el perfil '{entry.missing_from_profile}'")
        for profile, attrs in entry.present_attributes:
            lines.append(f"  {profile}: {format_attributes(attrs)}")
        return "\n".join(lines)

    if isinstance(entry, MissingProcedure):
        schema, proc = entry.qualified_name
        lines = [f"Procedimiento Almacenado / Rutina: {schema}.{proc}", ""]
        lines.append(f"  Faltante en el perfil '{entry.missing_from_profile}'")
        for profile, p_snap in entry.present_procedures:
            params_str = ", ".join(f"{p.name} {p.data_type}" for p in p_snap.parameters) or "sin parámetros"
            lines.append(f"  {profile}: {p_snap.routine_type} ({params_str})")
        return "\n".join(lines)

    if isinstance(entry, ProcedureMismatch):
        schema, proc = entry.qualified_name
        lines = [f"Procedimiento Almacenado / Rutina: {schema}.{proc}", ""]
        lines.append("Discrepancias detectadas entre perfiles:")
        for profile, p_snap in entry.values_by_profile:
            params_str = ", ".join(f"{p.name} {p.data_type}" for p in p_snap.parameters) or "sin parámetros"
            hash_str = p_snap.definition_hash[:10] if p_snap.definition_hash else "sin hash"
            lines.append(f"  {profile}: {p_snap.routine_type} | Params: [{params_str}] | Hash: {hash_str}")
        return "\n".join(lines)

    if isinstance(entry, MissingTable):
        schema, table = entry.qualified_name
        return f"{schema}.{table}: tabla faltante en el perfil '{entry.missing_from_profile}'"

    schema, table = entry.qualified_name
    return f"{schema}.{table}: {type(entry).__name__}"



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
    parts += [f"{label}: {counts[t]}" for t, label in _TYPE_LABELS.items() if counts[t] > 0 or t in (MissingTable, MissingColumn, ColumnMismatch)]
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


