"""Use case for loading profiles, extracting schemas, filtering, and comparing."""

from typing import Callable, Sequence

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.filters import filter_excluded_routines, filter_excluded_tables
from schema_comparator.domain.comparison.models import ComparisonFilters, ComparisonResult
from schema_comparator.domain.schema.models import SchemaSnapshot


class CompareProfilesUseCase:
    """Orchestrates schema extraction, table/routine filtering, and N-way comparison.

    Acts as the primary entry point for application logic, decoupling CLI
    and TUI callers from low-level extraction and comparison engines.
    """

    def __init__(
        self,
        *,
        extractor: Callable[[ConnectionProfile], SchemaSnapshot],
        filter_fn: Callable[[SchemaSnapshot, Sequence[str]], SchemaSnapshot] = filter_excluded_tables,
        compare_fn: Callable[[Sequence[SchemaSnapshot]], ComparisonResult] = compare_snapshots,
    ) -> None:
        self._extractor = extractor
        self._filter_fn = filter_fn
        self._compare_fn = compare_fn

    def execute(
        self,
        profiles: Sequence[ConnectionProfile],
        filters: ComparisonFilters | Sequence[str] | None = None,
    ) -> ComparisonResult:
        """Extract schemas for `profiles`, apply table/routine filters, and compare.

        Returns a `ComparisonResult` containing normalized diff entries.
        """
        if isinstance(filters, ComparisonFilters):
            ex_tables = filters.excluded_tables
            ex_routines = filters.excluded_routines
        elif filters is not None:
            ex_tables = filters
            ex_routines = ()
        else:
            ex_tables = ()
            ex_routines = ()

        snapshots: list[SchemaSnapshot] = [self._extractor(profile) for profile in profiles]

        filtered_snapshots: list[SchemaSnapshot] = []
        for snap in snapshots:
            if ex_tables:
                snap = self._filter_fn(snap, ex_tables)
            if ex_routines and hasattr(snap, "procedures"):
                snap = filter_excluded_routines(snap, ex_routines)
            filtered_snapshots.append(snap)

        return self._compare_fn(filtered_snapshots)
