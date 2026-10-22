"""Normalized object identity across profiles (ADR 0007).

`canonicalize` rewrites every snapshot so that objects meant to be the same
carry the same (canonical) names, letting the engine keep matching names
exactly. A name matches ignoring case; a schema equal to the snapshot's
`default_schema` counts as empty; names that collide inside one database
under that rule match exactly instead. The canonical spelling is the one of
the first profile (alphabetical) that has the object.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import TypeVar

from schema_comparator.domain.schema.models import (
    ForeignKeySnapshot,
    ProcedureSnapshot,
    SchemaSnapshot,
    TableSnapshot,
)

T = TypeVar("T")

# Spellings of each canonical object and column, for reports.
ObjectVariants = dict[tuple[str, str], tuple[str, ...]]
ColumnVariants = dict[tuple[str, str, str], tuple[str, ...]]


@dataclass(frozen=True)
class CanonicalSnapshots:
    snapshots: tuple[SchemaSnapshot, ...]
    table_variants: ObjectVariants
    column_variants: ColumnVariants
    procedure_variants: ObjectVariants


def _schema_key(snapshot: SchemaSnapshot, schema_name: str) -> str:
    if snapshot.default_schema is not None and schema_name == snapshot.default_schema:
        return ""
    return schema_name.casefold()


def _keys(
    items_by_profile: dict[str, Sequence[T]],
    loose_key: Callable[[str, T], tuple],
    exact_key: Callable[[str, T], tuple],
) -> dict[str, list[tuple[tuple, T]]]:
    """Key every item; loose keys that collide inside one profile fall back
    to the exact key in every profile."""
    colliding: set[tuple] = set()
    for profile, items in items_by_profile.items():
        counts = Counter(loose_key(profile, item) for item in items)
        colliding |= {key for key, count in counts.items() if count > 1}
    keyed: dict[str, list[tuple[tuple, T]]] = {}
    for profile, items in items_by_profile.items():
        keyed[profile] = []
        for item in items:
            key = loose_key(profile, item)
            if key in colliding:
                key = ("exact", *exact_key(profile, item))
            keyed[profile].append((key, item))
    return keyed


def _canonical_names(
    keyed: dict[str, list[tuple[tuple, T]]], spelling: Callable[[T], tuple[str, ...]]
) -> tuple[dict[tuple, tuple[str, ...]], dict[tuple, tuple[str, ...]]]:
    """Canonical spelling per key (first profile) and every distinct
    spelling in profile order."""
    canonical: dict[tuple, tuple[str, ...]] = {}
    spellings: dict[tuple, list[tuple[str, ...]]] = {}
    for profile in sorted(keyed):
        for key, item in keyed[profile]:
            name = spelling(item)
            canonical.setdefault(key, name)
            seen = spellings.setdefault(key, [])
            if name not in seen:
                seen.append(name)
    return canonical, {k: tuple(v) for k, v in spellings.items()}


def _column_mapper(
    column_names: dict[tuple, tuple[str, ...]],
) -> Callable[[str], str]:
    """Canonical spelling of a column name as a key, a foreign key or an
    index mentions it; a name no column of the table has stays as it is."""

    def canonical(name: str) -> str:
        for key in (("exact", name), (name.casefold(),)):
            if key in column_names:
                return column_names[key][0]
        return name

    return canonical


def _joined(spellings: tuple[tuple[str, ...], ...]) -> tuple[str, ...]:
    return tuple(".".join(s) for s in spellings) if len(spellings) > 1 else ()


def canonicalize(snapshots: Sequence[SchemaSnapshot]) -> CanonicalSnapshots:
    by_profile = {s.profile_name: s for s in snapshots}

    def object_key(profile: str, schema_name: str, name: str) -> tuple:
        return (_schema_key(by_profile[profile], schema_name), name.casefold())

    def exact_object_key(profile: str, schema_name: str, name: str) -> tuple:
        return (_schema_key(by_profile[profile], schema_name), name)

    tables = _keys(
        {p: s.tables for p, s in by_profile.items()},
        lambda p, t: object_key(p, t.schema_name, t.table_name),
        lambda p, t: exact_object_key(p, t.schema_name, t.table_name),
    )
    table_names, table_spellings = _canonical_names(
        tables, lambda t: (t.schema_name, t.table_name)
    )

    # Columns are keyed per canonical table, across the profiles that have it.
    tables_by_key: dict[tuple, dict[str, TableSnapshot]] = {}
    for profile, keyed_tables in tables.items():
        for table_key, table in keyed_tables:
            tables_by_key.setdefault(table_key, {})[profile] = table

    column_variants: ColumnVariants = {}
    keyed_columns_by_table: dict[tuple, dict[str, list]] = {}
    column_names_by_table: dict[tuple, dict[tuple, tuple[str, ...]]] = {}
    column_mappers: dict[tuple, Callable[[str], str]] = {}
    for table_key, table_by_profile in tables_by_key.items():
        keyed_columns = _keys(
            {p: t.columns for p, t in table_by_profile.items()},
            lambda _p, c: (c.name.casefold(),),
            lambda _p, c: (c.name,),
        )
        column_names, column_spellings = _canonical_names(
            keyed_columns, lambda c: (c.name,)
        )
        schema_name, table_name = table_names[table_key]
        for column_key, spellings in column_spellings.items():
            if variants := _joined(spellings):
                column = column_names[column_key][0]
                column_variants[(schema_name, table_name, column)] = variants
        keyed_columns_by_table[table_key] = keyed_columns
        column_names_by_table[table_key] = column_names
        column_mappers[table_key] = _column_mapper(column_names)

    def referenced_table_key(profile: str, table: TableSnapshot, fk) -> tuple | None:
        schema = (
            table.schema_name if fk.referenced_schema is None else fk.referenced_schema
        )
        sk = _schema_key(by_profile[profile], schema)
        for key in (
            ("exact", sk, fk.referenced_table),
            (sk, fk.referenced_table.casefold()),
        ):
            if key in column_mappers:
                return key
        return None

    def canonical_keys(profile: str, table: TableSnapshot, own: Callable[[str], str]):
        """The table's PK, FKs and indexes spelled with canonical names."""

        def own_columns(names: tuple[str, ...]) -> tuple[str, ...]:
            return tuple(own(n) for n in names)

        def foreign_key(fk: ForeignKeySnapshot) -> ForeignKeySnapshot:
            ref_key = referenced_table_key(profile, table, fk)
            if ref_key is None:
                return replace(fk, columns=own_columns(fk.columns))
            ref_schema, ref_table = table_names[ref_key]
            ref = column_mappers[ref_key]
            return replace(
                fk,
                columns=own_columns(fk.columns),
                referenced_table=ref_table,
                referenced_columns=tuple(ref(n) for n in fk.referenced_columns),
                referenced_schema=None if fk.referenced_schema is None else ref_schema,
            )

        return {
            "primary_key": None
            if table.primary_key is None
            else replace(
                table.primary_key, columns=own_columns(table.primary_key.columns)
            ),
            "foreign_keys": tuple(foreign_key(fk) for fk in table.foreign_keys),
            "indexes": tuple(
                replace(
                    index,
                    columns=own_columns(index.columns),
                    descending_columns=own_columns(index.descending_columns),
                    included_columns=own_columns(index.included_columns),
                )
                for index in table.indexes
            ),
        }

    renamed_tables: dict[str, list[TableSnapshot]] = {p: [] for p in by_profile}
    for table_key, table_by_profile in tables_by_key.items():
        schema_name, table_name = table_names[table_key]
        for profile, table in table_by_profile.items():
            column_names = column_names_by_table[table_key]
            renamed_tables[profile].append(
                replace(
                    table,
                    schema_name=schema_name,
                    table_name=table_name,
                    columns=tuple(
                        replace(c, name=column_names[k][0])
                        for k, c in keyed_columns_by_table[table_key][profile]
                    ),
                    **canonical_keys(profile, table, column_mappers[table_key]),
                )
            )

    procedures = _keys(
        {p: s.procedures for p, s in by_profile.items()},
        lambda p, r: object_key(p, r.schema_name, r.procedure_name),
        lambda p, r: exact_object_key(p, r.schema_name, r.procedure_name),
    )
    procedure_names, procedure_spellings = _canonical_names(
        procedures, lambda r: (r.schema_name, r.procedure_name)
    )

    def renamed_procedures(profile: str) -> tuple[ProcedureSnapshot, ...]:
        return tuple(
            sorted(
                (
                    replace(
                        r,
                        schema_name=procedure_names[k][0],
                        procedure_name=procedure_names[k][1],
                    )
                    for k, r in procedures[profile]
                ),
                key=lambda r: r.qualified_name,
            )
        )

    canonical = tuple(
        replace(
            snapshot,
            tables=tuple(
                sorted(
                    renamed_tables[snapshot.profile_name],
                    key=lambda t: t.qualified_name,
                )
            ),
            procedures=renamed_procedures(snapshot.profile_name),
        )
        for snapshot in snapshots
    )
    return CanonicalSnapshots(
        snapshots=canonical,
        table_variants={
            table_names[k]: v for k, s in table_spellings.items() if (v := _joined(s))
        },
        column_variants=column_variants,
        procedure_variants={
            procedure_names[k]: v
            for k, s in procedure_spellings.items()
            if (v := _joined(s))
        },
    )
