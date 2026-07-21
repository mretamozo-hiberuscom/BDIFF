"""Use case for loading profiles, extracting schemas, filtering, and comparing."""

from typing import Callable, Sequence

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.filters import filter_excluded_tables
from schema_comparator.discovery.service import extract_schema
from schema_comparator.domain.comparison.models import ComparisonResult
from schema_comparator.domain.schema.models import SchemaSnapshot


class CompareProfilesUseCase:
    """Orchestrates schema extraction, table filtering, and N-way comparison.

    Acts as the primary entry point for application logic, decoupling CLI
    and TUI callers from low-level extraction and comparison engines.
    """

    def __init__(
        self,
        extractor: Callable[[ConnectionProfile], SchemaSnapshot] = extract_schema,
        filter_fn: Callable[[SchemaSnapshot, Sequence[str]], SchemaSnapshot] = filter_excluded_tables,
        compare_fn: Callable[[Sequence[SchemaSnapshot]], ComparisonResult] = compare_snapshots,
    ) -> None:
        self._extractor = extractor
        self._filter_fn = filter_fn
        self._compare_fn = compare_fn

    def execute(
        self,
        profiles: Sequence[ConnectionProfile],
        exclude_patterns: Sequence[str] | None = None,
    ) -> ComparisonResult:
        """Extract schemas for `profiles`, apply `exclude_patterns`, and compare.

        Returns a `ComparisonResult` containing normalized diff entries.
        """
        snapshots: list[SchemaSnapshot] = [self._extractor(profile) for profile in profiles]
        if exclude_patterns:
            snapshots = [
                self._filter_fn(snapshot, exclude_patterns) for snapshot in snapshots
            ]
        return self._compare_fn(snapshots)
