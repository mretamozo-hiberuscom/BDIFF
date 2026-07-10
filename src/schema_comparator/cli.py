"""Command-line entry point: load profiles, extract schemas, compare, report.

Wires `config.loader.load_profiles` -> `discovery.service.extract_schema`
-> `compare.engine.compare_snapshots` -> `report.write.write_reports`. No
`--format` flag: v1 always generates all three report outputs.
"""

from __future__ import annotations

import argparse
import sys

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.config.loader import load_profiles
from schema_comparator.discovery.service import extract_schema
from schema_comparator.report.write import write_reports
from schema_comparator.tui import run_tui


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="schema-comparator")
    parser.add_argument(
        "--config", required=True, help="Path to connection profiles YAML"
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        help="Subset of profile names to compare (default: all)",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch an interactive findings browser instead of the plain "
        "console summary (requires an interactive terminal)",
    )
    return parser


def _resolve_summary_renderer(use_tui: bool):
    """Decide which `render_summary` callable (if any) to pass to
    `write_reports`. Returns `None` to keep `write_reports`'s own
    default (the plain console summary) when `--tui` is not requested or
    when the terminal is not interactive."""
    if not use_tui:
        return None
    if sys.stdout.isatty() and sys.stdin.isatty():
        return run_tui
    print(
        "[WARN] --tui requires an interactive terminal; "
        "falling back to plain console summary",
        file=sys.stderr,
    )
    return None


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    profiles = load_profiles(args.config)
    if args.profiles:
        profiles = [p for p in profiles if p.name in args.profiles]

    snapshots = [extract_schema(p) for p in profiles]
    result = compare_snapshots(snapshots)

    render_summary = _resolve_summary_renderer(args.tui)
    if render_summary is not None:
        write_reports(result, render_summary=render_summary)
    else:
        write_reports(result)  # always all three; no --format flag


if __name__ == "__main__":
    main()

