"""Textual-independent model of the consolidation (decision) screen.

Merges sibling findings into one decision card, says which profiles a
decision may target, and turns the decisions into the resolutions that
`compare.consolidation.write_sql_scripts` renders.
"""

from dataclasses import dataclass, field

from schema_comparator.compare.consolidation import (
    ColumnAction,
    ColumnDeletionResolution,
    ColumnResolution,
    TableAction,
    TableDeletionResolution,
    TableResolution,
)
from schema_comparator.infrastructure.providers.sqlserver.ddl_renderer import (
    column_change_may_lose_data,
)
from schema_comparator.compare.models import (
    ColumnAttributes,
    ColumnMismatch,
    DiffEntry,
    MissingColumn,
    MissingTable,
    NamedColumnAttributes,
)


@dataclass(frozen=True)
class MergedMissingTable:
    """Every MissingTable of one table identity, as a single decision.

    ``missing_from_profiles`` lists every profile where the table is ABSENT
    (sorted); ``present_columns`` every profile where it IS present, with
    its full column definition.
    """

    schema_name: str
    table_name: str
    missing_from_profiles: tuple[str, ...]
    present_columns: tuple[tuple[str, tuple[NamedColumnAttributes, ...]], ...]

    @property
    def qualified_name(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)


@dataclass(frozen=True)
class MergedMissingColumn:
    """Every MissingColumn of one column identity, as a single decision."""

    schema_name: str
    table_name: str
    column_name: str
    missing_from_profiles: tuple[str, ...]
    present_attributes: tuple[tuple[str, ColumnAttributes], ...]

    @property
    def qualified_name(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)


# A decision card: one merged missing table/column or one column mismatch.
DecisionEntry = MergedMissingTable | MergedMissingColumn | ColumnMismatch


def group_findings(
    entries: tuple[DiffEntry, ...],
) -> dict[str, list[DecisionEntry]]:
    """Decision cards per `schema.table`, merging the per-profile
    MissingTable/MissingColumn siblings and keeping the engine's order."""
    by_table: dict[str, list[DiffEntry]] = {}
    for entry in entries:
        schema, table = entry.qualified_name
        by_table.setdefault(f"{schema}.{table}", []).append(entry)

    groups: dict[str, list[DecisionEntry]] = {}
    for table_key, table_entries in by_table.items():
        cards: list[DecisionEntry] = []
        missing_tables = [e for e in table_entries if isinstance(e, MissingTable)]
        if missing_tables:
            first = missing_tables[0]
            cards.append(
                MergedMissingTable(
                    schema_name=first.schema_name,
                    table_name=first.table_name,
                    missing_from_profiles=tuple(
                        sorted(e.missing_from_profile for e in missing_tables)
                    ),
                    present_columns=first.present_columns,
                )
            )
        merged_columns: set[str] = set()
        for entry in table_entries:
            if isinstance(entry, MissingTable):
                continue
            if not isinstance(entry, MissingColumn):
                cards.append(entry)
                continue
            if entry.column_name in merged_columns:
                continue
            merged_columns.add(entry.column_name)
            siblings = [
                e
                for e in table_entries
                if isinstance(e, MissingColumn) and e.column_name == entry.column_name
            ]
            cards.append(
                MergedMissingColumn(
                    schema_name=entry.schema_name,
                    table_name=entry.table_name,
                    column_name=entry.column_name,
                    missing_from_profiles=tuple(
                        sorted(e.missing_from_profile for e in siblings)
                    ),
                    present_attributes=entry.present_attributes,
                )
            )
        groups[table_key] = cards
    return groups


def _present_profiles(entry: DecisionEntry) -> tuple[str, ...]:
    if isinstance(entry, MergedMissingTable):
        return tuple(profile for profile, _ in entry.present_columns)
    if isinstance(entry, MergedMissingColumn):
        return tuple(profile for profile, _ in entry.present_attributes)
    return tuple(profile for profile, _ in entry.values_by_profile)


def destination_choices(entry: DecisionEntry, target: object) -> tuple[str, ...]:
    """Profiles a decision may be applied to: where the object exists for a
    DROP; where it is missing for a missing table or column; where a column
    exists with a different definition for a mismatch fix."""
    if target is TableAction.DROP or target is ColumnAction.DROP:
        return _present_profiles(entry)
    if isinstance(entry, (MergedMissingTable, MergedMissingColumn)):
        return entry.missing_from_profiles
    return tuple(
        profile for profile, attrs in entry.values_by_profile if attrs != target
    )


def default_destinations(entry: DecisionEntry, target: object) -> tuple[str, ...]:
    """Profiles preselected when the user picks `target`."""
    if target is None:
        return ()
    return destination_choices(entry, target)


@dataclass(frozen=True)
class ColumnOptions:
    """What the user said about a column fix's data: a value for rows left
    NULL, and whether truncation or rounding is acceptable."""

    backfill_value: str | None = None
    accept_data_loss: bool = False


def needs_fill_value(target: object) -> bool:
    """A column fix asks for a fill value when it ends NOT NULL without a
    default: rows left NULL would otherwise abort the script."""
    return (
        isinstance(target, ColumnAttributes)
        and not target.is_nullable
        and not target.default_expression
    )


def may_lose_data(
    entry: DecisionEntry, target: object, destinations: tuple[str, ...]
) -> bool:
    """Whether applying `target` to a destination of a mismatch can
    truncate, round or fail to convert its values."""
    if not isinstance(entry, ColumnMismatch) or not isinstance(
        target, ColumnAttributes
    ):
        return False
    return any(
        column_change_may_lose_data(attrs, target)
        for profile, attrs in entry.values_by_profile
        if profile in destinations
    )


@dataclass
class Resolutions:
    columns: list[ColumnResolution] = field(default_factory=list)
    tables: list[TableResolution] = field(default_factory=list)
    table_deletions: list[TableDeletionResolution] = field(default_factory=list)
    column_deletions: list[ColumnDeletionResolution] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.columns or self.tables or self.table_deletions or self.column_deletions
        )


def build_resolutions(
    decisions: dict[DecisionEntry, tuple[object, tuple[str, ...]]],
    options: dict[DecisionEntry, ColumnOptions] | None = None,
) -> Resolutions:
    """Resolutions for every decision with a target and destinations; each
    destination outside `destination_choices` is ignored. `options` carries
    the fill value and accepted loss of column fixes; a blank fill value
    counts as none."""
    options = options or {}
    result = Resolutions()
    for entry, (target, destinations) in decisions.items():
        if target is None or not destinations:
            continue
        allowed = set(destination_choices(entry, target))
        dests = tuple(d for d in destinations if d in allowed)
        if not dests:
            continue
        schema, table = entry.qualified_name
        if isinstance(entry, MergedMissingTable):
            if target is TableAction.DROP:
                result.table_deletions.append(
                    TableDeletionResolution(
                        schema_name=schema,
                        table_name=table,
                        profiles_to_update=dests,
                        observed_columns_by_profile=tuple(
                            (profile, columns)
                            for profile, columns in entry.present_columns
                            if profile in dests
                        ),
                    )
                )
                continue
            columns = dict(entry.present_columns).get(target)
            if columns:
                result.tables.append(
                    TableResolution(
                        schema_name=schema,
                        table_name=table,
                        columns=columns,
                        profiles_to_update=dests,
                    )
                )
        elif target is ColumnAction.DROP:
            present = (
                entry.present_attributes
                if isinstance(entry, MergedMissingColumn)
                else entry.values_by_profile
            )
            result.column_deletions.append(
                ColumnDeletionResolution(
                    schema_name=schema,
                    table_name=table,
                    column_name=entry.column_name,
                    profiles_to_update=dests,
                    observed_by_profile=tuple(
                        (profile, attrs)
                        for profile, attrs in present
                        if profile in dests
                    ),
                )
            )
        else:
            column_options = options.get(entry, ColumnOptions())
            observed = (
                tuple(
                    (profile, attrs)
                    for profile, attrs in entry.values_by_profile
                    if profile in dests
                )
                if isinstance(entry, ColumnMismatch)
                else ()
            )
            result.columns.append(
                ColumnResolution(
                    schema_name=schema,
                    table_name=table,
                    column_name=entry.column_name,
                    target_attributes=target,
                    profiles_to_update=dests,
                    is_missing_column=isinstance(entry, MergedMissingColumn),
                    observed_by_profile=observed,
                    backfill_value=(
                        column_options.backfill_value
                        if (column_options.backfill_value or "").strip()
                        else None
                    ),
                    accept_data_loss=column_options.accept_data_loss,
                )
            )
    return result


@dataclass(frozen=True)
class DropItem:
    """One object a script will drop, and the profiles it is dropped from."""

    kind: str
    name: str
    profiles: tuple[str, ...]


def drops_in(resolutions: Resolutions) -> tuple[DropItem, ...]:
    """The DROPs the user must confirm before scripts are written."""
    tables = tuple(
        DropItem("tabla", f"{r.schema_name}.{r.table_name}", r.profiles_to_update)
        for r in resolutions.table_deletions
    )
    columns = tuple(
        DropItem(
            "columna",
            f"{r.schema_name}.{r.table_name}.{r.column_name}",
            r.profiles_to_update,
        )
        for r in resolutions.column_deletions
    )
    return tables + columns
