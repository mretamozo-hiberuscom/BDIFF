# 0008. Claves con nombre autogenerado y columnas canónicas

- Status: accepted
- Date: 2026-10-22
- Evidence: src/schema_comparator/infrastructure/providers/sqlserver/introspector.py:19, src/schema_comparator/compare/identity.py:83, src/schema_comparator/compare/engine.py:464

## Context and drivers

La ADR 0007 normaliza la identidad de tablas, columnas y rutinas, y deja
como límite conocido que las columnas de PK, FK e índices no se normalizan.
Mientras ningún proveedor extraía esos objetos el límite no se notaba. Al
extraerlos de SQL Server aparecen dos fuentes de falsa deriva: SQL Server
nombra por sí mismo las restricciones sin nombre (`PK__Users__3213E83F...`,
`UQ__...`, `FK__...`) con un sufijo que difiere entre bases, y una columna
`Id` frente a `id` figuraría como otra dentro de una PK o un índice. El
2026-10-21 se decidió que el nombre de PK, FK e índice cuenta en la igualdad;
el 2026-10-22 el usuario decidió exceptuar los nombres autogenerados.

Drivers: `scenario:no-false-drift`, `constraint:windows-primary`.

## Options considered
1. Comparar siempre el nombre: respeta la decisión del 2026-10-21, pero cada
   restricción sin nombre explícito sería una discrepancia entre bases.
2. Nombrar por estructura las restricciones autogeneradas y canonicalizar
   las columnas: sin falsos positivos, a costa de no ver un cambio de nombre
   que nadie eligió.
3. Ignorar siempre el nombre de las restricciones: simple, pero oculta
   renombres que alguien sí escribió.

## Decision
Se elige la opción 2, que amplía la ADR 0007 sin cambiar sus reglas:
- Una restricción que SQL Server nombró por sí mismo (`is_system_named`) se
  registra con un nombre derivado de su estructura: `PK (autogenerado)`,
  `FK (columnas) -> esquema.tabla (columnas)` y `UQ (columnas)`. Dos
  restricciones con la misma estructura en una tabla se distinguen con
  ` #2`, ` #3`. Los nombres explícitos siguen contando en la igualdad.
- Las columnas de PK, FK e índices, y la tabla y columnas que una FK
  referencia, se escriben con los nombres canónicos de tablas y columnas
  (primer perfil, sin distinguir mayúsculas), como fija la ADR 0007.
- PK, FK e índices solo se comparan entre perfiles cuyo proveedor los
  extrae (`SchemaFeature.KEYS`); un proveedor que no los extrae no genera
  faltantes.

## Consequences
- Más fácil: comparar bases SQL Server creadas por separado sin ruido por
  nombres generados ni por mayúsculas.
- Más difícil: dos restricciones distintas con la misma estructura se
  numeran por el orden en que las devuelve el catálogo.
- Límite conocido: la expresión de filtro de un índice se compara tal como
  la devuelve SQL Server, con las mayúsculas de sus columnas.
- Solo se extraen índices rowstore; columnstore, XML y espaciales no.
- Los proveedores distintos de SQL Server no extraen PK, FK ni índices aún.

## Fitness function
- Un test construye dos snapshots con `Id`/`id` en PK, FK e índice y espera
  cero hallazgos, y otro con un proveedor sin `KEYS` frente a uno con claves.
- Check: `python -m pytest -q tests/unit/compare/test_identity_normalization.py tests/unit/compare/test_cross_provider_semantic.py`

## Review trigger
Falsos emparejamientos reportados, o un segundo proveedor que extraiga
restricciones con nombre autogenerado propio (PostgreSQL, Oracle).
