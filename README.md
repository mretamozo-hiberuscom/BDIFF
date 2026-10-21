# BDIFF — Schema Comparator

Compara el esquema de varias bases de datos a la vez y detecta la deriva
entre ellas: tablas y columnas que faltan, diferencias de tipo, tamaño o
nulabilidad, y procedimientos almacenados distintos. Genera un resumen de
consola y reportes HTML, PDF y Excel; con `--tui` abre un navegador
interactivo de hallazgos que además genera scripts T-SQL de consolidación.

- **Plataforma principal:** Windows (Linux soportado).
- **Motores:** SQL Server (principal), PostgreSQL, MySQL, MariaDB, Oracle
  y SQLite.
- **Nunca ejecuta DDL** contra tus bases: los scripts los revisas y
  ejecutas tú. La única escritura es la recompilación de rutinas de SQL
  Server, siempre con confirmación explícita (ver
  `docs/architecture/decisions/0006-*`).

## Requisitos

- Python 3.11 o superior.
- Para SQL Server: Microsoft ODBC Driver 17 o 18 for SQL Server. Los
  scripts de corrección generados requieren SQL Server 2016 o posterior.
- Para otros motores: su driver Python, instalable como extra (ver abajo).

## Inicio rápido (Windows)

```powershell
copy config.example.yaml config.local.yaml   # completa tus cadenas reales
py run.py --config config.local.yaml
py run.py --config config.local.yaml --tui
```

En Linux, `python3 run.py ...`. La primera vez `run.py` crea `.venv`,
instala el proyecto y relanza el CLI; las siguientes arranca directo. Todos
los argumentos se reenvían al CLI y el código de salida se propaga.
`config.local.yaml` está en `.gitignore`: nunca se commitea.

## Configuración

Formato v2 (recomendado):

```yaml
profiles:
  polizas-dev:
    provider: sqlserver
    connection_string: "Data Source=srv;Initial Catalog=PolizasDB;Integrated Security=True;TrustServerCertificate=True;"
  polizas-pg:
    provider: postgresql
    connection_string: "host=localhost dbname=polizas user=app password=***"
  local:
    provider: sqlite
    connection_string: "./data/local.db"
```

El formato v1 (`databases:` nombre → cadena SQL Server) sigue aceptándose.
Para SQL Server se admiten cadenas ODBC y ADO.NET (copiadas de
`appsettings.json`). Si la cadena no indica `Driver=`, BDIFF usa el ODBC
Driver 17 instalado, o el 18 si el 17 no está; el 18 cifra por defecto, así
que con certificados autofirmados añade `TrustServerCertificate=yes`. Un
`Driver=` explícito nunca se cambia. El nombre del perfil es lo único que aparece en
reportes y mensajes.

## Opciones del CLI

| Opción | Efecto |
|---|---|
| `--config RUTA` | YAML de perfiles (obligatoria). |
| `--profiles A B ...` | Compara solo esos perfiles, sin distinguir mayúsculas (por defecto, todos). Un nombre desconocido detiene la ejecución. |
| `--tui` | Navegador interactivo (requiere terminal interactiva). |
| `--exclude-tables TXT ...` | Excluye tablas cuyo nombre contenga el texto. |
| `--exclude-routines TXT ...` | Excluye rutinas cuyo nombre contenga el texto. |
| `--validate-routines` | Valida dependencias de rutinas SQL Server (solo lectura). |
| `--refresh-modules --yes` | Recompila metadatos con `sp_refreshsqlmodule` (escribe en la BD). `--verify-sps` es un alias heredado. |

Códigos de salida: `0` sin diferencias, `1` con diferencias o fallos de
validación, `2` error o uso incorrecto (p. ej. `--refresh-modules` sin
`--yes`, que se rechaza antes de conectar).

## Salidas

- `reportes/<AAAAMMDD_HHMMSS>/schema-diff-report-<ts>.{html,pdf,xlsx}`.
- Desde la TUI: `scripts-db/<ts>/` con un `.sql` por perfil e
  `impact_report.md` (solo SQL Server). Cada script aplica todos sus cambios
  en una transacción: comprueba antes que cada objeto sigue como se comparó y
  que no se pierden datos, recrea índices y restricciones afectados y, ante
  cualquier error, lo deshace todo. Antes de cada eliminación copia los datos
  al esquema `bdiff_respaldo`, que BDIFF nunca borra. Ejecútalo con
  `sqlcmd -b -i <archivo>.sql` o completo desde SSMS. Junto a cada script,
  `<perfil>.deshacer.sql` revierte sus pasos en orden inverso, recuperando
  tablas, columnas, índices, restricciones y datos desde esos respaldos.

## Instalación manual

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -e ".[all]"          # o .[postgresql], .[mysql], .[oracle]...
python -m schema_comparator.cli --config config.local.yaml
```

## Desarrollo

```powershell
pip install -e ".[dev,all]"
python -m pytest -q
python -m ruff check . ; python -m ruff format --check .
```

En Linux, los tests de SQL Server necesitan el gestor ODBC del sistema
(`unixodbc`). Arquitectura, decisiones y roadmap: `docs/`.
