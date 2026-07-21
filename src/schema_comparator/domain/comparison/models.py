"""Result and diff-entry models for N-way schema comparison."""

from dataclasses import dataclass

from schema_comparator.domain.schema.models import ColumnSnapshot


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
    default_expression: str | None = None
    is_identity: bool = False
    collation: str | None = None

    @classmethod
    def from_snapshot(cls, column: ColumnSnapshot) -> "ColumnAttributes":
        return cls(
            data_type=column.data_type,
            character_maximum_length=column.character_maximum_length,
            numeric_precision=column.numeric_precision,
            numeric_scale=column.numeric_scale,
            is_nullable=column.is_nullable,
            default_expression=column.default_expression,
            is_identity=column.is_identity,
            collation=column.collation,
        )


@dataclass(frozen=True, slots=True)
class NamedColumnAttributes:
    """Column name + its comparable attributes, used by MissingTable to
    carry the full column definition for CREATE TABLE DDL generation."""

    name: str
    attributes: ColumnAttributes


@dataclass(frozen=True, slots=True)
class MissingTable:
    """A table present in the union baseline but absent from one profile."""

    schema_name: str
    table_name: str
    missing_from_profile: str
    present_columns: tuple[tuple[str, tuple[NamedColumnAttributes, ...]], ...] = ()

    @property
    def qualified_name(self) -> tuple[str, str]:
        """The table identity, matching `TableSnapshot.qualified_name`."""
        return (self.schema_name, self.table_name)


@dataclass(frozen=True, slots=True)
class MissingColumn:
    """A column present in some, but not all, profiles of a matched table."""

    schema_name: str
    table_name: str
    column_name: str
    missing_from_profile: str
    present_attributes: tuple[tuple[str, ColumnAttributes], ...] = ()

    @property
    def qualified_name(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)


@dataclass(frozen=True, slots=True)
class ColumnMismatch:
    """One column, 2+ profiles that have it, not all ColumnAttributes equal."""

    schema_name: str
    table_name: str
    column_name: str
    values_by_profile: tuple[tuple[str, ColumnAttributes], ...]

    @property
    def qualified_name(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)


DiffEntry = MissingTable | MissingColumn | ColumnMismatch


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """The full comparison output across N compared profiles."""

    compared_profiles: tuple[str, ...]
    entries: tuple[DiffEntry, ...]
