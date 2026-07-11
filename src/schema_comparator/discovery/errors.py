"""Domain error hierarchy and profile-safe driver failure translation.

Messages here never include a connection string, raw driver exception
text, server, database, username, password, connection object, or cursor
object. Both translation functions read only `exc.args[0]` (the SQLSTATE
pyodbc places first) — never `str(exc)` or `exc.args[1]` (the driver's
free-text message, which can contain server/database fragments).
"""


class DiscoveryError(Exception):
    """Base class for all schema-extraction failures."""


class DriverUnavailableError(DiscoveryError):
    """Raised when the required ODBC driver is not available."""

    @classmethod
    def for_profile(cls, profile_name: str) -> "DriverUnavailableError":
        return cls(
            f"La extracción de esquema para '{profile_name}' falló: el "
            "driver ODBC requerido no está disponible. Verificá que "
            "Microsoft ODBC Driver 17 o 18 para SQL Server esté instalado "
            "en esta máquina."
        )


class ConnectionFailedError(DiscoveryError):
    """Raised when a connection cannot be established or maintained,
    including connection/query timeout expiry."""

    @classmethod
    def for_profile(cls, profile_name: str) -> "ConnectionFailedError":
        return cls(
            f"La extracción de esquema para '{profile_name}' falló: no se "
            "pudo establecer o mantener la conexión dentro del tiempo "
            "límite. Verificá la conectividad de red y que el servidor sea "
            "accesible."
        )


class MetadataAccessError(DiscoveryError):
    """Raised when the connection cannot read required catalog metadata."""

    @classmethod
    def for_profile(cls, profile_name: str) -> "MetadataAccessError":
        return cls(
            f"La extracción de esquema para '{profile_name}' falló: la "
            "conexión no pudo leer los metadatos de catálogo requeridos. "
            "Verificá que el usuario del perfil tenga permisos de lectura "
            "de metadatos."
        )


def translate_connect_error(profile_name: str, exc: Exception) -> DiscoveryError:
    """Translate a connect-phase `pyodbc.Error` into a domain error."""
    sqlstate = exc.args[0] if exc.args else ""
    if sqlstate.startswith("IM"):
        return DriverUnavailableError.for_profile(profile_name)
    return ConnectionFailedError.for_profile(profile_name)


def translate_query_error(profile_name: str, exc: Exception) -> DiscoveryError:
    """Translate a query-phase `pyodbc.Error` into a domain error."""
    sqlstate = exc.args[0] if exc.args else ""
    if sqlstate == "HYT01" or sqlstate.startswith("08"):
        return ConnectionFailedError.for_profile(profile_name)
    return MetadataAccessError.for_profile(profile_name)
