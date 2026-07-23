"""Normalized, immutable table/column schema metadata models."""

from dataclasses import dataclass, field
from enum import Enum


class DefinitionAvailability(str, Enum):
    """Availability status of SQL definition (body)."""

    AVAILABLE = "available"
    ENCRYPTED = "encrypted"
    NOT_VISIBLE = "not-visible"


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
class ParameterSnapshot:
    """Stored procedure / routine parameter metadata."""

    name: str
    data_type: str
    user_type_schema: str | None = None
    max_length_bytes: int | None = None
    character_maximum_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None
    is_output: bool = False
    is_return_value: bool = False
    ordinal_position: int = 1


@dataclass(frozen=True, slots=True)
class ProcedureSnapshot:
    """One stored procedure or routine metadata.

    Identified by `(schema_name, procedure_name)`.
    `definition_hash` is an optional hash of normalized T-SQL body for drift detection.
    """

    schema_name: str
    procedure_name: str
    routine_type: str = "PROCEDURE"  # 'PROCEDURE', 'FUNCTION', etc.
    parameters: tuple[ParameterSnapshot, ...] = ()
    definition_hash: str | None = None
    definition_sql: str | None = None
    definition_availability: str = "available"
    uses_ansi_nulls: bool | None = None
    uses_quoted_identifier: bool | None = None
    is_schema_bound: bool | None = None

    @property
    def qualified_name(self) -> tuple[str, str]:
        return (self.schema_name, self.procedure_name)


@dataclass(frozen=True, slots=True)
class SchemaSnapshot:
    """The full extraction result for one profile.

    `tables` and `procedures` are sorted at construction time.
    """

    profile_name: str
    tables: tuple[TableSnapshot, ...]
    procedures: tuple[ProcedureSnapshot, ...] = ()
    provider_id: str = "sqlserver"
    extracted_features: tuple[str, ...] = ("tables", "procedures")
