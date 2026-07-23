"""Unit tests for stored procedure extraction, comparison, and verification."""

import pytest

from schema_comparator.domain.schema.models import (
    ParameterSnapshot,
    ProcedureSnapshot,
    SchemaSnapshot,
    TableSnapshot,
)
from schema_comparator.domain.comparison.models import (
    MissingProcedure,
    ProcedureMismatch,
)
from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.infrastructure.providers.sqlserver.introspector import (
    _hash_definition,
    build_snapshot,
)


def test_procedure_snapshot_models():
    param = ParameterSnapshot(
        name="@PolicyId",
        data_type="int",
        is_output=False,
        ordinal_position=1,
    )
    proc = ProcedureSnapshot(
        schema_name="dbo",
        procedure_name="sp_GetPolicy",
        routine_type="SQL_STORED_PROCEDURE",
        parameters=(param,),
        definition_hash="abc123hash",
        definition_sql="CREATE PROCEDURE dbo.sp_GetPolicy AS SELECT 1;",
    )
    assert proc.qualified_name == ("dbo", "sp_GetPolicy")
    assert len(proc.parameters) == 1
    assert proc.parameters[0].name == "@PolicyId"


def test_hash_definition_normalization():
    sql_crlf = "CREATE PROCEDURE dbo.test AS \r\n SELECT 1;\r\n"
    sql_lf = "CREATE PROCEDURE dbo.test AS \n SELECT 1;\n"

    h1 = _hash_definition(sql_crlf)
    h2 = _hash_definition(sql_lf)

    assert h1 is not None
    assert h1 == h2
    assert _hash_definition(None) is None


def test_introspector_build_snapshot_with_procedures():
    table_rows = [
        ("dbo", "Users", "Id", "int", None, 10, 0, "NO", 1),
    ]
    proc_rows = [
        ("dbo", "sp_GetUser", "SQL_STORED_PROCEDURE", "CREATE PROC dbo.sp_GetUser AS SELECT 1;", 0, "@UserId", "int", None, 10, 0, False, 1),
        ("dbo", "sp_GetUser", "SQL_STORED_PROCEDURE", "CREATE PROC dbo.sp_GetUser AS SELECT 1;", 0, "@ActiveOnly", "bit", None, None, None, False, 2),
    ]

    snapshot = build_snapshot("Profile1", table_rows, proc_rows=proc_rows)

    assert snapshot.profile_name == "Profile1"
    assert len(snapshot.tables) == 1
    assert len(snapshot.procedures) == 1

    proc = snapshot.procedures[0]
    assert proc.schema_name == "dbo"
    assert proc.procedure_name == "sp_GetUser"
    assert len(proc.parameters) == 2
    assert proc.parameters[0].name == "@UserId"
    assert proc.parameters[1].name == "@ActiveOnly"


def test_compare_snapshots_missing_procedure():
    proc1 = ProcedureSnapshot(
        schema_name="dbo",
        procedure_name="sp_SharedProc",
        parameters=(),
        definition_hash="hash1",
    )
    proc2 = ProcedureSnapshot(
        schema_name="dbo",
        procedure_name="sp_OnlyInProfile1",
        parameters=(),
        definition_hash="hash2",
    )

    snap1 = SchemaSnapshot(
        profile_name="Profile1",
        provider_id="sqlserver",
        tables=(),
        procedures=(proc1, proc2),
    )
    snap2 = SchemaSnapshot(
        profile_name="Profile2",
        provider_id="sqlserver",
        tables=(),
        procedures=(proc1,),
    )

    result = compare_snapshots([snap1, snap2])

    missing = [e for e in result.entries if isinstance(e, MissingProcedure)]
    assert len(missing) == 1
    assert missing[0].procedure_name == "sp_OnlyInProfile1"
    assert missing[0].missing_from_profile == "Profile2"


def test_compare_snapshots_procedure_mismatch():
    proc1 = ProcedureSnapshot(
        schema_name="dbo",
        procedure_name="sp_Calc",
        parameters=(ParameterSnapshot(name="@Val", data_type="int"),),
        definition_hash="hash_a",
    )
    proc2 = ProcedureSnapshot(
        schema_name="dbo",
        procedure_name="sp_Calc",
        parameters=(ParameterSnapshot(name="@Val", data_type="bigint"),),  # Different parameter type
        definition_hash="hash_b",
    )

    snap1 = SchemaSnapshot(profile_name="Profile1", provider_id="sqlserver", tables=(), procedures=(proc1,))
    snap2 = SchemaSnapshot(profile_name="Profile2", provider_id="sqlserver", tables=(), procedures=(proc2,))

    result = compare_snapshots([snap1, snap2])

    mismatches = [e for e in result.entries if isinstance(e, ProcedureMismatch)]
    assert len(mismatches) == 1
    assert mismatches[0].procedure_name == "sp_Calc"
    assert len(mismatches[0].values_by_profile) == 2
