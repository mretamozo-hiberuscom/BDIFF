"""Command-line entry point: load profiles, extract schemas, compare, report.

Wires `config.loader.load_profiles` -> `discovery.service.extract_schema`
-> `compare.engine.compare_snapshots` -> `report.write.write_reports`. No
`--format` flag: v1 always generates all four report outputs (HTML, PDF,
Excel, console/TUI).
"""

from __future__ import annotations

import argparse
import sys

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.config.loader import load_profiles
from schema_comparator.discovery.filters import filter_excluded_tables
from schema_comparator.discovery.service import extract_schema
from schema_comparator.report.write import write_reports
from schema_comparator.tui import run_tui


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="schema-comparator")
    parser.add_argument(
        "--config", required=True, help="Ruta al archivo YAML de perfiles de conexión"
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        help="Subconjunto de nombres de perfiles a comparar (por defecto: todos)",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Inicia un navegador interactivo de hallazgos en lugar del "
        "resumen de consola simple (requiere una terminal interactiva)",
    )
    parser.add_argument(
        "--exclude-tables",
        nargs="+",
        help="Excluye tablas cuyo nombre contenga alguno de estos textos "
        "(no distingue mayúsculas/minúsculas), p. ej. --exclude-tables LOG QRTZ",
    )
    return parser


def _resolve_summary_renderer_and_generate_reports(use_tui: bool) -> tuple:
    """Decide which `render_summary` callable (if any) to pass to
    `write_reports`, and whether automatic HTML/PDF/Excel generation
    should still happen at startup. Returns
    `(render_summary_or_None, generate_reports: bool)`.

    Automatic generation is skipped only when the interactive TUI
    actually launches (`--tui` on an interactive terminal); every other
    shape (no `--tui`, or `--tui` falling back to the console on a
    non-interactive terminal) keeps generating unconditionally, per
    REQ-reporting-and-output-002."""
    if not use_tui:
        return None, True
    if sys.stdout.isatty() and sys.stdin.isatty():
        return run_tui, False
    print(
        "[AVISO] --tui requiere una terminal interactiva; "
        "se usará el resumen de consola simple",
        file=sys.stderr,
    )
    return None, True


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    profiles = load_profiles(args.config)
    if args.profiles:
        profiles = [p for p in profiles if p.name in args.profiles]

    snapshots = [extract_schema(p) for p in profiles]
    if args.exclude_tables:
        snapshots = [
            filter_excluded_tables(snapshot, args.exclude_tables) for snapshot in snapshots
        ]
    result = compare_snapshots(snapshots)

    render_summary, do_generate = _resolve_summary_renderer_and_generate_reports(args.tui)
    if render_summary is not None:
        write_reports(result, render_summary=render_summary, generate_reports=do_generate)
    else:
        write_reports(result, generate_reports=do_generate)


if __name__ == "__main__":
    main()

