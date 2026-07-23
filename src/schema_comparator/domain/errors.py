"""Domain error hierarchy for schema comparison and provider operations."""


class SchemaComparatorError(Exception):
    """Base domain exception for BDIFF schema comparator."""


class RoutineIntrospectionError(RuntimeError, SchemaComparatorError):
    """Raised when extraction of procedures, functions, or routines fails."""


class ModuleEnumerationError(RuntimeError, SchemaComparatorError):
    """Raised when enumeration of dependent database modules fails."""


class ModuleRefreshError(RuntimeError, SchemaComparatorError):
    """Raised when refresh/compilation of a database module fails."""
