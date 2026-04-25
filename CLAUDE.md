# Event Game Framework

AI assistant instructions for the Event Game Framework project.

## Project

A self-hosted event management platform for escape rooms, CTF events, and team challenges.
Community-extensible via themes (CSS), language packs (JSON), and events (YAML).

## Tech Stack

- **Backend:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / PostgreSQL / pgvector / Redis
- **Frontend:** React 18 / TypeScript / Tailwind CSS / shadcn/ui
- **Auth:** JWT (HTTPOnly cookies, refresh rotation) + Azure OAuth — `backend/app/api/auth/`
- **AI:** Abstracted provider (Ollama / Claude / OpenAI) — `backend/app/services/providers/`
- **Realtime:** WebSockets + SSE — `backend/app/websocket/`, `backend/app/api/sse/`
- **Deploy:** Docker Swarm (prod) / Docker Compose (dev) — `deploy/`

## Five Rules — Active Always, No Exceptions

1. **300-line limit per file** — split into focused modules when approaching the limit
2. **Never log PII or credentials** — no passwords, tokens, emails, API keys in logs
3. **Pydantic for all API inputs** — no raw request body access anywhere in the backend
4. **Scope all non-admin DB queries** — every query filtered by `team_id` or `event_id`
5. **Tests against real PostgreSQL** — never SQLite; use the Docker Compose dev stack

## Repository Layout

```
backend/          FastAPI application
frontend/         React application
deploy/           Docker Compose + Swarm stack + Traefik config
docs/             Documentation (userguide, adminguide, developerguide, community, architecture)
scripts/          Community contribution validation scripts
.github/          CI/CD workflows and issue templates
themes/           Installed themes (gitignored)
langs/            Installed language packs (gitignored)
events/           Installed events (gitignored)
```

## AI Configuration

`.claude/` is gitignored — each developer maintains their own local AI setup.
Suggested structure: `rules/`, `agents/`, `commands/`, `design/`.

## V1 Reference

Working V1 implementation at `/home/daniel/event-game-framework/`.
Study before implementing: auth, AI providers, WebSocket patterns, seed data format.
Do not copy V1 code directly — V2 uses PostgreSQL (not SQLite) and Swarm (not Compose only).
