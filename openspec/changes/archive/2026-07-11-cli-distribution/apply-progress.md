# Apply Progress: Zero-Venv CLI Launcher (`run.py`)

## Summary

All 6 phases / ~24 tasks implemented via strict RED-GREEN TDD.

## What changed

- `run.py` (new, repo root, stdlib-only): pure helpers
  (`resolve_venv_dir`, `resolve_venv_python`, `is_venv_ready`,
  `build_pip_install_argv`, `build_relaunch_argv`) plus orchestration
  (`main`, `_provision`, `_run_checked`) per design.md §2-3. First-run
  provisioning, idempotent skip, self-heal, argument/exit-code
  forwarding, and fail-loud provisioning errors all implemented.
- `src/schema_comparator/__main__.py` (new): thin shim enabling
  `python -m schema_comparator.cli`, used by `run.py`'s relaunch step.
- `tests/unit/test_run_launcher.py` (new, 12 tests): pure-function
  assertions plus mocked-subprocess/venv orchestration tests (no real
  venv or network).
- `tests/unit/test_main_module.py` (new, 1 test): confirms the
  `__main__` guard reaches `cli.main`.
- `tests/integration/test_run_launcher_bootstrap.py` (new, 3 tests):
  real `venv.create` + `pip install -e .` + subprocess relaunch against
  a minimal, dependency-free fixture project (not this repo's full
  dependency set, to keep the integration run fast) — first-run
  provisioning, idempotent second run (marker mtime unchanged),
  self-heal after deleting `.venv`.
- `README.md` (new, repo root): "Quick start" section documenting
  `python run.py --config ... --tui` as the primary zero-setup entry
  point, `uv run`/`pipx run` noted as an alternative (not primary), plus
  a manual-install fallback section.

## Test results

- `tests/unit/test_run_launcher.py` + `tests/unit/test_main_module.py`:
  13 passed.
- `tests/integration/test_run_launcher_bootstrap.py`: 3 passed (~34s,
  real venv creation).
- Full suite (`pytest --cov=schema_comparator`): 276 passed, 1 skipped,
  99% coverage. `run.py` alone (`--cov=run`): 98% coverage (only the
  `if __name__ == "__main__":` guard line uncovered, expected).

## Notes

- No chained PRs (single PR, Medium risk per forecast, no
  delivery-strategy decision required per tasks.md).
