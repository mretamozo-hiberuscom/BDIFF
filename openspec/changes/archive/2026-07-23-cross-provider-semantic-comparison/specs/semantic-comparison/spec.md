# Specification: Cross-Provider Semantic Comparison

## Feature: Heterogeneous Database Schema Comparison

### Scenario: Native strict comparison mode (Default)
Given schema snapshots from different database engines
When comparing with `mode=ComparisonMode.NATIVE_STRICT`
Then native type string mismatches (e.g. `VARCHAR` vs `VARCHAR2`) MUST be reported as column mismatches.

### Scenario: Semantic equivalent comparison mode
Given schema snapshots from different database engines (e.g. PostgreSQL vs Oracle)
When comparing with `mode=ComparisonMode.SEMANTIC_EQUIVALENT`
Then semantically equivalent native types (e.g. `INT` vs `NUMBER(10, 0)`, `VARCHAR` vs `VARCHAR2`, `BOOLEAN` vs `TINYINT(1)`) MUST NOT be reported as errors.

### Scenario: Semantic type equivalence lookup
Given two type strings from different database providers
When evaluating semantic equivalence via `are_types_semantically_equivalent(type1, type2)`
Then equivalent types across SQL Server, PostgreSQL, SQLite, MySQL, and Oracle MUST evaluate to True.
