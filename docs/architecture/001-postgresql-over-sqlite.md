# ADR-001: PostgreSQL as Primary Database

**Status:** Accepted  
**Date:** 2026-04-25  
**Deciders:** Daniel Fuhrer

## Context

V1 used SQLite for simplicity. V2 needs to support multi-user concurrent access, full-text search,
vector similarity search (AI features), and production-grade reliability under Docker Swarm.

## Decision

Use PostgreSQL 16 with pgvector extension as the sole database. SQLite is not used at any layer.

## Consequences

- Tests must run against a real PostgreSQL instance (Docker service in CI, local Compose in dev)
- Migrations use Alembic targeting PostgreSQL-specific features freely
- pgvector enables embedding storage for AI hint retrieval without a separate vector DB
- Local dev requires Docker to be running (no zero-dependency dev mode)

## Alternatives Considered

- **SQLite:** Zero-setup dev, but no pgvector, no row-level locking, no concurrent writes — rejected
- **MySQL:** Widely supported, but no pgvector extension — rejected
- **Separate vector DB (Qdrant/Weaviate):** More powerful, but adds operational complexity for a feature that pgvector handles adequately — rejected
