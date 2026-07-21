-- SQLite Golden Fixture DDL

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS "users" (
    "id" INTEGER NOT NULL,
    "username" TEXT(50) NOT NULL,
    "email" TEXT(255) NOT NULL,
    "is_active" INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS "orders" (
    "id" INTEGER NOT NULL,
    "user_id" INTEGER NOT NULL,
    "total" NUMERIC(12, 2) NOT NULL,
    "status" TEXT(20) NOT NULL
);

ALTER TABLE "users" ADD COLUMN "phone" TEXT(20) NULL;

COMMIT;
PRAGMA foreign_keys = ON;
