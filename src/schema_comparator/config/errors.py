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
            f"Connection profile config file not found at '{path}'. "
            "Copy config.example.yaml to config.local.yaml and edit it "
            "with your real connection strings."
        )


class ConfigParseError(ConfigError):
    """Raised when the config file is not valid/shaped YAML."""

    @classmethod
    def invalid_yaml(cls) -> "ConfigParseError":
        return cls(
            "Connection profile config file is malformed or not valid "
            "YAML. See config.example.yaml for the expected format."
        )

    @classmethod
    def invalid_shape(cls) -> "ConfigParseError":
        return cls(
            "Connection profile config file must be a YAML mapping with a "
            "top-level 'databases:' key whose value is itself a mapping of "
            "profile name to connection string. See config.example.yaml "
            "for the expected format."
        )


class ProfileValidationError(ConfigError):
    """Raised when a parsed profile entry fails validation."""

    @classmethod
    def empty_name(cls) -> "ProfileValidationError":
        return cls(
            "A connection profile name is empty or blank. Every entry "
            "under 'databases:' must have a non-empty name."
        )

    @classmethod
    def duplicate_name(cls, name: str) -> "ProfileValidationError":
        return cls(
            f"Duplicate connection profile name '{name}' (name comparison "
            "is case-insensitive). Each profile name must be unique."
        )

    @classmethod
    def empty_connection_string(cls, name: str) -> "ProfileValidationError":
        return cls(
            f"Connection profile '{name}' has an empty or blank connection "
            "string. Every profile must have a non-empty connection string."
        )
