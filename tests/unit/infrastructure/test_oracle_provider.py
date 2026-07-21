"""Unit tests for Oracle provider."""

import pytest

from schema_comparator.config.errors import ProfileValidationError
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ColumnAttributes
from schema_comparator.infrastructure.providers.oracle import OracleProvider
from schema_comparator.infrastructure.providers.oracle.ddl_renderer import (
    format_oracle_column_definition,
    format_oracle_data_type,
    generate_oracle_script,
    quote_identifier,
)
from schema_comparator.infrastructure.providers.oracle.introspector import build_snapshot
from schema_comparator.infrastructure.providers.oracle.profile_parser import (
    parse_oracle_options,
    validate_oracle_profile,
)
from schema_comparator.infrastructure.providers.registry import get_default_registry


def test_oracle_registration():
    registry = get_default_registry()
    assert "oracle" in registry.list_providers()
    oracle_p = registry.require("oracle")
    assert isinstance(oracle_p, OracleProvider)
    assert oracle_p.provider_id == "oracle"


def test_oracle_capabilities():
    p = OracleProvider()
    caps = p.capabilities()
    assert caps.provider_id == "oracle"
    assert caps.supports_schemas is True
    assert caps.supports_drop_column is True


def test_quote_identifier():
    assert quote_identifier("EMPLOYEES") == '"EMPLOYEES"'
    assert quote_identifier('EMP"NAME') == '"EMP""NAME"'


def test_profile_validation_and_parsing():
    profile = ConnectionProfile(name="oracle_db", connection_string="Server=db.example.com;Port=1521;Service_Name=ORCL;Uid=hr;Pwd=secret;")
    validate_oracle_profile(profile)
    opts = parse_oracle_options(profile)
    assert opts["host"] == "db.example.com"
    assert opts["port"] == 1521
    assert opts["service_name"] == "ORCL"
    assert opts["user"] == "hr"
    assert opts["password"] == "secret"

    invalid_port = ConnectionProfile(name="bad_port", connection_string="Server=localhost;Port=invalid;")
    with pytest.raises(ProfileValidationError):
        parse_oracle_options(invalid_port)


def test_introspector_build_snapshot():
    rows = [
        ("HR", "EMPLOYEES", "EMPLOYEE_ID", "NUMBER", None, 6, 0, "N", 1, None, "YES"),
        ("HR", "EMPLOYEES", "EMAIL", "VARCHAR2", 100, None, None, "Y", 2, None, "NO"),
    ]
    snapshot = build_snapshot("oracle_profile", rows)
    assert snapshot.profile_name == "oracle_profile"
    assert len(snapshot.tables) == 1
    t = snapshot.tables[0]
    assert t.schema_name == "HR"
    assert t.table_name == "EMPLOYEES"
    assert len(t.columns) == 2
    assert t.columns[0].name == "EMPLOYEE_ID"
    assert t.columns[0].is_identity is True
    assert t.columns[1].name == "EMAIL"
    assert t.columns[1].is_nullable is True


def test_oracle_data_type_formatting():
    number_attrs = ColumnAttributes(data_type="NUMBER", character_maximum_length=None, numeric_precision=10, numeric_scale=2, is_nullable=False)
    assert format_oracle_data_type(number_attrs) == "NUMBER(10, 2)"

    varchar_attrs = ColumnAttributes(data_type="VARCHAR2", character_maximum_length=50, numeric_precision=None, numeric_scale=None, is_nullable=True)
    assert format_oracle_data_type(varchar_attrs) == "VARCHAR2(50)"


def test_generate_oracle_script():
    profile = ConnectionProfile(name="dev_oracle", connection_string="Server=localhost;", provider="oracle")
    col_attrs = ColumnAttributes(
        data_type="VARCHAR2",
        character_maximum_length=100,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    missing_tables = [
        ("HR", "DEPARTMENTS", [("DEPARTMENT_ID", ColumnAttributes(data_type="NUMBER", character_maximum_length=None, numeric_precision=4, numeric_scale=0, is_nullable=False))]),
    ]
    missing_cols = [("HR", "EMPLOYEES", "SALARY", ColumnAttributes(data_type="NUMBER", character_maximum_length=None, numeric_precision=8, numeric_scale=2, is_nullable=True))]
    discrepant_cols = [
        (
            "HR",
            "EMPLOYEES",
            "EMAIL",
            ColumnAttributes(data_type="VARCHAR2", character_maximum_length=50, numeric_precision=None, numeric_scale=None, is_nullable=True),
            col_attrs,
        )
    ]

    script = generate_oracle_script(profile, missing_tables, missing_cols, discrepant_cols)
    assert 'CREATE TABLE "HR"."DEPARTMENTS"' in script
    assert 'ALTER TABLE "HR"."EMPLOYEES" ADD ("SALARY" NUMBER(8, 2) NULL);' in script
    assert 'ALTER TABLE "HR"."EMPLOYEES" MODIFY ("EMAIL" VARCHAR2(100) NOT NULL);' in script
