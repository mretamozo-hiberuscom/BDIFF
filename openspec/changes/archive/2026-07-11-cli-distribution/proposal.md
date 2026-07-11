# Proposal: Zero-Venv CLI Launcher (`run.py`)

## Intent

Today, running the CLI requires a user to manually create a virtual
environment, activate it, and `pip install -e .` before `schema-comparator`
works. This proposal adds a single, stdlib-only, cross-platform launcher
script (`run.py`) at the repo root that any user with a Python 3.11+
interpreter can invoke directly — `py run.py ...`, `python run.py ...`, or
`python3 run.py ...` — with no manual environment setup step. `run.py`
detects whether `.venv` exists and is usable, creates and provisions it
transparently on first use (or whenever it is missing), then re-launches
the real CLI (`schema_comparator.cli:main`) inside that venv, forwarding
all arguments and the exit code unchanged.

## Scope

### In Scope

- A new `run.py` at the repository root, using only the Python standard
  library (`venv`, `subprocess`, `sys`, `os`, `pathlib`) — it must be
  runnable by a bare interpreter before any project dependency is
  installed.
- Idempotent `.venv` bootstrap: create the venv only if missing or not yet
  provisioned; skip both venv creation and `pip install -e .` on
  subsequent runs once a completion marker confirms the venv is ready
  (Decision 2).
- Self-healing: if `.venv` is deleted or partially created after a prior
  successful run, `run.py` recreates and re-provisions it rather than
  failing or requiring manual cleanup.
- Forwarding of all CLI arguments (`sys.argv[1:]`) and the child process's
  exit code, so `python run.py --config ... --tui` behaves identically to
  the current `python -m schema_comparator.cli --config ... --tui` inside
  an activated venv.
- A new `src/schema_comparator/__main__.py` so the provisioned venv's
  interpreter can be invoked as `python -m schema_comparator.cli` (already
  supported) as well as via the package's `__main__` module, giving
  `run.py` a stable, testable relaunch target.
- Clear, actionable error reporting (non-zero exit, message to `stderr`,
  no partially-marked "ready" state left behind) when venv creation or
  dependency installation fails.
- Pure, side-effect-free helper functions (path resolution, readiness
  checks, argv construction for `pip install`/relaunch) factored out of
  `run.py`'s `main()` so they are unit-testable without actually creating a
  venv; a smaller set of slower integration tests exercise the real `venv`
  creation path in `tmp_path`.
- A short README/docs note pointing at `python run.py ...` as the
  recommended zero-setup entry point, mentioning `uv run` / `pipx run` as
  a documented alternative for users who already have those tools, without
  making either the primary supported mechanism.

### Out of Scope

- A `[project.scripts]` console-script entry point (e.g. a
  `schema-comparator` executable placed on `PATH` after install) — this
  proposal only adds the zero-setup launcher; a PATH-level entry point can
  be proposed separately if desired.
- `uv run` / `pipx run` as the primary distribution mechanism — mentioned
  only as an alternative in documentation, per this change's approved
  scope.
- Automatic detection/handling of dependency drift (e.g. `pyproject.toml`
  gaining a new dependency after `.venv` was already provisioned); the v1
  self-healing story only covers a missing/deleted `.venv`, not a stale
  one. A documented manual workaround (delete `.venv` and re-run) covers
  this until a future change addresses it, if ever.
- Packaging as a standalone frozen executable/binary (e.g. PyInstaller) —
  a materially different distribution mechanism from an auto-provisioning
  launcher script.
- Windows-specific `.ps1`/`.bat` launchers — a single cross-platform
  `run.py` is the only launcher this change adds.
- Any change to `cli.py`'s argument parsing, comparison, or reporting
  behavior — `run.py` only bootstraps the environment and re-executes the
  existing, unmodified CLI entry point.

## Capabilities

### New Capabilities

- `cli-distribution`: given any Python 3.11+ interpreter and no
  pre-existing `.venv`, running `run.py` (via `py`, `python`, or
  `python3`) transparently provisions `.venv` and installs the project
  into it, then runs the CLI with the user's original arguments and exit
  code, requiring no manual environment setup step.

### Modified Capabilities

None. This change is purely additive; no existing spec's requirements are
touched.

## Approach

### Decision 1 — `run.py` at the repo root, stdlib-only

**Decision: a single `run.py` script at the repository root, importing
only the Python standard library.**

- Rationale: the launcher's entire job is to get from "bare interpreter,
  nothing installed" to "project installed and running" — it cannot import
  `schema_comparator` or any of its third-party dependencies (`PyYAML`,
  `pyodbc`, `textual`, ...) itself, since none of those are guaranteed to
  exist yet when it first runs. A root-level single file (rather than a
  package) is also the simplest thing a user can point `py`/`python`/
  `python3` at directly without first knowing anything about `src/`
  layout.

### Decision 2 — Idempotency via a completion marker file, not repeated installs

**Decision: after a successful `.venv` creation + `pip install -e .`,
write a marker file (e.g. `.venv/.schema_comparator_ready`) recording the
completion; subsequent runs skip both venv creation and the pip install
step when the marker is present and `.venv`'s interpreter exists.**

- Rationale: re-running `pip install -e .` on every invocation would add
  noticeable startup latency and unnecessary network/disk I/O to every
  single CLI invocation, defeating the "just works, fast" goal of a
  zero-setup launcher. A marker file is the simplest reliable signal of
  "provisioning completed successfully" without needing to introspect pip's
  installed-package state. The marker is only written after the install
  subprocess exits 0, so a failed install never leaves a false-positive
  marker behind (Decision 3 covers failure handling in more detail).

### Decision 3 — Failure handling: no partial "ready" state, actionable message

**Decision: if venv creation or `pip install -e .` fails, `run.py` prints
a clear, actionable error to `stderr` (including the failing command and
its output) and exits non-zero, without writing the readiness marker.**

- Rationale: a partially-provisioned `.venv` that is silently treated as
  "ready" on a later run would produce confusing `ModuleNotFoundError`s far
  removed from the actual root cause (a failed install). Failing loudly
  and immediately, with the marker withheld, means the next invocation
  retries provisioning from scratch rather than trusting a broken
  environment.

### Decision 4 — Relaunch via `subprocess.run`, not `os.exec*`

**Decision: `run.py` relaunches the CLI with
`subprocess.run([venv_python, "-m", "schema_comparator.cli", *sys.argv[1:]])`
and exits with the child's return code, rather than replacing the current
process via `os.execv`/`os.execve`.**

- Rationale: `os.exec*` has no direct equivalent on Windows (the
  `os.exec*` family on Windows spawns a new process and waits, it does not
  truly replace the calling process image the way POSIX `execve` does),
  which would make the two platforms behave subtly differently for
  signal handling and exit-code propagation. `subprocess.run` behaves
  identically cross-platform, and its explicit
  `sys.exit(completed.returncode)` makes the relaunch step a plain,
  synchronous, unit-testable function call (mockable in tests) rather
  than a process-replacing side effect that cannot return control to a
  test.

### Decision 5 — Testability boundary

**Decision: extract every decision `run.py` makes (venv path resolution,
"is this venv ready" check, the `pip install` argv, the relaunch argv)
into small, pure functions with no side effects; `main()` is a thin
orchestrator calling `venv.create`/`subprocess.run` and those pure
functions. Pure functions get direct unit tests; `main()`'s orchestration
(venv creation, install, relaunch) gets a smaller number of integration
tests using `tmp_path` that create a real (throwaway) venv.**

- Rationale: matches this project's existing convention (`compare/`,
  `report/`, `tui/formatting.py`) of separating pure decision logic from
  I/O/orchestration so the bulk of behavior is testable without expensive
  or environment-dependent side effects (spinning up a real venv is slow
  and, in CI, may not always be desirable to do dozens of times).

## Rollback Plan

- Deleting `run.py` and `src/schema_comparator/__main__.py` fully reverses
  this change; neither file is imported or depended on by any existing
  module, test, or the packaged CLI's own argument parsing/behavior.
- No existing file (`cli.py`, `pyproject.toml`'s dependency list, any spec)
  is modified in a way that requires a compensating change on rollback —
  this change is additive only.
- A user's own `.venv` and its `.schema_comparator_ready` marker are local,
  git-ignored artifacts; rollback of this change does not need to touch or
  clean them up.
