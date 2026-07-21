"""Unit tests for PrimaryKeySnapshot, ForeignKeySnapshot, IndexSnapshot, and comparison engine integration."""

from dataclasses import FrozenInstanceError

import pytest

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.domain.comparison.models import (
    ForeignKeyMismatch,
    IndexMismatch,
    PrimaryKeyMismatch,
)
from schema_comparator.domain.schema.models import (
    ColumnSnapshot,
    ForeignKeySnapshot,
    IndexSnapshot,
    PrimaryKeySnapshot,
    SchemaSnapshot,
    TableSnapshot,
)


def test_primary_key_snapshot():
    pk = PrimaryKeySnapshot(name="PK_users", columns=("id",))
    assert pk.name == "PK_users"
    assert pk.columns == ("id",)

    with pytest.raises(FrozenInstanceError):
        pk.name = "MUTATED"  # type: ignore


def test_foreign_key_snapshot():
    fk = ForeignKeySnapshot(
        name="FK_orders_users",
        columns=("user_id",),
        referenced_table="users",
        referenced_columns=("id",),
        referenced_schema="dbo",
        on_delete="CASCADE",
        on_update="NO ACTION",
    )
    assert fk.name == "FK_orders_users"
    assert fk.columns == ("user_id",)
    assert fk.referenced_table == "users"
    assert fk.referenced_schema == "dbo"
    assert fk.on_delete == "CASCADE"

    with pytest.raises(FrozenInstanceError):
        fk.referenced_table = "other"  # type: ignore


def test_index_snapshot():
    idx = IndexSnapshot(name="IX_users_email", columns=("email",), is_unique=True)
    assert idx.name == "IX_users_email"
    assert idx.columns == ("email",)
    assert idx.is_unique is True


def test_table_snapshot_with_advanced_objects():
    col = ColumnSnapshot(
        name="id",
        data_type="int",
        character_maximum_length=None,
        numeric_precision=10,
        numeric_scale=0,
        is_nullable=False,
        ordinal_position=1,
    )
    pk = PrimaryKeySnapshot(name="PK_items", columns=("id",))
    idx = IndexSnapshot(name="IX_items_id", columns=("id",), is_unique=True)
    table = TableSnapshot(
        schema_name="dbo",
        table_name="items",
        columns=(col,),
        primary_key=pk,
        indexes=(idx,),
    )

    assert table.primary_key == pk
    assert table.indexes == (idx,)
    assert table.foreign_keys == ()


def test_comparison_engine_detects_pk_fk_index_drift():
    col = ColumnSnapshot("id", "int", None, 10, 0, False, 1)

    # Profile 1 has PK and Index
    pk_1 = PrimaryKeySnapshot("PK_users", ("id",))
    idx_1 = IndexSnapshot("IX_users_id", ("id",), is_unique=True)
    t1 = TableSnapshot("dbo", "users", (col,), primary_key=pk_1, indexes=(idx_1,))
    s1 = SchemaSnapshot("prof1", (t1,))

    # Profile 2 has missing PK and missing Index
    t2 = TableSnapshot("dbo", "users", (col,), primary_key=None, indexes=())
    s2 = SchemaSnapshot("prof2", (t2,))

    result = compare_snapshots([s1, s2])
    pk_mismatches = [e for e in result.entries if isinstance(e, PrimaryKeyMismatch)]
    idx_mismatches = [e for e in result.entries if isinstance(e, IndexMismatch)]

    assert len(pk_mismatches) == 1
    assert pk_mismatches[0].table_name == "users"

    assert len(idx_mismatches) == 1
    assert idx_mismatches[0].index_name == "IX_users_id"
