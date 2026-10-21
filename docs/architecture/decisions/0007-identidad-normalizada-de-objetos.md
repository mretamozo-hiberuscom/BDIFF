# 0007. Identidad normalizada de objetos entre bases

- Status: accepted
- Date: 2026-10-21
- Evidence: src/schema_comparator/compare/engine.py:45, src/schema_comparator/infrastructure/providers/mysql_family/introspector.py:30

## Context and drivers

El motor emparejaba tablas, columnas y rutinas por `(esquema, nombre)`
exactos. En MySQL/MariaDB el esquema es la propia base y en Oracle el owner,
así que comparar `app_dev` con `app_prod` daba todas las tablas como
faltantes en ambos lados; y `dbo.Users` frente a `dbo.users` (iguales para
SQL Server con collation insensible) se reportaban como objetos distintos.
El usuario decidió el 2026-10-21 normalizar la identidad y mostrar todas
las variantes de nombre en los reportes.

Drivers: `scenario:no-false-drift`, `constraint:windows-primary` (bases
SQL Server con collation insensible a mayúsculas).

## Options considered
1. Identidad exacta (estado anterior): sin falsos emparejamientos, pero
   falsos faltantes masivos entre bases MySQL/Oracle y por mayúsculas.
2. Identidad normalizada en una pasada previa a la comparación: el motor
   sigue comparando nombres exactos sobre snapshots con nombres canónicos;
   las variantes viajan en los hallazgos para los reportes.
3. Mapa de esquemas configurable por perfil (`options.schema_alias`): sin
   reglas implícitas, pero obliga a configurar cada perfil.

## Decision
Se elige la opción 2. Antes de comparar, cada objeto recibe una clave:
- el esquema cuenta como vacío cuando coincide con el esquema por defecto
  del snapshot (MySQL/MariaDB: el único esquema cuando la conexión apunta a
  una base; Oracle: el esquema actual de la sesión); si no, se compara sin
  distinguir mayúsculas;
- el nombre de tabla, columna o rutina se compara sin distinguir mayúsculas;
- si dentro de una misma base dos objetos colisionan con esa clave, solo
  esos se emparejan con su nombre exacto en todas las bases.
El nombre canónico es el del primer perfil, en orden alfabético, que tiene
el objeto; los scripts generados lo usan. Cuando los nombres originales
difieren entre perfiles, el hallazgo lleva todas las variantes y los
reportes las muestran.

## Consequences
- Más fácil: comparar bases del mismo motor con nombres de base u owner
  distintos, y bases SQL Server con diferencias solo de mayúsculas.
- Más difícil: los scripts usan el nombre canónico, que en una base con
  collation sensible a mayúsculas puede no existir con esa grafía.
- Límite conocido: si un owner Oracle no predeterminado de un perfil se
  llama igual que el owner predeterminado de otro, sus tablas homónimas
  pueden emparejarse entre sí.
- Las columnas de PK, FK e índices no se normalizan todavía.

## Fitness function
- Un test compara dos snapshots MySQL con distinto nombre de base y las
  mismas tablas, y otro con `Users`/`users`, y espera cero faltantes.
- Check: `python -m pytest -q tests/unit/compare/test_identity_normalization.py`

## Review trigger
Falsos emparejamientos reportados por usuarios, o necesidad de comparar
esquemas no predeterminados con nombres distintos (opción 3).
