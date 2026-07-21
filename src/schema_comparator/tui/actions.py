"""Pure, Textual-independent business logic for TUI-triggered actions.

Kept separate from `app.py`/`widgets.py` so it can be unit-tested without
any Textual app/event-loop machinery, matching the existing
`formatting.py` convention of isolating pure logic from widget code.
"""

from schema_comparator.application.use_cases.compare_profiles import CompareProfilesUseCase
from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.filters import filter_excluded_tables
from schema_comparator.discovery.service import extract_schema
from schema_comparator.domain.comparison.models import ComparisonResult

__all__ = [
    "run_comparison",
    "extract_schema",
    "filter_excluded_tables",
    "compare_snapshots",
]


def run_comparison(
    profiles: list[ConnectionProfile], exclude_patterns: list[str]
) -> ComparisonResult:
    """Re-extract schemas for `profiles` and re-compare, delegating to `CompareProfilesUseCase`.

    Raises on extraction/connection failure — callers (the Textual worker
    in `app.py`) are responsible for catching and reporting it; this
    function intentionally has no `try`/`except` of its own.
    """
    use_case = CompareProfilesUseCase(
        extractor=extract_schema,
        filter_fn=filter_excluded_tables,
        compare_fn=compare_snapshots,
    )
    return use_case.execute(profiles, exclude_patterns)
