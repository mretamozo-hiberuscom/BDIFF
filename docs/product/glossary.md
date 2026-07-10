# Glossary — SQL Server Schema Comparator

| Term | Meaning in this project |
|---|---|
| Microservice database | One SQL Server database belonging to a single microservice; the unit being compared. |
| Schema drift | Any difference in table/column structure between two or more microservice databases that are expected to share structure. |
| Schema snapshot | The extracted metadata (tables, columns, types, etc.) captured from one database at one point in time. |
| Baseline database | Not a fixed database — the comparator treats the union of all objects seen across all configured databases as the reference set; any database missing an object relative to that union is flagged. |
| Missing table/column | An object (table or column) present in at least one configured database but absent in another. |
| Mismatch | A column present under the same name in two or more databases but differing in data type, size/precision/scale, or nullability. |
| Likely rename | A heuristic match suggesting a column in one database and a differently-named column in another database represent the same business field. |
| Discovery method | How the tool obtains schema metadata: live DB connection (v1) vs. exported DDL/snapshot files (later/optional). |
| Connection profile | One entry in the local config describing how to reach one microservice's database (server, database name, auth method, driver options). |
| Drift report | The generated output (HTML primary, console summary, optional CSV/Excel) presenting comparison results. |
