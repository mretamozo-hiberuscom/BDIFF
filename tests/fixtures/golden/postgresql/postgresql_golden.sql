-- PostgreSQL Golden Fixture DDL

BEGIN;

CREATE TABLE IF NOT EXISTS "public"."users" (
    "id" integer NOT NULL,
    "username" varchar(50) NOT NULL,
    "email" varchar(255) NOT NULL,
    "is_active" boolean NOT NULL,
    "created_at" timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS "public"."orders" (
    "id" bigint NOT NULL,
    "user_id" integer NOT NULL,
    "total" numeric(12, 2) NOT NULL,
    "status" varchar(20) NOT NULL
);

ALTER TABLE "public"."users" ADD COLUMN IF NOT EXISTS "phone" varchar(20) NULL;

ALTER TABLE "public"."orders" ALTER COLUMN "status" TYPE varchar(50) USING "status"::varchar;

COMMIT;
