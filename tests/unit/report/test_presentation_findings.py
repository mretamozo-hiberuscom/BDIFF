"""Parameterized test sweeping all DiffEntry types across all renderers to guarantee crash-free presentation."""

import pytest

from schema_comparator.compare.models import (
    ColumnAttributes,
    ColumnMismatch,
    ComparisonResult,
    ForeignKeyMismatch,
    IndexMismatch,
    MissingColumn,
    MissingProcedure,
    MissingTable,
    NamedColumnAttributes,
    PrimaryKeyMismatch,
    ProcedureMismatch,
)
from schema_comparator.domain.schema.models import (
    ForeignKeySnapshot,
    IndexSnapshot,
    ParameterSnapshot,
    PrimaryKeySnapshot,
    ProcedureSnapshot,
)
from schema_comparator.report.console import render_console
from schema_comparator.report.excel import export_excel
from schema_comparator.report.html import render_html
from schema_comparator.tui.formatting import build_tree_data, detail_text, leaf_label


@pytest.fixture
def all_diff_entries():
    col_attr = ColumnAttributes(data_type="int", character_maximum_length=None, numeric_precision=10, numeric_scale=0, is_nullable=False)

    named_col = NamedColumnAttributes(name="id", attributes=col_attr)

    missing_table = MissingTable(
        schema_name="dbo",
        table_name="Logs",
        missing_from_profile="Profile2",
        present_columns=(("Profile1", (named_col,)),),
    )
    missing_col = MissingColumn(
        schema_name="dbo",
        table_name="Users",
        column_name="email",
        missing_from_profile="Profile2",
        present_attributes=(("Profile1", col_attr),),
    )
    col_mismatch = ColumnMismatch(
        schema_name="dbo",
        table_name="Users",
        column_name="age",
        values_by_profile=(
            ("Profile1", ColumnAttributes("int", None, 10, 0, False)),
            ("Profile2", ColumnAttributes("bigint", None, 19, 0, False)),
        ),
    )
    pk_mismatch = PrimaryKeyMismatch(
        schema_name="dbo",
        table_name="Users",
        values_by_profile=(
            ("Profile1", PrimaryKeySnapshot("PK_Users", ("id",))),
            ("Profile2", None),
        ),
    )
    fk_mismatch = ForeignKeyMismatch(
        schema_name="dbo",
        table_name="Orders",
        fk_name="FK_Orders_Users",
        values_by_profile=(
            ("Profile1", ForeignKeySnapshot("FK_Orders_Users", ("user_id",), "Users", ("id",))),
            ("Profile2", None),
        ),
    )
    idx_mismatch = IndexMismatch(
        schema_name="dbo",
        table_name="Users",
        index_name="IX_Users_Email",
        values_by_profile=(
            ("Profile1", IndexSnapshot("IX_Users_Email", ("email",), is_unique=True)),
            ("Profile2", None),
        ),
    )
    missing_proc = MissingProcedure(
        schema_name="dbo",
        procedure_name="sp_CalculateDiscount",
        missing_from_profile="Profile2",
        present_procedures=(
            ("Profile1", ProcedureSnapshot("dbo", "sp_CalculateDiscount", parameters=(ParameterSnapshot("@Rate", "decimal"),))),
        ),
    )
    proc_mismatch = ProcedureMismatch(
        schema_name="dbo",
        procedure_name="sp_GetProfile",
        values_by_profile=(
            ("Profile1", ProcedureSnapshot("dbo", "sp_GetProfile", definition_hash="hashA")),
            ("Profile2", ProcedureSnapshot("dbo", "sp_GetProfile", definition_hash="hashB")),
        ),
    )

    return [
        missing_table,
        missing_col,
        col_mismatch,
        pk_mismatch,
        fk_mismatch,
        idx_mismatch,
        missing_proc,
        proc_mismatch,
    ]


def test_all_renderers_sweep_without_exceptions(all_diff_entries):
    result = ComparisonResult(
        compared_profiles=("Profile1", "Profile2"),
        entries=tuple(all_diff_entries),
    )

    # 1. Console
    console_out = render_console(result)
    assert isinstance(console_out, str)
    assert len(console_out) > 0

    # 2. HTML
    html_out = render_html(result)
    assert isinstance(html_out, str)
    assert "<html" in html_out.lower() or "<!doctype html" in html_out.lower()

    # 3. Excel
    excel_bytes = export_excel(result)
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0

    # 4. TUI TreeData
    tree_data = build_tree_data(result)
    assert len(tree_data.groups) > 0

    # 5. TUI Labels & Details per entry
    for entry in all_diff_entries:
        label = leaf_label(entry)
        detail = detail_text(entry)
        assert isinstance(label, str) and len(label) > 0
        assert isinstance(detail, str) and len(detail) > 0
