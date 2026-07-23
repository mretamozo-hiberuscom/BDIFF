"""Unit tests for filter_excluded_tables procedures preservation."""

from schema_comparator.discovery.filters import filter_excluded_tables, filter_excluded_routines
from schema_comparator.domain.schema.models import ProcedureSnapshot, SchemaSnapshot, TableSnapshot, ColumnSnapshot


def test_filter_excluded_tables_preserves_procedures():
    tbl = TableSnapshot(
        schema_name="dbo",
        table_name="AuditLogs",
        columns=(ColumnSnapshot("id", "int", None, 10, 0, False, 1),),
    )
    proc = ProcedureSnapshot(schema_name="dbo", procedure_name="sp_AuditCheck")
    snapshot = SchemaSnapshot(profile_name="Profile1", provider_id="sqlserver", tables=(tbl,), procedures=(proc,))

    filtered = filter_excluded_tables(snapshot, ["Audit"])

    assert len(filtered.tables) == 0
    assert filtered.procedures == snapshot.procedures
    assert len(filtered.procedures) == 1


def test_filter_excluded_routines():
    proc1 = ProcedureSnapshot(schema_name="dbo", procedure_name="sp_AuditCheck")
    proc2 = ProcedureSnapshot(schema_name="dbo", procedure_name="sp_GetUsers")
    snapshot = SchemaSnapshot(profile_name="Profile1", provider_id="sqlserver", tables=(), procedures=(proc1, proc2))

    filtered = filter_excluded_routines(snapshot, ["Audit"])

    assert len(filtered.procedures) == 1
    assert filtered.procedures[0].procedure_name == "sp_GetUsers"
