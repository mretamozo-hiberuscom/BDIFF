"""Value object representing a named database connection profile (v2 capable)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ConnectionProfile:
    """A named database connection profile.

    `provider` defaults to `"sqlserver"` for backward compatibility.
    `connection_string` contains the provider-specific connection string (with ADO.NET translation applied for SQL Server at load time).
    `options` contains additional key-value configuration options.
    """

    name: str
    connection_string: str
    provider: str = "sqlserver"
    options: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        # Defense-in-depth: redact the secret even if the object is logged
        # or interpolated with %r by an unrelated logger.
        return (
            f"ConnectionProfile(name={self.name!r}, provider={self.provider!r}, "
            "connection_string=<redacted>)"
        )
