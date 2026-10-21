"""SQL Server database provider package.

Submodules are imported explicitly (`...sqlserver.provider`, `.connection`)
so importing a driver-free one, such as `profile_parser`, never loads
pyodbc (ADR 0002).
"""
