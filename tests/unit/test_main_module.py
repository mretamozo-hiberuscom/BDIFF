"""Unit test for `schema_comparator.__main__`: confirms the module-level
guard reaches `cli.main`, enabling `python -m schema_comparator.cli`
style invocation used by run.py's relaunch step."""

import runpy
from unittest.mock import patch

import pytest


def test_module_invocation_runs_main_and_exits_with_its_code() -> None:
    with patch("schema_comparator.cli.main", return_value=1) as m_main:
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("schema_comparator.__main__", run_name="__main__")

    m_main.assert_called_once_with()
    assert exc_info.value.code == 1
