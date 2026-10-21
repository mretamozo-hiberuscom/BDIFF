"""SQL Server error translation from pyodbc exceptions to domain discovery errors."""

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import (
    ConnectionFailedError,
    DiscoveryError,
    DriverUnavailableError,
    translate_query_error,
)
from schema_comparator.discovery.errors import (
    translate_connect_error as _translate_connect_error,
)
from schema_comparator.domain.errors import describe_error
from schema_comparator.infrastructure.providers.sqlserver.profile_parser import (
    has_driver_keyword,
)

__all__ = ["describe_failure", "translate_connect_error", "translate_query_error"]

_DRIVER_18 = "ODBC Driver 18 for SQL Server"


def _uses_driver_18_without_trust(
    connection_string: str, installed_drivers: tuple[str, ...], profile_name: str
) -> bool:
    folded = connection_string.casefold()
    if "trustservercertificate" in folded:
        return False
    if has_driver_keyword(connection_string, name=profile_name):
        return _DRIVER_18.casefold() in folded
    # Without an explicit driver, connect() falls back to 18 only when 17 is
    # missing (see connection.DRIVER_PREFERENCE).
    return _DRIVER_18 in installed_drivers and not any(
        "Driver 17" in driver for driver in installed_drivers
    )


def translate_connect_error(
    profile_name: str,
    exc: Exception,
    *,
    connection_string: str = "",
    installed_drivers: tuple[str, ...] = (),
) -> DiscoveryError:
    """Translate a connect-phase `pyodbc.Error`, naming the installed SQL
    Server drivers or the Driver 18 certificate option when they explain the
    failure. Driver names are not secrets; the connection string never
    reaches the message."""
    error = _translate_connect_error(profile_name, exc)
    installed_drivers = tuple(d for d in installed_drivers if "SQL Server" in d)
    if isinstance(error, DriverUnavailableError):
        names = ", ".join(installed_drivers) if installed_drivers else "ninguno"
        return DriverUnavailableError.for_profile(
            profile_name, f"Drivers de SQL Server instalados: {names}."
        )
    if isinstance(error, ConnectionFailedError) and _uses_driver_18_without_trust(
        connection_string, installed_drivers, profile_name
    ):
        return ConnectionFailedError.for_profile(
            profile_name,
            "Con ODBC Driver 18 la conexión se cifra por defecto: si el "
            "servidor usa un certificado autofirmado, añadí "
            "TrustServerCertificate=yes a la cadena del perfil.",
        )
    return error


def describe_failure(profile: ConnectionProfile, exc: BaseException) -> str:
    """User-facing text for a failure while connecting to or validating a
    SQL Server profile: pyodbc errors are translated, anything else shows
    only BDIFF's own message or the exception type."""
    import pyodbc

    from schema_comparator.infrastructure.providers.sqlserver import connection

    if isinstance(exc, pyodbc.Error):
        return str(
            translate_connect_error(
                profile.name,
                exc,
                connection_string=profile.connection_string,
                installed_drivers=connection.installed_sqlserver_drivers(),
            )
        )
    return describe_error(exc)
