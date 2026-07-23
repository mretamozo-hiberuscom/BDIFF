"""Database provider capabilities and comparison mode policy models."""

from dataclasses import dataclass
from enum import Enum


class ComparisonMode(str, Enum):
    """Comparison policy modes."""

    NATIVE_STRICT = "native-strict"
    SEMANTIC_EQUIVALENT = "semantic-equivalent"


class RoutineComparisonPolicy(str, Enum):
    """Routine and stored procedure comparison policy across profiles."""

    DISABLED = "disabled"
    SAME_PROVIDER = "same-provider"
    ALL_CAPABLE = "all-capable"


class RoutineExtractionPolicy(str, Enum):
    """Policy for handling errors during routine introspection."""

    STRICT = "strict"
    BEST_EFFORT = "best-effort"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Capabilities and features supported by a specific database provider."""

    provider_id: str
    supports_schemas: bool = True
    supports_transactional_ddl: bool = True
    supports_drop_column: bool = True
    supports_alter_column: bool = True
    supports_routine_introspection: bool = False
    supports_routine_definition: bool = False
    supports_module_refresh: bool = False
