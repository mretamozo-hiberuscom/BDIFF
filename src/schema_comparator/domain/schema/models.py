"""Normalized, immutable table/column schema metadata models."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ColumnSnapshot:
    """One column's normalized metadata.

    Non-applicable size/precision/scale attributes are preserved as `None`
    exactly as returned by the catalog — never fabricated.
    """

    name: str
    data_type: str
    character_maximum_length: int | None
    numeric_precision: int | None
    numeric_scale: int | None
    is_nullable: bool
    ordinal_position: int
    default_expression: str | None = None
    is_identity: bool = False
    collation: str | None = None


@dataclass(frozen=True, slots=True)
class PrimaryKeySnapshot:
    """Primary key constraint metadata."""

    name: str
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ForeignKeySnapshot:
    """Foreign key constraint metadata."""

    name: str
    columns: tuple[str, ...]
    referenced_table: str
    referenced_columns: tuple[str, ...]
    referenced_schema: str | None = None
    on_delete: str | None = None
    on_update: str | None = None


@dataclass(frozen=True, slots=True)
class IndexSnapshot:
    """Secondary or unique index metadata."""

    name: str
    columns: tuple[str, ...]
    is_unique: bool = False


@dataclass(frozen=True, slots=True)
class TableSnapshot:
    """One base table, identified by the `(schema_name, table_name)` pair.

    `columns` is already sorted (ordinal position, then name) at
    construction time.
    """

    schema_name: str
    table_name: str
    columns: tuple[ColumnSnapshot, ...]
    primary_key: PrimaryKeySnapshot | None = None
    foreign_keys: tuple[ForeignKeySnapshot, ...] = ()
    indexes: tuple[IndexSnapshot, ...] = ()

    @property
    def qualified_name(self) -> tuple[str, str]:
        """The table identity used for equality, sorting, and dict keys."""
        return (self.schema_name, self.table_name)


@dataclass(frozen=True, slots=True)
class SchemaSnapshot:
    """The full extraction result for one profile.

    `tables` is already sorted (schema, then table name) at construction
    time.
    """

    profile_name: str
    tables: tuple[TableSnapshot, ...]
