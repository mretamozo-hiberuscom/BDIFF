"""Domain error hierarchy for comparison-engine precondition validation."""


class ComparisonError(Exception):
    """Base class for all comparison-engine failures."""


class InsufficientSnapshotsError(ComparisonError):
    """Raised when fewer than 2 snapshots are supplied for comparison."""

    @classmethod
    def for_count(cls, count: int) -> "InsufficientSnapshotsError":
        return cls(
            f"Comparison requires at least 2 snapshots, got {count}. "
            "Provide 2 or more named schema snapshots to compare."
        )


class DuplicateProfileNameError(ComparisonError):
    """Raised when 2+ input snapshots share the same `profile_name`."""

    @classmethod
    def for_names(cls, names: list[str]) -> "DuplicateProfileNameError":
        joined = ", ".join(sorted(set(names)))
        return cls(
            "Comparison requires distinct profile names among inputs; "
            f"duplicate profile name(s) found: {joined}."
        )
