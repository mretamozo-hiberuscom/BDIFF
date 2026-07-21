-- Script de corrección para la base de datos del perfil: profileB
-- Generado por BDIFF el 2026-07-14 12:00:00

USE [real_db_b];
GO

SET NUMERIC_ROUNDABORT OFF;
SET ANSI_PADDING, ANSI_WARNINGS, CONCAT_NULL_YIELDS_NULL, ARITHABORT, QUOTED_IDENTIFIER, ANSI_NULLS ON;
GO

BEGIN TRANSACTION;
BEGIN TRY
    IF NOT EXISTS (
        SELECT 1
        FROM sys.objects o
        JOIN sys.schemas s ON o.schema_id = s.schema_id
        WHERE s.name = 'dbo' AND o.name = 'products' AND o.type = 'U'
    )
    BEGIN
        CREATE TABLE [dbo].[products] (
        [id] int NOT NULL,
        [name] varchar(150) NULL
        );
        PRINT 'Tabla [dbo].[products] creada con exito.';
    END

    COMMIT TRANSACTION;
    PRINT 'Transaccion confirmada con exito.';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
    BEGIN
        ROLLBACK TRANSACTION;
        PRINT 'Transaccion abortada debido a un error.';
    END
    DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
    DECLARE @ErrorSeverity INT = ERROR_SEVERITY();
    DECLARE @ErrorState INT = ERROR_STATE();
    RAISERROR(@ErrorMessage, @ErrorSeverity, @ErrorState);
END CATCH;
GO
