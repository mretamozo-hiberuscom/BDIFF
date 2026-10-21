"""Unit tests for schema_comparator.config.loader.load_profiles.

Grows across phases 3-6 of the connection-profile-config change:
- Phase 3: happy path + explicit-path contract
- Phase 4: missing-file / malformed-YAML fail-fast
- Phase 5: trim + duplicate-key + validation pipeline
- Phase 6: cross-cutting guardrails (secret leakage, no-fallback, network)
"""

import io
import pathlib
import sys
import tokenize

import pytest

from schema_comparator.config.errors import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ProfileValidationError,
)
from schema_comparator.config.loader import load_profiles
from schema_comparator.config.models import ConnectionProfile


def _write_yaml(
    tmp_path: pathlib.Path, content: str, filename: str = "config.local.yaml"
) -> pathlib.Path:
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


# --- Phase 3: happy path + explicit-path contract ---------------------------


def test_two_entry_file_returns_two_profiles(tmp_path: pathlib.Path) -> None:
    content = """
databases:
    catalog-service: "Driver={ODBC Driver 18 for SQL Server};Server=srv1;Database=CatalogDB;UID=u;PWD=p;"
    orders-service: "Driver={ODBC Driver 18 for SQL Server};Server=srv2;Database=OrdersDB;Trusted_Connection=yes;"
"""
    config_path = _write_yaml(tmp_path, content)

    profiles = load_profiles(config_path)

    assert len(profiles) == 2
    by_name = {p.name: p for p in profiles}
    assert by_name["catalog-service"].connection_string == (
        "Driver={ODBC Driver 18 for SQL Server};Server=srv1;Database=CatalogDB;UID=u;PWD=p;"
    )
    assert by_name["orders-service"].connection_string == (
        "Driver={ODBC Driver 18 for SQL Server};Server=srv2;Database=OrdersDB;Trusted_Connection=yes;"
    )
    assert all(isinstance(p, ConnectionProfile) for p in profiles)


@pytest.mark.parametrize("count", [1, 3, 20])
def test_arbitrary_number_of_profiles_load(tmp_path: pathlib.Path, count: int) -> None:
    lines = [
        f'  service-{i}: "Driver=X;Server=srv{i};Database=Db{i};UID=u;PWD=p;"'
        for i in range(count)
    ]
    content = "databases:\n" + "\n".join(lines) + "\n"
    config_path = _write_yaml(tmp_path, content)

    profiles = load_profiles(config_path)

    assert len(profiles) == count


def test_load_profiles_with_no_args_raises_type_error() -> None:
    with pytest.raises(TypeError):
        load_profiles()  # type: ignore[call-arg]


def test_load_profiles_from_arbitrary_named_file_and_location(
    tmp_path: pathlib.Path,
) -> None:
    nested_dir = tmp_path / "nested" / "dir"
    nested_dir.mkdir(parents=True)
    content = (
        'databases:\n  only-service: "Driver=X;Server=srv;Database=Db;UID=u;PWD=p;"\n'
    )
    config_path = _write_yaml(nested_dir, content, filename="my-weird-name.yml")

    profiles = load_profiles(config_path)

    assert len(profiles) == 1
    assert profiles[0].name == "only-service"


# --- Phase 4: missing-file / malformed-YAML fail-fast ------------------------


def test_missing_file_raises_config_file_not_found_error(
    tmp_path: pathlib.Path,
) -> None:
    missing_path = tmp_path / "does-not-exist.yaml"

    with pytest.raises(ConfigFileNotFoundError) as exc_info:
        load_profiles(missing_path)

    assert "config.example.yaml" in str(exc_info.value)


def test_malformed_yaml_raises_config_parse_error(tmp_path: pathlib.Path) -> None:
    # Unterminated flow mapping -> a YAML syntax error.
    content = "databases: [unterminated"
    config_path = _write_yaml(tmp_path, content)

    with pytest.raises(ConfigParseError) as exc_info:
        load_profiles(config_path)

    message = str(exc_info.value)
    assert "YAMLError" not in message
    assert "ScannerError" not in message
    assert "ParserError" not in message
    assert "unterminated" not in message.lower()


def test_non_mapping_top_level_raises_config_parse_error(
    tmp_path: pathlib.Path,
) -> None:
    content = "- just\n- a\n- list\n"
    config_path = _write_yaml(tmp_path, content)

    with pytest.raises(ConfigParseError):
        load_profiles(config_path)


def test_missing_databases_key_raises_config_parse_error(
    tmp_path: pathlib.Path,
) -> None:
    content = "not_databases:\n  a: b\n"
    config_path = _write_yaml(tmp_path, content)

    with pytest.raises(ConfigParseError):
        load_profiles(config_path)


def test_databases_not_a_mapping_raises_config_parse_error(
    tmp_path: pathlib.Path,
) -> None:
    content = "databases:\n  - a\n  - b\n"
    config_path = _write_yaml(tmp_path, content)

    with pytest.raises(ConfigParseError):
        load_profiles(config_path)


# --- Phase 5: trim, duplicate-key, and validation pipeline -------------------


def test_leading_and_trailing_whitespace_is_trimmed(tmp_path: pathlib.Path) -> None:
    content = 'databases:\n  "  catalog-service  ": "  Driver=X;PWD=y;  "\n'
    config_path = _write_yaml(tmp_path, content)

    profiles = load_profiles(config_path)

    assert len(profiles) == 1
    assert profiles[0].name == "catalog-service"
    assert profiles[0].connection_string == "Driver=X;PWD=y;"


def test_exact_duplicate_yaml_key_raises_profile_validation_error(
    tmp_path: pathlib.Path,
) -> None:
    content = (
        "databases:\n"
        '  catalog-service: "Driver=X;PWD=first;"\n'
        '  catalog-service: "Driver=X;PWD=second;"\n'
    )
    config_path = _write_yaml(tmp_path, content)

    with pytest.raises(ProfileValidationError):
        load_profiles(config_path)


def test_case_insensitive_duplicate_name_raises_profile_validation_error(
    tmp_path: pathlib.Path,
) -> None:
    content = (
        "databases:\n"
        '  Catalog-Service: "Driver=X;PWD=first;"\n'
        '  catalog-service: "Driver=X;PWD=second;"\n'
    )
    config_path = _write_yaml(tmp_path, content)

    with pytest.raises(ProfileValidationError):
        load_profiles(config_path)


def test_blank_name_raises_profile_validation_error(tmp_path: pathlib.Path) -> None:
    content = 'databases:\n  "   ": "Driver=X;PWD=y;"\n'
    config_path = _write_yaml(tmp_path, content)

    with pytest.raises(ProfileValidationError) as exc_info:
        load_profiles(config_path)

    assert "PWD" not in str(exc_info.value)


def test_blank_connection_string_raises_profile_validation_error(
    tmp_path: pathlib.Path,
) -> None:
    content = 'databases:\n  catalog-service: "   "\n'
    config_path = _write_yaml(tmp_path, content)

    with pytest.raises(ProfileValidationError) as exc_info:
        load_profiles(config_path)

    assert "catalog-service" in str(exc_info.value)


# --- Phase 6: cross-cutting guardrails ---------------------------------------

_SENTINEL_USER = "SECRET_USER"
_SENTINEL_PASS = "SECRET_PASS"
_SENTINEL_CONN = (
    f"Driver=X;UID={_SENTINEL_USER};PWD={_SENTINEL_PASS};Trusted_Connection=yes;"
)


def _assert_no_sentinel_leakage(
    exc: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    for text in (str(exc), repr(exc)):
        assert _SENTINEL_USER not in text
        assert _SENTINEL_PASS not in text
    log_text = caplog.text
    assert _SENTINEL_USER not in log_text
    assert _SENTINEL_PASS not in log_text


def test_no_leakage_on_missing_file(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    missing_path = tmp_path / "does-not-exist.yaml"
    with pytest.raises(ConfigFileNotFoundError) as exc_info:
        load_profiles(missing_path)
    _assert_no_sentinel_leakage(exc_info.value, caplog)


def test_no_leakage_on_malformed_yaml(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    content = f'databases: [unterminated "{_SENTINEL_CONN}"'
    config_path = _write_yaml(tmp_path, content)
    with pytest.raises(ConfigParseError) as exc_info:
        load_profiles(config_path)
    _assert_no_sentinel_leakage(exc_info.value, caplog)


def test_no_leakage_on_empty_name(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    content = f'databases:\n  "   ": "{_SENTINEL_CONN}"\n'
    config_path = _write_yaml(tmp_path, content)
    with pytest.raises(ProfileValidationError) as exc_info:
        load_profiles(config_path)
    _assert_no_sentinel_leakage(exc_info.value, caplog)


def test_no_leakage_on_duplicate_name(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    content = (
        "databases:\n"
        f'  Catalog-Service: "{_SENTINEL_CONN}"\n'
        f'  catalog-service: "{_SENTINEL_CONN}"\n'
    )
    config_path = _write_yaml(tmp_path, content)
    with pytest.raises(ProfileValidationError) as exc_info:
        load_profiles(config_path)
    _assert_no_sentinel_leakage(exc_info.value, caplog)


def test_no_leakage_on_empty_connection_string(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    content = 'databases:\n  catalog-service: "   "\n'
    config_path = _write_yaml(tmp_path, content)
    with pytest.raises(ProfileValidationError) as exc_info:
        load_profiles(config_path)
    _assert_no_sentinel_leakage(exc_info.value, caplog)


def test_repr_redacts_sentinel_secret_end_to_end(tmp_path: pathlib.Path) -> None:
    content = f'databases:\n  catalog-service: "{_SENTINEL_CONN}"\n'
    config_path = _write_yaml(tmp_path, content)
    profiles = load_profiles(config_path)
    rendered = repr(profiles[0])
    assert _SENTINEL_USER not in rendered
    assert _SENTINEL_PASS not in rendered
    assert "<redacted>" in rendered


def _strip_comments_and_strings(source: str) -> str:
    """Return `source` with all comments and string literals blanked out.

    Lets the no-fallback-credentials source-inspection test ignore literals
    that appear only inside docstrings/comments explaining the guardrail.
    """
    out_tokens = []
    readline = io.StringIO(source).readline
    for tok in tokenize.generate_tokens(readline):
        tok_type, tok_string = tok[0], tok[1]
        if tok_type in (tokenize.COMMENT, tokenize.STRING):
            out_tokens.append(" ")
        else:
            out_tokens.append(tok_string)
    return " ".join(out_tokens)


@pytest.mark.parametrize("module_name", ["loader", "models", "errors"])
def test_no_hardcoded_credential_literals_outside_comments_or_docstrings(
    module_name: str,
) -> None:
    module = sys.modules.get(f"schema_comparator.config.{module_name}")
    assert module is not None and module.__file__ is not None
    source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
    code_only = _strip_comments_and_strings(source)
    for forbidden in ("UID=", "PWD=", "Driver="):
        assert forbidden not in code_only, (
            f"Found forbidden literal {forbidden!r} in executable code of {module_name}.py "
            "(fallback-credential guardrail)"
        )


def test_gitignore_ignores_config_local_yaml() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    gitignore_text = (repo_root / ".gitignore").read_text(encoding="utf-8")
    assert "config.local.yaml" in gitignore_text


def test_load_profiles_does_not_import_pyodbc_or_open_sockets(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket

    def _raise_if_socket_opened(*args: object, **kwargs: object) -> None:
        raise AssertionError("load_profiles must not open a network socket")

    monkeypatch.setattr(socket, "socket", _raise_if_socket_opened)
    sys.modules.pop("pyodbc", None)

    content = 'databases:\n  catalog-service: "Driver=X;UID=u;PWD=p;"\n'
    config_path = _write_yaml(tmp_path, content)

    profiles = load_profiles(config_path)

    assert len(profiles) == 1
    assert "pyodbc" not in sys.modules


# --- Phase 7: connection-string translation integration ---------------------


def test_ado_net_connection_string_is_translated_to_odbc_form(
    tmp_path: pathlib.Path,
) -> None:
    content = (
        "databases:\n"
        '  catalog-service: "Data Source=srv1;Initial Catalog=CatalogDB;User Id=u;Password=p;"\n'
    )
    config_path = _write_yaml(tmp_path, content)

    profiles = load_profiles(config_path)

    assert len(profiles) == 1
    connection_string = profiles[0].connection_string
    assert "Server=srv1" in connection_string
    assert "Database=CatalogDB" in connection_string
    assert "UID=u" in connection_string
    assert "PWD=p" in connection_string
    # The driver is picked from the installed ones at connect time.
    assert "Driver=" not in connection_string
    assert "Data Source=" not in connection_string


def test_unrecognized_connection_string_raises_profile_validation_error(
    tmp_path: pathlib.Path,
) -> None:
    content = 'databases:\n  catalog-service: "justsomeopaquevalue"\n'
    config_path = _write_yaml(tmp_path, content)

    with pytest.raises(ProfileValidationError) as exc_info:
        load_profiles(config_path)

    assert "catalog-service" in str(exc_info.value)


def test_no_leakage_on_unrecognized_connection_string_format(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    content = f'databases:\n  catalog-service: "{_SENTINEL_USER}{_SENTINEL_PASS}"\n'
    config_path = _write_yaml(tmp_path, content)

    with pytest.raises(ProfileValidationError) as exc_info:
        load_profiles(config_path)

    _assert_no_sentinel_leakage(exc_info.value, caplog)
