"""SQLite error translation to profile-safe domain errors."""

from schema_comparator.discovery.errors import (
    ConnectionFailedError,
    DiscoveryError,
    MetadataAccessError,
)


def translate_connect_error(profile_name: str, exc: Exception) -> DiscoveryError:
    """Translate a SQLite connection error into a domain error without leaking file paths."""
    if isinstance(exc, FileNotFoundError):
        return ConnectionFailedError(
            f"La extracción de esquema para '{profile_name}' falló: el archivo "
            "SQLite indicado en el perfil no existe. Revisá la ruta de "
            "connection_string."
        )
    return ConnectionFailedError.for_profile(profile_name)


def translate_query_error(profile_name: str, exc: Exception) -> DiscoveryError:
    """Translate a SQLite query execution error into a domain error."""
    return MetadataAccessError.for_profile(profile_name)
