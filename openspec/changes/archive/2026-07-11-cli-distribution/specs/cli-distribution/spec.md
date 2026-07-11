# Spec Delta: CLI Distribution

Status: NEW capability spec (no baseline exists yet at
`openspec/specs/cli-distribution/spec.md`). This delta is the initial
version of the capability.

Scope reminder (per proposal.md): a stdlib-only, cross-platform launcher
script that provisions `.venv` on demand and re-executes the existing CLI.
No change to `cli.py`'s own argument parsing or behavior, no PATH-level
console-script entry point, no dependency-drift detection.

## ADDED Requirements

### Requirement: Launch Without a Pre-Existing Virtual Environment {#REQ-cli-distribution-001}

Given a checkout of this repository with no `.venv` directory present, the
system MUST allow a user with any Python 3.11+ interpreter to run
`run.py` (via `py run.py`, `python run.py`, or `python3 run.py`) and have
the CLI become fully functional without any prior manual environment
setup step (no manual `python -m venv`, no manual `pip install`, no manual
activation).

#### Scenario: First run with no `.venv` present provisions and runs the CLI

- GIVEN a repository checkout with no `.venv` directory
- WHEN a user runs `python run.py --config config.local.yaml`
- THEN `run.py` SHALL create `.venv`, install the project into it, and run
  the CLI with the given arguments
- AND no manual environment-setup step SHALL be required beforehand

#### Scenario: `run.py` is invocable via `py`, `python`, or `python3`

- GIVEN any of the three common Python launcher commands is available on
  the user's system
- WHEN the user runs `run.py` via that command
- THEN the CLI SHALL run to completion identically regardless of which of
  the three commands was used to invoke `run.py`

### Requirement: Idempotent Re-Run Skips Redundant Provisioning {#REQ-cli-distribution-002}

Once `.venv` has been successfully provisioned by `run.py`, subsequent
invocations MUST NOT recreate the virtual environment or reinstall the
project; they MUST proceed directly to running the CLI.

#### Scenario: Second run with an already-provisioned `.venv` skips setup

- GIVEN `.venv` was successfully provisioned by a prior `run.py` invocation
- WHEN the user runs `run.py` again
- THEN `run.py` SHALL NOT recreate `.venv` or reinstall the project
- AND the CLI SHALL run directly with the given arguments

### Requirement: Self-Heal a Missing or Removed Virtual Environment {#REQ-cli-distribution-003}

If `.venv` is missing, deleted, or was left in a non-ready state (no
completion marker present) at the time `run.py` is invoked, the system
MUST provision it from scratch, exactly as on a first run, without
requiring manual cleanup or intervention.

#### Scenario: `.venv` was deleted after a prior successful run

- GIVEN `.venv` was previously provisioned successfully but has since been
  deleted
- WHEN the user runs `run.py` again
- THEN `run.py` SHALL recreate and re-provision `.venv` from scratch
- AND the CLI SHALL then run with the given arguments

### Requirement: Forward Arguments and Exit Code Unchanged {#REQ-cli-distribution-004}

`run.py` MUST forward every command-line argument it receives (other than
its own invocation) to the underlying CLI unmodified, and MUST exit with
the same exit code the underlying CLI process produced.

#### Scenario: All CLI arguments reach the underlying CLI unmodified

- GIVEN `run.py` is invoked as `python run.py --config config.local.yaml --tui --exclude-tables LOG`
- WHEN `run.py` relaunches the CLI inside the provisioned `.venv`
- THEN the CLI SHALL receive `--config config.local.yaml --tui --exclude-tables LOG` exactly as given

#### Scenario: Exit code is propagated from the underlying CLI

- GIVEN the underlying CLI process exits with a non-zero exit code for a
  given invocation
- WHEN `run.py` completes
- THEN `run.py`'s own process SHALL exit with that same non-zero code

### Requirement: Fail Loudly and Cleanly on Provisioning Failure {#REQ-cli-distribution-005}

If virtual environment creation or dependency installation fails, the
system MUST report the failure clearly (including the failing step and
its output) to `stderr`, MUST exit with a non-zero code, and MUST NOT
leave behind any state that would cause a later invocation to treat the
environment as successfully provisioned.

#### Scenario: A failed dependency install is reported clearly and does not mark the venv ready

- GIVEN `pip install -e .` fails during provisioning (e.g. a network
  failure)
- WHEN `run.py` handles that failure
- THEN it SHALL print a clear, actionable error message identifying the
  failed step to `stderr`
- AND it SHALL exit with a non-zero code
- AND a subsequent invocation SHALL attempt provisioning again rather than
  assuming the environment is ready
