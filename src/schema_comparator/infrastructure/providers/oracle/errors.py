"""Exception translation for Oracle provider.

Only the driver error code (`ORA-…`/`DPY-…`) reaches the message; the
driver text can name the host, port and service.
"""

from schema_comparator.discovery.errors import (
    DiscoveryError,
    ConnectionFailedError,
    DriverUnavailableError,
    MetadataAccessError,
)


def _code_detail(exc: Exception) -> str:
    error = exc.args[0] if exc.args else None
    code = getattr(error, "full_code", None)
    return f"Código del driver: {code}." if isinstance(code, str) else ""


def translate_connect_error(profile_name: str, exc: Exception) -> DiscoveryError:
    """Translate driver connect error into a profile-safe domain error."""
    if isinstance(exc, ImportError):
        return DriverUnavailableError(
            f"La extracción de esquema para '{profile_name}' falló: el driver "
            "Oracle 'oracledb' no está instalado. Ejecutá "
            "'pip install schema-comparator[oracle]'."
        )
    return ConnectionFailedError.for_profile(profile_name, _code_detail(exc))


def translate_query_error(profile_name: str, exc: Exception) -> MetadataAccessError:
    """Translate catalog query error into a profile-safe domain error."""
    return MetadataAccessError.for_profile(profile_name, _code_detail(exc))
