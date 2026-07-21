"""Domain layer root package."""

from schema_comparator.domain.capabilities import ComparisonMode, ProviderCapabilities
from schema_comparator.domain.schema.qualified_name import QualifiedName
from schema_comparator.domain.schema.types import SqlType, TypeFamily

__all__ = [
    "QualifiedName",
    "SqlType",
    "TypeFamily",
    "ProviderCapabilities",
    "ComparisonMode",
]
