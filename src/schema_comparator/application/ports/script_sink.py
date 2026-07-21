"""Script sink port interface."""

from pathlib import Path
from typing import Protocol

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ComparisonResult


class ScriptSink(Protocol):
    """Abstract interface for writing generated DDL migration scripts."""

    def write_scripts(
        self,
        result: ComparisonResult,
        target_dir: Path,
        profiles: list[ConnectionProfile],
    ) -> list[Path]:
        """Write generated migration scripts to disk."""
        ...
