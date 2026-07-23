"""Optional table and routine substring exclusion applied to SchemaSnapshot."""

from collections.abc import Sequence
from dataclasses import replace

from schema_comparator.discovery.models import SchemaSnapshot


def filter_excluded_tables(
    snapshot: SchemaSnapshot, exclude_patterns: Sequence[str]
) -> SchemaSnapshot:
    """Return a copy of `snapshot` using dataclasses.replace with tables dropped matching `exclude_patterns`.

    Preserves procedures and all other snapshot fields intact.
    """
    if not exclude_patterns:
        return snapshot
    needles = [p.lower() for p in exclude_patterns if p]
    if not needles:
        return snapshot
    tables = tuple(
        table
        for table in snapshot.tables
        if not any(needle in table.table_name.lower() for needle in needles)
    )
    return replace(snapshot, tables=tables)


def filter_excluded_routines(
    snapshot: SchemaSnapshot, exclude_routines: Sequence[str]
) -> SchemaSnapshot:
    """Return a copy of `snapshot` using dataclasses.replace with procedures dropped matching `exclude_routines`."""
    if not exclude_routines:
        return snapshot
    needles = [p.lower() for p in exclude_routines if p]
    if not needles:
        return snapshot
    procedures = tuple(
        proc
        for proc in snapshot.procedures
        if not any(needle in proc.procedure_name.lower() for needle in needles)
    )
    return replace(snapshot, procedures=procedures)
