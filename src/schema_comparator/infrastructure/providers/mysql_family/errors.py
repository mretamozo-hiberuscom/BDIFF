"""Exception translation for MySQL and MariaDB providers.

Only the driver error number (`exc.args[0]`) reaches the message; the
driver text can name the user and client host (`'app'@'10.0.0.5'`).
"""

from schema_comparator.discovery.errors import (
    DiscoveryError,
    ConnectionFailedError,
    DriverUnavailableError,
    MetadataAccessError,
)


def _code_detail(exc: Exception) -> str:
    code = exc.args[0] if exc.args else None
    return f"Código del driver: {code}." if isinstance(code, int) else ""


def translate_connect_error(profile_name: str, exc: Exception) -> DiscoveryError:
    """Translate driver connect error into a profile-safe domain error."""
    if isinstance(exc, ImportError):
        return DriverUnavailableError(
            f"La extracción de esquema para '{profile_name}' falló: el driver "
            "MySQL/MariaDB 'pymysql' no está instalado. Ejecutá "
            "'pip install schema-comparator[mysql]'."
        )
    return ConnectionFailedError.for_profile(profile_name, _code_detail(exc))


def translate_query_error(profile_name: str, exc: Exception) -> MetadataAccessError:
    """Translate catalog query error into a profile-safe domain error."""
    return MetadataAccessError.for_profile(profile_name, _code_detail(exc))
