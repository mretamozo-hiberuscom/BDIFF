# Specification: Advanced Schema Objects Comparison

## Feature: Primary Keys, Foreign Keys, and Indexes Comparison

### Scenario: Represent Primary Key in TableSnapshot
Given a table definition
When a primary key is defined on one or more columns
Then `TableSnapshot` MUST store a `PrimaryKeySnapshot` with constraint name and ordered column tuple.

### Scenario: Represent Foreign Keys in TableSnapshot
Given relational table constraints
When foreign keys are defined referencing target tables
Then `TableSnapshot` MUST store a tuple of `ForeignKeySnapshot` containing column mappings and action rules (`ON DELETE`, `ON UPDATE`).

### Scenario: Represent Indexes in TableSnapshot
Given database indexes
When secondary or unique indexes exist on table columns
Then `TableSnapshot` MUST store a tuple of `IndexSnapshot` containing index name, column list, and uniqueness flag.

### Scenario: Detect Primary Key and Foreign Key Drift
Given multiple database profiles
When running N-way schema comparison
Then the engine MUST flag missing or mismatched primary keys, foreign keys, and indexes across target profiles.
