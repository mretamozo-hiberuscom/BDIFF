"""Pure, synchronous formatting helpers for the interactive TUI.

No Textual imports and no widget/App state — every function here takes a
`ComparisonResult` or a single `DiffEntry` and returns plain data or
strings, so this module is testable without the `Pilot` harness.
"""

from dataclasses import dataclass
from itertools import groupby

from schema_comparator.compare.models import ColumnMismatch, ComparisonResult, DiffEntry, MissingColumn, MissingTable
from schema_comparator.report.attributes import format_attributes
from schema_comparator.report.console import _TYPE_LABELS


@dataclass(frozen=True, slots=True)
class TableGroup:
    """One qualified-table's worth of findings, in `console.py`'s
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
    findings, grouped by table."""

    groups: tuple[TableGroup, ...]


def build_tree_data(result: ComparisonResult) -> TreeData:
    """Group `result.entries` by qualified table identity, mirroring
    `console.py`'s `itertools.groupby` pattern (entries are pre-sorted by
    table identity by construction)."""
    groups = [
        TableGroup(schema_name=schema, table_name=table, entries=tuple(entries))
        for (schema, table), entries in groupby(
            result.entries, key=lambda e: e.qualified_name
        )
    ]
    return TreeData(groups=tuple(groups))


def leaf_label(entry: DiffEntry) -> str:
    """Mirror `console.py`'s three `isinstance` branches exactly, so the
    TUI's leaf text is never a second, drifting implementation of that
    formatting."""
    if isinstance(entry, MissingTable):
        return f"tabla faltante (de {entry.missing_from_profile})"
    if isinstance(entry, MissingColumn):
        return f"{entry.column_name}: columna faltante (de {entry.missing_from_profile})"
    profiles = ", ".join(p for p, _ in entry.values_by_profile)
    return f"{entry.column_name}: discrepancia de atributos entre {profiles}"


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

    # MissingTable: simplest shape, no column-level attributes to show.
    schema, table = entry.qualified_name
    return f"{schema}.{table}: tabla faltante en el perfil '{entry.missing_from_profile}'"


def header_counts(result: ComparisonResult) -> dict[type, int]:
    """Count findings per diff-entry category, using the exact same
    approach as `console.py`'s `render_console`, so the counts cannot
    diverge (imports `_TYPE_LABELS` rather than redefining it)."""
    counts = dict.fromkeys(_TYPE_LABELS, 0)
    for entry in result.entries:
        counts[type(entry)] += 1
    return counts


def header_text(result: ComparisonResult) -> str:
    """Render the header line: compared profiles plus per-category
    counts, matching `render_console`'s "Findings by category" totals."""
    counts = header_counts(result)
    profiles = ", ".join(result.compared_profiles)
    parts = [f"Perfiles comparados: {profiles}"]
    parts += [f"{label}: {counts[t]}" for t, label in _TYPE_LABELS.items()]
    return " | ".join(parts)


def entry_matches(entry: DiffEntry, filter_text: str) -> bool:
    """Case-insensitive substring match over diff-type label, qualified
    table name, and column name (when present). An empty `filter_text`
    always matches, restoring full visibility when the filter is
    cleared."""
    if not filter_text:
        return True
    needle = filter_text.lower()
    schema, table = entry.qualified_name
    haystacks = [type(entry).__name__, schema, table]
    if isinstance(entry, (MissingColumn, ColumnMismatch)):
        haystacks.append(entry.column_name)
    return any(needle in haystack.lower() for haystack in haystacks)
