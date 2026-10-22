# sqlserver-keys-and-indexes

## Intent and acceptance

Extraer PK, FK e índices de SQL Server a TableSnapshot para que la comparación ya existente los detecte

Acceptance: Dos bases SQL Server que difieren en una PK, FK o índice producen el hallazgo correspondiente; si son iguales no hay falsos positivos, incluidas las restricciones con nombre autogenerado

## Plan

1. Extracción (SQL Server): `PRIMARY_KEYS_QUERY_SQL`, `FOREIGN_KEYS_QUERY_SQL` e `INDEXES_QUERY_SQL` en `introspector.py`, ejecutadas por `provider.py`; `IndexSnapshot` gana `is_clustered`, `descending_columns`, `included_columns` y `filter_expression`.
2. Identidad: `compare/identity.py` canonicaliza las columnas de PK, FK e índices y la tabla referenciada, como ya hacía con tablas y columnas.
3. Presentación: `report/keys.py` da una sola redacción a PK, FK e índices para consola, HTML, Excel, PDF y TUI.
4. Alcance entre motores: `SchemaFeature.KEYS`; el motor solo compara claves entre perfiles cuyo proveedor las extrae.

## Decisions

- Índice igual = columnas con orden y DESC, unicidad, clustered, INCLUDE y filtro. FK igual = columnas, tabla y columnas referenciadas, ON DELETE y ON UPDATE; el estado (deshabilitada/NOCHECK) no cuenta. Decidido por el usuario.
- Una restricción con nombre autogenerado por SQL Server (`is_system_named`) se nombra por su estructura (`PK (autogenerado)`, `FK (cols) -> esquema.tabla (cols)`, `UQ (cols)`); los nombres explícitos siguen contando. Decidido por el usuario; matiza la decisión del 2026-10-21 (el nombre cuenta en la igualdad).
- Si una consulta de claves falla, la extracción aborta con el error traducido; nunca se compara con claves ausentes. Decidido por el usuario.
- Solo se extraen índices rowstore (clustered y nonclustered); columnstore, XML y espaciales quedan fuera.
- Los hallazgos de PK, FK e índices son informativos: no hay script de consolidación para ellos.

## Evidence

<!-- ospec:evidence:start -->
- ev-1: check-run for checks-pass (2026-10-22T11:19:05.189Z)
- ev-2: check-run for checks-pass (2026-10-22T11:23:57.879Z)
- ev-3: adr-impact-declaration for adr-impact-declaration (2026-10-22T11:23:57.879Z)
- ev-4: living-doc-current for living-doc (2026-10-22T11:24:04.975Z)
<!-- ospec:evidence:end -->
