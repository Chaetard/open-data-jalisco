-- Idempotent bootstrap: enable pgvector. ORM creates tables on demand.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
