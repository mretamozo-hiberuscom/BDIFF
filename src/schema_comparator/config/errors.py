"""Exception hierarchy for connection-profile configuration loading.

All messages here are pre-composed and secret-safe: no connection-string
value, fragment, or raw parser/OS traceback text is ever interpolated into
a message. Only a profile `name` may appear (never the connection string).
"""


class ConfigError(Exception):
    """Base class for all connection-profile configuration errors.

    Callers can catch this single type to handle any config-loading failure
    without needing to know the specific failure mode.
    """


class ConfigFileNotFoundError(ConfigError):
    """Raised when the config file path does not exist on disk."""

    @classmethod
    def at_path(cls, path: str) -> "ConfigFileNotFoundError":
        return cls(
            f"No se encontró el archivo de configuración de perfiles de "
            f"conexión en '{path}'. Copiá config.example.yaml a "
            "config.local.yaml y editalo con tus cadenas de conexión reales."
        )


class ConfigParseError(ConfigError):
    """Raised when the config file is not valid/shaped YAML."""

    @classmethod
    def invalid_yaml(cls) -> "ConfigParseError":
        return cls(
            "El archivo de configuración de perfiles de conexión está "
            "malformado o no es un YAML válido. Consultá config.example.yaml "
            "para ver el formato esperado."
        )

    @classmethod
    def invalid_shape(cls) -> "ConfigParseError":
        return cls(
            "El archivo de configuración de perfiles de conexión debe ser "
            "un mapeo YAML con una clave de nivel superior 'databases:' "
            "cuyo valor sea a su vez un mapeo de nombre de perfil a cadena "
            "de conexión. Consultá config.example.yaml para ver el formato "
            "esperado."
        )


class ProfileValidationError(ConfigError):
    """Raised when a parsed profile entry fails validation."""

    @classmethod
    def empty_name(cls) -> "ProfileValidationError":
        return cls(
            "El nombre de un perfil de conexión está vacío o en blanco. "
            "Cada entrada bajo 'databases:' debe tener un nombre no vacío."
        )

    @classmethod
    def duplicate_name(cls, name: str) -> "ProfileValidationError":
        return cls(
            f"Nombre de perfil de conexión duplicado '{name}' (la "
            "comparación de nombres no distingue mayúsculas/minúsculas). "
            "Cada nombre de perfil debe ser único."
        )

    @classmethod
    def empty_connection_string(cls, name: str) -> "ProfileValidationError":
        return cls(
            f"El perfil de conexión '{name}' tiene una cadena de conexión "
            "vacía o en blanco. Cada perfil debe tener una cadena de "
            "conexión no vacía."
        )

    @classmethod
    def unrecognized_connection_string_format(cls, name: str) -> "ProfileValidationError":
        return cls(
            f"El perfil de conexión '{name}' tiene una cadena de conexión "
            "en un formato no reconocido o malformado (no se encontró "
            "ninguna palabra clave ODBC/ADO.NET reconocida, o un grupo de "
            "llaves '{' sin cerrar). Revisá la cadena de conexión del "
            "perfil contra config.example.yaml para ver el formato "
            "esperado."
        )
