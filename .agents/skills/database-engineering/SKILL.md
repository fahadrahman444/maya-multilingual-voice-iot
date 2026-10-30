---
name: database-engineering
description: Best practices for database schema design, migrations, indexing, concurrency locking, and query performance across PostgreSQL, MySQL, and SQLite.
---

# Database Engineering & Migration Skill

Use this skill when designing schemas, writing migrations, indexing columns, or tuning database queries.

## 1. Migration Safety & Discipline
- **Reversible & Idempotent:** Write reversible migrations where possible. Use `IF EXISTS` / `IF NOT EXISTS`.
- **Zero-Downtime Safe DDL:**
  - In PostgreSQL, create indexes concurrently on active production tables: `CREATE INDEX CONCURRENTLY idx_name ON table (col);`.
  - Add nullable columns or columns with runtime defaults without table-locking rewrites.
- **Never Modify Schema In Place:** Never drop columns or rename tables without checking all application queries first.

## 2. Query Optimization & Indexing
- **Foreign Keys & Join Columns:** Always index foreign key columns to prevent full table scans during joins and deletes.
- **Composite Indexes:** Order composite index columns from highest selectivity to lowest selectivity.
- **Avoid N+1 Queries:** Use batch fetching, `JOIN` queries, or ORM preloading (`include`/`preload`).

## 3. Concurrency & Transactions
- **Atomic Transactions:** Wrap multi-table state mutations (e.g. creating an invoice and updating an account balance) in explicit database transactions (`BEGIN` ... `COMMIT`).
- **Partial Unique Indexes:** Use partial indexes to enforce business constraints across active states (e.g., `WHERE status IN ('PENDING', 'ACCEPTED')`).
