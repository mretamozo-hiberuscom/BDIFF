"""Domain error hierarchy for schema comparison and provider operations."""


class SchemaComparatorError(Exception):
    """Base domain exception for BDIFF schema comparator.

    Subclass messages are composed by BDIFF and never carry connection
    strings or driver free text, so they are safe to show."""


def describe_error(exc: BaseException) -> str:
    """User-facing text for `exc`: BDIFF's own message, or only the type of
    an unexpected error, whose text may hold server, database or user."""
    if isinstance(exc, SchemaComparatorError):
        return str(exc)
    return type(exc).__name__


class RoutineIntrospectionError(RuntimeError, SchemaComparatorError):
    """Raised when extraction of procedures, functions, or routines fails."""


class ModuleEnumerationError(RuntimeError, SchemaComparatorError):
    """Raised when enumeration of dependent database modules fails."""


class ModuleRefreshError(RuntimeError, SchemaComparatorError):
    """Raised when refresh/compilation of a database module fails."""


class SignatureInspectionError(RuntimeError, SchemaComparatorError):
    """Raised when checking cryptographic signatures of a module fails."""
