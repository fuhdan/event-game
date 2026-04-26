# Developer Guide

Documentation for contributors to the Event Game Framework core.

## Setup

See [CONTRIBUTING.md](../CONTRIBUTING.md) and the `.claude/` directory for all development rules.

## Architecture

The framework consists of:
- **Backend:** FastAPI application with PostgreSQL + Redis
- **Frontend:** React 19 with Tailwind CSS and shadcn/ui
- **AI layer:** Pluggable AI provider (Ollama / Claude / OpenAI)
- **Deployment:** Docker Swarm with Traefik reverse proxy
