-- Script de corrección para la base de datos del perfil: profileA
-- Generado por BDIFF el 2026-07-14 12:00:00
--
-- Todos los cambios van en una única transacción: primero se comprueba
-- que cada objeto sigue como se comparó, después se aplican los cambios
-- y se verifican antes de confirmar. Ante cualquier error se deshacen
-- completos y la base queda como estaba.
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

    DECLARE @skip_1 bit = 0;

    -- 1. Comprobaciones previas: todavia no se ha cambiado nada.
    -- Paso 1/1: agregar la columna [dbo].[users].[age]
    IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'users' AND COLUMN_NAME = N'age')
    BEGIN
        IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'users' AND COLUMN_NAME = N'age' AND DATA_TYPE = N'int' AND IS_NULLABLE = 'YES')
            SET @skip_1 = 1;
        ELSE
            THROW 50001, N'Paso 1/1: agregar la columna [dbo].[users].[age]: la columna ya existe con otra definicion; vuelve a comparar antes de aplicar.', 1;
    END
    ELSE IF NOT (OBJECT_ID(N'[dbo].[users]', N'U') IS NOT NULL)
        THROW 50001, N'Paso 1/1: agregar la columna [dbo].[users].[age]: la tabla [dbo].[users] no existe.', 1;

    -- 2. Cambios.
    IF @skip_1 = 0
    BEGIN
        PRINT N'Paso 1/1: agregar la columna [dbo].[users].[age]';
        ALTER TABLE [dbo].[users] ADD [age] int NULL;
        PRINT N'Columna [age] agregada con exito a [dbo].[users].';
    END
    ELSE
        PRINT N'Paso 1/1: agregar la columna [dbo].[users].[age] ya aplicado; se omite.';

    -- 3. Verificacion final antes de confirmar.
    IF NOT (EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'users' AND COLUMN_NAME = N'age' AND DATA_TYPE = N'int' AND IS_NULLABLE = 'YES'))
        THROW 50002, N'Paso 1/1: agregar la columna [dbo].[users].[age]: no quedo aplicado; se deshace todo.', 1;

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
