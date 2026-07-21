"""Database provider capabilities and comparison mode policy models."""

from dataclasses import dataclass
from enum import Enum


class ComparisonMode(str, Enum):
    """Comparison policy modes."""

    NATIVE_STRICT = "native-strict"
    SEMANTIC_EQUIVALENT = "semantic-equivalent"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Capabilities and features supported by a specific database provider."""

    provider_id: str
    supports_schemas: bool = True
    supports_transactional_ddl: bool = True
    supports_drop_column: bool = True
    supports_alter_column: bool = True
