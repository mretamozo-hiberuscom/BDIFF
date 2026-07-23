"""Shared per-table/per-object row grouping for grid-style reports (HTML, Excel)."""

from itertools import groupby

from schema_comparator.compare.models import ComparisonResult, DiffEntry


def _row_identity(entry: DiffEntry) -> tuple[type, str | None]:
    """Same diff type + same detail name (column, procedure, constraint) identifies one logical report row."""
    detail = getattr(entry, "column_name", None) or getattr(entry, "procedure_name", None) or getattr(entry, "name", None)
    return (type(entry), detail)


def grouped_rows_by_table(
    result: ComparisonResult,
) -> list[tuple[tuple[str, str], list[list[DiffEntry]]]]:
    """Group `result.entries` by qualified object name, then within each group
    group consecutive same-identity siblings into one row each."""
    tables: list[tuple[tuple[str, str], list[list[DiffEntry]]]] = []
    sorted_entries = sorted(result.entries, key=lambda e: e.qualified_name)
    for identity, table_entries in groupby(sorted_entries, key=lambda e: e.qualified_name):
        rows = [list(group) for _, group in groupby(table_entries, key=_row_identity)]
        tables.append((identity, rows))
    return tables
