-- Script de corrección para la base de datos del perfil: profileA
-- Generado por BDIFF el 2026-07-14 12:00:00
--
-- Todos los cambios van en una única transacción: ante cualquier error
-- se deshacen completos y la base queda como estaba.
-- Ejecución:
--   sqlcmd -S <servidor> -E -b -i "<este archivo>.sql"
--     (-b detiene sqlcmd en el primer error y devuelve código de salida <> 0)
--   SSMS: abrir el archivo y ejecutarlo completo (F5).
-- Si la base activa no es la esperada, el script no ejecuta nada.

USE [real_db_a];
GO

IF DB_NAME() <> N'real_db_a'
BEGIN
    RAISERROR(N'La base activa no es %s; no se aplica ningun cambio.', 16, 1, N'real_db_a');
    SET NOEXEC ON;
END
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET LOCK_TIMEOUT 30000;
SET NUMERIC_ROUNDABORT OFF;
SET ANSI_PADDING, ANSI_WARNINGS, CONCAT_NULL_YIELDS_NULL, ARITHABORT, QUOTED_IDENTIFIER, ANSI_NULLS ON;
GO

BEGIN TRY
    BEGIN TRANSACTION;
    IF NOT EXISTS (
        SELECT 1 
        FROM sys.columns c
        JOIN sys.objects o ON c.object_id = o.object_id
        JOIN sys.schemas s ON o.schema_id = s.schema_id
        WHERE s.name = N'dbo' AND o.name = N'users' AND c.name = N'age'
    )
    BEGIN
        ALTER TABLE [dbo].[users] ADD [age] int NULL;
        PRINT N'Columna [age] agregada con exito a [dbo].[users].';
    END

    COMMIT TRANSACTION;
    PRINT N'Transaccion confirmada con exito.';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    PRINT N'Transaccion abortada debido a un error; no se aplico ningun cambio.';
    THROW;
END CATCH;
GO

SET NOEXEC OFF;
GO
