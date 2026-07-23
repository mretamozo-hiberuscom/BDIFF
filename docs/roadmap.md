# Roadmap — BDIFF (Schema Drift Comparator)

Este documento refleja el estado real del proyecto y el plan evolutivo hacia una arquitectura modular y multi-motor de bases de datos, detallado en [docs/architecture/analisis-roadmap-multitarget.md](file:///c:/Users/sn4ke/dev/activos/BDIFF/docs/architecture/analisis-roadmap-multitarget.md).

Para ver el desglose detallado de tareas y OpenSpec Changes por fase, consulta [docs/architecture/roadmap-multitarget-changes.md](file:///c:/Users/sn4ke/dev/activos/BDIFF/docs/architecture/roadmap-multitarget-changes.md).

---

## 🟢 Estado Actual (v0.1 - v0.2 / Completado)

- [x] Configuración de perfiles de conexión (SQL Server, sintaxis ODBC y ADO.NET/SqlClient).
- [x] Extracción de esquemas en vivo (tablas y columnas: nombre, tipo, tamaño/precisión/escala, nullability).
- [x] Motor de comparación N-way (comparación de esquemas basada en unión de objetos baseline).
- [x] Detección de drift (tablas faltantes, columnas faltantes, discrepancias de tipo/tamaño/nullability).
- [x] Reportes exportables (HTML, PDF vía `xhtml2pdf`, Excel `.xlsx` vía `openpyxl`, salida por consola).
- [x] Interfaz TUI interactiva (`textual`) con `--tui`.
- [x] Consolidación interactiva de decisiones y generación de scripts de corrección T-SQL.

---

## 🚀 Versiones Objetivo & Roadmap Multibase de Datos (v0.3 — v1.0)

### Versión 0.3 — Arquitectura Limpia, Provider SQL Server & Config v2
* **`docs-roadmap-and-adrs` (Fase 0):** ADRs iniciales, pruebas de caracterización y golden files para SQL Server.
* **`architecture-layered-domain` (Fase 1.A):** Separación de capas `domain/schema` y `domain/comparison` neutras.
* **`architecture-application-use-cases` (Fase 1.B):** Puertos de aplicación, `CompareProfilesUseCase` y `cli.py` como composition root.
* **`provider-sqlserver-extraction` (Fase 2):** Extracción del proveedor de SQL Server a `infrastructure/providers/sqlserver/`.
* **`config-v2-and-optional-dependencies` (Fase 3):** Configuración `profiles:` v2, drivers como extras opcionales en `pyproject.toml` (`sqlserver`, `postgresql`, etc.) y comandos `bdiff providers doctor`.

### Versión 0.4 — Proveedor PostgreSQL (Completado)
* **`canonical-domain-models-and-capabilities` (Fase 4):** Modelos canónicos `QualifiedName`, `SqlType` y `ProviderCapabilities`.
* **`provider-postgresql` (Fase 5):** [x] Adaptador PostgreSQL con `psycopg`, introspección de catalog/enums/arrays, quoting `"name"` y DDL PostgreSQL.

### Versión 0.5 — Proveedor SQLite
* **`provider-sqlite` (Fase 6):** [x] Adaptador SQLite con `sqlite3`, soporte para `main`/`temp`/attached DBs, type affinity y estrategia de reconstrucción de tablas (`table rebuild`).

### Versión 0.6 — Proveedores MySQL y MariaDB (Completado)
* **`provider-mysql-mariadb` (Fase 7):** [x] Adaptadores independientes para `mysql` y `mariadb` compartiendo utilidades bajo `mysql_family`, manejo de `AUTO_INCREMENT`, `UNSIGNED`, `ENUM`, `SET` y backticks.

### Versión 0.7 — Proveedor Oracle (Completado)
* **`provider-oracle` (Fase 8):** [x] Adaptador Oracle con `python-oracledb` (Thin mode), introspección `ALL_TAB_COLUMNS`, mapeo de `OWNER`, mayúsculas y tipos nativos (`NUMBER`, `VARCHAR2`).

### Versión 0.8 — Objetos de Esquema Avanzados (Completado)
* **`advanced-schema-objects-comparison` (Fase 9):** [x] Inspección y comparación de Primary Keys, Foreign Keys, Unique Constraints, Check Constraints e Índices.

### Versión 0.9 — Comparación Semántica Cross-Provider (Completado)
* **`cross-provider-semantic-comparison` (Fase 10):** [x] Modo `semantic` opt-in para comparación heterogénea entre distintos motores (ej. SQL Server vs PostgreSQL), matriz de equivalencias y reportes de portabilidad.

### Versión 1.0 — Estabilización & API Pública (Completado)
* [x] API de proveedores estable, suite completa de pruebas de contrato en CI y documentación consolidada.
