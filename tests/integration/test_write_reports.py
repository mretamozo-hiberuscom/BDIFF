"""Integration test: real write_reports/render_html/export_pdf, writing
actual HTML/PDF files to a temp cwd."""

from schema_comparator.compare.models import ColumnMismatch, ComparisonResult
from schema_comparator.compare.models import ColumnAttributes, MissingColumn, MissingTable
from schema_comparator.report.html import render_html
from schema_comparator.report.write import write_reports


def _fixture_result() -> ComparisonResult:
    return ComparisonResult(
        compared_profiles=("a", "b", "c"),
        entries=(
            MissingColumn(
                schema_name="sales",
                table_name="Invoice",
                column_name="notes",
                missing_from_profile="c",
            ),
            ColumnMismatch(
                schema_name="sales",
                table_name="Invoice",
                column_name="amount",
                values_by_profile=(
                    (
                        "a",
                        ColumnAttributes(
                            data_type="decimal",
                            character_maximum_length=None,
                            numeric_precision=10,
                            numeric_scale=2,
                            is_nullable=False,
                        ),
                    ),
                    (
                        "b",
                        ColumnAttributes(
                            data_type="decimal",
                            character_maximum_length=None,
                            numeric_precision=12,
                            numeric_scale=2,
                            is_nullable=False,
                        ),
                    ),
                ),
            ),
            MissingTable(
                schema_name="sales",
                table_name="Payment",
                missing_from_profile="c",
            ),
        ),
    )


def test_write_reports_creates_paired_html_and_pdf_files_with_matching_timestamp_in_reportes_dir(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = _fixture_result()

    write_reports(result)

    html_files = list(tmp_path.glob("reportes/schema-diff-report-*.html"))
    pdf_files = list(tmp_path.glob("reportes/schema-diff-report-*.pdf"))
    assert len(html_files) == 1
    assert len(pdf_files) == 1

    html_stem = html_files[0].name.removesuffix(".html")
    pdf_stem = pdf_files[0].name.removesuffix(".pdf")
    assert html_stem == pdf_stem

    assert html_files[0].read_text(encoding="utf-8") == render_html(result)
