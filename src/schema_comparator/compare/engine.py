"""Two-pass union-of-identities N-way comparison engine."""

from collections.abc import Sequence

from schema_comparator.compare.errors import (
    DuplicateProfileNameError,
    InsufficientSnapshotsError,
)
from schema_comparator.compare.models import ComparisonResult, MissingTable
from schema_comparator.discovery.models import SchemaSnapshot


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


def _evaluate(
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


def compare_snapshots(snapshots: Sequence[SchemaSnapshot]) -> ComparisonResult:
    """Compare 2+ named schema snapshots and return a deterministic diff.

    Raises `InsufficientSnapshotsError` for fewer than 2 snapshots and
    `DuplicateProfileNameError` for repeated profile names. Never returns a
    partial `ComparisonResult` when a precondition is violated.
    """
    _validate(snapshots)
    profile_names = tuple(sorted(s.profile_name for s in snapshots))
    union, presence = _build_presence_index(snapshots)
    entries = _evaluate(union, presence, profile_names)
    return ComparisonResult(compared_profiles=profile_names, entries=entries)
