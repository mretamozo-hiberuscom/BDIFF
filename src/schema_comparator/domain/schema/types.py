"""Canonical SQL data type families and representation."""

from dataclasses import dataclass
from enum import Enum


class TypeFamily(str, Enum):
    """Semantic data type families across database engines."""

    BOOLEAN = "boolean"
    INTEGER = "integer"
    DECIMAL = "decimal"
    STRING = "string"
    DATETIME = "datetime"
    BINARY = "binary"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SqlType:
    """Canonical representation of a native SQL data type and its family."""

    native_type: str
    family: TypeFamily = TypeFamily.OTHER
