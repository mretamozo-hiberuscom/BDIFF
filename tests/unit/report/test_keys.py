"""Wording of primary key, foreign key and index findings, shared by every
report format and the TUI."""

from schema_comparator.compare.models import (
    ForeignKeyMismatch,
    IndexMismatch,
    PrimaryKeyMismatch,
)
from schema_comparator.domain.schema.models import (
    ForeignKeySnapshot,
    IndexSnapshot,
    PrimaryKeySnapshot,
)
from schema_comparator.report.attributes import MISSING_MARKER
from schema_comparator.report.keys import (
    format_key,
    key_subject,
    key_summary,
    key_values,
)
from schema_comparator.report.presentation import present_finding
from schema_comparator.tui.formatting import detail_markup, detail_text, leaf_parts


def _pk(columns=("id",), name="PK_orders") -> PrimaryKeySnapshot:
    return PrimaryKeySnapshot(name, columns)


def _fk(**changes) -> ForeignKeySnapshot:
    base = dict(
        name="FK_o_c",
        columns=("customer_id",),
        referenced_table="customers",
        referenced_columns=("id",),
        referenced_schema="dbo",
        on_delete="CASCADE",
        on_update="NO ACTION",
    )
    return ForeignKeySnapshot(**{**base, **changes})


def test_primary_key_shows_its_name_and_columns() -> None:
    assert format_key(_pk(("a", "b"))) == "PK_orders (a, b)"


def test_foreign_key_shows_target_and_actions() -> None:
    assert format_key(_fk()) == (
        "(customer_id) -> dbo.customers (id), ON DELETE CASCADE, ON UPDATE NO ACTION"
    )
    assert format_key(_fk(on_delete=None, on_update=None, referenced_schema=None)) == (
        "(customer_id) -> customers (id)"
    )


def test_index_shows_every_attribute_that_counts_for_equality() -> None:
    index = IndexSnapshot(
        "IX",
        ("a", "b"),
        is_unique=True,
        is_clustered=True,
        descending_columns=("b",),
        included_columns=("c",),
        filter_expression="([a]>(0))",
    )

    assert (
        format_key(index) == "UNIQUE CLUSTERED (a, b DESC) INCLUDE (c) WHERE ([a]>(0))"
    )
    assert format_key(IndexSnapshot("IX", ("a",))) == "(a)"


def test_a_profile_without_the_object_gets_the_missing_marker() -> None:
    assert format_key(None) == MISSING_MARKER
    assert format_key(None, "no existe") == "no existe"


def _pk_mismatch(a, b) -> PrimaryKeyMismatch:
    return PrimaryKeyMismatch("dbo", "orders", (("dev", a), ("prod", b)))


def test_summary_says_where_it_is_missing_or_who_differs() -> None:
    assert key_summary(_pk_mismatch(_pk(), None)) == "falta en prod"
    assert key_summary(_pk_mismatch(_pk(), _pk(("x",)))) == (
        "definición distinta entre dev, prod"
    )


def test_subjects_are_pk_foreign_key_and_index_names() -> None:
    assert key_subject(_pk_mismatch(_pk(), None)) == "PK"
    fk = ForeignKeyMismatch("dbo", "orders", "FK_o_c", (("dev", _fk()),))
    ix = IndexMismatch("dbo", "orders", "IX_o", (("dev", None),))
    assert key_subject(fk) == "FK_o_c" and key_subject(ix) == "IX_o"


def test_reports_show_each_profile_definition_instead_of_a_generic_text() -> None:
    entry = _pk_mismatch(_pk(("id",)), None)

    view = present_finding([entry], ("dev", "prod"))

    assert view.cells_by_profile == {"dev": "PK_orders (id)", "prod": MISSING_MARKER}
    assert view.detail_name == "PK"
    assert "Discrepancia en" not in str(view.cells_by_profile)


def test_tui_leaf_and_cards_name_the_object_and_each_definition() -> None:
    entry = ForeignKeyMismatch(
        "dbo",
        "orders",
        "FK_o_c",
        (("dev", _fk()), ("prod", _fk(on_delete="NO ACTION"))),
    )

    assert leaf_parts(entry) == ("FK_o_c", "definición distinta entre dev, prod")
    text = detail_text(entry)
    assert "FK_o_c de dbo.orders" in text
    assert "ON DELETE CASCADE" in text and "ON DELETE NO ACTION" in text
    markup = detail_markup(entry)
    assert "FK_o_c" in markup and "Definiciones distintas (2)" in markup
    assert "no genera scripts" in markup


def test_key_values_follow_the_profiles_of_the_finding() -> None:
    assert key_values(_pk_mismatch(_pk(), None), "no existe") == (
        ("dev", "PK_orders (id)"),
        ("prod", "no existe"),
    )
