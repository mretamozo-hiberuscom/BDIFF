"""Pure, Textual-independent business logic for TUI-triggered actions."""

from schema_comparator.application.services.extraction import (
    SchemaExtractionService,
    default_extract_schema as extract_schema,
)
from schema_comparator.application.use_cases.compare_profiles import CompareProfilesUseCase
from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.filters import filter_excluded_routines, filter_excluded_tables
from schema_comparator.domain.comparison.models import ComparisonFilters, ComparisonResult
from schema_comparator.infrastructure.providers import ProviderRegistry, get_default_registry

__all__ = [
    "build_compare_profiles_use_case",
    "run_comparison",
    "extract_schema",
    "filter_excluded_tables",
    "filter_excluded_routines",
    "compare_snapshots",
]


def build_compare_profiles_use_case(
    registry: ProviderRegistry | None = None,
) -> CompareProfilesUseCase:
    """Factory creating CompareProfilesUseCase wired to SchemaExtractionService."""
    extraction_service = SchemaExtractionService(registry or get_default_registry())
    return CompareProfilesUseCase(
        extractor=extraction_service.extract,
        filter_fn=filter_excluded_tables,
        compare_fn=compare_snapshots,
    )


def run_comparison(
    profiles: list[ConnectionProfile],
    filters: ComparisonFilters | list[str] | None = None,
    registry: ProviderRegistry | None = None,
) -> ComparisonResult:
    """Re-extract schemas for `profiles` and re-compare, delegating to `CompareProfilesUseCase`."""
    if registry is not None:
        extraction_service = SchemaExtractionService(registry)
        extractor = extraction_service.extract
    else:
        extractor = extract_schema

    use_case = CompareProfilesUseCase(
        extractor=extractor,
        filter_fn=filter_excluded_tables,
        compare_fn=compare_snapshots,
    )
    return use_case.execute(profiles, filters)
