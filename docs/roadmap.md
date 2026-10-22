# Roadmap — BDIFF

> Único roadmap vigente desde el 2026-10-21. Sustituye a `roadmap_v2.md`,
> `architecture/roadmap-multitarget-changes.md`,
> `architecture/analisis-roadmap-multitarget.md` y
> `architecture/decisions/pending-refactorings-issues.md` (siguen en el
> historial de git). Estado verificado contra el código v1.2.5; cada
> cambio se ejecuta con IDD y se cierra solo con evidencia de `ospec`.

## Estado real (`main`, 2026-10-21)

| Área | Estado |
|---|---|
| Config v1/v2, cadenas ODBC y ADO.NET; driver ODBC 17/18 elegido al conectar | Hecho |
| Extracción SQL Server (tablas, columnas, procedimientos) | Hecho, con default, identity, collation explícita y precisión de fecha/hora |
| Proveedores PostgreSQL, MySQL, MariaDB, SQLite (solo lectura), Oracle | Funcionan; MySQL pierde parámetros de tipo |
| Carga diferida de drivers (sin libodbc arranca para otros motores) | Hecho |
| Comparación N-way con identidad normalizada (ADR 0007) | Hecho |
| PK, FK, índices | Comparación correcta; sin extracción en ningún proveedor |
| Modo semántico entre motores | En el motor, sin acceso desde CLI/TUI |
| Reportes consola (segura en Windows), HTML, PDF, Excel | Hecho |
| TUI: hallazgos, consolidación T-SQL (solo SQL Server), rutinas | Hecho |
| Errores sin datos de conexión | Hecho |
| CI Windows + Ubuntu, lint estable | Hecho |

## Tanda de endurecimiento — cerrada (PR #21)

Cada cambio se cerró con evidencia de `ospec` y está archivado en
`idd/archive/2026-10-21-<cambio>/`.

| # | Cambio IDD | Qué resolvió |
|---|---|---|
| 1 | `pin-ruff-config` | Lint estable con cualquier versión de ruff. |
| 2 | `baseline-refresh` | Este baseline, ADR 0006, roadmap único. |
| 3 | `ci-windows-matrix` | CI en Windows y Ubuntu. |
| 4 | `console-encoding-windows` | Consola sin emojis y segura con cp1252. |
| 5 | `odbc-driver-autodetect` | Driver ODBC 17/18 instalado elegido al conectar. |
| 6 | `output-paths-and-filenames` | `scripts-db` en el directorio de trabajo; nombres válidos en Windows. |
| 7 | `lazy-driver-imports` | pyodbc solo se carga con SQL Server; módulos heredados eliminados. |
| 8 | `advanced-object-equality` | Sin falsos positivos de PK/FK/índices. |
| 9 | `object-identity-normalization` | Identidad normalizada y variantes en reportes (ADR 0007). |
| 10 | `cli-robustness` | `--yes` antes de conectar, `--profiles` estricto, errores limpios. |
| 11 | `driver-error-redaction` | Mensajes sin texto libre del driver; pistas `schema-comparator[<motor>]`. |
| 12 | `oracle-query-terminator` | Extracción Oracle operativa. |
| 13 | `sqlite-read-only-open` | SQLite en solo lectura; ruta inexistente es error. |
| 14 | `consolidation-sqlserver-only` | Consolidación limitada a SQL Server. |
| 15 | `sp-repair-master-script` | Script maestro de reparación ejecutable y escapado. |
| 16 | `tui-markup-escape` | Identificadores con corchetes mostrados literalmente. |
| 17 | `tui-thread-safety` | Estado de la TUI coherente entre hilos y re-ejecuciones. |
| 18 | `tui-screens-refactor` | Lógica de consolidación en módulo puro; bucle de rutinas único. |

## Tanda del generador de scripts — cerrada (PR #22)

Objetivo: que los scripts de consolidación cubran los casos comunes, nunca
se apliquen a medias y tengan control de rollback. Cada cambio se probó
contra SQL Server 2022 real (fixture Docker en `tests/integration/conftest.py`).

| # | Cambio IDD | Qué resolvió |
|---|---|---|
| 1 | `sqlserver-script-live-tests` | Pruebas que ejecutan los scripts con `sqlcmd` contra SQL Server en Docker. |
| 2 | `script-safety-envelope` | Guarda `DB_NAME()` + `NOEXEC`, `XACT_ABORT`, `LOCK_TIMEOUT`, `THROW`, literales `N''`, BOM; sin base en la cadena, error. |
| 3 | `script-preflight-state` | Comprobación previa contra lo comparado, pasos ya aplicados omitidos, verificación antes del `COMMIT`. |
| 4 | `script-data-loss-guard` | Sin relleno inventado; abortar con conteo ante NULL o pérdida salvo decisión explícita en la TUI. |
| 5 | `alter-column-dependencies` | Índices, PK/UNIQUE, FK, estadísticas, DEFAULT y CHECK recreados al cambiar una columna; SQL Server 2016+. |
| 6 | `sqlserver-column-attributes` | Extracción y aplicación de DEFAULT, IDENTITY, collation explícita y precisión de fecha/hora. |
| 7 | `drop-backups` | Respaldo en `bdiff_respaldo` antes de cada `DROP` y diario de dependencias eliminadas. |
| 8 | `undo-scripts` | `<perfil>.deshacer.sql` que revierte cada paso con datos, índices y restricciones. |

## Rediseño de la TUI — en curso

Objetivo: una TUI fácil de entender y de manejar. Símbolos Unicode sin emojis,
tuteo neutro, `Esc` cierra lo abierto y `q` confirma la salida (el estilo
común vive en `tui/theme.py` y `tui/modals.py`).

| # | Cambio IDD | Estado |
|---|---|---|
| 1 | `tui-main-redesign`: resumen por tipo, árbol y detalle, cajón de exclusiones y registro, ayuda | Hecho (PR #24) |
| 2 | `tui-consolidation-redesign`: formulario de decisiones con resumen y avance por tabla; incluye las propuestas 1 y 2 (confirmación de `DROP` con `ConfirmModal`, destinos limitados) | Hecho |
| 3 | `tui-routines-redesign`: pantalla de rutinas (`v`) con resumen, detalle por rutina, `ConfirmModal` con el conteo real de rutinas recompilables y ayuda `?` | Hecho |

## Próximas propuestas — por este orden

Las propuestas 1 y 2 ya se hicieron con `tui-consolidation-redesign`; queda la
tercera.

| # | Cambio | Estado |
|---|---|---|
| 1 | Confirmación en la TUI para `DROP` en la consolidación | Hecho |
| 2 | Destinos de una discrepancia de columna limitados a los perfiles que la tienen | Hecho |
| 3 | Extracción de PK, FK e índices (SQL Server primero, luego el resto) | Pendiente. Es lo que más amplía la comparación y la que más trabajo lleva; la comparación ya es correcta (`advanced-object-equality`), falta extraerlos. |

## Siguiente — funcionalidad

| Prioridad | Cambio | Notas |
|---|---|---|
| P1 | Conteos homogéneos entre formatos de reporte | Los atributos (DEFAULT, IDENTITY, collation, precisión) ya se muestran; falta igualar conteos. |
| P2 | Exclusión de esquemas Oracle por `ORACLE_MAINTAINED` en lugar de una lista fija | Hoy faltan owners de sistema (DVSYS, ORDSYS…). |
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
