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
    DiffEntry,
    ForeignKeyMismatch,
    IndexMismatch,
    MissingColumn,
    MissingProcedure,
    MissingTable,
    NamedColumnAttributes,
    PrimaryKeyMismatch,
    ProcedureMismatch,
)
from schema_comparator.domain.capabilities import ComparisonMode, RoutineComparisonPolicy
from schema_comparator.domain.comparison.type_equivalences import (
    are_types_semantically_equivalent,
)
from schema_comparator.domain.schema.models import (
    DefinitionAvailability,
    ProcedureSnapshot,
    SchemaFeature,
    SchemaSnapshot,
    TableSnapshot,
)


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
    table_index: dict[str, dict[tuple[str, str], TableSnapshot]],
    profile_names: tuple[str, ...],
) -> tuple[MissingTable, ...]:
    entries: list[MissingTable] = []
    for schema_name, table_name in sorted(union):
        identity = (schema_name, table_name)
        missing_from = sorted(
            name for name in profile_names if identity not in presence[name]
        )
        if not missing_from:
            continue

        present_profiles = sorted(
            name for name in profile_names if identity in presence[name]
        )
        present_columns: list[tuple[str, tuple[NamedColumnAttributes, ...]]] = []
        for prof in present_profiles:
            table_snap = table_index[prof][identity]
            cols = tuple(
                NamedColumnAttributes(
                    name=col.name,
                    attributes=ColumnAttributes.from_snapshot(col),
                )
                for col in table_snap.columns
            )
            present_columns.append((prof, cols))

        entries.extend(
            MissingTable(
                schema_name=schema_name,
                table_name=table_name,
                missing_from_profile=name,
                present_columns=tuple(present_columns),
            )
            for name in missing_from
        )
    return tuple(entries)


def _evaluate_columns(
    union: set[tuple[str, str]],
    presence: dict[str, set[tuple[str, str]]],
    table_index: dict[str, dict[tuple[str, str], TableSnapshot]],
    profile_names: tuple[str, ...],
    mode: ComparisonMode = ComparisonMode.NATIVE_STRICT,
) -> tuple[MissingColumn | ColumnMismatch, ...]:
    entries: list[MissingColumn | ColumnMismatch] = []

    for schema_name, table_name in sorted(union):
        identity = (schema_name, table_name)
        profiles_with_table = sorted(
            name for name in profile_names if identity in presence[name]
        )
        if len(profiles_with_table) < 2:
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

            present_attrs = tuple(
                sorted(
                    (
                        p,
                        ColumnAttributes.from_snapshot(columns_by_profile[p][column_name]),
                    )
                    for p in present
                )
            )

            entries.extend(
                MissingColumn(
                    schema_name=schema_name,
                    table_name=table_name,
                    column_name=column_name,
                    missing_from_profile=profile,
                    present_attributes=present_attrs,
                )
                for profile in sorted(missing)
            )

            if len(present) < 2:
                continue

            attrs_by_profile = dict(present_attrs)

            if mode == ComparisonMode.SEMANTIC_EQUIVALENT:
                from schema_comparator.domain.comparison.type_equivalences import get_type_family

                def _norm(attrs: ColumnAttributes) -> ColumnAttributes:
                    return ColumnAttributes(
                        data_type=get_type_family(attrs.data_type),
                        character_maximum_length=attrs.character_maximum_length,
                        numeric_precision=attrs.numeric_precision,
                        numeric_scale=attrs.numeric_scale,
                        is_nullable=attrs.is_nullable,
                        default_expression=attrs.default_expression,
                        is_identity=attrs.is_identity,
                        collation=attrs.collation,
                    )

                distinct_attrs = set(_norm(a) for a in attrs_by_profile.values())
            else:
                distinct_attrs = set(attrs_by_profile.values())

            if len(distinct_attrs) > 1:
                entries.append(
                    ColumnMismatch(
                        schema_name=schema_name,
                        table_name=table_name,
                        column_name=column_name,
                        values_by_profile=present_attrs,
                    )
                )

    return tuple(entries)


def _evaluate_advanced_objects(
    union: set[tuple[str, str]],
    presence: dict[str, set[tuple[str, str]]],
    table_index: dict[str, dict[tuple[str, str], TableSnapshot]],
    profile_names: tuple[str, ...],
) -> tuple[PrimaryKeyMismatch | ForeignKeyMismatch | IndexMismatch, ...]:
    entries: list[PrimaryKeyMismatch | ForeignKeyMismatch | IndexMismatch] = []

    for schema_name, table_name in sorted(union):
        identity = (schema_name, table_name)
        profiles_with_table = sorted(
            name for name in profile_names if identity in presence[name]
        )
        if len(profiles_with_table) < 2:
            continue

        pk_by_profile = tuple(
            (p, table_index[p][identity].primary_key) for p in profiles_with_table
        )
        pks = [pk for _, pk in pk_by_profile if pk is not None]
        if pks and len(set(pk_by_profile)) > 1:
            entries.append(
                PrimaryKeyMismatch(
                    schema_name=schema_name,
                    table_name=table_name,
                    values_by_profile=pk_by_profile,
                )
            )

        fk_names = sorted(
            {
                fk.name
                for p in profiles_with_table
                for fk in getattr(table_index[p][identity], "foreign_keys", ())
            }
        )
        for fk_name in fk_names:
            fk_by_profile = tuple(
                (
                    p,
                    next(
                        (
                            fk
                            for fk in getattr(table_index[p][identity], "foreign_keys", ())
                            if fk.name == fk_name
                        ),
                        None,
                    ),
                )
                for p in profiles_with_table
            )
            if len(set(fk_by_profile)) > 1:
                entries.append(
                    ForeignKeyMismatch(
                        schema_name=schema_name,
                        table_name=table_name,
                        fk_name=fk_name,
                        values_by_profile=fk_by_profile,
                    )
                )

        index_names = sorted(
            {
                idx.name
                for p in profiles_with_table
                for idx in getattr(table_index[p][identity], "indexes", ())
            }
        )
        for index_name in index_names:
            idx_by_profile = tuple(
                (
                    p,
                    next(
                        (
                            idx
                            for idx in getattr(table_index[p][identity], "indexes", ())
                            if idx.name == index_name
                        ),
                        None,
                    ),
                )
                for p in profiles_with_table
            )
            if len(set(idx_by_profile)) > 1:
                entries.append(
                    IndexMismatch(
                        schema_name=schema_name,
                        table_name=table_name,
                        index_name=index_name,
                        values_by_profile=idx_by_profile,
                    )
                )

    return tuple(entries)


def _evaluate_procedures(
    snapshots: Sequence[SchemaSnapshot],
    profile_names: tuple[str, ...],
    routine_policy: RoutineComparisonPolicy = RoutineComparisonPolicy.SAME_PROVIDER,
) -> tuple[MissingProcedure | ProcedureMismatch, ...]:
    if routine_policy == RoutineComparisonPolicy.DISABLED:
        return ()

    # Check provider capabilities
    if routine_policy == RoutineComparisonPolicy.ALL_CAPABLE:
        capable = [s for s in snapshots if SchemaFeature.ROUTINES in s.extracted_features]
        if len(capable) < 2:
            return ()
        snapshots = capable
        profile_names = tuple(sorted(s.profile_name for s in snapshots))
    elif routine_policy == RoutineComparisonPolicy.SAME_PROVIDER:
        providers = {s.provider_id for s in snapshots}
        if len(providers) > 1:
            return ()

    entries: list[MissingProcedure | ProcedureMismatch] = []

    proc_index: dict[str, dict[tuple[str, str], ProcedureSnapshot]] = {
        s.profile_name: {p.qualified_name: p for p in s.procedures}
        for s in snapshots
    }

    union_procs: set[tuple[str, str]] = set()
    presence_procs: dict[str, set[tuple[str, str]]] = {}
    for s in snapshots:
        identities = {p.qualified_name for p in s.procedures}
        union_procs |= identities
        presence_procs[s.profile_name] = identities

    for schema_name, proc_name in sorted(union_procs):
        identity = (schema_name, proc_name)
        missing_from = sorted(
            name for name in profile_names if identity not in presence_procs[name]
        )
        present_profiles = sorted(
            name for name in profile_names if identity in presence_procs[name]
        )

        present_procs_list = tuple(
            (p, proc_index[p][identity]) for p in present_profiles
        )

        if missing_from:
            entries.extend(
                MissingProcedure(
                    schema_name=schema_name,
                    procedure_name=proc_name,
                    missing_from_profile=name,
                    present_procedures=present_procs_list,
                )
                for name in missing_from
            )

        if len(present_profiles) >= 2:
            first_proc = present_procs_list[0][1]
            has_mismatch = False
            for _, p_snap in present_procs_list[1:]:
                if (
                    p_snap.routine_type != first_proc.routine_type
                    or p_snap.parameters != first_proc.parameters
                    or p_snap.definition_hash != first_proc.definition_hash
                    or p_snap.definition_availability != first_proc.definition_availability
                ):

                    has_mismatch = True
                    break

            if has_mismatch:
                entries.append(
                    ProcedureMismatch(
                        schema_name=schema_name,
                        procedure_name=proc_name,
                        values_by_profile=present_procs_list,
                    )
                )

    return tuple(entries)


_TYPE_RANK: dict[type, int] = {
    MissingTable: 0,
    MissingColumn: 1,
    ColumnMismatch: 2,
    PrimaryKeyMismatch: 3,
    ForeignKeyMismatch: 4,
    IndexMismatch: 5,
    MissingProcedure: 6,
    ProcedureMismatch: 7,
}


def _sort_key(
    entry: DiffEntry,
) -> tuple[str, str, int, str, str]:
    table_or_proc = getattr(entry, "table_name", getattr(entry, "procedure_name", ""))
    return (
        entry.schema_name,
        table_or_proc,
        _TYPE_RANK[type(entry)],
        getattr(entry, "column_name", getattr(entry, "procedure_name", getattr(entry, "fk_name", getattr(entry, "index_name", "")))),
        getattr(entry, "missing_from_profile", ""),
    )


def compare_snapshots(
    snapshots: Sequence[SchemaSnapshot],
    mode: ComparisonMode = ComparisonMode.NATIVE_STRICT,
    routine_policy: RoutineComparisonPolicy = RoutineComparisonPolicy.SAME_PROVIDER,
) -> ComparisonResult:
    """Compare 2+ named schema snapshots and return a deterministic diff."""
    _validate(snapshots)
    profile_names = tuple(sorted(s.profile_name for s in snapshots))
    union, presence = _build_presence_index(snapshots)
    table_index = _build_table_index(snapshots)

    table_entries = _evaluate_tables(union, presence, table_index, profile_names)
    column_entries = _evaluate_columns(union, presence, table_index, profile_names, mode=mode)
    advanced_entries = _evaluate_advanced_objects(union, presence, table_index, profile_names)
    procedure_entries = _evaluate_procedures(snapshots, profile_names, routine_policy=routine_policy)

    entries = tuple(sorted(table_entries + column_entries + advanced_entries + procedure_entries, key=_sort_key))
    return ComparisonResult(compared_profiles=profile_names, entries=entries)
