"""Run a routine operation (validation or metadata refresh) on every SQL
Server profile: connect, enumerate routines, drop excluded ones, apply the
operation. Shared by the CLI and the TUI routines screen."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.infrastructure.providers.sqlserver import (
    connection,
    sp_validator,
)
from schema_comparator.infrastructure.providers.sqlserver.errors import (
    describe_failure,
)
from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
    RoutineIdentity,
)

RoutineOperation = Callable[[object, tuple[RoutineIdentity, ...]], Sequence]


@dataclass(frozen=True)
class RoutineRun:
    """Outcome for one profile: the operation results, or a safe message
    when connecting or enumerating failed."""

    results: tuple = ()
    error: str | None = None


def run_routines(
    profiles: Sequence[ConnectionProfile],
    exclude_patterns: Sequence[str],
    operation: RoutineOperation,
) -> dict[str, RoutineRun]:
    """Apply `operation` to the non-excluded routines of every SQL Server
    profile; other providers are skipped. A routine is excluded when its
    name contains a pattern, ignoring case."""
    needles = [pattern.lower() for pattern in exclude_patterns if pattern]
    runs: dict[str, RoutineRun] = {}
    for profile in profiles:
        if profile.provider.casefold() != "sqlserver":
            continue
        try:
            with connection.connect(profile) as conn:
                targets = tuple(
                    routine
                    for routine in sp_validator.enumerate_routines(conn)
                    if not any(n in routine.object_name.lower() for n in needles)
                )
                runs[profile.name] = RoutineRun(results=tuple(operation(conn, targets)))
        except Exception as exc:
            runs[profile.name] = RoutineRun(error=describe_failure(profile, exc))
    return runs
