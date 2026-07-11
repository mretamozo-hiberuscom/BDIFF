"""Unit tests for schema_comparator.config.connection_string.

Grows across phases 2-9 of the connection-string-translation change:
- Phase 2: brace-aware tokenizer
- Phase 3: keyword mapping, Integrated Security, duplicate precedence
- Phase 4: driver auto-prepend and idempotency
- Phase 5: backward-compatibility byte-identical regression suite
- Phase 9: cross-cutting secret-safety guardrail
"""

import pytest

from schema_comparator.config.connection_string import _split_token, _tokenize, translate
from schema_comparator.config.errors import ProfileValidationError

# --- Phase 2: brace-aware tokenizer ------------------------------------------


def test_plain_semicolon_delimited_string_splits_into_segments() -> None:
    tokens = _tokenize("Server=srv;Database=Db;UID=u;", name="x")
    assert tokens == ["Server=srv", "Database=Db", "UID=u"]


def test_trailing_semicolon_and_double_semicolon_drop_empty_segments() -> None:
    assert _tokenize("Server=srv;", name="x") == ["Server=srv"]
    assert _tokenize("Server=srv;;Database=Db;", name="x") == ["Server=srv", "Database=Db"]


def test_braced_driver_value_kept_intact_as_one_token() -> None:
    tokens = _tokenize("Driver={ODBC Driver 18 for SQL Server};Server=srv;", name="x")
    assert tokens == ["Driver={ODBC Driver 18 for SQL Server}", "Server=srv"]


def test_braced_value_containing_literal_semicolon_is_not_split() -> None:
    tokens = _tokenize("PWD={p;w=d};Server=srv;", name="x")
    assert tokens == ["PWD={p;w=d}", "Server=srv"]


def test_doubled_closing_brace_is_treated_as_one_literal_brace() -> None:
    tokens = _tokenize("Driver={Foo}}Bar};", name="x")
    assert tokens == ["Driver={Foo}Bar}"]


def test_unterminated_brace_raises_unrecognized_format_error() -> None:
    with pytest.raises(ProfileValidationError):
        _tokenize("Driver={ODBC Driver 18 for SQL Server;Server=srv;", name="x")


def test_split_token_splits_on_first_equals_only() -> None:
    assert _split_token("PWD=p@ss=word") == ("PWD", "p@ss=word")


def test_split_token_returns_none_when_no_equals_present() -> None:
    assert _split_token("justsomevalue") is None


# --- Phase 3: keyword mapping, Integrated Security, duplicate precedence ----


def test_pure_ado_net_string_is_fully_translated() -> None:
    result = translate("Data Source=srv1;Initial Catalog=PolizaDB;User Id=u;Password=p;", name="x")
    assert "Server=srv1" in result
    assert "Database=PolizaDB" in result
    assert "UID=u" in result
    assert "PWD=p" in result
    assert "Data Source=" not in result
    assert "Initial Catalog=" not in result
    assert "User Id=" not in result
    assert "Password=" not in result


@pytest.mark.parametrize(
    "keyword",
    ["Server", "Database", "Trusted_Connection", "Encrypt", "TrustServerCertificate"],
)
def test_odbc_passthrough_keywords_are_left_unchanged(keyword: str) -> None:
    raw = f"{keyword}=SomeValue;UID=u;"
    result = translate(raw, name="x")
    assert f"{keyword}=SomeValue" in result


@pytest.mark.parametrize("value", ["True", "sspi", "yes", "SSPI", "TRUE"])
def test_integrated_security_true_variants_map_to_trusted_connection(value: str) -> None:
    result = translate(f"Server=srv;Integrated Security={value};", name="x")
    assert "Trusted_Connection=yes" in result
    assert "Integrated Security" not in result


@pytest.mark.parametrize("value", ["False", "No", "no", "FALSE"])
def test_integrated_security_false_variants_are_dropped(value: str) -> None:
    result = translate(f"Server=srv;UID=u;PWD=p;Integrated Security={value};", name="x")
    assert "Integrated Security" not in result
    assert "Trusted_Connection" not in result


@pytest.mark.parametrize("keyword", ["Encrypt", "TrustServerCertificate"])
@pytest.mark.parametrize("value", ["True", "TRUE", "true"])
def test_adonet_true_boolean_value_normalized_to_odbc_yes(keyword: str, value: str) -> None:
    # The Microsoft ODBC Driver for SQL Server only documents yes/mandatory
    # and no/optional (plus strict, 18.0+) as valid Encrypt/
    # TrustServerCertificate values -- ADO.NET's True/False literals raise
    # SQLSTATE 08001 ("invalid value specified for connection string
    # attribute") at connect time. This must be normalized, not passed
    # through verbatim.
    result = translate(f"Server=srv;{keyword}={value};", name="x")
    assert f"{keyword}=yes" in result
    assert f"{keyword}={value}" not in result


@pytest.mark.parametrize("keyword", ["Encrypt", "TrustServerCertificate"])
@pytest.mark.parametrize("value", ["False", "FALSE", "false"])
def test_adonet_false_boolean_value_normalized_to_odbc_no(keyword: str, value: str) -> None:
    result = translate(f"Server=srv;{keyword}={value};", name="x")
    assert f"{keyword}=no" in result
    assert f"{keyword}={value}" not in result


@pytest.mark.parametrize("keyword", ["Encrypt", "TrustServerCertificate"])
@pytest.mark.parametrize("value", ["yes", "no", "Mandatory", "Optional", "Strict"])
def test_already_odbc_boolean_value_passes_through_unchanged(keyword: str, value: str) -> None:
    # Values already in ODBC's own vocabulary (including the 18.0+-only
    # Mandatory/Optional/Strict literals) must never be rewritten.
    result = translate(f"Server=srv;{keyword}={value};", name="x")
    assert f"{keyword}={value}" in result


def test_unrecognized_keyword_alongside_recognized_keyword_passes_through() -> None:
    result = translate("Server=srv;AppName=foo;", name="x")
    assert "AppName=foo" in result
    assert "Server=srv" in result


def test_duplicate_data_source_and_server_last_occurrence_wins() -> None:
    result = translate("Data Source=old-srv;Server=new-srv;", name="x")
    assert "Server=new-srv" in result
    assert "old-srv" not in result


def test_duplicate_password_and_pwd_last_occurrence_wins() -> None:
    result = translate("Password=old-pwd;PWD=new-pwd;", name="x")
    assert "PWD=new-pwd" in result
    assert "old-pwd" not in result


def test_zero_recognized_tokens_raises_unrecognized_format_error() -> None:
    with pytest.raises(ProfileValidationError):
        translate("justsomeopaquevalue", name="x")


def test_only_unknown_keywords_raises_unrecognized_format_error() -> None:
    with pytest.raises(ProfileValidationError):
        translate("AppName=foo;Whatever=bar;", name="x")


# --- Phase 4: driver auto-prepend and idempotency ---------------------------


def test_driver_auto_prepended_when_absent() -> None:
    result = translate("Data Source=srv1;Initial Catalog=PolizaDB;", name="x")
    assert result.startswith("Driver={ODBC Driver 17 for SQL Server};")
    assert result.count("Driver=") == 1


@pytest.mark.parametrize("driver_kw", ["driver", "DRIVER", "Driver"])
def test_driver_auto_prepend_suppressed_case_insensitively(driver_kw: str) -> None:
    raw = f"{driver_kw}={{Custom Driver}};Data Source=srv1;Initial Catalog=PolizaDB;"
    result = translate(raw, name="x")
    assert result.casefold().count("driver=") == 1


def test_translate_is_idempotent() -> None:
    raw = "Data Source=srv1;Initial Catalog=PolizaDB;User Id=u;Password=p;"
    once = translate(raw, name="x")
    twice = translate(once, name="x")
    assert once == twice


# --- Phase 5: backward-compatibility byte-identical regression suite -------

_PURE_ODBC_FIXTURES = [
    # config.example.yaml -> example-sql-auth
    "Driver={ODBC Driver 18 for SQL Server};Server=your-server;Database=YourDb;UID=your-user;PWD=your-password;TrustServerCertificate=yes;",
    # config.example.yaml -> example-windows-auth
    "Driver={ODBC Driver 18 for SQL Server};Server=your-server;Database=YourOtherDb;Trusted_Connection=yes;",
    # config.local.yaml -> salud
    "Driver={ODBC Driver 18 for SQL Server};Server=your-server;Database=YourOtherDb;Trusted_Connection=yes;",
    # tests/unit/config/test_loader.py -> poliza-service
    "Driver={ODBC Driver 18 for SQL Server};Server=srv1;Database=PolizaDB;UID=u;PWD=p;",
    # tests/unit/config/test_loader.py -> siniestro-service
    "Driver={ODBC Driver 18 for SQL Server};Server=srv2;Database=SiniestroDB;Trusted_Connection=yes;",
    # tests/unit/config/test_loader.py -> only-service (minimal/non-standard driver token)
    "Driver=X;Server=srv;Database=Db;UID=u;PWD=p;",
]


@pytest.mark.parametrize("raw", _PURE_ODBC_FIXTURES)
def test_pure_odbc_string_is_byte_identical_after_translation(raw: str) -> None:
    assert translate(raw, name="x") == raw


def test_mixed_autos_shaped_string_translates_correctly() -> None:
    raw = (
        "Driver={ODBC Driver 18 for SQL Server};"
        "Data Source=IBPFMPRU.example;"
        "Initial Catalog=SegurosEcosistemaAutos;"
        "User Id=USR_x;"
        "Password=xxxxxxxxx;"
        "Integrated Security=False;"
        "Encrypt=True;"
        "TrustServerCertificate=True;"
    )
    result = translate(raw, name="x")
    assert result.count("Driver=") == 1
    assert "Driver={ODBC Driver 18 for SQL Server}" in result
    assert "Server=IBPFMPRU.example" in result
    assert "Database=SegurosEcosistemaAutos" in result
    assert "UID=USR_x" in result
    assert "PWD=xxxxxxxxx" in result
    assert "Integrated Security" not in result
    assert "Encrypt=yes" in result
    assert "TrustServerCertificate=yes" in result


# --- Phase 9: cross-cutting secret-safety guardrail -------------------------

_SENTINEL_FRAGMENT = "UID=SECRET_USER;PWD=SECRET_PASS;Whatever=SentinelToken"


@pytest.mark.parametrize(
    "raw",
    [
        # A realistic UID=/PWD=-shaped fragment embedded as the *value* of
        # an unrecognized keyword (braced so the tokenizer keeps it as one
        # segment) - zero recognized tokens overall.
        f"Whatever={{{_SENTINEL_FRAGMENT}}}",
        f"Driver={{Unterminated{_SENTINEL_FRAGMENT}",
    ],
)
def test_error_never_leaks_connection_string_content(raw: str) -> None:
    with pytest.raises(ProfileValidationError) as exc_info:
        translate(raw, name="profile-x")

    exc = exc_info.value
    message = str(exc)
    assert "profile-x" in message
    assert "SECRET_USER" not in message
    assert "SECRET_PASS" not in message
    assert "SentinelToken" not in message
    assert raw not in message

    # No exception chaining that could leak connection-string content via a
    # lower-level exception's own message/args in a full traceback.
    assert exc.__cause__ is None
    chained = exc.__context__
    while chained is not None:
        assert "SECRET_USER" not in str(chained)
        assert "SECRET_PASS" not in str(chained)
        assert "SentinelToken" not in str(chained)
        chained = chained.__context__
