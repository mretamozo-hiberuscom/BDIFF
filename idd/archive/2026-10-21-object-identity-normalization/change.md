# object-identity-normalization

## Intent and acceptance

Emparejar tablas, columnas y rutinas entre bases sin distinguir mayúsculas y normalizando el esquema que es la propia base (MySQL/MariaDB) o el owner por defecto (Oracle); hoy app_dev vs app_prod da todas las tablas como faltantes

Acceptance: Comparar dos bases MySQL u Oracle con las mismas tablas en esquemas/owners distintos no produce faltantes; dbo.Users y dbo.users se emparejan; los reportes muestran el nombre original

## Plan

1. Dominio y motor: `SchemaSnapshot.default_schema`; `compare/identity.py`
   reescribe los snapshots con nombres canónicos antes de comparar; los
   hallazgos llevan `object_variants`/`column_variants`; helpers
   `object_label`/`column_label`.
2. Proveedores: MySQL/MariaDB declaran su esquema por defecto cuando el
   snapshot tiene un solo esquema; Oracle consulta el esquema de la sesión.
3. Presentación: consola, HTML, Excel y TUI muestran todas las grafías.

## Decisions

### Decision: Normalizar antes de comparar en lugar de reescribir el motor

Kind: dc

La identidad se resuelve en una pasada previa que renombra los objetos al
nombre canónico; el motor sigue emparejando nombres exactos. Así no cambian
las ocho evaluaciones del motor ni la consolidación, que usa el nombre
canónico para el T-SQL.

### Decision: Colisiones resueltas en todas las bases

Kind: dc

Si una clave sin mayúsculas colisiona en cualquier base, esa clave pasa a
emparejarse con el nombre exacto en todas las bases; si no, la tabla
exacta de una base no se emparejaría con la homónima no ambigua de otra.

## Evidence

<!-- ospec:evidence:start -->
- ev-1: check-run for checks-pass (2026-10-21T11:05:20.750Z)
- ev-2: check-run for checks-pass (2026-10-21T11:05:39.913Z)
- ev-3: adr-impact-declaration for adr-impact-declaration (2026-10-21T11:05:39.913Z)
- ev-4: check-run for checks-pass (2026-10-21T11:06:01.640Z)
- ev-5: living-doc-current for living-doc (2026-10-21T11:06:01.696Z)
<!-- ospec:evidence:end -->
