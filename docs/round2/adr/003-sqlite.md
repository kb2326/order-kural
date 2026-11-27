# ADR-003: SQLite in a Docker volume

- **Date:** 2026-11-27 · **Status:** Accepted
- **Context:** we store orders, lines, khata entries, the price list and traces for one shop. The app must start with
  no external services or keys.
- **Options:** (1) SQLite file; (2) Postgres container; (3) a cloud database (Firestore).
- **Decision:** SQLite, created and seeded on first start, kept in a named Docker volume.
- **Consequences:** zero setup for the judges. On Cloud Run the file is not durable between restarts, which is fine
  for a demo (the seed data comes back). A real multi-shop product would move to Postgres.
