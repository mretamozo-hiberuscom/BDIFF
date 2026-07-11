Design: Zero-Venv CLI Launcher (`run.py`)

Change: `cli-distribution`
Status: design (phase artifact)
Scope: a single stdlib-only `run.py` at the repo root that provisions
`.venv` on demand and relaunches the CLI inside it, forwarding all
arguments and the exit code.

This design realizes the five requirements in
`openspec/changes/cli-distribution/specs/cli-distribution/spec.md` and the
five decisions recorded in `openspec/changes/cli-distribution/proposal.md`.

---

## 1. File layout

```text
run.py                                # new, repo root, stdlib-only
src/schema_comparator/__main__.py     # new, thin `-m schema_comparator.cli` shim
tests/unit/test_run_launcher.py       # new, pure-function unit tests
tests/integration/test_run_launcher_bootstrap.py  # new, real-venv integration tests
```

`run.py` lives at the repo root (not under `src/`) since it must be
runnable before the package is installed anywhere, and is the file a user
is told to invoke directly.

## 2. Pure functions (`run.py`, no side effects)

```python
# run.py
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_VENV_DIR_NAME = ".venv"
_READY_MARKER_NAME = ".schema_comparator_ready"


def resolve_venv_dir(repo_root: Path) -> Path:
    return repo_root / _VENV_DIR_NAME


def resolve_venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def is_venv_ready(venv_dir: Path) -> bool:
    return resolve_venv_python(venv_dir).exists() and (venv_dir / _READY_MARKER_NAME).exists()


def build_pip_install_argv(venv_python: Path, repo_root: Path) -> list[str]:
    return [str(venv_python), "-m", "pip", "install", "-e", str(repo_root)]


def build_relaunch_argv(venv_python: Path, cli_args: list[str]) -> list[str]:
    return [str(venv_python), "-m", "schema_comparator.cli", *cli_args]
```

- Every function above takes plain arguments (`Path`, `list[str]`) and
  returns a plain value — no `subprocess.run`, no `venv.create`, no
  filesystem writes. This is the layer `tests/unit/test_run_launcher.py`
  exercises directly and exhaustively (REQ-cli-distribution-001 through
  004's argument-shape assertions), per proposal Decision 5.
- `is_venv_ready` folds both "does the interpreter exist" and "was the
  marker written" into one check — this is the single predicate `main()`
  branches on for REQ-cli-distribution-002 (skip) vs.
  REQ-cli-distribution-001/003 (provision), keeping the orchestration
  function itself branch-free beyond this one call.

## 3. Orchestration (`main()`)

```python
# run.py (continued)
def _run_checked(argv: list[str], *, step_name: str) -> None:
    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] {step_name} failed:", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode or 1)


def _provision(repo_root: Path, venv_dir: Path) -> None:
    import venv as venv_module

    venv_module.create(venv_dir, with_pip=True)
    venv_python = resolve_venv_python(venv_dir)
    _run_checked(
        build_pip_install_argv(venv_python, repo_root),
        step_name="pip install -e .",
    )
    (venv_dir / _READY_MARKER_NAME).write_text("ok\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    cli_args = sys.argv[1:] if argv is None else argv
    repo_root = Path(__file__).resolve().parent
    venv_dir = resolve_venv_dir(repo_root)

    if not is_venv_ready(venv_dir):
        _provision(repo_root, venv_dir)

    venv_python = resolve_venv_python(venv_dir)
    completed = subprocess.run(build_relaunch_argv(venv_python, cli_args))
    sys.exit(completed.returncode)


if __name__ == "__main__":
    main()
```

- **REQ-cli-distribution-001/003 (provision / self-heal):**
  `is_venv_ready` returning `False` — whether because `.venv` never
  existed or because it was deleted/partial after a prior run — takes the
  identical `_provision` path; there is no separate "self-heal" branch,
  satisfying both requirements with one code path (proposal Decision 2's
  marker-file design is what makes "missing" and "never finished" collapse
  into the same check).
- **REQ-cli-distribution-002 (idempotent skip):** `is_venv_ready` returning
  `True` skips `_provision` entirely — no `venv.create` call, no
  `pip install` subprocess — going straight to the relaunch step.
- **REQ-cli-distribution-004 (argument/exit-code forwarding):** `cli_args`
  is passed through `build_relaunch_argv` unmodified (no parsing or
  re-interpretation by `run.py` itself), and `main()`'s final
  `sys.exit(completed.returncode)` propagates the child's exact exit code,
  per proposal Decision 4 (`subprocess.run`, not `os.exec*`).
- **REQ-cli-distribution-005 (fail loudly, no partial ready state):**
  `_run_checked` is called for the `pip install` step (not for
  `venv.create`, which either succeeds or raises directly — an uncaught
  `venv.create` exception already propagates as a Python traceback with a
  non-zero exit, which is an acceptable failure mode for a bootstrap
  script per the proposal's "fail loudly" intent). The readiness marker
  (`(venv_dir / _READY_MARKER_NAME).write_text(...)`) is only reached
  after `_run_checked` returns without exiting, i.e. only after a
  zero-exit `pip install` — an install failure calls `sys.exit` inside
  `_run_checked` before the marker line is ever reached, so no partial
  "ready" state is possible by construction.

## 4. `src/schema_comparator/__main__.py`

```python
"""Enables `python -m schema_comparator.cli` style invocation from
run.py's relaunch step, and `python -m schema_comparator` directly."""

from schema_comparator.cli import main

if __name__ == "__main__":
    main()
```

This mirrors the existing `if __name__ == "__main__": main()` guard
already present in `cli.py` (see `src/schema_comparator/cli.py`), giving
`run.py` a stable `-m schema_comparator.cli` target that does not depend
on `cli.py`'s own `__main__` guard (both work; `run.py` targets the module
form for clarity, per Decision 4's intent to keep the relaunch step a
plain, predictable subprocess invocation).

## 5. Testing strategy (REQ-cli-distribution-001 through 005)

### 5.1 Pure-function unit tests (`tests/unit/test_run_launcher.py`)

Direct assertions against `resolve_venv_dir`, `resolve_venv_python`,
`is_venv_ready`, `build_pip_install_argv`, `build_relaunch_argv` using
`tmp_path` for filesystem-shape setup (creating/removing the interpreter
path and marker file to drive `is_venv_ready`'s branches) — no real venv
or subprocess involved. `resolve_venv_python`'s OS-branch is tested with
`monkeypatch.setattr(os, "name", ...)` for both `"nt"` and a POSIX value.

### 5.2 Orchestration tests with mocked subprocess (`tests/unit/test_run_launcher.py`, continued)

`main()`'s three branches (`_provision` skipped, `_provision` runs and
succeeds, `_provision`'s `pip install` fails) are tested by monkeypatching
`subprocess.run` and `venv.create` (module-level, via `monkeypatch.setattr`)
to fake process results, asserting: which functions were called with which
argv, whether `sys.exit` was invoked with which code, and whether the
marker file was written — covering
REQ-cli-distribution-002/004/005 without any real venv creation or network
access.

### 5.3 Integration tests with a real venv (`tests/integration/test_run_launcher_bootstrap.py`)

A small number of slower tests that actually invoke `run.py` as a
subprocess against a `tmp_path` copy of a minimal project layout,
asserting: a first run creates a working `.venv` with the marker file
present (REQ-cli-distribution-001), a second run does not touch
`.venv`'s modification time / does not re-run `pip install`
(REQ-cli-distribution-002, asserted via a mtime check or a monkeypatched
sentinel), and deleting `.venv` before a third run causes it to be
recreated (REQ-cli-distribution-003). These mirror the existing
`tests/integration/` convention (e.g. `test_extraction_live.py`) of
isolating slow/environment-dependent tests from the fast unit suite.

## 6. Documentation update

A short section is added to the top-level README (or created if absent)
documenting `python run.py --config ... --tui` as the recommended
zero-setup entry point, with one paragraph noting `uv run`/`pipx run` as
an alternative for users who already have those tools installed, without
presenting either as the primary supported mechanism (per proposal
Out-of-Scope).
