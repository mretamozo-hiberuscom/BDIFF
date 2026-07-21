"""Profile parser for Oracle provider."""

import urllib.parse
from typing import Any

from schema_comparator.config.errors import ProfileValidationError
from schema_comparator.config.models import ConnectionProfile


def validate_oracle_profile(profile: ConnectionProfile) -> None:
    """Validate connection profile options for Oracle."""
    if not profile.connection_string and "dsn" not in profile.options and "user" not in profile.options:
        raise ProfileValidationError(
            f"El perfil '{profile.name}' para 'oracle' debe definir una cadena de conexión "
            "o especificar 'user' / 'dsn' en las opciones."
        )


def parse_oracle_options(profile: ConnectionProfile) -> dict[str, Any]:
    """Parse connection options for oracle driver."""
    options: dict[str, Any] = {}

    if profile.connection_string:
        cs = profile.connection_string
        if cs.startswith("oracle://"):
            url = urllib.parse.urlparse(cs)
            if url.hostname:
                options["host"] = url.hostname
            if url.port:
                options["port"] = url.port
            if url.username:
                options["user"] = urllib.parse.unquote(url.username)
            if url.password:
                options["password"] = urllib.parse.unquote(url.password)
            if url.path and len(url.path) > 1:
                options["service_name"] = url.path[1:]
        else:
            parts = [p.strip() for p in cs.split(";") if p.strip()]
            for part in parts:
                if "=" in part:
                    k, v = part.split("=", 1)
                    k_lower = k.strip().lower()
                    v_val = v.strip()
                    if k_lower in ("server", "host", "data source"):
                        options["host"] = v_val
                    elif k_lower in ("port",):
                        try:
                            options["port"] = int(v_val)
                        except ValueError as exc:
                            raise ProfileValidationError(
                                f"Puerto inválido '{v_val}' en el perfil de conexión."
                            ) from exc
                    elif k_lower in ("service_name", "service", "database"):
                        options["service_name"] = v_val
                    elif k_lower in ("uid", "user", "user id", "username"):
                        options["user"] = v_val
                    elif k_lower in ("pwd", "password"):
                        options["password"] = v_val

    for key, val in profile.options.items():
        options[key] = val

    return options
