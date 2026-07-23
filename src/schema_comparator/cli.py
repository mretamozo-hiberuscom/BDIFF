"""Command-line entry point: load profiles, extract schemas, compare, report."""

from __future__ import annotations

import argparse
import functools
import sys

from schema_comparator.config.loader import load_profiles
from schema_comparator.domain.comparison.models import ComparisonFilters
from schema_comparator.domain.errors import SchemaComparatorError
from schema_comparator.report.write import write_reports
from schema_comparator.tui import run_tui
from schema_comparator.tui.actions import run_comparison


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
        help="Excluye tablas cuyo nombre contenga alguno de estos textos (p. ej. --exclude-tables LOG QRTZ)",
    )
    parser.add_argument(
        "--exclude-routines",
        nargs="+",
        help="Excluye procedimientos/vistas cuyo nombre contenga alguno de estos textos",
    )
    parser.add_argument(
        "--validate-routines",
        action="store_true",
        help="Ejecuta una verificación de solo lectura (no mutante) sobre las dependencias de procedimientos y vistas",
    )
    parser.add_argument(
        "--refresh-modules",
        action="store_true",
        help="Ejecuta sp_refreshsqlmodule (mutante) sobre rutinas no firmadas. Requiere la bandera --yes.",
    )
    parser.add_argument(
        "--verify-sps",
        action="store_true",
        help="Alias heredado de --refresh-modules",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma explícitamente operaciones mutantes como --refresh-modules",
    )
    return parser


def _resolve_summary_renderer_and_generate_reports(
    use_tui: bool,
    profiles: list,
    exclude_patterns: list[str],
) -> tuple:
    if not use_tui:
        return None, True
    if sys.stdout.isatty() and sys.stdin.isatty():
        bound_run_tui = functools.partial(
            run_tui, profiles=profiles, exclude_patterns=exclude_patterns
        )
        return bound_run_tui, False
    print(
        "[AVISO] --tui requiere una terminal interactiva; se usará el resumen de consola simple",
        file=sys.stderr,
    )
    return None, True


def _run_routine_validation(
    profiles: list,
    exclude_routines: list[str] | None = None,
    read_only: bool = True,
) -> bool:
    from schema_comparator.infrastructure.providers.sqlserver import connection
    from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
        enumerate_routines,
        refresh_modules_mutating,
        validate_routines_read_only,
    )

    patterns = [p.lower() for p in (exclude_routines or [])]
    mode_str = "solo lectura" if read_only else "recompilación mutante (sp_refreshsqlmodule)"
    print(f"\n🔍 Ejecutando validación de rutinas [{mode_str}]...")
    has_errors = False

    for profile in profiles:
        provider_name = str(getattr(profile, "provider", "sqlserver")).lower()
        if provider_name == "sqlserver":
            try:
                with connection.connect(profile) as conn:
                    targets = enumerate_routines(conn)
                    if patterns:
                        targets = tuple(
                            t for t in targets
                            if not any(pat in t.object_name.lower() for pat in patterns)
                        )
                    if read_only:
                        results = validate_routines_read_only(conn, targets)
                    else:
                        results = refresh_modules_mutating(conn, targets)

                    failures = [r for r in results if not r.is_success]
                    if failures:
                        has_errors = True
                        print(f"❌ Perfil '{profile.name}': {len(failures)} objeto(s) con fallos:")
                        for f in failures:
                            proc_name = getattr(f, "routine", f).object_name
                            err_msg = getattr(f, "error_message", "Error")
                            print(f"   - [{getattr(f, 'routine', f).schema_name}].[{proc_name}]: {err_msg}")
                    else:
                        print(f"✅ Perfil '{profile.name}': todas las rutinas evaluadas están correctas ({len(results)} verificadas).")
            except Exception as exc:
                has_errors = True
                print(f"⚠️ Perfil '{profile.name}': error al conectar o validar rutinas: {exc}")

    return has_errors


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_arg_parser().parse_args(argv)
        profiles = load_profiles(args.config)
        if args.profiles:
            profiles = [p for p in profiles if p.name in args.profiles]

        exclude_tables = list(args.exclude_tables or [])
        exclude_routines = list(args.exclude_routines or [])

        filters = ComparisonFilters(
            excluded_tables=tuple(exclude_tables),
            excluded_routines=tuple(exclude_routines),
        )

        result = run_comparison(profiles, filters)

        render_summary, do_generate = _resolve_summary_renderer_and_generate_reports(
            args.tui, profiles, exclude_tables
        )
        if render_summary is not None:
            write_reports(result, render_summary=render_summary, generate_reports=do_generate)
        else:
            write_reports(result, generate_reports=do_generate)

        validation_failed = False
        if args.validate_routines:
            validation_failed = _run_routine_validation(profiles, exclude_routines=exclude_routines, read_only=True)

        if args.refresh_modules or args.verify_sps:
            if not args.yes:
                print(
                    "\n⚠️ ATENCIÓN: --refresh-modules ejecuta sp_refreshsqlmodule para recompilar metadatos en la BD. "
                    "Para confirmar esta acción mutante, incluye la bandera --yes.",
                    file=sys.stderr,
                )
                return 1
            v_fail = _run_routine_validation(profiles, exclude_routines=exclude_routines, read_only=False)
            validation_failed = validation_failed or v_fail

        if bool(result.entries) or validation_failed:
            return 1
        return 0

    except SchemaComparatorError as exc:
        print(f"[ERROR DE INFRAESTRUCTURA] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[ERROR INESPERADO] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
