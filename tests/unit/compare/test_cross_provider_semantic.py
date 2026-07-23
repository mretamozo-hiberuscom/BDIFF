"""Unit tests for cross-provider semantic type equivalences and comparison mode."""

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.domain.capabilities import ComparisonMode
from schema_comparator.domain.comparison.models import ColumnMismatch
from schema_comparator.domain.comparison.type_equivalences import (
    are_types_semantically_equivalent,
    get_type_family,
)
from schema_comparator.domain.schema.models import ColumnSnapshot, SchemaSnapshot, TableSnapshot


def test_type_family_mapping() -> None:
    assert get_type_family("varchar(100)") == "STRING"
    assert get_type_family("VARCHAR2(100)") == "STRING"
    assert get_type_family("character varying") == "STRING"
    assert get_type_family("text") == "STRING"
    assert get_type_family("int") == "INTEGER"
    assert get_type_family("number(10, 0)") == "INTEGER"
    assert get_type_family("double precision") == "FLOAT"
    assert get_type_family("boolean") == "BOOLEAN"
    assert get_type_family("tinyint(1)") == "BOOLEAN"
    assert get_type_family("uuid") == "UUID"
    assert get_type_family("uniqueidentifier") == "UUID"


def test_are_types_semantically_equivalent() -> None:
    assert are_types_semantically_equivalent("varchar(50)", "VARCHAR2(50)") is True
    assert are_types_semantically_equivalent("character varying", "varchar(50)") is True
    assert are_types_semantically_equivalent("int", "number(10, 0)") is True
    assert are_types_semantically_equivalent("boolean", "tinyint(1)") is True
    assert are_types_semantically_equivalent("uuid", "uniqueidentifier") is True
    assert are_types_semantically_equivalent("int", "varchar(50)") is False


def test_semantic_comparison_suppresses_equivalent_mismatches() -> None:
    # Profile 1 (PostgreSQL): VARCHAR
    col1 = ColumnSnapshot("name", "varchar", 50, None, None, False, 1)
    t1 = TableSnapshot("public", "users", (col1,))
    s1 = SchemaSnapshot("pg_prof", (t1,))

    # Profile 2 (Oracle): VARCHAR2
    col2 = ColumnSnapshot("name", "VARCHAR2", 50, None, None, False, 1)
    t2 = TableSnapshot("public", "users", (col2,))
    s2 = SchemaSnapshot("ora_prof", (t2,))

    # Native strict mode flags mismatch
    strict_res = compare_snapshots([s1, s2], mode=ComparisonMode.NATIVE_STRICT)
    mismatches = [e for e in strict_res.entries if isinstance(e, ColumnMismatch)]
    assert len(mismatches) == 1

    # Semantic equivalent mode ignores equivalent type mismatch
    semantic_res = compare_snapshots([s1, s2], mode=ComparisonMode.SEMANTIC_EQUIVALENT)
    semantic_mismatches = [e for e in semantic_res.entries if isinstance(e, ColumnMismatch)]
    assert len(semantic_mismatches) == 0


def test_semantic_comparison_still_flags_length_and_attribute_mismatches() -> None:
    # Profile 1: varchar(50)
    col1 = ColumnSnapshot("name", "varchar", 50, None, None, False, 1)
    t1 = TableSnapshot("public", "users", (col1,))
    s1 = SchemaSnapshot("pg_prof", (t1,))

    # Profile 2: VARCHAR2(100) - Different length!
    col2 = ColumnSnapshot("name", "VARCHAR2", 100, None, None, False, 1)
    t2 = TableSnapshot("public", "users", (col2,))
    s2 = SchemaSnapshot("ora_prof", (t2,))

    # Semantic mode MUST flag mismatch due to length difference (50 vs 100)
    semantic_res = compare_snapshots([s1, s2], mode=ComparisonMode.SEMANTIC_EQUIVALENT)
    semantic_mismatches = [e for e in semantic_res.entries if isinstance(e, ColumnMismatch)]
    assert len(semantic_mismatches) == 1
