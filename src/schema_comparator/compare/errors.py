"""Domain error hierarchy for comparison-engine precondition validation."""


class ComparisonError(Exception):
    """Base class for all comparison-engine failures."""


class InsufficientSnapshotsError(ComparisonError):
    """Raised when fewer than 2 snapshots are supplied for comparison."""

    @classmethod
    def for_count(cls, count: int) -> "InsufficientSnapshotsError":
        return cls(
            f"La comparación requiere al menos 2 instantáneas, se "
            f"recibieron {count}. Proporcioná 2 o más instantáneas de "
            "esquema con nombre para comparar."
        )


class DuplicateProfileNameError(ComparisonError):
    """Raised when 2+ input snapshots share the same `profile_name`."""

    @classmethod
    def for_names(cls, names: list[str]) -> "DuplicateProfileNameError":
        joined = ", ".join(sorted(set(names)))
        return cls(
            "La comparación requiere nombres de perfil distintos entre las "
            f"entradas; se encontraron nombre(s) de perfil duplicado(s): "
            f"{joined}."
        )
