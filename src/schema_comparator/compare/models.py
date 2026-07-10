"""Result and diff-entry models for N-way schema comparison."""

from dataclasses import dataclass

from schema_comparator.discovery.models import ColumnSnapshot


@dataclass(frozen=True, slots=True)
class MissingTable:
    """A table present in the union baseline but absent from one profile.

    Carries only the qualified table identity and the profile lacking the
    table — never column metadata from profiles where the table exists
    (missing-column detection is a separate diff-entry type).
    """

    schema_name: str
    table_name: str
    missing_from_profile: str

    @property
    def qualified_name(self) -> tuple[str, str]:
        """The table identity, matching `TableSnapshot.qualified_name`."""
        return (self.schema_name, self.table_name)


@dataclass(frozen=True, slots=True)
class ColumnAttributes:
    """The comparable subset of ColumnSnapshot for mismatch detection.

    Deliberately excludes `ordinal_position` (a reorder alone is not drift)
    and `name` (identity, not an attribute — two columns are compared under
    the same name by construction). Frozen + slots makes instances
    value-comparable and hashable, so equality/`set()`-based distinctness
    checks in the engine work without custom `__eq__`/`__hash__`.
    """

    data_type: str
    character_maximum_length: int | None
    numeric_precision: int | None
    numeric_scale: int | None
    is_nullable: bool

    @classmethod
    def from_snapshot(cls, column: ColumnSnapshot) -> "ColumnAttributes":
        return cls(
            data_type=column.data_type,
            character_maximum_length=column.character_maximum_length,
            numeric_precision=column.numeric_precision,
            numeric_scale=column.numeric_scale,
            is_nullable=column.is_nullable,
        )


@dataclass(frozen=True, slots=True)
class MissingColumn:
    """A column present in some, but not all, profiles of a matched table.

    Mirrors MissingTable's shape one level deeper: only emitted for
    profiles where the table itself is present — a profile missing the
    table entirely is exclusively covered by MissingTable.
    """

    schema_name: str
    table_name: str
    column_name: str
    missing_from_profile: str

    @property
    def qualified_name(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)


@dataclass(frozen=True, slots=True)
class ColumnMismatch:
    """One column, 2+ profiles that have it, not all ColumnAttributes equal.

    `values_by_profile` is a tuple of (profile_name, ColumnAttributes)
    pairs — not a dict — to stay a plain immutable, order-preserving,
    hashable/eq-comparable field on a frozen dataclass. It is always
    constructed pre-sorted ascending by profile name, so `==` comparisons
    in tests are order-independent by construction, not by coincidence.
    """

    schema_name: str
    table_name: str
    column_name: str
    values_by_profile: tuple[tuple[str, ColumnAttributes], ...]

    @property
    def qualified_name(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)


# Future changes may add further sibling frozen dataclasses and widen this
# alias — no reshape of ComparisonResult or existing entry types.
DiffEntry = MissingTable | MissingColumn | ColumnMismatch


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """The full comparison output across N compared profiles.

    `compared_profiles` names every input profile, in the same normalized
    ascending order as `entries`, so a report can render "compared: A, B, C"
    even for tables/columns present everywhere. `entries` is a flat,
    ordered, immutable sequence — deliberately not grouped or nested — so
    later diff-entry types can be appended without reshaping this
    container.
    """

    compared_profiles: tuple[str, ...]
    entries: tuple[DiffEntry, ...]
