"""MySQL & MariaDB connection context manager."""

from contextlib import contextmanager
from typing import Any, Generator

from schema_comparator.config.models import ConnectionProfile


@contextmanager
def connect(
    profile: ConnectionProfile | None = None, **kwargs: Any
) -> Generator[Any, None, None]:
    """Establish connection to MySQL / MariaDB using pymysql driver."""
    try:
        import pymysql
    except ImportError as exc:
        raise ImportError(
            "pymysql es necesario para conectar a MySQL/MariaDB. Instálalo con 'pip install pymysql' "
            "o 'pip install schema-comparator[mysql]'."
        ) from exc

    conn_args: dict[str, Any] = {
        "host": kwargs.get("host", "localhost"),
        "port": int(kwargs.get("port", 3306))
        if kwargs.get("port") is not None
        else 3306,
        "user": kwargs.get("user", "root"),
        "password": kwargs.get("password", ""),
        "database": kwargs.get("database"),
        "charset": kwargs.get("charset", "utf8mb4"),
    }

    # Pass through any additional custom pymysql connection parameters
    standard_keys = {"host", "port", "user", "password", "database", "charset"}
    for k, v in kwargs.items():
        if k not in standard_keys and v is not None:
            conn_args[k] = v

    # Filter out None values
    conn_args = {k: v for k, v in conn_args.items() if v is not None}

    conn = pymysql.connect(**conn_args)
    try:
        yield conn
    finally:
        conn.close()
