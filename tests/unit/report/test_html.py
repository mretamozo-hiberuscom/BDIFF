"""Unit tests for report.html: build_context (pure dict-shape, no Jinja2)
and render_html (Jinja2, checked against golden structural substrings)."""

from pathlib import Path

from report.conftest import comparison_result_empty, comparison_result_with_findings

from schema_comparator.compare.models import ComparisonResult, MissingTable
from schema_comparator.report.html import build_context, render_html

_GOLDEN_DIR = Path(__file__).parent / "golden"


def _golden_substrings(name: str) -> list[str]:
    text = (_GOLDEN_DIR / name).read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]


def test_build_context_missing_table_marks_profile_distinctly() -> None:
    context = build_context(comparison_result_with_findings())

    payment_group = next(
        g for g in context["groups"] if g["table_name"] == "Payment"
    )
    row = payment_group["rows"][0]
    assert row["diff_type"] == "MissingTable"
    assert row["cells"]["c"] == {"kind": "missing", "text": "\u274c"}
    assert row["cells"]["a"] is None
    assert row["cells"]["b"] is None


def test_build_context_table_missing_from_multiple_profiles_is_a_single_row() -> None:
    result = ComparisonResult(
        compared_profiles=("autos", "decesos", "hogar", "vida"),
        entries=(
            MissingTable(schema_name="dbo", table_name="TC_Productos", missing_from_profile="decesos"),
            MissingTable(schema_name="dbo", table_name="TC_Productos", missing_from_profile="hogar"),
            MissingTable(schema_name="dbo", table_name="TC_Productos", missing_from_profile="vida"),
        ),
    )

    context = build_context(result)

    group = context["groups"][0]
    assert len(group["rows"]) == 1
    row = group["rows"][0]
    assert row["cells"]["autos"] is None
    assert row["cells"]["decesos"] == {"kind": "missing", "text": "\u274c"}
    assert row["cells"]["hogar"] == {"kind": "missing", "text": "\u274c"}
    assert row["cells"]["vida"] == {"kind": "missing", "text": "\u274c"}


def test_build_context_missing_column_marks_profile_distinctly() -> None:
    context = build_context(comparison_result_with_findings())

    invoice_group = next(
        g for g in context["groups"] if g["table_name"] == "Invoice"
    )
    row = next(r for r in invoice_group["rows"] if r["diff_type"] == "MissingColumn")
    assert row["column_name"] == "notes"
    assert row["cells"]["c"] == {"kind": "missing", "text": "\u274c"}
    assert row["cells"]["a"] == {"kind": "value", "text": "varchar(255), NULL"}
    assert row["cells"]["b"] == {"kind": "value", "text": "varchar(255), NULL"}


def test_build_context_column_mismatch_renders_present_profiles_and_blanks_absent() -> None:
    context = build_context(comparison_result_with_findings())

    invoice_group = next(
        g for g in context["groups"] if g["table_name"] == "Invoice"
    )
    row = next(r for r in invoice_group["rows"] if r["diff_type"] == "ColumnMismatch")
    assert row["column_name"] == "amount"
    assert row["cells"]["a"]["kind"] == "value"
    assert "decimal" in row["cells"]["a"]["text"]
    assert row["cells"]["b"]["kind"] == "value"
    assert row["cells"]["c"] is None


def test_build_context_preserves_engine_entry_order_without_resorting() -> None:
    context = build_context(comparison_result_with_findings())

    table_order = [g["table_name"] for g in context["groups"]]
    assert table_order == ["Invoice", "Payment"]

    invoice_group = context["groups"][0]
    diff_type_order = [r["diff_type"] for r in invoice_group["rows"]]
    assert diff_type_order == ["MissingColumn", "ColumnMismatch"]


def test_build_context_groups_by_qualified_table_identity() -> None:
    context = build_context(comparison_result_with_findings())

    assert len(context["groups"]) == 2
    identities = {(g["schema_name"], g["table_name"]) for g in context["groups"]}
    assert identities == {("sales", "Invoice"), ("sales", "Payment")}


def test_build_context_empty_entries_sets_has_findings_false() -> None:
    context = build_context(comparison_result_empty())

    assert context["has_findings"] is False
    assert context["groups"] == []
    assert context["compared_profiles"] == ("a", "b")


def test_render_html_includes_every_diff_entry() -> None:
    html = render_html(comparison_result_with_findings())

    assert ">notes<" in html
    assert ">amount<" in html
    assert "sales.Payment" in html
    assert "sales.Invoice" in html


def test_render_html_header_row_lists_profiles_in_result_order() -> None:
    html = render_html(comparison_result_with_findings())

    for substring in _golden_substrings("with_findings_expected_substrings.txt"):
        assert substring in html


def test_render_html_no_findings_shows_no_drift_message_and_no_empty_table() -> None:
    html = render_html(comparison_result_empty())

    for substring in _golden_substrings("empty_expected_substrings.txt"):
        assert substring in html
    assert "<table>" not in html


def test_render_html_is_self_contained_with_no_external_asset_links() -> None:
    html = render_html(comparison_result_with_findings())

    assert "<link" not in html
    assert "http://" not in html
    assert "https://" not in html
