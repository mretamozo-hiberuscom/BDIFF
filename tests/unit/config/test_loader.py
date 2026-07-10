"""Unit tests for schema_comparator.config.loader.load_profiles.

Grows across phases 3-6 of the connection-profile-config change:
- Phase 3: happy path + explicit-path contract
- Phase 4: missing-file / malformed-YAML fail-fast
- Phase 5: trim + duplicate-key + validation pipeline
- Phase 6: cross-cutting guardrails (secret leakage, no-fallback, network)
"""

import pathlib

import pytest

from schema_comparator.config.loader import load_profiles
from schema_comparator.config.models import ConnectionProfile


def _write_yaml(tmp_path: pathlib.Path, content: str, filename: str = "config.local.yaml") -> pathlib.Path:
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


# --- Phase 3: happy path + explicit-path contract ---------------------------


def test_two_entry_file_returns_two_profiles(tmp_path: pathlib.Path) -> None:
    content = """
databases:
  poliza-service: "Driver={ODBC Driver 18 for SQL Server};Server=srv1;Database=PolizaDB;UID=u;PWD=p;"
  siniestro-service: "Driver={ODBC Driver 18 for SQL Server};Server=srv2;Database=SiniestroDB;Trusted_Connection=yes;"
"""
    config_path = _write_yaml(tmp_path, content)

    profiles = load_profiles(config_path)

    assert len(profiles) == 2
    by_name = {p.name: p for p in profiles}
    assert by_name["poliza-service"].connection_string == (
        "Driver={ODBC Driver 18 for SQL Server};Server=srv1;Database=PolizaDB;UID=u;PWD=p;"
    )
    assert by_name["siniestro-service"].connection_string == (
        "Driver={ODBC Driver 18 for SQL Server};Server=srv2;Database=SiniestroDB;Trusted_Connection=yes;"
    )
    assert all(isinstance(p, ConnectionProfile) for p in profiles)


@pytest.mark.parametrize("count", [1, 3, 20])
def test_arbitrary_number_of_profiles_load(tmp_path: pathlib.Path, count: int) -> None:
    lines = [f'  service-{i}: "Driver=X;Server=srv{i};Database=Db{i};UID=u;PWD=p;"' for i in range(count)]
    content = "databases:\n" + "\n".join(lines) + "\n"
    config_path = _write_yaml(tmp_path, content)

    profiles = load_profiles(config_path)

    assert len(profiles) == count


def test_load_profiles_with_no_args_raises_type_error() -> None:
    with pytest.raises(TypeError):
        load_profiles()  # type: ignore[call-arg]


def test_load_profiles_from_arbitrary_named_file_and_location(tmp_path: pathlib.Path) -> None:
    nested_dir = tmp_path / "nested" / "dir"
    nested_dir.mkdir(parents=True)
    content = 'databases:\n  only-service: "Driver=X;Server=srv;Database=Db;UID=u;PWD=p;"\n'
    config_path = _write_yaml(nested_dir, content, filename="my-weird-name.yml")

    profiles = load_profiles(config_path)

    assert len(profiles) == 1
    assert profiles[0].name == "only-service"
