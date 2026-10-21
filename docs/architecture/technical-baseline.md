# Baseline técnico — BDIFF

> Baseline brownfield revisado el 2026-10-21 contra v1.2.5. Las
> divergencias entre documentación y código, con evidencia `path:línea`,
> viven en `docs/architecture/component-map.yaml`; el backlog que las
> corrige, en `docs/roadmap.md`.

## Contexto y fronteras

| Elemento | Detalle |
|---|---|
| Actores | Desarrollador que ejecuta BDIFF; lectores de reportes. |
| Sistemas externos | Bases comparadas (SQL Server vía ODBC 17/18, PostgreSQL, MySQL, MariaDB, Oracle, archivos SQLite). |
| Entradas | `config.local.yaml` (ignorado por git) y argumentos del CLI. |
| Salidas | Consola; `reportes/<ts>/` (HTML, PDF, Excel); `scripts-db/<ts>/` (T-SQL de consolidación e `impact_report.md`); scripts de reparación de rutinas. Los scripts de consolidación son UTF-8 con BOM, requieren SQL Server 2016+ y aplican todo o nada: comprobaciones previas de estado y datos, cambios con dependencias recreadas y verificación antes del COMMIT. |
| Fuera de alcance | Servidor, web, ejecución de DDL, comparación de datos, gestión de conexiones en la TUI. |

Frontera de confianza: la máquina del desarrollador. Las cadenas de
conexión son secretos que nunca salen hacia logs, mensajes de error ni
reportes; el nombre del perfil es lo único que se muestra.

## Componentes y datos

Arquitectura hexagonal ligera (ADR 0001) en un único proceso:

| Componente | Paquete | Responsabilidad | Datos que posee |
|---|---|---|---|
| Presentación | `cli.py`, `tui/` | Argumentos, TUI Textual, códigos de salida | Ninguno |
| Aplicación | `application/` | Puertos (`DatabaseProvider`…), `CompareProfilesUseCase`, `SchemaExtractionService` | Ninguno |
| Dominio | `domain/` | Snapshots, hallazgos, capacidades, errores base | Modelos inmutables |
| Comparación | `compare/` | Motor N-way, consolidación T-SQL | Ninguno (deriva de snapshots) |
| Configuración | `config/` | Carga YAML v1/v2, `ConnectionProfile` | Perfiles en memoria; el YAML es del usuario |
| Proveedores | `infrastructure/providers/<motor>/` | Conexión, introspección, parser de perfil, renderer DDL, errores | Ninguno |
| Reportes | `report/` | Consola, HTML (Pico.css embebido), PDF, Excel | Archivos de `reportes/` |
| Heredados | `discovery/` | Errores de extracción, filtros y reexport de modelos previos a la ADR 0001 | — |

Nadie escribe en las bases comparadas salvo `sqlserver/sp_validator.py`
para la recompilación confirmada (ADR 0006).

## Integraciones

| Dependencia | Propietario | Protocolo | Modo de fallo |
|---|---|---|---|
| SQL Server | Equipo de cada microservicio | ODBC (`pyodbc`, driver 17/18 de Microsoft) | Driver ausente, timeout, permisos de catálogo → error traducido sin secretos |
| PostgreSQL | Idem | `psycopg` 3 | Igual; sin timeout de conexión |
| MySQL / MariaDB | Idem | `pymysql` | Igual; el mensaje solo lleva el código del driver |
| Oracle | Idem | `python-oracledb` (thin) | Igual; el mensaje solo lleva el código ORA/DPY |
| SQLite | Usuario (archivo) | `sqlite3` (solo lectura) | Ruta inexistente → error de conexión sin mostrar la ruta |

## Escenarios de calidad

| Id | Atributo | Estímulo | Respuesta esperada | Prioridad |
|---|---|---|---|---|
| `windows-first-run` | Portabilidad | Un desarrollador ejecuta `python run.py` en Windows con solo Python y el driver ODBC 17 o 18 | Se provisiona `.venv`, conecta y genera reportes; la consola no falla por codificación | Alta |
| `no-false-drift` | Corrección | Dos bases con estructura idéntica | Cero hallazgos | Alta |
| `secret-safety` | Seguridad | Fallo de conexión o de consulta | El mensaje nombra el perfil y la causa, nunca cadena, host, usuario ni contraseña | Alta |
| `mutation-requires-confirmation` | Seguridad | Petición de recompilar rutinas sin confirmación | BDIFF termina con error antes de abrir conexión | Alta |
| `optional-drivers` | Instalabilidad | Usuario de un solo motor sin los demás drivers | El CLI arranca y compara; solo se pide el driver del motor usado | Media |

No hay medidas numéricas acordadas para ningún escenario.

## Restricciones

| Id | Restricción | Fuente |
|---|---|---|
| `windows-primary` | Windows es la plataforma principal; Linux se soporta para desarrollo y CI | Usuario, 2026-10-21 |
| `no-ddl-execution` | Nunca ejecutar DDL generado | ADR 0005 |
| `local-only` | Sin servidor ni servicio en segundo plano | Brief |
| `secrets-local` | Credenciales solo en config local ignorada por git | Brief |
| `python-311` | Python 3.11 o superior | `pyproject.toml` |

## Estrategia de tests

| Capa | Qué protege | Dónde |
|---|---|---|
| Unitarios | Reglas del motor, filtros, parsers de cadenas, traducción de errores, renderers DDL, formateo de reportes, lógica pura de la TUI | `tests/unit/` |
| Integración | Arranque de `run.py`, escritura de reportes, PDF, flujo de rutinas con dobles de conexión | `tests/integration/` |
| Contrato por proveedor | Consultas reales contra cada motor | Pendiente (roadmap) |
| CI | Matriz Windows + Ubuntu × Python 3.11-3.13 | `.github/workflows/ci.yml` |

Los unitarios no abren red ni bases reales. Sin porcentaje de cobertura
obligatorio.

## Registro tecnológico

| Elección | Implementa | Alternativas | Por qué |
|---|---|---|---|
| Python 3.11+, pip + venv vía `run.py` | Brief (instalación sin fricción) | uv, poetry | No exige herramientas extra en Windows |
| `pyodbc` + driver ODBC de Microsoft | ADR 0002 | `pymssql`, SQLAlchemy | Control directo de la cadena; ODBC viene con Windows |
| `psycopg`, `pymysql`, `oracledb`, `sqlite3` | ADR 0002 | SQLAlchemy | Drivers nativos opcionales por extra |
| Textual | TUI | prompt_toolkit, curses | Widgets de árbol, tablas y pantallas |
| Jinja2 + Pico.css embebido | Reporte HTML | Bootstrap, CDN | Archivo único offline |
| xhtml2pdf | PDF | weasyprint, wkhtmltopdf | Sin binarios del sistema en Windows |
| openpyxl | Excel | xlsxwriter | Lectura y escritura, sin dependencias nativas |
| ruff (config fijada en `pyproject.toml`) | Calidad | flake8, black | Un solo binario rápido |

Fuentes: decisiones originales de 2026-07 (historial abajo) y revisión del
código del 2026-10-21.

## Historial de decisiones del baseline original (2026-07)

| # | Decisión original | Estado 2026-10-21 |
|---|---|---|
| 1 | Driver `pyodbc` directo | Vigente para SQL Server |
| 2 | Cadena de conexión opaca por perfil, con traducción ADO.NET → ODBC al cargar | Vigente; v2 añade `provider` y `options` (ADR 0004) |
| 3 | Descubrimiento por conexión en vivo; DDL exportado diferido | Vigente |
| 4 | HTML principal + PDF; Excel/CSV en v2 | Excel implementado; CSV pendiente |
| 5 | Supuesto de 3-20 bases | Sigue siendo supuesto sin validar |
| 6 | pip + venv | Vigente (`run.py`) |
| 7 | TUI como entrada con gestión de conexiones | Sustituida: el CLI es la entrada y la TUI navega hallazgos |
| 9 | Pico.css embebido | Vigente |
| 10 | YAML local escrito por la TUI | Sustituida: el YAML lo edita el usuario |
| — | "Monolito modular config→connectors→discovery→compare→report" | Sustituida por la ADR 0001 |
| — | "La herramienta nunca escribe en las bases" | Ampliada por la ADR 0006 |
