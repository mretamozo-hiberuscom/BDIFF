"""Report sink port interface."""

from typing import Protocol

from schema_comparator.domain.comparison.models import ComparisonResult


class ReportSink(Protocol):
    """Abstract interface for writing comparison reports."""

    def write_reports(self, result: ComparisonResult) -> None:
        """Render and persist comparison reports."""
        ...
