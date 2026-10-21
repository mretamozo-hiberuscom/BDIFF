# Alcance funcional — BDIFF

> Estado verificado contra el código v1.2.5 el 2026-10-21. "Parcial" y
> "Roto" remiten al backlog de `docs/roadmap.md`.

## Actores

| Actor | Qué hace |
|---|---|
| Desarrollador (operador) | Mantiene `config.local.yaml`, ejecuta el CLI o la TUI, decide la consolidación y ejecuta los scripts por su cuenta. |
| Lector de reportes | Abre HTML, PDF o Excel generados; no ejecuta BDIFF. |
| Bases comparadas | Sistemas externos de solo lectura salvo la recompilación confirmada (ADR 0006). |

## Recorridos

**Detectar deriva (CLI)**

- Dado un `config.local.yaml` con dos o más perfiles,
- cuando el desarrollador ejecuta `python run.py --config config.local.yaml [--profiles a b] [--exclude-tables X] [--exclude-routines Y]`,
- entonces BDIFF extrae cada esquema, compara, imprime el resumen y escribe
  HTML, PDF y Excel en `reportes/<timestamp>/`. Sale con 0 sin deriva, 1
  con deriva o fallos de validación y 2 ante errores.

**Explorar y consolidar (TUI)**

- Con `--tui` en una terminal interactiva, el desarrollador navega los
  hallazgos, filtra, re-ejecuta (`r`), genera reportes (`g`), decide la
  consolidación (`d`) y obtiene scripts T-SQL e `impact_report.md` en
  `scripts-db/<timestamp>/`.

**Validar y reparar rutinas (SQL Server)**

- `--validate-routines` (solo lectura) o la pantalla `v` de la TUI listan
  rutinas con dependencias rotas y generan scripts de reparación.
- `--refresh-modules --yes` o la confirmación modal de la TUI recompilan
  metadatos con `sp_refreshsqlmodule` (ADR 0006).

## Capacidades

| # | Capacidad | Estado |
|---|---|---|
| 1 | Config YAML v2 (`profiles:` con `provider`, `connection_string`, `options`) y v1 (`databases:`) | Hecho |
| 2 | Cadenas ODBC y ADO.NET para SQL Server | Hecho |
| 3 | Extracción de tablas y columnas — SQL Server | Parcial: sin default, identity, collation ni precisión de fecha |
| 4 | Extracción — PostgreSQL, MySQL, MariaDB, SQLite | Parcial: MySQL pierde parámetros de tipo; SQLite crea la BD si la ruta no existe |
| 5 | Extracción — Oracle | Roto: la consulta termina en `;` |
| 6 | Extracción de procedimientos (SQL Server) | Hecho |
| 7 | Comparación N-way de tablas, columnas y procedimientos | Hecho para un mismo motor |
| 8 | Comparación de PK, FK e índices | Roto: falsos positivos; ningún proveedor los extrae |
| 9 | Emparejamiento por identidad normalizada (esquema MySQL/Oracle, mayúsculas) | Pendiente (decidido 2026-10-21) |
| 10 | Comparación semántica entre motores | Parcial: existe en el motor, sin acceso desde CLI ni TUI |
| 11 | Reportes consola, HTML, PDF, Excel | Hecho, con conteos no homogéneos entre formatos |
| 12 | TUI de hallazgos, consolidación y rutinas | Hecho, con fallos de concurrencia y de markup |
| 13 | Scripts T-SQL de consolidación | Hecho solo para SQL Server; se restringe a ese motor (decisión 2026-10-21) |
| 14 | Validación y recompilación de rutinas | Hecho; el script maestro de reparación está roto |
| 15 | Detección de renombres | No implementado |
| 16 | Export CSV | No implementado |
| 17 | Descubrimiento desde DDL exportado (offline) | No implementado |

## Exclusiones

- Ejecutar DDL generado (ADR 0005).
- Gestión de conexiones dentro de la TUI.
- Comparación de datos.
- Scripts de consolidación para motores distintos de SQL Server hasta que
  sus renderers estén corregidos.

## Especificaciones

Los specs de `openspec/specs/` describen el producto de julio de 2026 y
están desfasados (ver divergencias en
`docs/architecture/component-map.yaml`). Hasta que se sincronicen, la
referencia es este documento, el baseline técnico y los tests.
