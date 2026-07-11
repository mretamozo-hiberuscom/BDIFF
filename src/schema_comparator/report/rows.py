"""Shared per-table/per-finding row grouping for grid-style reports
(HTML, Excel).

The comparison engine emits one `MissingTable`/`MissingColumn` entry per
*missing* profile (see `compare/engine.py`), so a table or column absent
from 3 profiles produces 3 sibling `DiffEntry` objects with the same
identity. A grid report showing one row per raw entry then repeats the
same table/column label across several near-empty rows, which reads as
several unrelated findings rather than one. Grouping those siblings back
into a single row (one cell marked per missing profile) is a pure
presentation concern — the engine's one-entry-per-missing-profile model
is unchanged and still drives the console/TUI text, which already names
the profile per line.
"""

from itertools import groupby

from schema_comparator.compare.models import ComparisonResult, DiffEntry


def _row_identity(entry: DiffEntry) -> tuple[type, str | None]:
    """Same diff type + same column name (`None` for `MissingTable`,
    which has no column) identifies one logical report row."""
    return (type(entry), getattr(entry, "column_name", None))


def grouped_rows_by_table(
    result: ComparisonResult,
) -> list[tuple[tuple[str, str], list[list[DiffEntry]]]]:
    """Group `result.entries` by qualified table, then within each table
    group consecutive same-identity siblings into one row each.

    Relies on the engine's stable sort order (schema, table, diff-type,
    column name, then profile name) so `itertools.groupby` — which only
    merges *consecutive* equal keys — is sufficient; entries are never
    re-sorted here.
    """
    tables: list[tuple[tuple[str, str], list[list[DiffEntry]]]] = []
    for identity, table_entries in groupby(result.entries, key=lambda e: e.qualified_name):
        rows = [list(group) for _, group in groupby(table_entries, key=_row_identity)]
        tables.append((identity, rows))
    return tables
