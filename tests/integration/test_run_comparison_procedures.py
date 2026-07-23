"""Integration tests for run_comparison pipeline with stored procedures extraction."""

from unittest.mock import patch

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import MissingProcedure
from schema_comparator.domain.schema.models import ProcedureSnapshot, SchemaSnapshot
from schema_comparator.tui.actions import run_comparison


def test_run_comparison_detects_missing_sqlserver_procedure():
    """Verify that run_comparison invokes extraction pipeline and detects MissingProcedure."""
    prof1 = ConnectionProfile(name="Profile1", provider="sqlserver", connection_string="Server=host1;Database=db1;")
    prof2 = ConnectionProfile(name="Profile2", provider="sqlserver", connection_string="Server=host2;Database=db2;")

    snap1 = SchemaSnapshot(
        profile_name="Profile1",
        provider_id="sqlserver",
        tables=(),
        procedures=(
            ProcedureSnapshot(schema_name="dbo", procedure_name="sp_CalculateInterest"),
        ),
    )
    snap2 = SchemaSnapshot(
        profile_name="Profile2",
        provider_id="sqlserver",
        tables=(),
        procedures=(),
    )

    def mock_extract(self, profile):
        if profile.name == "Profile1":
            return snap1
        return snap2

    with patch("schema_comparator.application.services.extraction.SchemaExtractionService.extract", side_effect=mock_extract, autospec=True):
        result = run_comparison([prof1, prof2])

    missing_procs = [e for e in result.entries if isinstance(e, MissingProcedure)]
    assert len(missing_procs) == 1
    assert missing_procs[0].procedure_name == "sp_CalculateInterest"
    assert missing_procs[0].missing_from_profile == "Profile2"
