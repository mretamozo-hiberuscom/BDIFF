"""PostgreSQL error translation to profile-safe domain errors."""

from schema_comparator.discovery.errors import (
    ConnectionFailedError,
    DiscoveryError,
    DriverUnavailableError,
    MetadataAccessError,
)


def translate_connect_error(profile_name: str, exc: Exception) -> DiscoveryError:
    """Translate a PostgreSQL connection error into a domain error without leaking credentials."""
    if isinstance(exc, ImportError):
        return DriverUnavailableError(
            f"La extracción de esquema para '{profile_name}' falló: el driver "
            "PostgreSQL 'psycopg' no está instalado. Ejecutá 'pip install bdiff[postgresql]' "
            "para instalar las dependencias requeridas."
        )
    return ConnectionFailedError.for_profile(profile_name)


def translate_query_error(profile_name: str, exc: Exception) -> DiscoveryError:
    """Translate a PostgreSQL query execution error into a domain error."""
    return MetadataAccessError.for_profile(profile_name)
