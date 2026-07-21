"""Unit tests for the ConnectionProfile value object."""

import dataclasses

import pytest

from schema_comparator.config.models import ConnectionProfile


def test_profile_exposes_expected_fields() -> None:
    profile = ConnectionProfile(
        name="poliza-service",
        connection_string=(
            "Driver={ODBC Driver 18 for SQL Server};Server=srv1;"
            "Database=PolizaDB;UID=u;PWD=p;"
        ),
    )
    field_names = {f.name for f in dataclasses.fields(profile)}
    assert field_names == {"name", "connection_string", "provider", "options"}
    assert profile.provider == "sqlserver"
    assert profile.options == {}
    with pytest.raises((AttributeError, TypeError)):
        profile.extra_attribute = "not allowed"  # type: ignore[attr-defined]


def test_profile_is_immutable() -> None:
    profile = ConnectionProfile(name="siniestro-service", connection_string="X")
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.name = "changed"  # type: ignore[misc]


def test_windows_auth_connection_string_accepted_unchanged() -> None:
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};Server=srv2;"
        "Database=SiniestroDB;Trusted_Connection=yes;"
    )
    profile = ConnectionProfile(name="siniestro-service", connection_string=conn_str)
    assert profile.connection_string == conn_str


def test_repr_redacts_sql_auth_connection_string() -> None:
    profile = ConnectionProfile(
        name="poliza-service",
        connection_string="Driver={ODBC Driver 18 for SQL Server};UID=SECRET_USER;PWD=SECRET_PASS;",
    )
    rendered = repr(profile)
    assert "<redacted>" in rendered
    assert "SECRET_USER" not in rendered
    assert "SECRET_PASS" not in rendered


def test_repr_redacts_windows_auth_connection_string() -> None:
    profile = ConnectionProfile(
        name="siniestro-service",
        connection_string="Driver={ODBC Driver 18 for SQL Server};Trusted_Connection=yes;",
    )
    rendered = repr(profile)
    assert "<redacted>" in rendered
    assert "Trusted_Connection" not in rendered


def test_docstring_reflects_load_time_translation_contract() -> None:
    docstring = ConnectionProfile.__doc__ or ""
    assert "NEVER parsed into" not in docstring
    assert "translat" in docstring.lower()
