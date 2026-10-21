-- Script de corrección para la base de datos del perfil: profileB
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

USE [real_db_b];
GO

IF DB_NAME() <> N'real_db_b'
BEGIN
    RAISERROR(N'La base activa no es %s; no se aplica ningun cambio.', 16, 1, N'real_db_b');
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
    -- Paso 1/1: crear la tabla [dbo].[products]
    IF OBJECT_ID(N'[dbo].[products]', N'U') IS NOT NULL
    BEGIN
        IF OBJECT_ID(N'[dbo].[products]', N'U') IS NOT NULL
        AND (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'products') = 2
        AND EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'products' AND COLUMN_NAME = N'id' AND DATA_TYPE = N'int' AND IS_NULLABLE = 'NO' AND COLUMN_DEFAULT IS NULL AND COLUMNPROPERTY(OBJECT_ID(QUOTENAME(TABLE_SCHEMA) + N'.' + QUOTENAME(TABLE_NAME)), COLUMN_NAME, 'IsIdentity') = 0)
        AND EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'products' AND COLUMN_NAME = N'name' AND DATA_TYPE = N'varchar' AND IS_NULLABLE = 'YES' AND CHARACTER_MAXIMUM_LENGTH = 150 AND COLLATION_NAME = CONVERT(nvarchar(128), DATABASEPROPERTYEX(DB_NAME(), 'Collation')) AND COLUMN_DEFAULT IS NULL AND COLUMNPROPERTY(OBJECT_ID(QUOTENAME(TABLE_SCHEMA) + N'.' + QUOTENAME(TABLE_NAME)), COLUMN_NAME, 'IsIdentity') = 0)
            SET @skip_1 = 1;
        ELSE
            THROW 50001, N'Paso 1/1: crear la tabla [dbo].[products]: la tabla ya existe con otra definicion; vuelve a comparar antes de aplicar.', 1;
    END

    -- 2. Cambios.
    IF @skip_1 = 0
    BEGIN
        PRINT N'Paso 1/1: crear la tabla [dbo].[products]';
        CREATE TABLE [dbo].[products] (
            [id] int NOT NULL,
            [name] varchar(150) NULL
        );
        PRINT N'Tabla [dbo].[products] creada con exito.';
    END
    ELSE
        PRINT N'Paso 1/1: crear la tabla [dbo].[products] ya aplicado; se omite.';

    -- 3. Verificacion final antes de confirmar.
    IF NOT (OBJECT_ID(N'[dbo].[products]', N'U') IS NOT NULL
        AND (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'products') = 2
        AND EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'products' AND COLUMN_NAME = N'id' AND DATA_TYPE = N'int' AND IS_NULLABLE = 'NO' AND COLUMN_DEFAULT IS NULL AND COLUMNPROPERTY(OBJECT_ID(QUOTENAME(TABLE_SCHEMA) + N'.' + QUOTENAME(TABLE_NAME)), COLUMN_NAME, 'IsIdentity') = 0)
        AND EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'products' AND COLUMN_NAME = N'name' AND DATA_TYPE = N'varchar' AND IS_NULLABLE = 'YES' AND CHARACTER_MAXIMUM_LENGTH = 150 AND COLLATION_NAME = CONVERT(nvarchar(128), DATABASEPROPERTYEX(DB_NAME(), 'Collation')) AND COLUMN_DEFAULT IS NULL AND COLUMNPROPERTY(OBJECT_ID(QUOTENAME(TABLE_SCHEMA) + N'.' + QUOTENAME(TABLE_NAME)), COLUMN_NAME, 'IsIdentity') = 0))
        THROW 50002, N'Paso 1/1: crear la tabla [dbo].[products]: no quedo aplicado; se deshace todo.', 1;

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
