"""Two-pass union-of-identities N-way comparison engine."""

from collections.abc import Sequence

from schema_comparator.compare.errors import (
    DuplicateProfileNameError,
    InsufficientSnapshotsError,
)
from schema_comparator.compare.models import (
    ColumnAttributes,
    ColumnMismatch,
    ComparisonResult,
    MissingColumn,
    MissingTable,
)
from schema_comparator.discovery.models import SchemaSnapshot, TableSnapshot


def _validate(snapshots: Sequence[SchemaSnapshot]) -> None:
    if len(snapshots) < 2:
        raise InsufficientSnapshotsError.for_count(len(snapshots))

    names = [s.profile_name for s in snapshots]
    if len(set(names)) != len(names):
        duplicates = [n for n in names if names.count(n) > 1]
        raise DuplicateProfileNameError.for_names(duplicates)


def _build_presence_index(
    snapshots: Sequence[SchemaSnapshot],
) -> tuple[set[tuple[str, str]], dict[str, set[tuple[str, str]]]]:
    union: set[tuple[str, str]] = set()
    presence: dict[str, set[tuple[str, str]]] = {}
    for snapshot in snapshots:
        identities = {t.qualified_name for t in snapshot.tables}
        union |= identities
        presence[snapshot.profile_name] = identities
    return union, presence


def _build_table_index(
    snapshots: Sequence[SchemaSnapshot],
) -> dict[str, dict[tuple[str, str], TableSnapshot]]:
    return {
        snapshot.profile_name: {t.qualified_name: t for t in snapshot.tables}
        for snapshot in snapshots
    }


def _evaluate_tables(
    union: set[tuple[str, str]],
    presence: dict[str, set[tuple[str, str]]],
    profile_names: tuple[str, ...],
) -> tuple[MissingTable, ...]:
    entries: list[MissingTable] = []
    for schema_name, table_name in sorted(union):
        identity = (schema_name, table_name)
        missing_from = sorted(
            name for name in profile_names if identity not in presence[name]
        )
        entries.extend(
            MissingTable(
                schema_name=schema_name,
                table_name=table_name,
                missing_from_profile=name,
            )
            for name in missing_from
        )
    return tuple(entries)


def _evaluate_columns(
    union: set[tuple[str, str]],
    presence: dict[str, set[tuple[str, str]]],
    table_index: dict[str, dict[tuple[str, str], TableSnapshot]],
    profile_names: tuple[str, ...],
) -> tuple[MissingColumn | ColumnMismatch, ...]:
    entries: list[MissingColumn | ColumnMismatch] = []

    for schema_name, table_name in sorted(union):
        identity = (schema_name, table_name)
        profiles_with_table = sorted(
            name for name in profile_names if identity in presence[name]
        )
        if len(profiles_with_table) < 2:
            # Not a matched table (present in 0 or 1 profile) — the
            # table-level pass already fully covers this case. A profile
            # missing the table entirely is simply never a member of
            # `profiles_with_table`, so it can never contribute or receive
            # a MissingColumn/ColumnMismatch entry here.
            continue

        columns_by_profile = {
            name: {c.name: c for c in table_index[name][identity].columns}
            for name in profiles_with_table
        }
        column_names = sorted(
            {name for cols in columns_by_profile.values() for name in cols}
        )

        for column_name in column_names:
            present = [
                p for p in profiles_with_table if column_name in columns_by_profile[p]
            ]
            missing = [
                p
                for p in profiles_with_table
                if column_name not in columns_by_profile[p]
            ]

            entries.extend(
                MissingColumn(
                    schema_name=schema_name,
                    table_name=table_name,
                    column_name=column_name,
                    missing_from_profile=profile,
                )
                for profile in sorted(missing)
            )

            if len(present) < 2:
                continue  # nothing to compare — at most one profile has it

            attrs_by_profile = {
                p: ColumnAttributes.from_snapshot(columns_by_profile[p][column_name])
                for p in present
            }
            if len(set(attrs_by_profile.values())) > 1:
                entries.append(
                    ColumnMismatch(
                        schema_name=schema_name,
                        table_name=table_name,
                        column_name=column_name,
                        values_by_profile=tuple(sorted(attrs_by_profile.items())),
                    )
                )

    return tuple(entries)


_TYPE_RANK: dict[type, int] = {
    MissingTable: 0,
    MissingColumn: 1,
    ColumnMismatch: 2,
}


def _sort_key(
    entry: MissingTable | MissingColumn | ColumnMismatch,
) -> tuple[str, str, int, str, str]:
    return (
        entry.schema_name,
        entry.table_name,
        _TYPE_RANK[type(entry)],
        getattr(entry, "column_name", ""),
        getattr(entry, "missing_from_profile", ""),
    )


def compare_snapshots(snapshots: Sequence[SchemaSnapshot]) -> ComparisonResult:
    """Compare 2+ named schema snapshots and return a deterministic diff.

    Raises `InsufficientSnapshotsError` for fewer than 2 snapshots and
    `DuplicateProfileNameError` for repeated profile names. Never returns a
    partial `ComparisonResult` when a precondition is violated.
    """
    _validate(snapshots)
    profile_names = tuple(sorted(s.profile_name for s in snapshots))
    union, presence = _build_presence_index(snapshots)
    table_index = _build_table_index(snapshots)

    table_entries = _evaluate_tables(union, presence, profile_names)
    column_entries = _evaluate_columns(union, presence, table_index, profile_names)

    entries = tuple(sorted(table_entries + column_entries, key=_sort_key))
    return ComparisonResult(compared_profiles=profile_names, entries=entries)
