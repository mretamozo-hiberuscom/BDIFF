# Roadmap — BDIFF

> Único roadmap vigente desde el 2026-10-21. Sustituye a `roadmap_v2.md`,
> `architecture/roadmap-multitarget-changes.md`,
> `architecture/analisis-roadmap-multitarget.md` y
> `architecture/decisions/pending-refactorings-issues.md` (siguen en el
> historial de git). Estado verificado contra el código v1.2.5; cada
> cambio se ejecuta con IDD y se cierra solo con evidencia de `ospec`.

## Estado real (v1.2.5)

| Área | Estado |
|---|---|
| Config v1/v2, cadenas ODBC y ADO.NET | Hecho |
| Extracción SQL Server (tablas, columnas, procedimientos) | Hecho, sin default/identity/collation |
| Proveedores PostgreSQL, MySQL, MariaDB, SQLite | Funcionan con huecos (tipos MySQL, SQLite crea archivos) |
| Proveedor Oracle | Roto (consulta con `;`) |
| Comparación N-way de tablas, columnas, procedimientos | Hecho para un mismo motor |
| PK, FK, índices | Modelos y motor existen; comparación con falsos positivos; sin extracción |
| Modo semántico entre motores | En el motor, sin acceso desde CLI/TUI |
| Reportes consola, HTML, PDF, Excel | Hecho |
| TUI: hallazgos, consolidación T-SQL, rutinas | Hecho con fallos de robustez |
| CI | Solo Ubuntu; lint roto con ruff 0.17 (corregido en `pin-ruff-config`) |

## Tanda actual — endurecimiento (rama `refactor/baseline-hardening`)

Orden de ejecución. Prioridad: Windows primero, luego corrección, luego
deuda.

| # | Cambio IDD | Tipo | Qué resuelve |
|---|---|---|---|
| 1 | `pin-ruff-config` | bug | Lint del CI estable con cualquier versión de ruff. **Cerrado.** |
| 2 | `baseline-refresh` | docs | Este baseline, ADR 0006, roadmap único. |
| 3 | `ci-windows-matrix` | feature | CI en `windows-latest` + `ubuntu-latest`. |
| 4 | `console-encoding-windows` | bug | `UnicodeEncodeError` con emojis al redirigir la salida en Windows (cp1252). |
| 5 | `odbc-driver-autodetect` | bug | Driver 17 fijo por defecto; elegir el driver de SQL Server instalado (18 o 17). |
| 6 | `output-paths-and-filenames` | bug | `scripts-db` relativo al directorio de trabajo; nombres reservados de Windows y colisiones de nombre de archivo. |
| 7 | `lazy-driver-imports` | bug | Carga diferida real de `pyodbc` (ADR 0002); eliminar `discovery/service.py`, `discovery/queries.py` y `connectors/` muertos; `pyodbc` solo como extra. |
| 8 | `advanced-object-equality` | bug | Falsos positivos de PK/FK/índices en el motor. |
| 9 | `object-identity-normalization` | feature | Emparejar sin distinguir mayúsculas; esquema MySQL/MariaDB ignorado; owner Oracle normalizado (ADR 0007). |
| 10 | `cli-robustness` | bug | Errores bajo `SchemaComparatorError`; `--profiles` desconocido; `--yes` antes de conectar (ADR 0006); código de salida de `python -m schema_comparator`; `--exclude-routines` en la TUI. |
| 11 | `driver-error-redaction` | bug | Mensajes de MySQL/MariaDB, Oracle y CLI de rutinas sin host ni usuario; pista de instalación `schema-comparator[<motor>]` en vez de `bdiff[<motor>]`. |
| 12 | `oracle-query-terminator` | bug | Quitar `;` de la consulta Oracle. |
| 13 | `sqlite-read-only-open` | bug | Abrir SQLite en solo lectura y fallar si la ruta no existe. |
| 14 | `consolidation-sqlserver-only` | bug | Bloquear la consolidación con perfiles de otros motores, con mensaje claro. |
| 15 | `sp-repair-master-script` | bug | Script maestro de reparación: crear la tabla temporal de resumen, `USE` por perfil, escapar nombres. |
| 16 | `tui-markup-and-threads` | bug | Escapar markup Rich de identificadores; actualizar estado solo desde el hilo de la app; re-ejecución desde "sin diferencias". |
| 17 | `tui-screens-refactor` | refactor | Extraer la lógica pura de `decision_screen.py` y `procedure_screen.py` a módulos testeables. |

## Siguiente — funcionalidad

| Prioridad | Cambio | Notas |
|---|---|---|
| P1 | Extracción SQL Server de default, identity, collation y precisión de fecha/hora | El motor ya compara esos atributos; hoy SQL Server no los extrae. |
| P1 | Extracción de PK, FK e índices (SQL Server primero, luego el resto) | Requiere el cambio 8. |
| P1 | Reportes con todos los atributos que difieren y conteos homogéneos entre formatos | Hoy un mismatch de default/identity se ve idéntico. |
| P1 | Confirmación y aviso para `DROP` en la consolidación | Hoy se generan sin modal ni aviso en el script. |
| P1 | Sincronizar `openspec/specs/` con el comportamiento real | Ver divergencias `spec-*` en `docs/architecture/component-map.yaml`. |
| P2 | Flag de CLI para el modo semántico y política de motores mezclados con aviso (ADR 0003) | |
| P2 | Tipos MySQL con `COLUMN_TYPE` (UNSIGNED, ENUM, precisión) | |
| P2 | Timeout de conexión PostgreSQL y opciones de timeout por perfil | |
| P2 | Pruebas de arquitectura como fitness de las ADR 0001, 0002 y 0006 | |
| P2 | Unificar `MySqlProvider`/`MariaDbProvider` y la plantilla de introspección | |
| P2 | Deuda heredada de `pending-refactorings-issues.md` | Claves YAML duplicadas dentro de `options:` reportadas como perfil duplicado (`config/loader.py:27`); `translate` elimina claves con la grafía original (`sqlserver/profile_parser.py:100`); `SqlServerProvider.introspect` no traduce cadenas ADO.NET de perfiles creados fuera del loader; tipo `str | Path` en `ProfileRepository`; puertos `ReportSink`/`ScriptSink` sin implementación (implementar o retirar); más tests de `CompareProfilesUseCase`. |
| P3 | Renderers DDL de PostgreSQL, MySQL, Oracle y SQLite corregidos y conectados a la consolidación | SQLite hoy reconstruye con pérdida; Oracle `MODIFY` repite nulabilidad. |
| P3 | Plan de migración neutro con clasificación SAFE/DESTRUCTIVE (ADR 0005) | |
| P3 | Matriz de tests de contrato contra motores reales | |
| P3 | Detección de renombres, export CSV, descubrimiento desde DDL exportado | Capacidades del brief original nunca implementadas. |

## Decisiones diferidas

| Decisión | Responsable | Último momento responsable |
|---|---|---|
| Medidas de éxito (tiempo por ejecución, número de bases) | Autor | Antes de paralelizar la extracción |
| Comando de diagnóstico de drivers (`providers doctor`) | Autor | Cuando se distribuya fuera del equipo |
