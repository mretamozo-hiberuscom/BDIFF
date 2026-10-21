"""The README's CLI options table is the public contract of the CLI: every
documented flag exists in the parser and every parser flag is documented."""

import pathlib
import re

from schema_comparator.cli import build_arg_parser

_README = pathlib.Path(__file__).resolve().parents[2] / "README.md"


def _documented_flags() -> set[str]:
    text = _README.read_text(encoding="utf-8")
    section = text.split("## Opciones del CLI", 1)[1].split("\n## ", 1)[0]
    flags: set[str] = set()
    for line in section.splitlines():
        if line.startswith("| `"):
            first_cell = line.split("|")[1]
            flags.update(re.findall(r"--[a-z][a-z-]*", first_cell))
        flags.update(re.findall(r"`(--[a-z][a-z-]*)` es un alias", line))
    return flags


def _parser_flags() -> set[str]:
    return {
        option
        for action in build_arg_parser()._actions
        for option in action.option_strings
        if option.startswith("--") and option != "--help"
    }


def test_readme_documents_every_cli_flag() -> None:
    assert _parser_flags() - _documented_flags() == set()


def test_readme_documents_no_unknown_cli_flag() -> None:
    assert _documented_flags() - _parser_flags() == set()
