"""Fictitious end-to-end demo: build two fake schema snapshots in memory
(no SQL Server connection needed), run them through the real comparison
engine, and generate real HTML/PDF/console reports.

Useful to see the tool's output shape before wiring up real database
connections. Run from the repo root with the project's venv:

    .\\.venv\\Scripts\\python.exe examples\\demo_fictitious_comparison.py

This writes `schema-diff-report-<timestamp>.html` and `.pdf` in the
current directory, and prints the console summary to stdout.
"""

from __future__ import annotations

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.discovery.models import (
    ColumnSnapshot,
    SchemaSnapshot,
    TableSnapshot,
)
from schema_comparator.report.write import write_reports


def _column(
    name: str,
    data_type: str,
    *,
    length: int | None = None,
    precision: int | None = None,
    scale: int | None = None,
    nullable: bool = True,
    ordinal: int,
) -> ColumnSnapshot:
    return ColumnSnapshot(
        name=name,
        data_type=data_type,
        character_maximum_length=length,
        numeric_precision=precision,
        numeric_scale=scale,
        is_nullable=nullable,
        ordinal_position=ordinal,
    )


def build_service_a() -> SchemaSnapshot:
    """Fictitious "policies-service" schema (the baseline)."""
    customers = TableSnapshot(
        schema_name="dbo",
        table_name="customers",
        columns=(
            _column("id", "int", nullable=False, ordinal=1),
            _column("full_name", "nvarchar", length=200, ordinal=2),
            _column("email", "nvarchar", length=320, ordinal=3),
            # Only in service A -> MissingColumn in service B.
            _column("loyalty_tier", "nvarchar", length=20, ordinal=4),
        ),
    )
    policies = TableSnapshot(
        schema_name="dbo",
        table_name="policies",
        columns=(
            _column("id", "int", nullable=False, ordinal=1),
            _column("customer_id", "int", nullable=False, ordinal=2),
            # decimal(10,2) here vs decimal(12,4) in service B -> ColumnMismatch.
            _column("premium_amount", "decimal", precision=10, scale=2, ordinal=3),
        ),
    )
    return SchemaSnapshot(
        profile_name="policies-service",
        tables=(customers, policies),
    )


def build_service_b() -> SchemaSnapshot:
    """Fictitious "claims-service" schema (diverges on purpose)."""
    customers = TableSnapshot(
        schema_name="dbo",
        table_name="customers",
        columns=(
            _column("id", "int", nullable=False, ordinal=1),
            _column("full_name", "nvarchar", length=200, ordinal=2),
            _column("email", "nvarchar", length=320, ordinal=3),
            # loyalty_tier intentionally absent here.
        ),
    )
    policies = TableSnapshot(
        schema_name="dbo",
        table_name="policies",
        columns=(
            _column("id", "int", nullable=False, ordinal=1),
            _column("customer_id", "int", nullable=False, ordinal=2),
            _column("premium_amount", "decimal", precision=12, scale=4, ordinal=3),
        ),
    )
    # "claims" table only exists in service B -> MissingTable in service A.
    claims = TableSnapshot(
        schema_name="dbo",
        table_name="claims",
        columns=(
            _column("id", "int", nullable=False, ordinal=1),
            _column("policy_id", "int", nullable=False, ordinal=2),
            _column("status", "nvarchar", length=30, ordinal=3),
        ),
    )
    return SchemaSnapshot(
        profile_name="claims-service",
        tables=(customers, policies, claims),
    )


def main() -> None:
    snapshots = [build_service_a(), build_service_b()]
    result = compare_snapshots(snapshots)

    print(f"Compared profiles: {', '.join(result.compared_profiles)}")
    print(f"Diff entries found: {len(result.entries)}\n")

    write_reports(result)


if __name__ == "__main__":
    main()
