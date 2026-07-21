-- Script de corrección para la base de datos del perfil: profileA
-- Generado por BDIFF el 2026-07-14 12:00:00

USE [real_db_a];
GO

SET NUMERIC_ROUNDABORT OFF;
SET ANSI_PADDING, ANSI_WARNINGS, CONCAT_NULL_YIELDS_NULL, ARITHABORT, QUOTED_IDENTIFIER, ANSI_NULLS ON;
GO

BEGIN TRANSACTION;
BEGIN TRY
    IF NOT EXISTS (
        SELECT 1 
        FROM sys.columns c
        JOIN sys.objects o ON c.object_id = o.object_id
        JOIN sys.schemas s ON o.schema_id = s.schema_id
        WHERE s.name = 'dbo' AND o.name = 'users' AND c.name = 'age'
    )
    BEGIN
        ALTER TABLE [dbo].[users] ADD [age] int NULL;
        PRINT 'Columna [age] agregada con exito a [dbo].[users].';
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
