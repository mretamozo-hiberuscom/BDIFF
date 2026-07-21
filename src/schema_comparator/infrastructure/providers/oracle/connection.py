"""Oracle connection context manager using python-oracledb."""

from contextlib import contextmanager
from typing import Any, Generator

from schema_comparator.config.models import ConnectionProfile


@contextmanager
def connect(profile: ConnectionProfile | None = None, **kwargs: Any) -> Generator[Any, None, None]:
    """Establish connection to Oracle using oracledb driver."""
    try:
        import oracledb
    except ImportError as exc:
        raise ImportError(
            "python-oracledb es necesario para conectar a Oracle. Instálalo con 'pip install oracledb' "
            "o 'pip install bdiff[oracle]'."
        ) from exc

    user = kwargs.get("user")
    password = kwargs.get("password")
    dsn = kwargs.get("dsn")

    if not dsn and kwargs.get("host"):
        host = kwargs.get("host")
        port = kwargs.get("port", 1521)
        service = kwargs.get("service_name", "")
        dsn = f"{host}:{port}/{service}" if service else f"{host}:{port}"

    conn_kwargs: dict[str, Any] = {}
    if user:
        conn_kwargs["user"] = user
    if password:
        conn_kwargs["password"] = password
    if dsn:
        conn_kwargs["dsn"] = dsn

    standard_keys = {"user", "password", "dsn", "host", "port", "service_name"}
    for k, v in kwargs.items():
        if k not in standard_keys and v is not None:
            conn_kwargs[k] = v

    conn = oracledb.connect(**conn_kwargs)
    try:
        yield conn
    finally:
        conn.close()
